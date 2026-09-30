"""
Tests for Phase 2: Multimodal Input Pipeline.

Validates handling of:
1. Human photograph (zero OCR text, reaches vision model / visual understanding, does NOT fail)
2. Image containing text (document-like image, OCR + vision)
3. Scanned PDF page (rasterized -> OCR / vision)
4. Normal text PDF (digital text extraction)
5. Screenshot / diagram (diagram visual understanding)
"""
import io
import fitz
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.services.multimodal_service import multimodal_service, InputType
from backend.services.ocr_vision_service import ocr_vision_service

client = TestClient(main_module.app)


def _get_test_font(size=32):
    from PIL import ImageFont
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 1. Human Photograph (Zero OCR Text)
# ---------------------------------------------------------------------------

def test_human_photograph_does_not_fail_and_reaches_vision(tmp_path, monkeypatch):
    """CRITICAL BUG FIX:
    A normal photograph with ZERO OCR text must NOT fail with 'no content'.
    It must produce visual understanding and reach the vision pipeline.
    """
    # Create a photo-like image with shapes and colors, but ZERO text
    photo_path = tmp_path / "doctor_photo.jpg"
    img = Image.new("RGB", (300, 300), color=(120, 180, 220))
    d = ImageDraw.Draw(img)
    # Draw simple shapes representing a human subject / background
    d.ellipse((100, 50, 200, 150), fill=(240, 200, 160))  # head
    d.rectangle((80, 150, 220, 300), fill=(50, 80, 150))   # coat
    img.save(photo_path)

    # Mock vision understanding to return a description of the photo
    def mock_understand(image, instruction=None):
        return ("A portrait photograph of a medical professional wearing a blue coat in a clinic.", None)

    monkeypatch.setattr(ocr_vision_service, "understand_image", mock_understand)

    # Process via multimodal_service
    pages = multimodal_service.process_image(str(photo_path))
    assert len(pages) == 1
    assert pages[0].input_type == InputType.VISUAL_IMAGE.value
    assert pages[0].has_visuals is True
    assert "portrait photograph" in pages[0].text.lower()
    assert pages[0].source_type == "visual_understanding"

    # Ingest through the real API endpoint /documents/upload
    with open(photo_path, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("doctor_photo.jpg", f, "image/jpeg")})

    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert doc["status"] == "completed"
    assert doc["error"] is None


# ---------------------------------------------------------------------------
# 2. Image Containing Text (Document Image / Assignment)
# ---------------------------------------------------------------------------

def test_image_containing_text(tmp_path):
    """An image containing text should be classified as document_image with OCR/text extraction."""
    img_path = tmp_path / "receipt.png"
    img = Image.new("RGB", (600, 200), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Medical Receipt: Total Amount 350 USD", fill="black", font=_get_test_font(30))
    img.save(img_path)

    pages = multimodal_service.process_image(str(img_path))
    assert len(pages) == 1
    # Either document_image with OCR, or visual understanding fallback
    assert pages[0].has_text is True or pages[0].has_visuals is True
    assert pages[0].text.strip() != ""

    with open(img_path, "rb") as f:
        resp = client.post("/documents/upload", files={"files": ("receipt.png", f, "image/png")})

    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert doc["status"] == "completed"


# ---------------------------------------------------------------------------
# 3. Scanned PDF Page
# ---------------------------------------------------------------------------

def test_scanned_pdf_page(tmp_path):
    """A scanned PDF (rasterized page with no digital text) renders and uses OCR/vision."""
    pdf_path = tmp_path / "scanned_doc.pdf"

    # Create an image containing text
    img = Image.new("RGB", (800, 300), color="white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Patient Diagnosis: Hypertension stage 1", fill="black", font=_get_test_font(32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Insert image into PDF without native text
    doc = fitz.open()
    page = doc.new_page(width=800, height=300)
    page.insert_image(fitz.Rect(0, 0, 800, 300), stream=buf.read())
    doc.save(str(pdf_path))
    doc.close()

    pages = multimodal_service.process_pdf(str(pdf_path))
    assert len(pages) == 1
    assert pages[0].input_type == InputType.SCANNED_PDF.value
    assert pages[0].has_visuals is True


# ---------------------------------------------------------------------------
# 4. Normal Text PDF
# ---------------------------------------------------------------------------

def test_normal_text_pdf(tmp_path):
    """A native text PDF extracts digital text directly without rasterization."""
    pdf_path = tmp_path / "native.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a digital medical report with native searchable text.")
    doc.save(str(pdf_path))
    doc.close()

    pages = multimodal_service.process_pdf(str(pdf_path))
    assert len(pages) == 1
    assert pages[0].input_type == InputType.TEXT_PDF.value
    assert pages[0].source_type == "text"
    assert "digital medical report" in pages[0].text


# ---------------------------------------------------------------------------
# 5. Screenshot / Architecture Diagram
# ---------------------------------------------------------------------------

def test_diagram_screenshot_understanding(tmp_path, monkeypatch):
    """A diagram or system architecture screenshot produces visual understanding."""
    diagram_path = tmp_path / "architecture.png"
    img = Image.new("RGB", (500, 300), color=(245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle((50, 50, 150, 120), fill=(200, 220, 255), outline="black")
    d.rectangle((250, 50, 350, 120), fill=(220, 255, 200), outline="black")
    d.line((150, 85, 250, 85), fill="black", width=3)
    img.save(diagram_path)

    def mock_understand(image, instruction=None):
        return ("An architecture flow diagram showing two connected system blocks.", None)

    monkeypatch.setattr(ocr_vision_service, "understand_image", mock_understand)

    pages = multimodal_service.process_image(str(diagram_path))
    assert len(pages) == 1
    assert "architecture flow diagram" in pages[0].text.lower()
    assert pages[0].has_visuals is True
