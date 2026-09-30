"""
Unit tests for Phase 1: AI Orchestrator and Intelligent Router.

Validates:
1. An explicit user request to search the web MUST route to web search (Rule 1).
2. Failure to find information in a document MUST NOT terminate the request (Rule 2).
3. A normal general question should NOT automatically trigger document RAG (Rule 3).
4. A current/time-sensitive question should be eligible for web search (Rule 4).
5. An image should route to vision / image_qa rather than pure text retrieval (Rule 5).
6. Multiple sources must be allowed for hybrid questions (Rule 6).
7. Structured RoutingDecision schemas and responses.
"""
import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.orchestrator_service import orchestrator_service
from backend.schemas import RoutingDecision

client = TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Router Unit Tests
# ---------------------------------------------------------------------------

def test_explicit_web_search_routes_to_web():
    """Rule 1: An explicit user request to search the web MUST route to web search."""
    doc = ResolvedDocument("doc1", "pdf", "completed")
    decision = query_router.route_decision(
        question="Please search the web for the latest Python 3.13 features",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True
    assert decision.document_required is False
    assert "web" in decision.sources
    assert decision.to_legacy_route() == "WEB_SEARCH"


def test_google_keyword_routes_to_web():
    """Rule 1: Variations like 'Google this' route to web search."""
    decision = query_router.route_decision(
        question="Google the current weather in Tokyo",
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True


def test_general_question_does_not_trigger_document_rag():
    """Rule 3: A normal general question should NOT automatically trigger document RAG."""
    # Even if documents exist globally or in session
    doc = ResolvedDocument("doc1", "pdf", "completed")
    decision = query_router.route_decision(
        question="Explain the difference between supervised and unsupervised learning.",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=False,
    )
    assert decision.intent == "general_knowledge"
    assert decision.document_required is False
    assert decision.web_required is False
    assert decision.sources == ["llm"]
    assert decision.to_legacy_route() == "GENERAL_LLM"


def test_general_greeting_routes_to_general_knowledge():
    """Greetings route cleanly to general knowledge."""
    decision = query_router.route_decision(
        question="Hello! How are you today?",
        resolved_documents=[],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.document_required is False


def test_time_sensitive_question_routes_to_web():
    """Rule 4: A current/time-sensitive question should be eligible for web search."""
    decision = query_router.route_decision(
        question="What are the latest breaking news headlines today?",
        resolved_documents=[],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True
    assert decision.to_legacy_route() == "WEB_SEARCH"


def test_explicit_document_query_routes_to_document_qa():
    """Asking specifically about uploaded document routes to document_qa."""
    doc = ResolvedDocument("doc1", "pdf", "completed")
    decision = query_router.route_decision(
        question="According to the uploaded document, what was the Q3 net revenue?",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "document_qa"
    assert decision.document_required is True
    assert "document" in decision.sources
    assert decision.to_legacy_route() == "DOCUMENT_RAG"


def test_active_image_routes_to_image_qa():
    """Rule 5: An image should route to image_qa / vision."""
    image_doc = ResolvedDocument("img1", "png", "completed")
    decision = query_router.route_decision(
        question="What is written on the sign in this image?",
        resolved_documents=[image_doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "image_qa"
    assert decision.vision_required is True
    assert "vision" in decision.sources
    assert decision.to_legacy_route() == "VISION"


def test_hybrid_question_routes_to_multiple_sources():
    """Rule 6: Multiple sources must be allowed for hybrid questions."""
    doc = ResolvedDocument("doc1", "pdf", "completed")
    decision = query_router.route_decision(
        question="Compare our internal roadmap in the document with the latest AI news today",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "hybrid"
    assert decision.document_required is True
    assert decision.web_required is True
    assert "document" in decision.sources
    assert "web" in decision.sources
    assert decision.to_legacy_route() == "HYBRID"


# ---------------------------------------------------------------------------
# Orchestrator & Fallback Integration Tests
# ---------------------------------------------------------------------------

def test_missing_document_info_does_not_terminate_request(monkeypatch):
    """Rule 2: Failure to find information in a document MUST NOT terminate the request."""
    import backend.services.retriever_service as rs
    import backend.services.web_search_service as ws

    # Mock empty retrieval (document has no matching chunks)
    monkeypatch.setattr(rs.retriever_service, "retrieve", lambda *a, **kw: [])

    # Test via /query endpoint
    resp = client.post("/query", json={
        "question": "According to the uploaded document, what is the secret code?",
        "mode": "DOCUMENT_RAG",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert body["answer"]  # Must produce a valid answer, not crash or terminate
    assert any("no relevant content" in w.lower() for w in body["warnings"])


def test_query_endpoint_returns_structured_routing_metadata():
    """Verifies that QueryResponse includes the structured RoutingDecision."""
    resp = client.post("/query", json={
        "question": "What is the boiling point of water?",
        "mode": "GENERAL_LLM",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_used"] == "GENERAL_LLM"
    assert "routing" in body
    assert body["routing"] is not None
    assert body["routing"]["intent"] == "general_knowledge"
    assert body["routing"]["sources"] == ["llm"]
    assert body["routing"]["document_required"] is False
    assert body["routing"]["web_required"] is False
