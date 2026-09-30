"""
Unit tests for Phase 3: Hybrid Retrieval + Corrective RAG (CRAG) + Reranking.

Validates:
1. Good retrieval (high score, relevant grade, 0 correction attempts)
2. Poor retrieval requiring query rewrite (CRAG loop activates, expands query, succeeds)
3. Query with exact keywords (BM25 sparse boost)
4. Semantic query (Dense retrieval match)
5. No relevant document (CRAG reaches MAX_CORRECTION_ATTEMPTS, prevents infinite loop, returns structured poor state)
6. Multiple relevant chunks (RRF fusion and compression preserve multiple distinct chunks)
"""
import pytest
from backend.services.retriever_service import retriever_service, RetrievedChunk, RetrievalResult


@pytest.fixture(autouse=True)
def setup_chunk_registry():
    """Ensure chunk registry is clean before each test."""
    retriever_service.chunk_registry._chunks_by_doc.clear()
    yield
    retriever_service.chunk_registry._chunks_by_doc.clear()


# ---------------------------------------------------------------------------
# 1. Good Retrieval
# ---------------------------------------------------------------------------

def test_good_retrieval(monkeypatch):
    """Direct relevant query matches document immediately with 0 correction attempts."""
    doc_id = "doc_good_1"
    text = "Nexora AI provides multimodal medical query assistance with cited sources."
    metadata = {"document_id": doc_id, "filename": "nexora_overview.pdf", "page_number": 1, "text": text}

    retriever_service.register_chunks(doc_id, [text], [metadata])

    # Mock vectorstore dense search to return this chunk
    monkeypatch.setattr(
        "backend.services.vectorstore_service.vectorstore_service.query",
        lambda vec, top_k=8, document_ids=None: [{"metadata": metadata, "score": 0.92}],
    )

    result: RetrievalResult = retriever_service.retrieve_with_crag(
        question="What does Nexora AI provide for medical queries?",
        document_ids=[doc_id],
    )

    assert result.status == "relevant"
    assert result.grade == "relevant"
    assert result.correction_attempts == 0
    assert result.initial_retrieval_score >= 0.50
    assert result.evidence_quality == "high"
    assert len(result.chunks) >= 1
    assert "multimodal medical query assistance" in result.chunks[0].text


# ---------------------------------------------------------------------------
# 2. Poor Retrieval Requiring Query Rewrite (CRAG Loop)
# ---------------------------------------------------------------------------

def test_poor_retrieval_requiring_query_rewrite(monkeypatch):
    """Vague initial query fails initial retrieval, triggers CRAG rewrite, and succeeds."""
    doc_id = "doc_crag_2"
    text = "Amoxicillin dosage guideline for adult bacterial infections is 500mg every 8 hours."
    metadata = {"document_id": doc_id, "filename": "antibiotics.pdf", "page_number": 3, "text": text}

    retriever_service.register_chunks(doc_id, [text], [metadata])

    # Initial query yields 0 dense matches, but rewritten query yields the match
    def mock_query(vector, top_k=8, document_ids=None):
        return [{"metadata": metadata, "score": 0.88}]

    # Force initial query to have poor keyword overlap and poor dense score,
    # but expansion succeeds
    call_count = {"count": 0}

    def mock_hybrid(query, document_ids=None, top_k=8):
        call_count["count"] += 1
        if call_count["count"] == 1:
            # Poor initial candidate with low score
            return [RetrievedChunk(text="General administrative records.", metadata={"document_id": "other"}, score=0.002, dense_score=0.1)]
        # Corrected / expanded query succeeds
        return [RetrievedChunk(text=text, metadata=metadata, score=0.03, dense_score=0.9)]

    monkeypatch.setattr(retriever_service, "_hybrid_retrieve", mock_hybrid)
    monkeypatch.setattr(retriever_service, "_expand_query", lambda q: "Amoxicillin adult dosage guidelines")

    result: RetrievalResult = retriever_service.retrieve_with_crag(
        question="how much of that pill should adults take",
        document_ids=[doc_id],
    )

    assert result.status == "relevant"
    assert result.correction_attempts >= 1
    assert "Amoxicillin adult dosage guidelines" in result.queries_attempted
    assert len(result.chunks) >= 1
    assert "Amoxicillin dosage guideline" in result.chunks[0].text


# ---------------------------------------------------------------------------
# 3. Query with Exact Keywords (Sparse BM25 Boost)
# ---------------------------------------------------------------------------

def test_query_with_exact_keywords(monkeypatch):
    """BM25 sparse retrieval boosts exact keyword matches via RRF fusion."""
    doc_id = "doc_cardiac"
    chunk1_text = "Ventricular fibrillation is a life-threatening cardiac arrhythmia requiring defibrillation."
    chunk2_text = "Common cardiovascular conditions include hypertension and coronary artery disease."

    meta1 = {"document_id": doc_id, "filename": "cardiac.pdf", "page_number": 1, "text": chunk1_text}
    meta2 = {"document_id": doc_id, "filename": "cardiac.pdf", "page_number": 2, "text": chunk2_text}

    retriever_service.register_chunks(doc_id, [chunk1_text, chunk2_text], [meta1, meta2])

    # Dense retrieval returns both chunks with similar dense scores
    monkeypatch.setattr(
        "backend.services.vectorstore_service.vectorstore_service.query",
        lambda vec, top_k=8, document_ids=None: [
            {"metadata": meta2, "score": 0.75},  # dense put chunk 2 first
            {"metadata": meta1, "score": 0.70},
        ],
    )

    # User queries with exact term "ventricular fibrillation"
    candidates = retriever_service._hybrid_retrieve("ventricular fibrillation", document_ids=[doc_id])
    reranked = retriever_service._rerank("ventricular fibrillation", candidates, top_k=2)

    # BM25 lexical match should boost chunk1 to the top
    assert len(reranked) >= 1
    assert "Ventricular fibrillation" in reranked[0].text
    assert reranked[0].sparse_score > 0.5


# ---------------------------------------------------------------------------
# 4. Semantic Query (Dense Retrieval Match)
# ---------------------------------------------------------------------------

def test_semantic_query(monkeypatch):
    """Dense vector retrieval captures semantic intent even with zero keyword overlap."""
    doc_id = "doc_semantic"
    text = "Elevated arterial blood pressure increases long-term stroke and myocardial infarction risk."
    metadata = {"document_id": doc_id, "filename": "hypertension.pdf", "page_number": 5, "text": text}

    retriever_service.register_chunks(doc_id, [text], [metadata])

    # Query uses different vocabulary: "high BP lead to heart attacks"
    monkeypatch.setattr(
        "backend.services.vectorstore_service.vectorstore_service.query",
        lambda vec, top_k=8, document_ids=None: [{"metadata": metadata, "score": 0.89}],
    )

    candidates = retriever_service._hybrid_retrieve("Can high BP lead to heart attacks?", document_ids=[doc_id])
    reranked = retriever_service._rerank("Can high BP lead to heart attacks?", candidates, top_k=2)

    assert len(reranked) >= 1
    assert "Elevated arterial blood pressure" in reranked[0].text
    assert reranked[0].dense_score >= 0.80


# ---------------------------------------------------------------------------
# 5. No Relevant Document (Prevent Infinite Loop & Return Structured Poor)
# ---------------------------------------------------------------------------

def test_no_relevant_document_prevents_infinite_loop(monkeypatch):
    """Irrelevant documents trigger CRAG retries up to MAX_CORRECTION_ATTEMPTS, then return structured failure."""
    doc_id = "doc_tax"
    text = "Corporate balance sheet depreciation methods under GAAP."
    metadata = {"document_id": doc_id, "filename": "accounting.pdf", "page_number": 1, "text": text}

    retriever_service.register_chunks(doc_id, [text], [metadata])

    # Vector store returns poor/irrelevant candidate
    monkeypatch.setattr(
        "backend.services.vectorstore_service.vectorstore_service.query",
        lambda vec, top_k=8, document_ids=None: [{"metadata": metadata, "score": 0.05}],
    )

    # Medical question completely unrelated to corporate accounting
    result: RetrievalResult = retriever_service.retrieve_with_crag(
        question="What is the emergency protocol for acute pediatric asthma?",
        document_ids=[doc_id],
        max_attempts=2,
    )

    # Must NOT loop infinitely; must stop at max_attempts (2)
    assert result.status == "poor"
    assert result.grade == "irrelevant"
    assert result.evidence_quality == "none"
    assert result.correction_attempts == 2
    assert result.chunks == []  # Structured empty failure state


# ---------------------------------------------------------------------------
# 6. Multiple Relevant Chunks
# ---------------------------------------------------------------------------

def test_multiple_relevant_chunks(monkeypatch):
    """Multiple relevant chunks from different sections are preserved and fused."""
    doc_id = "doc_multi"
    chunk1 = "Chemotherapy Protocol Alpha: Administer paclitaxel 175 mg/m2 over 3 hours on Day 1."
    chunk2 = "Chemotherapy Protocol Alpha: Follow with carboplatin AUC 6 over 60 minutes on Day 1."

    meta1 = {"document_id": doc_id, "filename": "chemo.pdf", "page_number": 10, "text": chunk1}
    meta2 = {"document_id": doc_id, "filename": "chemo.pdf", "page_number": 11, "text": chunk2}

    retriever_service.register_chunks(doc_id, [chunk1, chunk2], [meta1, meta2])

    monkeypatch.setattr(
        "backend.services.vectorstore_service.vectorstore_service.query",
        lambda vec, top_k=8, document_ids=None: [
            {"metadata": meta1, "score": 0.85},
            {"metadata": meta2, "score": 0.82},
        ],
    )

    result: RetrievalResult = retriever_service.retrieve_with_crag(
        question="What are the complete infusion steps for Chemotherapy Protocol Alpha?",
        document_ids=[doc_id],
    )

    assert result.status == "relevant"
    assert len(result.chunks) == 2
    assert any("paclitaxel" in c.text for c in result.chunks)
    assert any("carboplatin" in c.text for c in result.chunks)
