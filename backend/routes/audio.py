"""
Audio upload and transcription endpoint for Nexora AI.

Accepts audio files (mp3, wav, m4a, ogg, webm, etc.) and returns
the transcribed text, which can then be passed directly to /query.

Endpoint: POST /audio/transcribe
Request:  multipart/form-data   field: file (audio file)
                                field: language (optional ISO 639-1 code)
                                field: session_id (optional)
Response: { "transcription": "...", "language": "...", "session_id": "..." }

The /audio/ask endpoint is a shortcut that transcribes + queries in one call.
"""
import os

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.logger import logger
from backend.services.audio_service import (
    audio_service,
    AudioServiceUnavailableError,
    AudioTranscriptionError,
    SUPPORTED_AUDIO_FORMATS,
)
from backend.utils.security import sanitize_filename

router = APIRouter(tags=["audio"], prefix="/audio")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploaded_docs")


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form(default=None),
    session_id: str = Form(default=None),
):
    """
    Transcribe an uploaded audio file to text using Groq Whisper.

    Returns the transcribed text, which the client can then send to POST /query.
    """
    if not audio_service.is_available():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Audio transcription is not available. "
                "GROQ_API_KEY must be set to enable Whisper transcription."
            },
        )

    filename = sanitize_filename(file.filename or "audio.wav")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_AUDIO_FORMATS:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unsupported audio format: '{ext}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
            },
        )

    # Read bytes and transcribe
    try:
        audio_bytes = await file.read()
        if len(audio_bytes) == 0:
            return JSONResponse(status_code=400, content={"error": "Uploaded file is empty."})

        transcription = audio_service.transcribe_bytes(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language or None,
        )

        return {
            "transcription": transcription,
            "filename": filename,
            "language": language or "auto-detected",
            "session_id": session_id,
            "word_count": len(transcription.split()),
        }

    except AudioServiceUnavailableError as e:
        return JSONResponse(status_code=503, content={"error": str(e)})
    except AudioTranscriptionError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        logger.exception("[AUDIO] Unexpected transcription error")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/ask")
async def audio_ask(
    file: UploadFile = File(...),
    language: str = Form(default=None),
    session_id: str = Form(default=None),
    document_ids: str = Form(default=None),
):
    """
    One-shot: transcribe audio → run AI query → return answer.

    This is a convenience wrapper around /audio/transcribe + /query.
    """
    if not audio_service.is_available():
        return JSONResponse(
            status_code=503,
            content={"error": "Audio transcription requires GROQ_API_KEY to be set."},
        )

    filename = sanitize_filename(file.filename or "audio.wav")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_AUDIO_FORMATS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported audio format: '{ext}'."},
        )

    try:
        audio_bytes = await file.read()
        transcription = audio_service.transcribe_bytes(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language or None,
        )
    except (AudioServiceUnavailableError, AudioTranscriptionError) as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        logger.exception("[AUDIO] Transcription error in /audio/ask")
        return JSONResponse(status_code=500, content={"error": str(e)})

    # Parse document_ids (comma-separated string from form data)
    doc_id_list = None
    if document_ids:
        doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()]

    # Now run the orchestrator with the transcribed text
    try:
        from backend.services.orchestrator_service import orchestrator_service

        result = orchestrator_service.orchestrate(
            question=transcription,
            session_id=session_id,
            document_ids=doc_id_list,
        )

        return {
            "transcription": transcription,
            "answer": result.answer,
            "route_used": result.route_used,
            "session_id": result.session_id,
            "document_citations": [c.model_dump() for c in result.document_citations],
            "web_citations": [c.model_dump() for c in result.web_citations],
        }
    except Exception as e:
        logger.exception("[AUDIO] Orchestration error in /audio/ask")
        return JSONResponse(status_code=500, content={"error": str(e)})
