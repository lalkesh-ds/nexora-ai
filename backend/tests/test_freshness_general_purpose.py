"""
Regression & verification tests for:
1. FreshnessService (geopolitical, officeholder, temporal, market triggers)
2. General-Purpose Routing (China-Arunachal border, gradient descent, coding, calculations)
3. Date extraction and freshness scoring in WebSearchService
4. Web search limitation disclosure on search failure in AnswerService
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.schemas import RoutingDecision
from backend.services.freshness_service import freshness_service
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.web_search_service import web_search_service, WebSearchResult
from backend.services.answer_service import answer_service


# ---------------------------------------------------------------------------
# 1. Freshness Service Tests
# ---------------------------------------------------------------------------

def test_freshness_china_arunachal_pradesh():
    """Geopolitical query regarding China & Arunachal Pradesh must require freshness."""
    q = "Is China entering Arunachal Pradesh? What is the latest situation?"
    eval_res = freshness_service.evaluate(q)
    assert eval_res["requires_freshness"] is True
    assert eval_res["time_sensitivity"] in ["critical", "high"]
    assert eval_res["freshness_policy"] == "breaking_geopolitical"

    # Search query formulation
    sq = freshness_service.formulate_search_query(q)
    assert "China" in sq or "Arunachal" in sq


def test_freshness_static_concept_no_trigger():
    """Foundational conceptual questions should not trigger freshness requirements."""
    q = "Explain gradient descent in machine learning."
    eval_res = freshness_service.evaluate(q)
    assert eval_res["requires_freshness"] is False
    assert eval_res["time_sensitivity"] in ["none", "static"]


def test_freshness_temporal_keywords():
    """Explicit temporal keywords like 'today', 'this week', 'latest update' must trigger freshness."""
    q = "What are the latest updates on space exploration this week?"
    eval_res = freshness_service.evaluate(q)
    assert eval_res["requires_freshness"] is True
    assert eval_res["time_sensitivity"] in ["critical", "high"]


# ---------------------------------------------------------------------------
# 2. Query Router Intent & Freshness Tests
# ---------------------------------------------------------------------------

def test_query_router_geopolitical_triggers_web_search():
    """The critical bug question must route to web_research and require web search."""
    q = "Is China entering Arunachal Pradesh? What is the latest situation?"
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent in ["web_research", "hybrid"]
    assert decision.web_required is True
    assert decision.requires_web is True
    assert decision.requires_freshness is True
    assert "China" in decision.search_query or "Arunachal" in decision.search_query


def test_query_router_general_knowledge():
    """General conceptual questions route to general_knowledge without web search."""
    q = "Explain the difference between L1 and L2 regularization."
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.web_required is False
    assert decision.requires_web is False


def test_query_router_code_assistance():
    """Coding queries route to code_assistance with requires_code_execution flag."""
    q = "Write a Python async queue worker with exponential backoff retry."
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "code_assistance"
    assert decision.requires_code_execution is True


def test_query_router_calculation():
    """Math or formula calculation queries route to calculation."""
    q = "Calculate the compound annual growth rate (CAGR) for an investment of $10,000 growing to $25,000 over 5 years."
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "calculation"
    assert decision.requires_calculation is True


def test_query_router_document_qa():
    """Uploaded document queries with explicit doc scope route to document_qa."""
    q = "Summarize chapter 3 from the uploaded quarterly financial report."
    doc = ResolvedDocument(document_id="doc-quarterly-2026", source_type="pdf", status="completed")
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=True,
    )
    assert decision.intent == "document_qa"
    assert decision.requires_document_retrieval is True


# ---------------------------------------------------------------------------
# 3. Web Search Service Date & Authority Tests
# ---------------------------------------------------------------------------

def test_web_search_date_extraction_and_scoring():
    """WebSearchService must extract dates and rank authoritative domains higher."""
    raw_results = [
        {
            "title": "Border Situation in Arunachal Pradesh: Latest Updates",
            "url": "https://www.thehindu.com/news/national/border-situation-arunachal-pradesh/article1234.ece",
            "snippet": "October 24, 2026 - Government officials stated that border peace remains stable along the LAC.",
        },
        {
            "title": "Random Blog Post on Borders",
            "url": "https://randomblog.example.com/opinion/border",
            "snippet": "Just my personal thoughts on international borders.",
        }
    ]

    filtered = web_search_service._filter_sources(raw_results)
    extracted = web_search_service._extract_content(filtered)
    ranked = web_search_service._rank_sources("China Arunachal Pradesh border latest", extracted, max_results=5)

    assert len(ranked) == 2
    # The Hindu result has a date and authoritative domain (.thehindu.com)
    hindu_result = next(r for r in ranked if "thehindu.com" in r.url)
    assert hindu_result.published_date is not None
    assert "2026" in hindu_result.published_date
    assert hindu_result.score > 0.4


# ---------------------------------------------------------------------------
# 4. Answer Service Web Search Limitation Notice
# ---------------------------------------------------------------------------

def test_answer_service_discloses_search_failure():
    """When mandatory web search fails or returns zero results, answer must include limitation notice."""
    decision = RoutingDecision(
        intent="web_research",
        web_required=True,
        requires_freshness=True,
        search_query="China Arunachal Pradesh latest 2026",
    )

    prompts_captured = []

    def mock_invoke(prompt):
        prompts_captured.append(prompt)
        res = MagicMock()
        res.content = "Current live verification is unavailable. Background: the LAC is situated in Arunachal Pradesh..."
        return res

    mock_llm = MagicMock()
    mock_llm.invoke = mock_invoke

    # Mock get_chat_llm and web_search_service.search_evidence returning no results
    with patch("backend.services.answer_service.get_chat_llm", return_value=mock_llm):
        with patch.object(web_search_service, "is_available", return_value=True):
            with patch.object(
                web_search_service,
                "search_evidence",
                return_value=MagicMock(status="no_results", results=[]),
            ):
                resp = answer_service.answer(
                    question="Is China entering Arunachal Pradesh? What is the latest situation?",
                    routing_decision=decision,
                )

                assert len(prompts_captured) > 0
                prompt_text = prompts_captured[0]
                assert "[WEB SEARCH LIMITATION NOTICE]" in prompt_text
                assert "Live web search was required to verify current information, but returned no verified recent results." in prompt_text
                assert "Current live verification is unavailable" in resp.answer
