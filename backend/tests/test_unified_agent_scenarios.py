"""
Comprehensive automated tests covering Scenarios A through L defined in Section 13
of the Nexora AI Master Engineering Specification:

Test A — Stable general knowledge
Test B — Current geopolitical information
Test C — Explicitly historical question
Test D — Uploaded document question
Test E — Document plus current information (Hybrid)
Test F — Insufficient retrieval & safe abstention
Test G — Verification & ungrounded claim detection
Test H — Web provider failure & limitation notice
Test I — Invalid/unknown citations filtered out
Test J — Landing page isolation
Test K — Document upload failure handling
Test L — Follow-up conversation context scoping
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.schemas import QueryRequest, RoutingDecision, SourceCitation, WebCitation
from backend.services.freshness_service import freshness_service
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.citation_service import citation_service
from backend.services.answer_service import answer_service
from backend.services.verification_service import verification_service
from backend.services.conversation_service import conversation_service
from fastapi.testclient import TestClient
import backend.main as main_module

client = TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Test A — Stable general knowledge
# ---------------------------------------------------------------------------
def test_scenario_a_stable_general_knowledge():
    q = "Explain the difference between a Python list and a tuple."
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.web_required is False
    assert decision.requires_web is False
    assert decision.requires_freshness is False


# ---------------------------------------------------------------------------
# Test B — Current geopolitical information
# ---------------------------------------------------------------------------
def test_scenario_b_current_geopolitical():
    q = "What is the latest situation concerning China and Arunachal Pradesh?"
    freshness = freshness_service.evaluate(q)
    assert freshness["requires_freshness"] is True
    assert freshness["volatility_level"] == "critical"

    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent in ["web_research", "hybrid"]
    assert decision.web_required is True
    assert decision.requires_freshness is True
    assert decision.search_query is not None


# ---------------------------------------------------------------------------
# Test C — Explicitly historical question
# ---------------------------------------------------------------------------
def test_scenario_c_explicitly_historical():
    q = "What happened during the 2020 India-China border clashes?"
    freshness = freshness_service.evaluate(q)
    # Explicitly historical past does not require current-news web search
    assert freshness["requires_freshness"] is False

    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.web_required is False


# ---------------------------------------------------------------------------
# Test D — Uploaded document question
# ---------------------------------------------------------------------------
def test_scenario_d_uploaded_document():
    q = "Summarize the key findings of my uploaded report."
    doc = ResolvedDocument("doc-audit-123", "pdf", "completed")
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=True,
    )
    assert decision.intent == "document_qa"
    assert decision.document_required is True
    assert decision.requires_document_retrieval is True


# ---------------------------------------------------------------------------
# Test E — Document plus current information (Hybrid)
# ---------------------------------------------------------------------------
def test_scenario_e_document_plus_current_information():
    q = "Compare the findings in my uploaded 2024 report with the latest available research."
    doc = ResolvedDocument("doc-report-2024", "pdf", "completed")
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=True,
    )
    assert decision.intent == "hybrid"
    assert decision.document_required is True
    assert decision.web_required is True


# ---------------------------------------------------------------------------
# Test F — Insufficient retrieval
# ---------------------------------------------------------------------------
def test_scenario_f_insufficient_retrieval_notice():
    decision = RoutingDecision(
        intent="document_qa",
        document_required=True,
        web_required=False,
    )
    prompts_captured = []

    def mock_invoke(prompt):
        prompts_captured.append(prompt)
        res = MagicMock()
        res.content = "The uploaded document does not contain information regarding this topic."
        return res

    mock_llm = MagicMock()
    mock_llm.invoke = mock_invoke

    with patch("backend.services.answer_service.get_chat_llm", return_value=mock_llm):
        with patch("backend.services.retriever_service.retriever_service.retrieve_with_crag") as mock_retrieve:
            mock_res = MagicMock()
            mock_res.chunks = []
            mock_res.evidence_quality = "none"
            mock_retrieve.return_value = mock_res

            with patch("backend.services.web_search_service.web_search_service.is_available", return_value=False):
                resp = answer_service.answer(
                    question="What was the EBITDA margin in 2018?",
                    routing_decision=decision,
                )
                assert len(prompts_captured) > 0
                assert "[DOCUMENT RETRIEVAL NOTICE]" in prompts_captured[0]
                assert "not found in the uploaded document" in prompts_captured[0]


# ---------------------------------------------------------------------------
# Test G — Conflicting sources / unsupported claims
# ---------------------------------------------------------------------------
def test_scenario_g_ungrounded_claims_fail_verification():
    v = verification_service.verify(
        question="What is the recommended dose of drug X?",
        answer="The recommended dose is 500mg three times daily with meals.",
        route="DOCUMENT_RAG",
        context_blocks=["The document discusses drug X safety profile but specifies no dosing guidelines."],
        document_citations=[],
    )
    assert v.passed is False
    assert v.hallucination_risk in ["medium", "high"]
    assert len(v.unsupported_claims) > 0


# ---------------------------------------------------------------------------
# Test H — Web provider failure & limitation notice
# ---------------------------------------------------------------------------
def test_scenario_h_web_provider_failure_limitation():
    decision = RoutingDecision(
        intent="web_research",
        web_required=True,
        requires_freshness=True,
        search_query="latest international clean energy policies",
    )
    prompts_captured = []

    def mock_invoke(prompt):
        prompts_captured.append(prompt)
        res = MagicMock()
        res.content = "I am currently unable to retrieve live search results. As of past records..."
        return res

    mock_llm = MagicMock()
    mock_llm.invoke = mock_invoke

    with patch("backend.services.answer_service.get_chat_llm", return_value=mock_llm):
        with patch("backend.services.web_search_service.web_search_service.is_available", return_value=True):
            with patch("backend.services.web_search_service.web_search_service.search_evidence") as mock_search:
                mock_search.return_value = MagicMock(status="failed", results=[], error="Connection reset")
                resp = answer_service.answer(
                    question="What are the latest clean energy policies?",
                    routing_decision=decision,
                )
                assert len(prompts_captured) > 0
                assert "[WEB SEARCH LIMITATION NOTICE]" in prompts_captured[0]


# ---------------------------------------------------------------------------
# Test I — Invalid/unknown citations filtered out
# ---------------------------------------------------------------------------
def test_scenario_i_invalid_citations_filtered():
    # Chunks with missing or "unknown" metadata
    chunk1 = MagicMock()
    chunk1.metadata = {"filename": "unknown", "document_id": ""}
    chunk1.text = "Text without valid source"
    chunk1.score = 0.5

    chunk2 = MagicMock()
    chunk2.metadata = {"filename": "", "document_id": ""}
    chunk2.text = "Text with empty filename"
    chunk2.score = 0.4

    chunk3 = MagicMock()
    chunk3.metadata = {"filename": "real_report.pdf", "document_id": "doc123", "page_number": 2}
    chunk3.text = "Valid verified evidence text"
    chunk3.score = 0.9

    cites = citation_service.from_chunks([chunk1, chunk2, chunk3])
    assert len(cites) == 1
    assert cites[0].filename == "real_report.pdf"
    assert cites[0].page_number == 2
    # Ensure no 'unknown' citation was generated
    assert all(c.filename != "unknown" and c.filename != "" for c in cites)

    # Web citations with unknown or malformed url
    web_res1 = MagicMock(url="javascript:void(0)", title="Bad Link", snippet="bad")
    web_res2 = MagicMock(url="", title="No URL", snippet="bad")
    web_res3 = MagicMock(url="https://docs.python.org/3/library/asyncio.html", title="Asyncio Docs", snippet="Good")

    web_cites = citation_service.from_web_results([web_res1, web_res2, web_res3])
    assert len(web_cites) == 1
    assert web_cites[0].url == "https://docs.python.org/3/library/asyncio.html"


# ---------------------------------------------------------------------------
# Test J — Landing page isolation
# ---------------------------------------------------------------------------
def test_scenario_j_landing_page_isolation():
    # User queries do not pollute static landing page examples
    from backend.services.conversation_service import conversation_service
    s1 = conversation_service.create_session()
    conversation_service.add_turn(s1, "user", "Sensitive user question about proprietary system.")
    conversation_service.add_turn(s1, "assistant", "Confidential assistant response.")

    # A separate session must not see s1's history
    s2 = conversation_service.create_session()
    hist2 = conversation_service.get_history(s2)
    assert len(hist2) == 0


# ---------------------------------------------------------------------------
# Test K — Document upload failure handling
# ---------------------------------------------------------------------------
def test_scenario_k_upload_failure(tmp_path):
    bad_file = tmp_path / "corrupt.exe"
    bad_file.write_bytes(b"MZfakebinary")
    with open(bad_file, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("corrupt.exe", f, "application/octet-stream")})
    assert resp.status_code == 422
    data = resp.json()
    assert data["documents"][0]["status"] == "rejected"


# ---------------------------------------------------------------------------
# Test L — Follow-up conversation context scoping
# ---------------------------------------------------------------------------
def test_scenario_l_conversation_followup_scoping():
    s = conversation_service.create_session()
    conversation_service.add_turn(s, "user", "My project is named Nexora.")
    conversation_service.add_turn(s, "assistant", "Understood, your project is Nexora.")

    hist_text = conversation_service.history_as_text(s)
    assert "Nexora" in hist_text

    # Unrelated session has empty history
    other_s = conversation_service.create_session()
    assert conversation_service.history_as_text(other_s) == ""
