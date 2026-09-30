"""
OCRVisionService

Responsible for turning "pixels" (scanned PDF pages, photos, screenshots)
into usable text/answers when plain text extraction fails or is absent.

Two paths:
  1. OCR path (default, offline, no API key): pytesseract on a rasterized
     page/image. Good enough for printed text, tables-as-text, etc.
  2. Vision-LLM path (VISION_PROVIDER=groq_vision|gemini_vision): sends the
     image directly to a multimodal model, which handles handwriting,
     diagrams and math far better than OCR. Falls back to the OCR path if
     the call fails, so a missing/invalid API key never hard-breaks vision
     questions.

Every vision attempt logs a single structured [VISION] line so callers
(and operators) can tell, after the fact, whether the vision LLM was
actually invoked and why it did or didn't produce usable output -
"using OCR/vision" in an upstream log is NOT proof the vision LLM ran.
"""
import base64
import io
from typing import Optional, Tuple

from PIL import Image

from backend.config import settings
from backend.logger import logger

# Reasons _vision_llm_describe can fail with. Kept as constants so callers
# and tests can branch on them instead of parsing log strings.
VISION_NOT_CONFIGURED = "not_configured"       # VISION_PROVIDER == "tesseract"/unknown
VISION_NO_API_KEY = "no_api_key"               # provider selected but key missing
VISION_EMPTY_RESPONSE = "empty_response"       # call succeeded, model returned nothing useful
VISION_EXCEPTION = "exception"                 # import/network/API error (see message)


def is_text_sufficient(text: str) -> bool:
    return bool(text) and len(text.strip()) >= settings.OCR_MIN_TEXT_CHARS_PER_PAGE


def render_pdf_page_to_image(pdf_path: str, page_number: int, zoom: float = 2.0) -> Image.Image:
    """page_number is 0-indexed."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_number]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")
    finally:
        doc.close()


def ocr_image(image: Image.Image) -> str:
    import pytesseract

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return ""


def _image_to_data_uri(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _log_vision(provider: str, model: str, success: bool, failure_reason: Optional[str]):
    logger.info(
        f"[VISION] provider={provider} model={model} success={str(success).lower()} "
        f"failure_reason={failure_reason or 'none'}"
    )


def _extract_content_text(content) -> str:
    """Extract string text from LLM response content, handling string or list of content blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text", ""))
            else:
                parts.append(str(p))
        return "".join(parts).strip()
    return str(content or "").strip()


def _vision_llm_describe(image: Image.Image, instruction: str) -> Tuple[Optional[str], Optional[str]]:
    """Ask a multimodal LLM to read/answer from an image.

    Returns (text, failure_reason). text is None iff failure_reason is set.
    Always emits exactly one [VISION] log line describing what happened -
    never logs the API key itself.
    """
    provider = settings.VISION_PROVIDER

    if provider not in {"groq_vision", "gemini_vision"}:
        return None, VISION_NOT_CONFIGURED

    # Groq current vision model: qwen/qwen3.8-27b
    # Gemini current vision model: configurable via GEMINI_VISION_MODEL (defaults to gemini-3.5-flash)
    configured_gemini_model = getattr(settings, "GEMINI_VISION_MODEL", None) or "gemini-3.5-flash"
    model = "qwen/qwen3.8-27b" if provider == "groq_vision" else configured_gemini_model

    try:
        if provider == "groq_vision":
            from langchain_groq import ChatGroq
            from langchain_core.messages import HumanMessage

            if not settings.GROQ_API_KEY:
                _log_vision(provider, model, False, VISION_NO_API_KEY)
                return None, VISION_NO_API_KEY

            llm = ChatGroq(groq_api_key=settings.GROQ_API_KEY, model_name=model)
            msg = HumanMessage(content=[
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": _image_to_data_uri(image)}},
            ])
            resp = llm.invoke([msg])
            text = _extract_content_text(resp.content) if resp else ""

        else:  # gemini_vision
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            if not settings.GOOGLE_API_KEY:
                _log_vision(provider, model, False, VISION_NO_API_KEY)
                return None, VISION_NO_API_KEY

            text = ""
            gemini_candidates = [
                model,
                "gemini-3.5-flash",
                "gemini-3.8-flash",
                "gemini-flash-latest",
                "gemini-2.5-flash",
                "gemini-1.5-flash",
            ]
            seen_cands = set()
            deduped_candidates = [c for c in gemini_candidates if not (c in seen_cands or seen_cands.add(c))]
            last_err = None
            for cand in deduped_candidates:
                try:
                    llm = ChatGoogleGenerativeAI(model=cand, google_api_key=settings.GOOGLE_API_KEY)
                    msg = HumanMessage(content=[
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": _image_to_data_uri(image)},
                    ])
                    resp = llm.invoke([msg])
                    text = _extract_content_text(resp.content) if resp else ""
                    model = cand
                    break
                except Exception as ex:
                    last_err = ex
                    continue

            if not text and last_err and not text:
                raise last_err

        if not text:
            _log_vision(provider, model, False, VISION_EMPTY_RESPONSE)
            return None, VISION_EMPTY_RESPONSE

        _log_vision(provider, model, True, None)
        return text, None

    except Exception as e:
        reason = f"{VISION_EXCEPTION}:{type(e).__name__}"
        logger.warning(f"Vision-LLM provider '{provider}' raised {type(e).__name__}: {e}")
        _log_vision(provider, model, False, reason)
        return None, reason


class OCRVisionService:
    def extract_page_text(self, pdf_path: str, page_number: int, prior_text: str) -> Tuple[str, str]:
        """Returns (text, source_type). source_type is 'text' if prior_text was
        already good, otherwise 'ocr' or 'vision'. Never silently discards a
        page: if both vision and OCR fail, returns ("", "none") so the caller
        can distinguish "no content" from "content exists"."""
        if is_text_sufficient(prior_text):
            return prior_text, "text"

        image = render_pdf_page_to_image(pdf_path, page_number)

        described, reason = _vision_llm_describe(
            image,
            "Transcribe all readable text, tables and diagram labels from this "
            "document page. Preserve structure. Output only the content, no commentary.",
        )
        if described:
            logger.info(f"[INGEST] page={page_number + 1} extraction_method=vision characters={len(described)}")
            return described, "vision"

        ocr_text = ocr_image(image)
        method = "ocr" if ocr_text else "none"
        logger.info(
            f"[INGEST] page={page_number + 1} extraction_method={method} "
            f"characters={len(ocr_text)} vision_reason={reason}"
        )
        return ocr_text, method

    def extract_image_text(self, image: Image.Image) -> Tuple[str, str]:
        """For standalone image ingestion (jpg/png/webp uploads). Returns (text, source_type)."""
        described, reason = _vision_llm_describe(
            image,
            "Transcribe all readable text, tables and diagram labels from this "
            "image. Preserve structure. Output only the content, no commentary.",
        )
        if described:
            logger.info(f"[INGEST] page=1 extraction_method=vision characters={len(described)}")
            return described, "vision"

        ocr_text = ocr_image(image)
        method = "ocr" if ocr_text else "none"
        logger.info(
            f"[INGEST] page=1 extraction_method={method} characters={len(ocr_text)} vision_reason={reason}"
        )
        return ocr_text, method

    def understand_image(self, image: Image.Image, instruction: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Direct visual understanding for photographs, scenes, people, diagrams,
        and visual artwork where text transcription is not primary."""
        instruction = instruction or (
            "Describe this photograph or visual image in detail. Identify the subject, people, "
            "objects, environment, actions, context, and visual characteristics. If there are any "
            "visible markings, signs, or text, include them."
        )
        return _vision_llm_describe(image, instruction)

    def answer_image_question(self, image: Image.Image, question: str) -> Tuple[str, bool, Optional[str]]:
        """Direct image Q&A (assignment photo, screenshot, human photo, diagram).
        Returns (answer_or_extracted_text, used_llm_vision, vision_failure_reason)."""
        answer, reason = _vision_llm_describe(
            image,
            f"Look at this image and answer the following question precisely. "
            f"If it involves visual elements, people, or objects, describe them accurately. "
            f"If it involves a calculation, show the calculation.\n\nQuestion: {question}",
        )
        if answer:
            return answer, True, None

        # Offline fallback: OCR then let caller pass the extracted text to a text LLM.
        text = ocr_image(image)
        return text, False, reason


ocr_vision_service = OCRVisionService()
