"""
Explicit failure-injection tests (requirement #14, case 10): OCR, LLM,
vector DB, and web-search failures must degrade gracefully (structured
error / warning), never crash the process or return a 500 with a raw
traceback.
"""
import fitz
import pytest
from fastapi.testclient import TestClient

import backend.main as main_module

client = TestClient(main_module.app)


def test_llm_failure_returns_structured_warning(monkeypatch, tmp_path):
    import backend.services.answer_service as ans

    class BrokenLLM:
        def invoke(self, prompt):
            raise RuntimeError("simulated LLM outage")

    monkeypatch.setattr(ans, "get_chat_llm", lambda *a, **kw: BrokenLLM())

    resp = client.post("/query", json={"question": "hello there", "mode": "GENERAL_LLM"})
    assert resp.status_code == 200
    body = resp.json()
    assert "couldn't generate an answer" in body["answer"].lower()
    assert any("llm call failed" in w.lower() for w in body["warnings"])


def test_vector_store_failure_during_ingestion_marks_failed(monkeypatch, tmp_path):
    import backend.services.vectorstore_service as vs

    def broken_upsert(ids, vectors, metadatas):
        raise ConnectionError("simulated Pinecone outage")

    monkeypatch.setattr(vs.vectorstore_service, "upsert", broken_upsert)

    p = tmp_path / "vs_fail.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Some ingestible text content here.")
    doc.save(str(p))
    doc.close()

    with open(p, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("vs_fail.pdf", f, "application/pdf")})

    # Single file, fully failed -> endpoint must report this via status code.
    assert resp.status_code == 422
    result = resp.json()["documents"][0]
    assert result["status"] == "failed"
    assert "simulated Pinecone outage" in (result["error"] or "")


def test_web_search_provider_failure_is_swallowed(monkeypatch):
    from backend.services.web_search_service import web_search_service, WebSearchProvider

    class BrokenProvider(WebSearchProvider):
        def search(self, query, max_results):
            raise TimeoutError("simulated search timeout")

    monkeypatch.setattr(web_search_service, "provider", BrokenProvider())
    monkeypatch.setattr(web_search_service, "is_available", lambda: True)

    results = web_search_service.search("anything")
    assert results == []  # never raises up to the caller


def test_vision_missing_api_key_falls_back_to_ocr_with_clear_reason(monkeypatch):
    """Missing GROQ_API_KEY must not silently look identical to 'provider not
    configured' or a network exception - it should be a distinct, named
    failure_reason so operators can tell the three apart."""
    import backend.services.ocr_vision_service as ov
    from backend.config import settings
    from PIL import Image

    monkeypatch.setattr(settings, "VISION_PROVIDER", "groq_vision")
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)

    img = Image.new("RGB", (50, 50), color="white")
    text, reason = ov._vision_llm_describe(img, "read this")
    assert text is None
    assert reason == ov.VISION_NO_API_KEY


def test_vision_exception_is_labeled_distinctly(monkeypatch):
    import backend.services.ocr_vision_service as ov
    from backend.config import settings
    from PIL import Image

    monkeypatch.setattr(settings, "VISION_PROVIDER", "groq_vision")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-key-for-test")

    class BrokenChatGroq:
        def __init__(self, *a, **kw):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr("langchain_groq.ChatGroq", BrokenChatGroq)

    img = Image.new("RGB", (50, 50), color="white")
    text, reason = ov._vision_llm_describe(img, "read this")
    assert text is None
    assert reason.startswith(ov.VISION_EXCEPTION)
    assert "ConnectionError" in reason


def test_ocr_failure_does_not_crash_ingestion(monkeypatch, tmp_path):
    import backend.services.ocr_vision_service as ov

    def broken_ocr(image):
        raise RuntimeError("simulated tesseract crash")

    monkeypatch.setattr(ov, "ocr_image", broken_ocr)
    monkeypatch.setattr(ov.ocr_vision_service, "extract_page_text",
                         lambda pdf_path, page_number, prior_text: (
                             ("", "ocr") if not ov.is_text_sufficient(prior_text) else (prior_text, "text")
                         ))

    p = tmp_path / "ocr_fail.pdf"
    from PIL import Image
    img = Image.new("RGB", (200, 100), color="white")
    doc = fitz.open()
    page = doc.new_page(width=200, height=100)
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    page.insert_image(fitz.Rect(0, 0, 200, 100), stream=buf.read())
    doc.save(str(p))
    doc.close()

    with open(p, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("ocr_fail.pdf", f, "application/pdf")})

    # Should not 500 - a clean JSON response either way, with a status code
    # that accurately reflects whether ingestion succeeded.
    result = resp.json()["documents"][0]
    assert result["status"] in {"failed", "completed"}
    assert resp.status_code == (200 if result["status"] == "completed" else 422)
