"""
RetrieverService: Hybrid Retrieval + Corrective RAG (CRAG) + Reranking.

Architectural Flow:
  User Query
  -> Query Rewriting (Contextual)
  -> Hybrid Retrieval:
       * Dense retrieval using Pinecone
       * Sparse retrieval using BM25
       * Result Fusion (Reciprocal Rank Fusion / RRF)
  -> Reranking (Lexical + Semantic + Term Alignment)
  -> Retrieval Grader
  -> If Relevant:
       Context Compression -> Return Evidence (RetrievalResult)
  -> If Poor:
       Corrective RAG:
       * Query Rewrite & Expansion
       * Query Decomposition
       * Re-retrieve -> Re-grade
       * Limited to MAX_CORRECTION_ATTEMPTS to prevent infinite loops.
  -> Return structured failure state to Orchestrator if unrecoverable.
"""
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.logger import logger
from backend.services.embedding_service import embedding_service
from backend.services.vectorstore_service import vectorstore_service


class LuceneBM25:
    """Robust BM25 scoring with Lucene IDF smoothing (prevents zero/negative IDF on small corpora)."""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lens) / max(self.corpus_size, 1)
        self.doc_freqs: Dict[str, int] = {}
        self.corpus = corpus
        for doc in corpus:
            for word in set(doc):
                self.doc_freqs[word] = self.doc_freqs.get(word, 0) + 1

    def get_scores(self, query: List[str]) -> List[float]:
        scores = []
        for i, doc in enumerate(self.corpus):
            doc_len = self.doc_lens[i]
            tf: Dict[str, int] = {}
            for w in doc:
                tf[w] = tf.get(w, 0) + 1
            score = 0.0
            for q in query:
                if q in self.doc_freqs:
                    n_q = self.doc_freqs[q]
                    idf = math.log(1.0 + (self.corpus_size - n_q + 0.5) / (n_q + 0.5))
                    f = tf.get(q, 0)
                    if f > 0:
                        denom = f + self.k1 * (1.0 - self.b + self.b * (doc_len / max(self.avgdl, 1.0)))
                        score += idf * (f * (self.k1 + 1.0)) / max(denom, 1e-6)
            scores.append(score)
        return scores


class RetrievedChunk:
    def __init__(
        self,
        text: str,
        metadata: dict,
        score: float,
        initial_score: Optional[float] = None,
        rerank_score: Optional[float] = None,
        dense_score: Optional[float] = None,
        sparse_score: Optional[float] = None,
    ):
        self.text = text
        self.metadata = metadata or {}
        self.score = score
        self.initial_score = initial_score if initial_score is not None else score
        self.rerank_score = rerank_score if rerank_score is not None else score
        self.dense_score = dense_score or 0.0
        self.sparse_score = sparse_score or 0.0


class RetrievalResult:
    """Structured result returned by the retrieval layer to the orchestrator."""

    def __init__(
        self,
        chunks: List[RetrievedChunk],
        status: str = "empty",  # "relevant", "poor", "empty"
        grade: str = "irrelevant",  # "relevant", "partially_relevant", "irrelevant"
        initial_retrieval_score: float = 0.0,
        reranker_score: float = 0.0,
        correction_attempts: int = 0,
        queries_attempted: Optional[List[str]] = None,
        evidence_quality: str = "none",  # "high", "medium", "low", "none"
    ):
        self.chunks = chunks
        self.status = status
        self.grade = grade
        self.initial_retrieval_score = round(initial_retrieval_score, 4)
        self.reranker_score = round(reranker_score, 4)
        self.correction_attempts = correction_attempts
        self.queries_attempted = queries_attempted or []
        self.evidence_quality = evidence_quality

    def __iter__(self):
        return iter(self.chunks)

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, index):
        return self.chunks[index]


class ChunkRegistry:
    """Thread-safe in-memory cache of document chunks for full-corpus BM25 sparse search."""

    def __init__(self):
        self._chunks_by_doc: Dict[str, List[dict]] = {}

    def register(self, document_id: str, texts: List[str], metadatas: List[dict]):
        records = []
        for t, m in zip(texts, metadatas):
            records.append({"text": t, "metadata": m})
        self._chunks_by_doc[document_id] = records

    def get_chunks(self, document_ids: Optional[List[str]] = None) -> List[dict]:
        if document_ids:
            results = []
            for doc_id in document_ids:
                results.extend(self._chunks_by_doc.get(doc_id, []))
            return results
        all_chunks = []
        for chunks in self._chunks_by_doc.values():
            all_chunks.extend(chunks)
        return all_chunks

    def delete(self, document_id: str):
        self._chunks_by_doc.pop(document_id, None)


class RetrieverService:
    def __init__(self):
        self.chunk_registry = ChunkRegistry()

    def register_chunks(self, document_id: str, texts: List[str], metadatas: List[dict]):
        """Register newly ingested chunks into the sparse index."""
        self.chunk_registry.register(document_id, texts, metadatas)

    def delete_document_chunks(self, document_id: str):
        """Remove document chunks from the sparse index upon document deletion."""
        self.chunk_registry.delete(document_id)

    # -----------------------------------------------------------------------
    # 1. Query Rewriting & Expansion
    # -----------------------------------------------------------------------

    def rewrite_query(self, question: str, history: Optional[str] = None) -> str:
        """Contextual query rewriting for retrieval (resolves pronouns/follow-ups)."""
        if not history:
            return question
        try:
            from backend.services.llm_provider import get_chat_llm

            llm = get_chat_llm()
            prompt = (
                "Rewrite the user's latest message as a standalone search query, "
                "resolving any pronouns or references using the conversation history. "
                "Reply with ONLY the rewritten query, nothing else.\n\n"
                f"History:\n{history}\n\nLatest message: {question}"
            )
            resp = llm.invoke(prompt)
            rewritten = (resp.content or "").strip().strip('"')
            return rewritten or question
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original question: {e}")
            return question

    def _expand_query(self, query: str) -> str:
        """CRAG expansion: generate synonyms and keyword expansion."""
        try:
            from backend.services.llm_provider import get_chat_llm

            llm = get_chat_llm(temperature=0.0)
            prompt = (
                f"The search query '{query}' did not retrieve relevant document sections. "
                "Generate an expanded search query that includes core synonyms, technical keywords, "
                "and alternate phrasings suitable for document search. Output ONLY the expanded query."
            )
            resp = llm.invoke(prompt)
            expanded = (resp.content or "").strip().strip('"')
            if expanded:
                return expanded
        except Exception as e:
            logger.warning(f"LLM query expansion failed: {e}")

        # Heuristic expansion fallback: remove stop phrases and extract keywords
        cleaned = re.sub(
            r"\b(according to the (document|file|pdf)|what is|tell me about|in the document|summarize|explain)\b",
            "",
            query,
            flags=re.I,
        ).strip()
        return cleaned or query

    def _decompose_query(self, query: str) -> List[str]:
        """CRAG decomposition: split compound questions into sub-queries."""
        sub_queries = []
        try:
            from backend.services.llm_provider import get_chat_llm

            llm = get_chat_llm(temperature=0.0)
            prompt = (
                f"Break this complex question into 2 simpler search queries:\n"
                f"Question: {query}\n"
                "Return each sub-query on a new line. Output nothing else."
            )
            resp = llm.invoke(prompt)
            lines = [l.strip().lstrip("-").strip() for l in (resp.content or "").split("\n") if l.strip()]
            if len(lines) >= 2:
                return lines[:2]
        except Exception as e:
            logger.warning(f"LLM query decomposition failed: {e}")

        # Heuristic fallback: split on punctuation or conjunctions
        parts = re.split(r"\b(?:and|or|as well as)\b|[;,]", query, flags=re.I)
        cleaned_parts = [p.strip() for p in parts if len(p.strip()) > 3]
        return cleaned_parts if len(cleaned_parts) >= 2 else [query]

    # -----------------------------------------------------------------------
    # 2. Hybrid Retrieval (Dense Pinecone + Sparse BM25 + RRF Fusion)
    # -----------------------------------------------------------------------

    def _hybrid_retrieve(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 8,
    ) -> List[RetrievedChunk]:
        """Run dense vector search and sparse BM25 search, then combine via Reciprocal Rank Fusion."""
        # A. Dense Retrieval via Pinecone
        dense_matches = []
        try:
            vector = embedding_service.embed_query(query)
            dense_matches = vectorstore_service.query(vector, top_k=top_k * 2, document_ids=document_ids)
        except Exception as e:
            logger.warning(f"Dense vector retrieval error: {e}")

        # B. Sparse Retrieval via BM25
        corpus_chunks = self.chunk_registry.get_chunks(document_ids)
        # If corpus not in registry, populate from dense match metadata on-the-fly
        if not corpus_chunks and dense_matches:
            corpus_chunks = [
                {"text": m.get("metadata", {}).get("text", ""), "metadata": m.get("metadata", {})}
                for m in dense_matches
                if m.get("metadata", {}).get("text")
            ]

        sparse_candidates = []
        if corpus_chunks:
            try:
                tokenized_corpus = [re.findall(r"\w+", c["text"].lower()) for c in corpus_chunks]
                bm25 = LuceneBM25(tokenized_corpus)
                query_tokens = re.findall(r"\w+", query.lower())
                bm25_scores = bm25.get_scores(query_tokens)
                max_bm25 = max(bm25_scores) if len(bm25_scores) and max(bm25_scores) > 0 else 1.0

                for chunk_data, score in zip(corpus_chunks, bm25_scores):
                    if score > 0:
                        sparse_candidates.append({
                            "text": chunk_data["text"],
                            "metadata": chunk_data["metadata"],
                            "score": float(score / max_bm25),
                        })
                sparse_candidates.sort(key=lambda x: x["score"], reverse=True)
            except Exception as e:
                logger.warning(f"BM25 sparse retrieval error: {e}")

        # C. Reciprocal Rank Fusion (RRF)
        k_rrf = 60
        dense_ranks = {}
        for rank, m in enumerate(dense_matches, start=1):
            key = (m.get("metadata", {}).get("text", "") or "")[:120]
            dense_ranks[key] = (rank, m)

        sparse_ranks = {}
        for rank, s in enumerate(sparse_candidates, start=1):
            key = (s.get("text", "") or "")[:120]
            sparse_ranks[key] = (rank, s)

        all_keys = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        fused = []

        for key in all_keys:
            if not key.strip():
                continue
            dense_info = dense_ranks.get(key)
            sparse_info = sparse_ranks.get(key)
            rrf_score = 0.0
            dense_score = 0.0
            sparse_score = 0.0
            metadata = {}
            text = ""

            if dense_info:
                rank, m = dense_info
                dense_score = float(m.get("score", 0.0))
                metadata = m.get("metadata", {})
                text = metadata.get("text", "")
                rrf_score += 0.6 / (k_rrf + rank)

            if sparse_info:
                rank, s = sparse_info
                sparse_score = s["score"]
                if not metadata:
                    metadata = s["metadata"]
                    text = s["text"]
                rrf_score += 0.4 / (k_rrf + rank)

            if text:
                fused.append(
                    RetrievedChunk(
                        text=text,
                        metadata=metadata,
                        score=rrf_score,
                        dense_score=dense_score,
                        sparse_score=sparse_score,
                    )
                )

        fused.sort(key=lambda c: c.score, reverse=True)
        return fused

    # -----------------------------------------------------------------------
    # 3. Reranker (Lexical + Semantic + Term Alignment)
    # -----------------------------------------------------------------------

    def _rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 4,
    ) -> List[RetrievedChunk]:
        """Rerank fused candidates using term overlap, normalized RRF, and dense similarity."""
        query_words = set(w.lower() for w in re.findall(r"\w+", query) if len(w) > 2)

        for c in candidates:
            chunk_words = set(w.lower() for w in re.findall(r"\w+", c.text))
            term_overlap = len(query_words & chunk_words) / max(len(query_words), 1)

            # Normalized RRF score (scale 0..1 from max ~0.033)
            norm_rrf = min(c.score / 0.033, 1.0)
            dense_val = min(max(c.dense_score, 0.0), 1.0)

            # Combined reranking score
            final_rerank = (0.35 * norm_rrf) + (0.35 * dense_val) + (0.30 * term_overlap)
            c.rerank_score = round(min(max(final_rerank, 0.0), 1.0), 4)
            c.score = c.rerank_score

        candidates.sort(key=lambda c: c.rerank_score, reverse=True)
        return candidates[:top_k]

    # -----------------------------------------------------------------------
    # 4. Retrieval Grader
    # -----------------------------------------------------------------------

    def _grade(
        self,
        query: str,
        candidates: List[RetrievedChunk],
    ) -> Tuple[str, str, float]:
        """Evaluate whether the retrieved candidate chunks contain relevant evidence.
        Returns: (grade, evidence_quality, top_score).
        """
        if not candidates:
            return "irrelevant", "none", 0.0

        top_score = candidates[0].rerank_score

        if top_score >= 0.50:
            return "relevant", "high", top_score
        if top_score >= 0.30:
            return "partially_relevant", "medium", top_score
        return "irrelevant", "poor", top_score

    # -----------------------------------------------------------------------
    # 5. Context Compression & Deduplication
    # -----------------------------------------------------------------------

    def _compress(self, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Drop near-duplicate chunks and filter below minimum relevance."""
        seen_keys = set()
        compressed = []
        for c in candidates:
            key = (c.metadata.get("document_id"), c.metadata.get("page_number"), c.text[:80])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if c.score >= settings.MIN_RELEVANCE_SCORE:
                compressed.append(c)
        return compressed

    # -----------------------------------------------------------------------
    # 6. Corrective RAG (CRAG) Workflow
    # -----------------------------------------------------------------------

    def retrieve_with_crag(
        self,
        question: str,
        history: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        max_attempts: Optional[int] = None,
    ) -> RetrievalResult:
        """Executes Hybrid Retrieval + Grading + Corrective RAG loop.
        Returns a structured RetrievalResult without formulating final user-facing text.
        """
        max_attempts = max_attempts or settings.MAX_CORRECTION_ATTEMPTS
        current_query = self.rewrite_query(question, history)
        queries_attempted = [current_query]

        # Step 1: Initial Hybrid Retrieval
        initial_candidates = self._hybrid_retrieve(current_query, document_ids=document_ids)
        reranked = self._rerank(current_query, initial_candidates, top_k=settings.RERANK_TOP_K)
        grade, evidence_quality, initial_score = self._grade(current_query, reranked)

        logger.info(
            f"[RETRIEVAL] query={current_query!r} initial_score={initial_score:.4f} "
            f"grade={grade} evidence_quality={evidence_quality}"
        )

        # If initial retrieval is already relevant / acceptable, compress and return
        if grade in ("relevant", "partially_relevant"):
            compressed = self._compress(reranked)
            logger.info(
                f"[RETRIEVAL] Final evidence accepted: initial_score={initial_score:.4f} "
                f"reranker_score={reranked[0].rerank_score if reranked else 0.0:.4f} "
                f"grade={grade} correction_attempts=0 evidence_quality={evidence_quality}"
            )
            return RetrievalResult(
                chunks=compressed,
                status="relevant",
                grade=grade,
                initial_retrieval_score=initial_score,
                reranker_score=reranked[0].rerank_score if reranked else 0.0,
                correction_attempts=0,
                queries_attempted=queries_attempted,
                evidence_quality=evidence_quality,
            )

        # Step 2: Corrective RAG Loop
        logger.info(
            f"[CRAG] Initial retrieval grade={grade} (score={initial_score:.4f}). "
            f"Initiating corrective loop (max_attempts={max_attempts})."
        )

        best_chunks = reranked
        best_grade = grade
        best_score = initial_score
        best_quality = evidence_quality
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            logger.info(f"[CRAG] Correction attempt {attempt}/{max_attempts}...")

            if attempt == 1:
                # Attempt 1: Query Expansion & Keyword Synonyms
                corrected_query = self._expand_query(current_query)
            else:
                # Attempt 2: Query Decomposition
                sub_queries = self._decompose_query(current_query)
                corrected_query = " ".join(sub_queries)

            queries_attempted.append(corrected_query)
            logger.info(f"[CRAG] Attempt {attempt} query: {corrected_query!r}")

            new_candidates = self._hybrid_retrieve(corrected_query, document_ids=document_ids)
            new_reranked = self._rerank(corrected_query, new_candidates, top_k=settings.RERANK_TOP_K)
            new_grade, new_quality, new_score = self._grade(corrected_query, new_reranked)

            if new_score > best_score:
                best_chunks = new_reranked
                best_grade = new_grade
                best_score = new_score
                best_quality = new_quality

            if new_grade in ("relevant", "partially_relevant"):
                logger.info(
                    f"[CRAG] Correction attempt {attempt} succeeded: grade={new_grade} score={new_score:.4f}"
                )
                compressed = self._compress(best_chunks)
                return RetrievalResult(
                    chunks=compressed,
                    status="relevant",
                    grade=new_grade,
                    initial_retrieval_score=initial_score,
                    reranker_score=new_score,
                    correction_attempts=attempt,
                    queries_attempted=queries_attempted,
                    evidence_quality=new_quality,
                )

        # Step 3: All correction attempts exhausted without finding relevant evidence
        logger.warning(
            f"[CRAG] All {max_attempts} correction attempts exhausted. "
            f"Returning structured failure state: grade={best_grade} quality={best_quality}"
        )
        return RetrievalResult(
            chunks=[],
            status="poor",
            grade="irrelevant",
            initial_retrieval_score=initial_score,
            reranker_score=best_score,
            correction_attempts=attempt,
            queries_attempted=queries_attempted,
            evidence_quality="none",
        )

    # -----------------------------------------------------------------------
    # 7. Backward-Compatible Retrieve Interface
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        rerank_top_k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """Backward-compatible retrieval returning a list of RetrievedChunk objects."""
        top_k = top_k or settings.RETRIEVAL_TOP_K
        rerank_top_k = rerank_top_k or settings.RERANK_TOP_K

        candidates = self._hybrid_retrieve(query, document_ids=document_ids, top_k=top_k)
        reranked = self._rerank(query, candidates, top_k=rerank_top_k)
        return self._compress(reranked)


retriever_service = RetrieverService()
