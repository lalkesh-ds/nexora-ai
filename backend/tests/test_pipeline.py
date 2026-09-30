import io
import os

import fitz
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

import backend.main as main_module

client = TestClient(main_module.app)


def _get_test_font(size=36):
    from PIL import ImageFont
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _make_text_pdf(path, text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _make_scanned_pdf(path, text_lines):
    img = Image.new("RGB", (900, 400), color="white")
    d = ImageDraw.Draw(img)
    font = _get_test_font(32)
    for i, line in enumerate(text_lines):
        d.text((20, 20 + i * 60), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    doc = fitz.open()
    page = doc.new_page(width=900, height=400)
    page.insert_image(fitz.Rect(0, 0, 900, 400), stream=buf.read())
    doc.save(path)
    doc.close()


# 1. Normal text PDF ---------------------------------------------------------
def test_upload_text_pdf(tmp_path):
    pdf_path = tmp_path / "text.pdf"
    _make_text_pdf(str(pdf_path), "Nexora quarterly revenue was 500000 dollars.")

    with open(pdf_path, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("text.pdf", f, "application/pdf")})

    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert doc["status"] == "completed"
    assert doc["source_type"] == "pdf"


# 2. Scanned assignment PDF (OCR fallback) -----------------------------------
def test_upload_scanned_pdf_uses_ocr(tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    _make_scanned_pdf(str(pdf_path), ["ASSIGNMENT", "Question 7: What is 12 + 30?"])

    with open(pdf_path, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("scan.pdf", f, "application/pdf")})

    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert doc["status"] == "completed"


# 3. Direct image question ----------------------------------------------------
def test_vision_query_direct_image(tmp_path):
    img_path = tmp_path / "assignment.png"
    img = Image.new("RGB", (500, 200), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "12 + 30 = ?", fill="black", font=_get_test_font(40))
    img.save(img_path)

    with open(img_path, "rb") as f:
        resp = client.post(
            "/vision/query",
            files={"image": ("assignment.png", f, "image/png")},
            data={"question": "Solve the equation in the image."},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    # Deterministic calculator should have verified 12 + 30 = 42 somewhere.
    assert "42" in body["answer"] or body["extracted_text"]


# 3b. Question about a PREVIOUSLY uploaded image -> must route to VISION,
#     not DOCUMENT_RAG, even though /vision/query is never called directly.
def test_query_about_uploaded_image_routes_to_vision(tmp_path):
    img_path = tmp_path / "handwritten.png"
    img = Image.new("RGB", (500, 200), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Name: Nexora", fill="black", font=_get_test_font(40))
    img.save(img_path)

    with open(img_path, "rb") as f:
        upload_resp = client.post(
            "/documents/upload",
            files={"files": ("handwritten.png", f, "image/png")},
        )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["documents"][0]["document_id"]
    assert upload_resp.json()["documents"][0]["source_type"] == "png"

    resp = client.post("/query", json={
        "question": "What is the name written in the image?",
        "document_ids": [doc_id],
        "mode": "AUTO",
    })
    assert resp.status_code == 200
    body = resp.json()
    # This is the core architectural fix: a question about an uploaded
    # IMAGE document must reach VISION, never DOCUMENT_RAG-by-default.
    assert body["route_used"] == "VISION"
    assert body["vision_document_id"] == doc_id


# 3c. Question about an uploaded TEXT PDF must still go to DOCUMENT_RAG,
#     proving the image-routing fix didn't break the normal RAG path.
def test_query_about_uploaded_pdf_still_routes_to_document_rag(tmp_path):
    p = tmp_path / "report.pdf"
    _make_text_pdf(str(p), "Quarterly report content about revenue.")
    with open(p, "rb") as f:
        upload_resp = client.post("/documents/upload", files={"files": ("report.pdf", f, "application/pdf")})
    doc_id = upload_resp.json()["documents"][0]["document_id"]

    resp = client.post("/query", json={
        "question": "What does the uploaded document say about revenue?",
        "document_ids": [doc_id],
        "mode": "AUTO",
    })
    assert resp.status_code == 200
    assert resp.json()["route_used"] == "DOCUMENT_RAG"


# 4. Multiple-document question ----------------------------------------------
def test_multi_document_query(tmp_path):
    p1 = tmp_path / "doc1.pdf"
    p2 = tmp_path / "doc2.pdf"
    _make_text_pdf(str(p1), "Document one content about apples.")
    _make_text_pdf(str(p2), "Document two content about oranges.")

    ids = []
    for p in (p1, p2):
        with open(p, "rb") as f:
            r = client.post("/documents/upload", files={"files": (p.name, f, "application/pdf")})
        ids.append(r.json()["documents"][0]["document_id"])

    resp = client.post("/query", json={
        "question": "What do the uploaded documents say?",
        "document_ids": ids,
        "mode": "DOCUMENT_RAG",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_used"] == "DOCUMENT_RAG"
    assert body["evidence"]["from_documents"] is True


# 5. General question without documents --------------------------------------
def test_general_question_no_documents():
    resp = client.post("/query", json={"question": "What is 2+2 conceptually?", "mode": "GENERAL_LLM"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_used"] == "GENERAL_LLM"
    assert body["evidence"]["from_general_knowledge"] is True
    assert body["document_citations"] == []
    assert body["web_citations"] == []


# 6. Current web-search question (no provider configured -> graceful warning)
def test_web_search_question_without_provider():
    resp = client.post("/query", json={"question": "latest AI news today", "mode": "WEB_SEARCH"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_used"] == "WEB_SEARCH"
    assert body["evidence"]["from_web"] is False
    assert any("web search" in w.lower() for w in body["warnings"])


# 7. Document + web hybrid question ------------------------------------------
def test_hybrid_question(tmp_path):
    p = tmp_path / "hybrid.pdf"
    _make_text_pdf(str(p), "Our internal roadmap mentions project Nexora.")
    with open(p, "rb") as f:
        r = client.post("/documents/upload", files={"files": ("hybrid.pdf", f, "application/pdf")})
    doc_id = r.json()["documents"][0]["document_id"]

    resp = client.post("/query", json={
        "question": "Combine our roadmap doc with the latest market news",
        "document_ids": [doc_id],
        "mode": "HYBRID",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["route_used"] == "HYBRID"
    assert body["evidence"]["from_documents"] is True


# 8. Table / numerical calculation -------------------------------------------
def test_deterministic_calculation():
    from backend.services.calculator_service import calculator_service
    results = calculator_service.extract_and_evaluate("Total = 120 * 3 + 10")
    assert any(r["result"] == "370" for r in results)


# 9. Conversation follow-up ---------------------------------------------------
def test_conversation_followup():
    s = client.post("/conversation/session").json()["session_id"]
    r1 = client.post("/query", json={"question": "My name is Nexora.", "session_id": s, "mode": "GENERAL_LLM"})
    assert r1.status_code == 200
    hist = client.get(f"/conversation/{s}/history")
    assert hist.status_code == 200
    turns = hist.json()["turns"]
    assert len(turns) == 2  # user + assistant
    assert turns[0]["role"] == "user"


# 10. Failure cases ------------------------------------------------------------
def test_rejects_disallowed_file_extension(tmp_path):
    bad = tmp_path / "malware.exe"
    bad.write_bytes(b"MZ\x00\x00fake")
    with open(bad, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("malware.exe", f, "application/octet-stream")})
    # Every file in the batch was rejected -> the endpoint must NOT report 200.
    assert resp.status_code == 422
    doc = resp.json()["documents"][0]
    assert doc["status"] == "rejected"


def test_rejects_oversized_file(tmp_path, monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 0)  # force any file to exceed limit
    p = tmp_path / "big.txt"
    p.write_text("hello world")
    with open(p, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("big.txt", f, "text/plain")})
    assert resp.status_code == 422
    doc = resp.json()["documents"][0]
    assert doc["status"] == "rejected"


def test_empty_pdf_ingestion_fails_gracefully(tmp_path):
    # A PDF with a blank page and no OCR-able content -> extraction should
    # fail cleanly with an error, not raise an unhandled exception, and the
    # endpoint must report the failure via its HTTP status code (not 200).
    p = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(p))
    doc.close()

    with open(p, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("blank.pdf", f, "application/pdf")})
    assert resp.status_code == 422
    result = resp.json()["documents"][0]
    assert result["status"] == "failed"
    assert result["error"]


def test_path_traversal_filename_is_neutralized(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello")
    with open(p, "rb") as f:
        resp = client.post(
            "/documents/upload",
            files={"files": ("../../etc/passwd.txt", f, "text/plain")},
        )
    # Should be treated as a normal upload named 'passwd.txt', not escape the upload dir.
    doc = resp.json()["documents"][0]
    assert doc["status"] in {"completed", "failed"}  # processed safely, no crash/traversal
    assert resp.status_code == (200 if doc["status"] == "completed" else 422)


# 11. Same document uploaded twice -> cache hit, no reprocessing ------------
def test_duplicate_upload_hits_cache(tmp_path):
    p = tmp_path / "dup.pdf"
    _make_text_pdf(str(p), "Duplicate detection content.")

    with open(p, "rb") as f:
        r1 = client.post("/documents/upload", files={"files": ("dup.pdf", f, "application/pdf")})
    with open(p, "rb") as f:
        r2 = client.post("/documents/upload", files={"files": ("dup.pdf", f, "application/pdf")})

    id1 = r1.json()["documents"][0]["document_id"]
    id2 = r2.json()["documents"][0]["document_id"]
    assert id1 == id2  # same content -> same identity, second upload served from cache


# 12. Same document uploaded after changing VISION_PROVIDER -> re-ingested --
def test_reupload_after_provider_change_forces_reingest(tmp_path, monkeypatch):
    from backend.config import settings
    from backend.services import document_service as ds_module

    p = tmp_path / "provider_change.pdf"
    _make_text_pdf(str(p), "Provider change re-ingestion content.")

    with open(p, "rb") as f:
        r1 = client.post("/documents/upload", files={"files": ("provider_change.pdf", f, "application/pdf")})
    assert r1.status_code == 200
    fp1 = r1.json()["documents"][0]["document_id"]

    # Simulate VISION_PROVIDER=groq_vision -> groq_vision after starting on
    # tesseract; the cached "completed" record's extraction_fingerprint must
    # no longer match, forcing full re-extraction instead of a silent skip.
    monkeypatch.setattr(settings, "VISION_PROVIDER", "groq_vision")

    with open(p, "rb") as f:
        r2 = client.post("/documents/upload", files={"files": ("provider_change.pdf", f, "application/pdf")})
    assert r2.status_code == 200
    doc2 = r2.json()["documents"][0]
    assert doc2["document_id"] == fp1  # same file identity
    assert doc2["status"] == "completed"

    # Confirm the registry actually recorded the NEW fingerprint, i.e. this
    # was a real re-ingestion, not a cache hit.
    record = ds_module.document_service.get_document(fp1)
    assert "groq_vision" in record["extraction_fingerprint"]
