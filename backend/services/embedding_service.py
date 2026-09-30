"""
EmbeddingService: thin, cache-aware wrapper around the embedding provider.

Kept separate from vectorstore_service so the embedding backend can be
swapped (e.g. OpenAI, Cohere) without touching Pinecone logic.
"""
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
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
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
            logger.debug(f"Embedding {len(to_embed_text)} new chunks (of {len(texts)} total)")
            new_vectors = model.embed_documents(to_embed_text)
            for idx, text, vec in zip(to_embed_idx, to_embed_text, new_vectors):
                results[idx] = vec
                embedding_cache.set(hash_text(text), vec)

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
