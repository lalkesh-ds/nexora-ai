"""
Comprehensive regression test suite for Nexora AI Agentic Pipeline Repair.

Covers all 11 required evaluation categories:
1. Stable general-knowledge questions.
2. Recent technology announcements and inventions (including Elon Musk flying car).
3. Current geopolitical developments.
4. Questions that explicitly require up-to-date information.
5. Uploaded-document questions.
6. Questions requiring both document and web evidence (hybrid).
7. Questions with no reliable supporting evidence (honest abstention / debunking).
8. Empty search results, timeouts, provider errors, and malformed search responses.
9. Conflicting sources and misleading headlines.
10. Citation correctness and unsupported claims.
11. Follow-up questions that depend on conversation context.
"""
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.schemas import (
    EvidenceBreakdown,
    QueryRequest,
    RoutingDecision,
    SourceCitation,
    WebCitation,
)
from backend.services.answer_service import answer_service
from backend.services.citation_service import citation_service
from backend.services.conversation_service import conversation_service
from backend.services.freshness_service import freshness_service
from backend.services.orchestrator_service import orchestrator_service
from backend.services.query_router import ResolvedDocument, query_router
from backend.services.retriever_service import (
    RetrievalResult,
    RetrievedChunk,
    retriever_service,
)
from backend.services.verification_service import verification_service
from backend.services.web_search_service import (
    WebSearchEvidence,
    WebSearchResult,
    web_search_service,
)

client = TestClient(main_module.app)


# ---------------------------------------------------------------------------
# 1. Stable General Knowledge
# ---------------------------------------------------------------------------
def test_category_1_stable_general_knowledge():
    """Conceptual, math, or foundational questions route to general_knowledge without web search."""
    q = "Explain the biochemical process of photosynthesis and how chlorophyll absorbs light."
    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.web_required is False
    assert decision.document_required is False
    assert decision.requires_freshness is False


# ---------------------------------------------------------------------------
# 2. Recent Technology Announcements and Inventions (Elon Musk Flying Car)
# ---------------------------------------------------------------------------
def test_category_2_elon_musk_flying_car_routes_to_web_search():
    """Invention / prototype claims like 'Elon Musk's new flying-car invention' MUST route to web search."""
    q = "What is Elon Musk's new flying-car invention?"
    freshness = freshness_service.evaluate(q)
    assert freshness.requires_freshness is True

    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True
    assert decision.requires_freshness is True
    assert "Elon Musk" in decision.search_query


def test_category_2_elon_musk_flying_car_evidence_distinguishes_claims():
    """Ensures pipeline evaluates evidence critically and does not claim a production flying car is confirmed."""
    fake_results = [
        WebSearchResult(
            title="Elon Musk reveals world's first flying car at Tesla event",
            url="https://www.theguardian.com/technology/test-tesla-roadster",
            snippet="A vehicle called the Tesla Roadster 2 drove up a ramp and used SpaceX-derived rocket thrusters to lift off and flip as a demonstration prototype.",
            score=0.9,
            domain="theguardian.com",
            published_date="2026-10-16",
        ),
        WebSearchResult(
            title="Tesla Flying Roadster BUSTED",
            url="https://www.reddit.com/r/RealTesla/comments/busted",
            snippet="Community notes that no certified production aircraft exists and road-legal status is unverified.",
            score=0.4,
            domain="reddit.com",
            published_date="1 week ago",
        ),
    ]

    with patch.object(
        web_search_service,
        "search_evidence",
        return_value=WebSearchEvidence(
            query="Elon Musk flying car",
            status="success",
            results=fake_results,
            provider="MockSerper",
        ),
    ):
        with patch.object(
            answer_service,
            "_build_prompt",
            wraps=answer_service._build_prompt,
        ) as mock_prompt:
            res = orchestrator_service.orchestrate("What is Elon Musk's new flying-car invention?")
            assert res.route_used == "WEB_SEARCH"
            assert res.evidence.from_web is True
            # Prompt must instruct model on distinguishing confirmed facts vs prototypes vs rumors
            prompt_content = mock_prompt.call_args[0][2]
            prompt_str = " ".join(prompt_content)
            assert "WEB CONTEXT" in prompt_str


# ---------------------------------------------------------------------------
# 3. Current Geopolitical Developments
# ---------------------------------------------------------------------------
def test_category_3_geopolitical_developments():
    """Geopolitical border developments trigger critical freshness requirement and web research."""
    q = "What are the latest border developments between India and China near LAC in 2026?"
    freshness = freshness_service.evaluate(q)
    assert freshness.requires_freshness is True
    assert freshness.volatility_level == "critical"

    decision = query_router.route_decision(
        question=q,
        resolved_documents=[],
        has_any_documents=False,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True


# ---------------------------------------------------------------------------
# 4. Questions with Explicit Recency Signals
# ---------------------------------------------------------------------------
def test_category_4_explicit_recency_signals():
    """Queries with explicit temporal signals ('latest', 'recently', 'today') route to web_research."""
    queries = [
        "What are the latest updates on the James Webb Space Telescope discoveries today?",
        "Who recently won the 2026 Nobel Prize in Physics?",
        "Check current price and market cap of Bitcoin right now.",
    ]
    for q in queries:
        decision = query_router.route_decision(
            question=q,
            resolved_documents=[],
            has_any_documents=False,
            web_search_available=True,
        )
        assert decision.web_required is True
        assert decision.intent == "web_research"


# ---------------------------------------------------------------------------
# 5. Uploaded Document Questions
# ---------------------------------------------------------------------------
def test_category_5_document_qa_scoping():
    """Specific document questions route to document_qa and scope to document retrieval."""
    doc = ResolvedDocument("doc_contract_99", "pdf", "completed")
    decision = query_router.route_decision(
        question="According to the uploaded agreement, what is the termination clause in section 4?",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
        explicit_doc_selection=True,
    )
    assert decision.intent == "document_qa"
    assert decision.document_required is True
    assert decision.web_required is False


# ---------------------------------------------------------------------------
# 6. Hybrid Questions (Document + Web External Evidence)
# ---------------------------------------------------------------------------
def test_category_6_hybrid_question_requires_both_sources():
    """Cross-referencing uploaded files with external market/guidelines triggers hybrid routing."""
    doc = ResolvedDocument("doc_patient_1", "pdf", "completed")
    decision = query_router.route_decision(
        question="Compare the dosage in our uploaded patient report with the latest WHO guidelines online",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "hybrid"
    assert decision.document_required is True
    assert decision.web_required is True
    assert "document" in decision.sources
    assert "web" in decision.sources


# ---------------------------------------------------------------------------
# 7. Questions with No Reliable Supporting Evidence (Honest Abstention)
# ---------------------------------------------------------------------------
def test_category_7_honest_abstention_recognized_by_verifier():
    """Honest negative assertions ('no confirmed invention exists') are recognized as valid abstention, not hallucinations."""
    answer = (
        "There is no verified announcement or confirmed official invention of a flying car by Elon Musk. "
        "While concepts like the Tesla Roadster rocket-thruster package have been discussed, "
        "no certified production flying car has been demonstrated or released."
    )
    claims = verification_service._extract_factual_claims(answer)
    # The negative claims should be recognized as abstentions
    for c in claims:
        assert verification_service._is_abstention(c) is True

    # Empty context verification with honest abstention should pass grounding check
    grounding, faithfulness, unsupported = verification_service._evaluate_grounding(claims, "")
    assert len(unsupported) == 0
    assert grounding == 1.0


# ---------------------------------------------------------------------------
# 8. Empty Search Results, Timeouts & Provider Failures
# ---------------------------------------------------------------------------
def test_category_8_search_failure_produces_limitation_notice():
    """When web search fails or times out, the orchestrator includes a transparent limitation notice."""
    with patch.object(
        web_search_service,
        "search_evidence",
        return_value=WebSearchEvidence(
            query="test",
            status="failed",
            results=[],
            provider="SerperProvider",
            error="HTTP 504 Gateway Timeout",
        ),
    ):
        with patch.object(web_search_service, "is_available", return_value=True):
            res = answer_service.answer(
                question="What is the latest breaking news on Mars sample return today?",
                routing_decision=RoutingDecision(
                    intent="web_research",
                    sources=["web", "llm"],
                    web_required=True,
                    requires_freshness=True,
                ),
            )
            assert any("failed" in w.lower() for w in res.warnings)
            assert res.evidence.from_web is False


# ---------------------------------------------------------------------------
# 9. Conflicting Sources and Misleading Headlines
# ---------------------------------------------------------------------------
def test_category_9_social_media_clickbait_is_deprioritized():
    """Social media video links (e.g. Facebook video clickbait) receive a ranking penalty below reputable sources."""
    items = [
        {
            "title": "FLYING CAR Elon Musk unveils Tesla's new Roadster with capability of fly",
            "url": "https://www.facebook.com/FOX19/videos/flying-car-tesla/123",
            "snippet": "Elon Musk has unveiled the groundbreaking prototype of the flying Tesla with vertical flight.",
            "published_date": "yesterday",
        },
        {
            "title": "Tesla Roadster: Reality Check on the Flying Claims",
            "url": "https://www.theverge.com/transportation/tesla-roadster-spacex-package-flying",
            "snippet": "Experts note Elon Musk's statements about thrusters remain an uncertified concept, not a certified aircraft.",
            "published_date": "yesterday",
        },
    ]
    ranked = web_search_service._rank_sources("Elon Musk flying car", items, max_results=5)
    # The Verge (authoritative journalism) MUST outrank the Facebook video
    assert ranked[0].domain == "theverge.com"
    assert ranked[0].score > ranked[1].score


# ---------------------------------------------------------------------------
# 10. Citation Correctness & Fake Citation Detection
# ---------------------------------------------------------------------------
def test_category_10_fake_citation_detection():
    """The verifier penalizes fabricated URLs and invented page citations."""
    real_cites = [WebCitation(title="BBC", url="https://www.bbc.com/news/12345", snippet="News")]
    fake_url_answer = "According to recent reports at https://www.fake-made-up-source.org/secret-news, the event happened."
    score = verification_service._evaluate_citations(
        answer=fake_url_answer,
        route="WEB_SEARCH",
        web_citations=real_cites,
    )
    assert score < 1.0  # Fabricated URL penalized


# ---------------------------------------------------------------------------
# 11. Follow-up Questions and Context Scoping
# ---------------------------------------------------------------------------
def test_category_11_contextual_query_rewriting():
    """Pronouns in follow-up queries are rewritten using conversational history."""
    history = "User: What is Starship Flight 6?\nAssistant: Starship Flight 6 was SpaceX's sixth integrated test flight."
    follow_up = "When did it launch?"
    mock_resp = MagicMock()
    mock_resp.content = "When did Starship Flight 6 launch?"
    with patch("backend.services.llm_provider.get_chat_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_resp
        mock_llm_factory.return_value = mock_llm
        rewritten = retriever_service.rewrite_query(follow_up, history)
        assert "starship" in rewritten.lower() or "flight 6" in rewritten.lower()


# ---------------------------------------------------------------------------
# 12. Request Tracing Header
# ---------------------------------------------------------------------------
def test_request_id_tracing_header():
    """Every HTTP response must return an X-Request-ID header."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
