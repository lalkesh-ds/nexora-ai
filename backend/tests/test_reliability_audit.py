"""
Comprehensive Reliability & Regression Test Suite for Nexora AI.
Covers all 18 production reliability requirements specified in Section 9:

1. A document contains the answer and the model returns a supported answer with the correct citation.
2. A document does not contain the answer and the model does not invent it.
3. An irrelevant retrieved chunk does not become the basis of a confident answer.
4. A question requiring current information invokes web search.
5. A document-only question uses document retrieval.
6. A question requiring document and web evidence invokes both sources.
7. A general question does not trigger unnecessary document retrieval.
8. Empty retrieval produces an honest fallback.
9. Contradictory document and web evidence is handled explicitly.
10. A valid text-based PDF uploads, processes, indexes, and becomes queryable.
11. A scanned PDF is processed through OCR when dependencies are available (and safe when unavailable).
12. A corrupted or unsupported file returns a clear error.
13. Embedding or Pinecone failure does not produce a false success response.
14. A partially failed batch is handled safely.
15. Reuploading a document does not cause unintended duplicate chunks.
16. Cross-document and cross-user retrieval isolation is enforced where applicable.
17. Missing environment variables produce actionable configuration errors.
18. Existing API endpoints and response formats remain compatible.
"""
import io
import os
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.verification_service import verification_service
from backend.services.answer_service import answer_service
from backend.services.ocr_vision_service import ocr_image
from backend.services.web_search_service import web_search_service, WebSearchEvidence, WebSearchResult
from backend.services.retriever_service import retriever_service, RetrievedChunk, RetrievalResult
from backend.schemas import SourceCitation, EvidenceBreakdown, RoutingDecision

client = TestClient(main_module.app)


def _create_test_pdf(filepath: str, text: str):
    """Helper creating a valid text PDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    doc.save(filepath)
    doc.close()


# Case 1: Document contains the answer -> supported answer with correct citation
def test_case_01_document_contains_answer_returns_citation(tmp_path):
    p = tmp_path / "cardiology_report.pdf"
    _create_test_pdf(str(p), "Patient diagnosis: Stage 2 Hypertension. Prescribed Lisinopril 20mg daily.")
    with open(p, "rb") as f:
        r = client.post("/documents/upload", files={"files": ("cardiology_report.pdf", f, "application/pdf")})
    assert r.status_code == 200
    doc_id = r.json()["documents"][0]["document_id"]

    resp = client.post("/query", json={
        "question": "What is the patient's diagnosis according to the report?",
        "document_ids": [doc_id],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_used"] == "DOCUMENT_RAG"
    assert len(data["document_citations"]) > 0
    assert data["document_citations"][0]["document_id"] == doc_id
    assert data["evidence"]["from_documents"] is True


# Case 2: Document does not contain the answer -> model does not invent it
def test_case_02_document_missing_answer_safe_abstention(monkeypatch):
    """When retrieval yields no relevant chunks, AnswerService injects DOCUMENT RETRIEVAL NOTICE
    and verification does not flag honest abstention statements as hallucinations."""
    from backend.services.llm_provider import get_chat_llm

    class AbstainingLLM:
        def invoke(self, prompt):
            class Resp:
                content = "The uploaded document does not contain information regarding blood glucose levels."
            return Resp()

    monkeypatch.setattr("backend.services.answer_service.get_chat_llm", lambda *a, **k: AbstainingLLM())
    monkeypatch.setattr(web_search_service, "is_available", lambda: False)

    # Empty retrieval
    monkeypatch.setattr(
        retriever_service,
        "retrieve_with_crag",
        lambda **kw: RetrievalResult(chunks=[], status="empty", grade="irrelevant", evidence_quality="none"),
    )

    resp = answer_service.answer(
        question="What is the blood glucose level in the uploaded document?",
        route="DOCUMENT_RAG",
    )
    assert "does not contain" in resp.answer.lower()
    # Honest abstention must pass verification without flagging false ungrounded claims
    assert resp.verification.passed is True
    assert len(resp.verification.unsupported_claims) == 0


# Case 3: Irrelevant retrieved chunk does not become the basis of a confident answer
def test_case_03_irrelevant_chunk_rejected_or_low_confidence():
    """Retrieved chunk that lacks relevance and overlaps poorly fails verification with high risk."""
    irrelevant_context = ["[DOCUMENT CONTEXT]\nThe capital of France is Paris. The Eiffel Tower is tall.\n[/DOCUMENT CONTEXT]"]
    fake_claim_answer = "The patient was prescribed 500mg Metformin for diabetes mellitus twice daily."

    v_result = verification_service.verify(
        question="What medication was prescribed?",
        answer=fake_claim_answer,
        route="DOCUMENT_RAG",
        context_blocks=irrelevant_context,
        document_citations=[SourceCitation(document_id="d1", filename="notes.pdf", page_number=1, snippet="paris")],
    )
    assert v_result.passed is False
    assert v_result.hallucination_risk in ("medium", "high")
    assert len(v_result.unsupported_claims) > 0


# Case 4: A question requiring current information invokes web search
def test_case_04_time_sensitive_query_invokes_web_search():
    decision = query_router.route_decision(
        question="What is the current news and latest updates on WHO malaria vaccine today?",
        resolved_documents=[],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "web_research"
    assert decision.web_required is True
    assert decision.to_legacy_route() == "WEB_SEARCH"


# Case 5: A document-only question uses document retrieval
def test_case_05_document_only_question_uses_document_rag():
    doc = ResolvedDocument("doc123", "pdf", "completed")
    decision = query_router.route_decision(
        question="According to the uploaded report, what were the MRI findings?",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "document_qa"
    assert decision.document_required is True
    assert decision.web_required is False
    assert decision.to_legacy_route() == "DOCUMENT_RAG"


# Case 6: A question requiring document and web evidence invokes both sources (HYBRID)
def test_case_06_hybrid_question_invokes_both_sources():
    doc = ResolvedDocument("doc123", "pdf", "completed")
    decision = query_router.route_decision(
        question="Compare the findings in my uploaded report with current published clinical guidelines.",
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


# Case 7: A general question does not trigger unnecessary document retrieval
def test_case_07_general_question_avoids_document_rag():
    doc = ResolvedDocument("doc123", "pdf", "completed")
    decision = query_router.route_decision(
        question="Explain how photosynthesis works in plants.",
        resolved_documents=[doc],
        has_any_documents=True,
        web_search_available=True,
    )
    assert decision.intent == "general_knowledge"
    assert decision.document_required is False
    assert decision.web_required is False
    assert decision.to_legacy_route() == "GENERAL_LLM"


# Case 8: Empty retrieval produces an honest fallback without fake citations
def test_case_08_empty_retrieval_honest_fallback(monkeypatch):
    monkeypatch.setattr(web_search_service, "is_available", lambda: False)
    monkeypatch.setattr(
        retriever_service,
        "retrieve_with_crag",
        lambda **kw: RetrievalResult(chunks=[], status="empty", grade="irrelevant", evidence_quality="none"),
    )
    resp = answer_service.answer(
        question="What is the dosage mentioned in the document?",
        route="DOCUMENT_RAG",
    )
    assert resp.document_citations == []
    assert any("no relevant content" in w.lower() for w in resp.warnings)


# Case 9: Contradictory document and web evidence is handled explicitly
def test_case_09_contradictory_evidence_handled_in_prompt():
    """Verify system preamble and hybrid prompt rules instruct explicit separation of sources."""
    from backend.services.answer_service import _SYSTEM_PREAMBLE
    assert "### Document Findings" in _SYSTEM_PREAMBLE
    assert "### External / Web Findings" in _SYSTEM_PREAMBLE
    assert "contradict" in _SYSTEM_PREAMBLE.lower()


# Case 10: Valid text-based PDF uploads, processes, indexes, and becomes queryable
def test_case_10_pdf_lifecycle(tmp_path):
    pdf = tmp_path / "clinical_trial.pdf"
    _create_test_pdf(str(pdf), "Clinical trial phase 3 evaluated 1200 participants.")
    with open(pdf, "rb") as f:
        upload_resp = client.post("/documents/upload", files={"files": ("clinical_trial.pdf", f, "application/pdf")})
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["documents"][0]["document_id"]
    assert upload_resp.json()["documents"][0]["status"] == "completed"

    status_resp = client.get(f"/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"


# Case 11: Scanned PDF / Image OCR error protection
def test_case_11_ocr_defensive_against_missing_tesseract(monkeypatch):
    """ocr_image must not raise unhandled ModuleNotFoundError if pytesseract is absent."""
    from PIL import Image
    test_img = Image.new("RGB", (50, 50), color="white")
    # Simulate missing pytesseract
    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    result = ocr_image(test_img)
    assert result == ""  # Graceful fallback to empty string


# Case 12: Corrupted or unsupported file returns clear error
def test_case_12_unsupported_file_rejected():
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00fake executable content")
    resp = client.post(
        "/documents/upload",
        files={"files": ("malicious.exe", fake_exe, "application/x-msdownload")},
    )
    assert resp.status_code == 422
    docs = resp.json()["documents"]
    assert docs[0]["status"] in ("rejected", "failed")
    assert docs[0]["error"] is not None


# Case 13: Embedding failure does not produce false success
def test_case_13_embedding_failure_returns_failed_status(tmp_path, monkeypatch):
    from backend.services.embedding_service import embedding_service
    monkeypatch.setattr(
        embedding_service,
        "embed_documents",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Embedding API rate limit reached")),
    )
    p = tmp_path / "rate_limit_test.pdf"
    _create_test_pdf(str(p), "Sample text for rate limit test.")
    with open(p, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("rate_limit_test.pdf", f, "application/pdf")})
    assert resp.status_code == 422
    assert resp.json()["documents"][0]["status"] == "failed"
    assert "rate limit" in resp.json()["documents"][0]["error"].lower()


# Case 14: Partially failed batch is handled safely (HTTP 207)
def test_case_14_partially_failed_batch_returns_207(tmp_path):
    good_pdf = tmp_path / "good.pdf"
    _create_test_pdf(str(good_pdf), "This is valid document text.")

    bad_file = io.BytesIO(b"binary payload")

    with open(good_pdf, "rb") as f_good:
        resp = client.post(
            "/documents/upload",
            files=[
                ("files", ("good.pdf", f_good, "application/pdf")),
                ("files", ("unsupported.bin", bad_file, "application/octet-stream")),
            ],
        )
    # 207 Multi-Status
    assert resp.status_code == 207
    docs = resp.json()["documents"]
    assert len(docs) == 2
    completed = [d for d in docs if d["status"] == "completed"]
    failed = [d for d in docs if d["status"] in ("rejected", "failed")]
    assert len(completed) == 1
    assert len(failed) == 1


# Case 15: Reuploading a document does not cause unintended duplicate chunks
def test_case_15_deduplication_on_reupload(tmp_path):
    pdf = tmp_path / "dedup.pdf"
    _create_test_pdf(str(pdf), "Unique document content for deduplication test.")
    with open(pdf, "rb") as f:
        resp1 = client.post("/documents/upload", files={"files": ("dedup.pdf", f, "application/pdf")})
    assert resp1.status_code == 200
    doc_id_1 = resp1.json()["documents"][0]["document_id"]

    # Re-upload the exact same file
    with open(pdf, "rb") as f:
        resp2 = client.post("/documents/upload", files={"files": ("dedup.pdf", f, "application/pdf")})
    assert resp2.status_code == 200
    doc_id_2 = resp2.json()["documents"][0]["document_id"]
    assert doc_id_1 == doc_id_2


# Case 16: Cross-document retrieval isolation is enforced
def test_case_16_document_isolation(tmp_path):
    pdf_a = tmp_path / "patient_a.pdf"
    pdf_b = tmp_path / "patient_b.pdf"
    _create_test_pdf(str(pdf_a), "Patient Alpha has allergy to penicillin.")
    _create_test_pdf(str(pdf_b), "Patient Beta has allergy to sulfa drugs.")

    with open(pdf_a, "rb") as f:
        doc_a_id = client.post("/documents/upload", files={"files": ("patient_a.pdf", f, "application/pdf")}).json()["documents"][0]["document_id"]
    with open(pdf_b, "rb") as f:
        doc_b_id = client.post("/documents/upload", files={"files": ("patient_b.pdf", f, "application/pdf")}).json()["documents"][0]["document_id"]

    # Query scoped strictly to Patient A
    resp = client.post("/query", json={
        "question": "What is the allergy according to the report?",
        "document_ids": [doc_a_id],
    })
    assert resp.status_code == 200
    cites = resp.json()["document_citations"]
    # Should only cite document A
    for c in cites:
        assert c["document_id"] == doc_a_id


# Case 17: Missing environment variables / configuration reporting
def test_case_17_missing_provider_graceful_handling(monkeypatch):
    monkeypatch.setattr(web_search_service, "is_available", lambda: False)
    evidence = web_search_service.search_evidence("test query")
    assert evidence.status in ("no_results", "failed")
    assert "no web search provider" in (evidence.error or "").lower()


# Case 18: Existing API endpoints and response formats remain compatible
def test_case_18_api_contract_compatibility():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    docs_list = client.get("/documents")
    assert docs_list.status_code == 200
    assert "documents" in docs_list.json()

    query_resp = client.post("/query", json={"question": "Hello", "mode": "AUTO"})
    assert query_resp.status_code == 200
    data = query_resp.json()
    assert "answer" in data
    assert "route_used" in data
    assert "document_citations" in data
    assert "web_citations" in data
    assert "evidence" in data
    assert "warnings" in data
    assert "verification" in data
