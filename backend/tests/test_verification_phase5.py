"""
Unit and integration tests for Phase 5: Answer Verification and Quality Control.

Scenarios tested:
1. Well-grounded document answer (passes verification with high confidence)
2. Unsupported document answer (fails due to ungrounded claims and high hallucination risk)
3. Web-grounded answer (validates web source alignment and citations)
4. General LLM answer (validates relevance and absence of fabricated citations)
5. Image-based answer (evaluates visual context consistency)
6. Failed verification requiring repair (fails initial check, triggers repair loop, re-verifies, bounds retries)
"""
import pytest
from unittest.mock import MagicMock

from backend.schemas import SourceCitation, WebCitation, RoutingDecision, VerificationResult
from backend.services.verification_service import verification_service
from backend.services.answer_service import answer_service
from backend.services.retriever_service import retriever_service, RetrievedChunk, RetrievalResult


# ---------------------------------------------------------------------------
# 1. Well-Grounded Document Answer
# ---------------------------------------------------------------------------

def test_well_grounded_document_answer():
    """Well-grounded answer citing true document facts passes verification with high confidence."""
    question = "What is the recommended dosage for Amoxicillin in adult bacterial infections according to the report?"
    context_blocks = [
        "[DOCUMENT CONTEXT]\n"
        "(filename: antibiotics.pdf, page: 3)\n"
        "Amoxicillin dosage guideline for adult bacterial infections is 500mg every 8 hours for 7 to 10 days.\n"
        "[/DOCUMENT CONTEXT]"
    ]
    citations = [
        SourceCitation(filename="antibiotics.pdf", page_number=3, document_id="doc_1", snippet="Amoxicillin 500mg")
    ]
    answer = (
        "According to page 3 of antibiotics.pdf, the recommended dosage of Amoxicillin for "
        "adult bacterial infections is 500mg taken every 8 hours for 7 to 10 days."
    )

    result: VerificationResult = verification_service.verify(
        question=question,
        answer=answer,
        route="DOCUMENT_RAG",
        context_blocks=context_blocks,
        document_citations=citations,
    )

    assert result.passed is True
    assert result.evidence_grounding >= 0.85
    assert result.faithfulness == 1.0
    assert result.unsupported_claims == []
    assert result.hallucination_risk == "low"
    assert result.citation_support == 1.0
    assert result.is_grounded is True
    # Factual confidence must be calculated strictly and reasonably high
    assert result.confidence_score >= 0.80


# ---------------------------------------------------------------------------
# 2. Unsupported Document Answer
# ---------------------------------------------------------------------------

def test_unsupported_document_answer():
    """Answer with hallucinated dosages and medications fails verification with high risk."""
    question = "What is the recommended dosage for Amoxicillin according to the report?"
    context_blocks = [
        "[DOCUMENT CONTEXT]\n"
        "(filename: antibiotics.pdf, page: 3)\n"
        "Amoxicillin dosage guideline for adult bacterial infections is 500mg every 8 hours for 7 to 10 days.\n"
        "[/DOCUMENT CONTEXT]"
    ]
    citations = [
        SourceCitation(filename="antibiotics.pdf", page_number=3, document_id="doc_1", snippet="Amoxicillin 500mg")
    ]
    # Fabricated numbers (2500mg, 40mg), fabricated medication (Prednisone), out-of-context claims
    hallucinated_answer = (
        "The report states that the patient should take 2500mg of Prednisone with high-fat meals. "
        "Additionally, Amoxicillin should be combined with 40mg of Lisinopril for maximum absorption."
    )

    result: VerificationResult = verification_service.verify(
        question=question,
        answer=hallucinated_answer,
        route="DOCUMENT_RAG",
        context_blocks=context_blocks,
        document_citations=citations,
    )

    assert result.passed is False
    assert result.evidence_grounding < 0.60
    assert len(result.unsupported_claims) >= 1
    assert result.hallucination_risk == "high"
    assert result.is_grounded is False
    assert result.repair_action == "regenerate_answer"
    # Strict score calculation caps high hallucination risk
    assert result.confidence_score <= 0.40


# ---------------------------------------------------------------------------
# 3. Web-Grounded Answer
# ---------------------------------------------------------------------------

def test_web_grounded_answer():
    """Web-grounded answer aligning with retrieved web snippets and source URLs passes verification."""
    question = "What is the latest FDA decision on once-weekly insulin?"
    context_blocks = [
        "[WEB CONTEXT]\n"
        "Title: FDA Approves Once-Weekly Basal Insulin\n"
        "Source: https://fda.gov/news/weekly-insulin-2026\n"
        "The US FDA has approved the first once-weekly basal insulin injection for adults with type 2 diabetes.\n"
        "[/WEB CONTEXT]"
    ]
    web_citations = [
        WebCitation(
            title="FDA Approves Once-Weekly Basal Insulin",
            url="https://fda.gov/news/weekly-insulin-2026",
            snippet="FDA approved once-weekly basal insulin injection.",
        )
    ]
    answer = (
        "The US FDA approved the first once-weekly basal insulin injection for adults "
        "with type 2 diabetes (source: https://fda.gov/news/weekly-insulin-2026)."
    )

    result: VerificationResult = verification_service.verify(
        question=question,
        answer=answer,
        route="WEB_SEARCH",
        context_blocks=context_blocks,
        web_citations=web_citations,
    )

    assert result.passed is True
    assert result.evidence_grounding >= 0.85
    assert result.citation_support == 1.0
    assert result.unsupported_claims == []
    assert result.hallucination_risk == "low"
    assert result.confidence_score >= 0.80


# ---------------------------------------------------------------------------
# 4. General LLM Answer
# ---------------------------------------------------------------------------

def test_general_llm_answer():
    """General knowledge answers verify question relevance and ensure no fake citations are fabricated."""
    question = "Explain how ATP synthase operates during oxidative phosphorylation."
    answer = (
        "ATP synthase is a rotary molecular motor located in the inner mitochondrial membrane. "
        "As protons flow down their electrochemical gradient from the intermembrane space into the "
        "matrix, the enzyme's rotor subunit spins, synthesizing ATP from ADP and inorganic phosphate."
    )

    result: VerificationResult = verification_service.verify(
        question=question,
        answer=answer,
        route="GENERAL_LLM",
        context_blocks=[],
    )

    assert result.passed is True
    assert result.answer_relevance >= 0.50
    assert result.citation_support == 1.0
    assert result.hallucination_risk == "low"
    assert result.confidence_score >= 0.70

    # Case 4b: General LLM fabricating document citations fails citation check
    fake_citation_answer = (
        "According to page 4 of the uploaded document, ATP synthase rotates and creates energy."
    )
    fake_result = verification_service.verify(
        question=question,
        answer=fake_citation_answer,
        route="GENERAL_LLM",
        context_blocks=[],
    )
    assert fake_result.citation_support == 0.0
    assert fake_result.passed is False


# ---------------------------------------------------------------------------
# 5. Image-Based Answer
# ---------------------------------------------------------------------------

def test_image_based_answer():
    """Vision-based answer evaluated against visual understanding context."""
    question = "What does the chest radiograph indicate?"
    visual_context = [
        "Chest radiograph demonstrates clear lung parenchyma bilaterally without consolidation, "
        "pleural effusion, or pneumothorax. Cardiothoracic silhouette is within normal limits."
    ]
    answer = (
        "The radiograph indicates clear lung fields on both sides with no signs of consolidation, "
        "pleural effusion, or pneumothorax. The heart size is within normal limits."
    )

    result: VerificationResult = verification_service.verify(
        question=question,
        answer=answer,
        route="VISION",
        context_blocks=visual_context,
    )

    assert result.passed is True
    assert result.evidence_grounding >= 0.75
    assert result.hallucination_risk == "low"
    assert result.unsupported_claims == []


# ---------------------------------------------------------------------------
# 6. Failed Verification Requiring Repair (End-to-End Orchestrator Flow)
# ---------------------------------------------------------------------------

def test_failed_verification_requiring_repair(monkeypatch):
    """Initial hallucinated answer triggers repair action; regenerated answer passes verification."""
    doc_id = "doc_repair_test"
    text = "Clinical trial NCT-001 results: Metformin lowered HbA1c by 1.2% over 24 weeks with no serious adverse events."
    metadata = {"filename": "metformin_trial.pdf", "page_number": 1, "document_id": doc_id, "text": text}

    # Mock CRAG retrieval to return valid chunk
    mock_chunk = RetrievedChunk(text=text, metadata=metadata, score=0.90)
    monkeypatch.setattr(
        retriever_service,
        "retrieve_with_crag",
        lambda *args, **kwargs: RetrievalResult(
            status="relevant",
            chunks=[mock_chunk],
            grade="relevant",
            evidence_quality="high",
            initial_retrieval_score=0.90,
            reranker_score=0.90,
        ),
    )

    # First LLM call returns hallucinated numbers; repair regeneration call returns strictly grounded answer
    call_tracker = {"count": 0}

    def mock_llm_call(prompt):
        call_tracker["count"] += 1
        resp = MagicMock()
        if call_tracker["count"] == 1:
            # Initial answer: hallucinated dosage and side effects not in evidence
            resp.content = (
                "Metformin was prescribed at 3000mg daily and caused severe renal failure in 45% of subjects."
            )
        else:
            # Repaired answer: strictly adheres to context
            resp.content = (
                "According to metformin_trial.pdf (page 1), Metformin lowered HbA1c by 1.2% over 24 weeks "
                "with no serious adverse events reported."
            )
        return resp

    monkeypatch.setattr(
        "backend.services.answer_service.get_chat_llm",
        lambda *args, **kwargs: MagicMock(invoke=mock_llm_call),
    )

    decision = RoutingDecision(
        intent="document_qa",
        sources=["document", "llm"],
        document_required=True,
        web_required=False,
    )

    resp = answer_service.answer(
        question="What were the outcomes and adverse events in the Metformin clinical trial?",
        routing_decision=decision,
        document_ids=[doc_id],
    )

    # Verifications:
    # 1. Repair loop was executed (LLM invoked twice: initial + repair)
    assert call_tracker["count"] >= 2

    # 2. Final response reflects the repaired, grounded answer
    assert "lowered HbA1c by 1.2%" in resp.answer
    assert "severe renal failure in 45%" not in resp.answer

    # 3. Final verification status is passed with repair attempts recorded
    assert resp.verification is not None
    assert resp.verification.passed is True
    assert resp.verification.repair_attempts == 1
    assert resp.verification.hallucination_risk == "low"
    assert resp.verification.evidence_grounding >= 0.80

    # 4. Infinite loop prevention: repair attempts strictly bounded
    assert resp.verification.repair_attempts <= 1
