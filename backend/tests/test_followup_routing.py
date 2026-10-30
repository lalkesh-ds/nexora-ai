"""
Tests for Rule 3b: follow-up continuation routing when active text docs are present.
Ensures "also search for X" / "for X" queries route to document_qa, while
general knowledge questions with active docs still route to general_knowledge.
"""
import pytest
from backend.services.query_router import QueryRouter, ResolvedDocument

router = QueryRouter()

def _make_text_doc(doc_id: str = "doc1") -> ResolvedDocument:
    return ResolvedDocument(doc_id, "pdf", "completed")


# ── Follow-up queries SHOULD route to document_qa ────────────────────────────

@pytest.mark.parametrize("query", [
    "also search for sujal baid",
    "also find diya rathore",
    "for diya rathore",
    "for Diya Rathore",
    "search for 24bcon0162",
    "find raj kumar",
    "what about anita sharma",
    "check for rohan singh",
])
def test_followup_routes_to_document_qa(query):
    """Short follow-up continuation queries with active text doc → document_qa."""
    doc = _make_text_doc()
    d = router.route_decision(
        question=query,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=False,
    )
    assert d.intent == "document_qa", (
        f"Expected document_qa for follow-up '{query}' with active doc, got {d.intent!r} "
        f"(reasoning: {d.reasoning})"
    )


# ── General knowledge questions with active docs should NOT route to doc_qa ──

@pytest.mark.parametrize("query", [
    "Explain the difference between supervised and unsupervised learning.",
    "What is the capital of France?",
    "How does photosynthesis work?",
    "Write a Python function to reverse a string.",
    "What is the GDP of India?",
])
def test_general_question_with_active_doc_stays_general(query):
    """Long general questions with active docs should NOT route to document_qa."""
    doc = _make_text_doc()
    d = router.route_decision(
        question=query,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=False,
    )
    assert d.intent != "document_qa", (
        f"General question '{query}' should NOT route to document_qa, got {d.intent!r}"
    )


# ── No docs active → follow-up marker alone must NOT force document_qa ───────

@pytest.mark.parametrize("query", [
    "also search for sujal baid",
    "for diya rathore",
])
def test_followup_without_active_docs_no_doc_route(query):
    """Follow-up marker without active text docs must NOT route to document_qa."""
    d = router.route_decision(
        question=query,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
        explicit_doc_selection=False,
    )
    assert d.intent != "document_qa", (
        f"Query '{query}' without active docs should not route to document_qa, got {d.intent!r}"
    )
