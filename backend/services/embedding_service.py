"""
EmbeddingService: thin, cache-aware wrapper around the embedding provider.

Kept separate from vectorstore_service so the embedding backend can be
swapped (e.g. OpenAI, Cohere) without touching Pinecone logic.
"""
import re
import time
from typing import List

from backend.config import settings
from backend.logger import logger
from backend.utils.hashing import hash_text
from backend.utils.cache import embedding_cache

_embed_model = None


def _get_model():
    global _embed_model
    if _embed_model is None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not settings.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set; cannot create embeddings."
            )
        _embed_model = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            output_dimensionality=settings.EMBEDDING_DIM,
        )
    return _embed_model


class EmbeddingService:
    def embed_documents(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Embed documents in batches with automatic retry & rate-limit handling.
        Google Free Tier limits embedding tokens to 30,000/minute.
        Batching into smaller chunks and honoring server retry delays prevents 429 failures.
        """
        if not texts:
            return []
        model = _get_model()
        results: List[List[float]] = [None] * len(texts)
        to_embed_idx = []
        to_embed_text = []

        for i, t in enumerate(texts):
            cached = embedding_cache.get(hash_text(t))
            if cached is not None:
                results[i] = cached
            else:
                to_embed_idx.append(i)
                to_embed_text.append(t)

        if to_embed_text:
            logger.info(f"[EMBEDDING] Embedding {len(to_embed_text)} new chunks in batches of {batch_size}")

            for b_start in range(0, len(to_embed_text), batch_size):
                b_end = min(b_start + batch_size, len(to_embed_text))
                batch = to_embed_text[b_start:b_end]
                batch_indices = to_embed_idx[b_start:b_end]

                # Retry loop honoring API retryDelay for 429 rate limits
                max_retries = 8
                backoff = 10.0
                for attempt in range(max_retries):
                    try:
                        batch_vectors = model.embed_documents(batch)
                        for orig_idx, text, vec in zip(batch_indices, batch, batch_vectors):
                            results[orig_idx] = vec
                            embedding_cache.set(hash_text(text), vec)
                        break
                    except Exception as exc:
                        err_str = str(exc).lower()
                        if ("429" in err_str or "resource_exhausted" in err_str or "quota" in err_str) and attempt < max_retries - 1:
                            # Attempt to parse requested retry delay from Google API error payload
                            delay = backoff
                            m = re.search(r"retry\s+in\s+([\d\.]+)\s*s", err_str) or re.search(r"retrydelay['\":\s]+(\d+)", err_str)
                            if m:
                                try:
                                    delay = float(m.group(1)) + 2.5
                                except Exception:
                                    delay = 40.0
                            else:
                                delay = max(backoff, 40.0)

                            logger.warning(
                                f"[EMBEDDING] Rate limit encountered on batch {b_start}-{b_end}. "
                                f"Waiting {delay:.1f}s for quota window to reset (attempt {attempt + 1}/{max_retries})..."
                            )
                            time.sleep(delay)
                            backoff = min(backoff * 1.5, 60.0)
                        else:
                            logger.error(f"[EMBEDDING] Batch {b_start}-{b_end} failed permanently: {exc}")
                            raise exc

                # Brief polite pause between batches to conserve quota
                if b_end < len(to_embed_text):
                    time.sleep(1.5)

        return results

    def embed_query(self, text: str) -> List[float]:
        cached = embedding_cache.get(hash_text("q::" + text))
        if cached is not None:
            return cached
        model = _get_model()
        vec = model.embed_query(text)
        embedding_cache.set(hash_text("q::" + text), vec)
        return vec


embedding_service = EmbeddingService()
