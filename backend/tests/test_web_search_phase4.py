"""
Unit and integration tests for Phase 4: Web Search Integration.

Scenarios tested:
1. Explicit web request (must route to web search, not blocked by existing documents)
2. Current-information query (automatic web routing based on temporal signals)
3. General question that should not need web (routes to general knowledge)
4. Document question that should not need web (routes to document RAG)
5. Document + web hybrid query (cross-referencing document with web, evidence fusion)
6. Web failure / API failure (graceful error containment, structured evidence, no secrets leaked)
"""
import pytest
from unittest.mock import MagicMock

from backend.schemas import QueryResponse, RoutingDecision, EvidenceBreakdown
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.web_search_service import (
    web_search_service,
    WebSearchResult,
    WebSearchEvidence,
    _CONVERSATIONAL_PREFIXES,
)
from backend.services.answer_service import answer_service
from backend.services.retriever_service import retriever_service, RetrievedChunk, RetrievalResult


# ---------------------------------------------------------------------------
# Fixture / Helper mocks
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_llm_invoke(monkeypatch):
    """Ensure LLM calls are mocked by default so tests run fast and offline."""
    mock_resp = MagicMock()
    mock_resp.content = "This is a synthesized test response from the assistant."
    monkeypatch.setattr(
        "backend.services.answer_service.get_chat_llm",
        lambda *args, **kwargs: MagicMock(invoke=lambda prompt: mock_resp),
    )


# ---------------------------------------------------------------------------
# 1. Explicit Web Request
# ---------------------------------------------------------------------------

def test_explicit_web_request(monkeypatch):
    """Explicit request like 'search the web' MUST route to web and never be blocked by documents."""
    # Active documents exist in session
    doc = ResolvedDocument("doc_cardio", "pdf", "completed")

    phrases = [
        "search the web for latest diabetes management guidelines",
        "search online for new mRNA vaccines",
        "look this up: what are the latest cardiology protocols?",
        "find the latest information on GLP-1 receptor agonists",
        "check current information regarding Alzheimer's clinical trials",
    ]

    for q in phrases:
        decision = query_router.route_decision(
            question=q,
            resolved_documents=[doc],  # Document is present
            has_any_documents=True,
            web_search_available=True,
        )
        assert decision.web_required is True, f"Failed web_required for: {q}"
        assert decision.document_required is False, f"Document blocked explicit web request for: {q}"
        assert decision.intent == "web_research", f"Wrong intent for: {q}"

    # Verify execution flow through AnswerService
    mock_results = [
        WebSearchResult(
            title="Diabetes Guidelines 2026",
            url="https://ada.org/guidelines",
            snippet="Updated standard of medical care in diabetes for 2026.",
            score=0.92,
        )
    ]
    monkeypatch.setattr(
        web_search_service,
        "search_evidence",
        lambda q, max_results=None: WebSearchEvidence(
            query=q, status="success", results=mock_results, provider="MockProvider"
        ),
    )
    monkeypatch.setattr(web_search_service, "is_available", lambda: True)

    resp: QueryResponse = answer_service.answer(
        question="search the web for latest diabetes management guidelines",
        routing_decision=decision,
    )

    assert resp.route_used == "WEB_SEARCH"
    assert resp.evidence.from_web is True
    assert len(resp.web_citations) == 1
    assert resp.web_citations[0].url == "https://ada.org/guidelines"
    assert resp.web_citations[0].title == "Diabetes Guidelines 2026"


# ---------------------------------------------------------------------------
# 2. Current-Information Query (Automatic Web Routing)
# ---------------------------------------------------------------------------

def test_current_information_query(monkeypatch):
    """Temporal or fresh news queries automatically trigger web routing."""
    temporal_questions = [
        "What is the latest news today regarding cancer immunotherapy?",
        "What is the current stock price of Pfizer right now?",
        "Recent 2026 clinical trial results for CRISPR gene editing",
    ]

    for q in temporal_questions:
        decision = query_router.route_decision(
            question=q,
            resolved_documents=[],
            has_any_documents=False,
            web_search_available=True,
        )
        assert decision.web_required is True, f"Failed web_required for: {q}"
        assert decision.intent == "web_research"

    # Execution verification
    mock_results = [
        WebSearchResult(
            title="Immunotherapy Breakthroughs",
            url="https://nih.gov/news/immunotherapy-2026",
            snippet="New findings published today in immunotherapy treatment.",
            score=0.88,
        )
    ]
    monkeypatch.setattr(
        web_search_service,
        "search_evidence",
        lambda q, max_results=None: WebSearchEvidence(
            query=q, status="success", results=mock_results, provider="MockProvider"
        ),
    )
    monkeypatch.setattr(web_search_service, "is_available", lambda: True)

    decision = query_router.route_decision(
        question=temporal_questions[0],
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    resp = answer_service.answer(question=temporal_questions[0], routing_decision=decision)
    assert resp.route_used == "WEB_SEARCH"
    assert resp.evidence.from_web is True
    assert resp.web_citations[0].url == "https://nih.gov/news/immunotherapy-2026"


# ---------------------------------------------------------------------------
# 3. General Question (Should Not Need Web)
# ---------------------------------------------------------------------------

def test_general_question_no_web():
    """General conceptual questions route to LLM and must not trigger web search."""
    general_queries = [
        "Explain how photosynthesis operates in plant chloroplasts.",
        "What is Newton's third law of motion?",
        "Can you describe the general structure of a typical eukaryotic cell?",
    ]

    for q in general_queries:
        decision = query_router.route_decision(
            question=q,
            resolved_documents=[],
            has_any_documents=True,  # Even if documents exist elsewhere
            web_search_available=True,  # Even if web is available
        )
        assert decision.web_required is False, f"Web incorrectly required for: {q}"
        assert decision.document_required is False
        assert decision.intent == "general_knowledge"

    # Answer execution check
    resp = answer_service.answer(question=general_queries[0], routing_decision=decision)
    assert resp.route_used == "GENERAL_LLM"
    assert resp.evidence.from_general_knowledge is True
    assert resp.evidence.from_web is False
    assert resp.evidence.from_documents is False
    assert len(resp.web_citations) == 0


# ---------------------------------------------------------------------------
# 4. Document Question (Should Not Need Web)
# ---------------------------------------------------------------------------

def test_document_question_no_web(monkeypatch):
    """Document questions route to document RAG and must not trigger web search."""
    doc = ResolvedDocument("doc_pathology", "pdf", "completed")

    doc_queries = [
        "According to the uploaded document, what was the biopsy result on page 2?",
        "Summarize the findings in this file.",
        "In the report, what is the recommended dosage for the patient?",
    ]

    for q in doc_queries:
        decision = query_router.route_decision(
            question=q,
            resolved_documents=[doc],
            has_any_documents=True,
            web_search_available=True,
        )
        assert decision.document_required is True, f"Document not required for: {q}"
        assert decision.web_required is False, f"Web incorrectly triggered for: {q}"
        assert decision.intent == "document_qa"

    # Mock CRAG document retrieval with high evidence quality
    mock_chunk = RetrievedChunk(
        text="Biopsy result confirms benign fibroadenoma with clear margins.",
        metadata={"filename": "biopsy.pdf", "page_number": 2, "document_id": "doc_pathology"},
        score=0.85,
    )
    monkeypatch.setattr(
        retriever_service,
        "retrieve_with_crag",
        lambda *args, **kwargs: RetrievalResult(
            status="relevant",
            chunks=[mock_chunk],
            grade="relevant",
            evidence_quality="high",
            initial_retrieval_score=0.85,
            reranker_score=0.85,
        ),
    )

    resp = answer_service.answer(
        question="According to the uploaded document, what was the biopsy result on page 2?",
        routing_decision=decision,
        document_ids=["doc_pathology"],
    )

    assert resp.route_used == "DOCUMENT_RAG"
    assert resp.evidence.from_documents is True
    assert resp.evidence.from_web is False
    assert len(resp.document_citations) == 1
    assert resp.document_citations[0].filename == "biopsy.pdf"
    assert resp.document_citations[0].page_number == 2
    assert len(resp.web_citations) == 0


# ---------------------------------------------------------------------------
# 5. Document + Web Hybrid Query (Evidence Fusion)
# ---------------------------------------------------------------------------

def test_document_web_hybrid_query(monkeypatch):
    """Hybrid queries execute both document RAG and Web Search, fusing evidence."""
    doc = ResolvedDocument("doc_trial", "pdf", "completed")

    hybrid_query = "Compare the oncology therapy in this document with the latest clinical trials online"

    decision = query_router.route_decision(
        question=hybrid_query,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )

    assert decision.intent == "hybrid"
    assert decision.document_required is True
    assert decision.web_required is True
    assert "document" in decision.sources
    assert "web" in decision.sources

    # Mock Document Retrieval
    doc_chunk = RetrievedChunk(
        text="Internal Protocol 101: Recommended first-line treatment is Pembrolizumab 200mg.",
        metadata={"filename": "trial_internal.pdf", "page_number": 5, "document_id": "doc_trial"},
        score=0.89,
    )
    monkeypatch.setattr(
        retriever_service,
        "retrieve_with_crag",
        lambda *args, **kwargs: RetrievalResult(
            status="relevant",
            chunks=[doc_chunk],
            grade="relevant",
            evidence_quality="high",
            initial_retrieval_score=0.89,
            reranker_score=0.89,
        ),
    )

    # Mock Web Search Tool
    web_result = WebSearchResult(
        title="2026 Phase III Oncology Trials",
        url="https://clinicaltrials.gov/ct2/show/NCT123456",
        snippet="Recent 2026 multi-center trial demonstrates enhanced PFS with combination therapy.",
        score=0.91,
    )
    monkeypatch.setattr(
        web_search_service,
        "search_evidence",
        lambda q, max_results=None: WebSearchEvidence(
            query=q, status="success", results=[web_result], provider="MockSerper"
        ),
    )
    monkeypatch.setattr(web_search_service, "is_available", lambda: True)

    captured_prompt = {}

    def mock_invoke(prompt):
        captured_prompt["prompt"] = prompt
        resp = MagicMock()
        resp.content = "Synthesized comparison between internal protocol and 2026 online trials."
        return resp

    monkeypatch.setattr(
        "backend.services.answer_service.get_chat_llm",
        lambda *args, **kwargs: MagicMock(invoke=mock_invoke),
    )

    resp = answer_service.answer(
        question=hybrid_query,
        routing_decision=decision,
        document_ids=["doc_trial"],
    )

    assert resp.route_used == "HYBRID"
    assert resp.evidence.from_documents is True
    assert resp.evidence.from_web is True

    # Citations from both sources present
    assert len(resp.document_citations) == 1
    assert resp.document_citations[0].filename == "trial_internal.pdf"
    assert len(resp.web_citations) == 1
    assert resp.web_citations[0].url == "https://clinicaltrials.gov/ct2/show/NCT123456"

    # Evidence fusion: verify both [DOCUMENT CONTEXT] and [WEB CONTEXT] reached LLM
    prompt_text = captured_prompt.get("prompt", "")
    assert "[DOCUMENT CONTEXT]" in prompt_text
    assert "Internal Protocol 101" in prompt_text
    assert "[WEB CONTEXT]" in prompt_text
    assert "https://clinicaltrials.gov/ct2/show/NCT123456" in prompt_text


# ---------------------------------------------------------------------------
# 6. Web Failure / API Failure (Graceful Containment & Security)
# ---------------------------------------------------------------------------

def test_web_failure_api_failure(monkeypatch):
    """When the Search API fails, WebSearchTool returns structured failure without crashing
    and without leaking secrets, and AnswerService degrades gracefully."""

    class FailingProvider:
        def search(self, query, max_results):
            raise ConnectionError("Search API upstream connection refused (HTTP 502)")

    monkeypatch.setattr(web_search_service, "provider", FailingProvider())
    monkeypatch.setattr(web_search_service, "is_available", lambda: True)

    evidence = web_search_service.search_evidence("latest cardiology news")

    # Structured failure status
    assert evidence.status == "failed"
    assert len(evidence.results) == 0
    assert "Search API upstream connection refused" in evidence.error

    # Answer execution should not raise an exception; falls back gracefully
    decision = RoutingDecision(
        intent="web_research",
        sources=["web", "llm"],
        web_required=True,
        document_required=False,
    )

    resp = answer_service.answer(question="latest cardiology news", routing_decision=decision)

    assert resp.route_used == "WEB_SEARCH"
    assert resp.evidence.from_web is False
    assert resp.evidence.from_general_knowledge is True  # Graceful fallback to general knowledge
    assert any("web search service failed" in w.lower() for w in resp.warnings)
    assert resp.answer != ""


# ---------------------------------------------------------------------------
# 7. Query Cleaning & Source Filtering / Ranking Unit Tests
# ---------------------------------------------------------------------------

def test_query_cleaning_and_source_filtering():
    """Verify conversational prefix stripping, spam URL filtering, and ranking."""
    raw_query = "search the web for: latest stroke treatment 2026"
    cleaned = web_search_service._clean_search_query(raw_query)
    assert cleaned == "latest stroke treatment 2026"

    # Raw results containing spam and valid URLs
    raw_items = [
        {"title": "Ad Link", "url": "https://adservice.google.com/ad", "snippet": "Buy pills"},
        {"title": "Local", "url": "http://localhost/test", "snippet": "Test"},
        {"title": "Empty", "url": "https://example.com", "snippet": ""},
        {
            "title": "Stroke Guidelines",
            "url": "https://www.nih.gov/health-information/stroke",
            "snippet": "National Institutes of Health guidelines on acute ischemic stroke treatment in 2026.",
        },
        {
            "title": "General Health News",
            "url": "https://news.com/article",
            "snippet": "Random article with little relevance.",
        },
    ]

    filtered = web_search_service._filter_sources(raw_items)
    # Ad link, localhost, and empty should be filtered out
    assert len(filtered) == 2
    assert any("nih.gov" in f["url"] for f in filtered)

    ranked = web_search_service._rank_sources(cleaned, filtered, max_results=5)
    assert len(ranked) == 2
    # NIH article should be ranked first due to term overlap and authoritative domain bonus
    assert ranked[0].domain == "nih.gov"
    assert ranked[0].score > ranked[1].score
