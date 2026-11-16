"""
AudioService: Transcribes audio input using the Groq Whisper API.

Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg
Max file size: 25 MB (Groq limit)

Flow:
  Audio file bytes
  -> Groq Whisper API (whisper-large-v3)
  -> Transcribed text
  -> Returned to orchestrator as a text question

If GROQ_API_KEY is not set, raises AudioServiceUnavailableError so
callers can return a helpful message rather than a silent failure.
"""
import os
from typing import Optional

from backend.config import settings
from backend.logger import logger

SUPPORTED_AUDIO_FORMATS = {
    ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"
}

WHISPER_MODEL = "whisper-large-v3"
MAX_AUDIO_SIZE_MB = 25


class AudioServiceUnavailableError(RuntimeError):
    pass


class AudioTranscriptionError(RuntimeError):
    pass


class AudioService:
    """Transcribes audio files to text using Groq Whisper."""

    def is_available(self) -> bool:
        return bool(settings.GROQ_API_KEY)

    def transcribe(self, file_path: str, language: Optional[str] = None) -> str:
        """
        Transcribe an audio file. Returns the transcription text.

        Args:
            file_path: Absolute path to the saved audio file.
            language:  Optional ISO 639-1 language code (e.g. "en", "hi").
                       If None, Whisper auto-detects.

        Raises:
            AudioServiceUnavailableError: if GROQ_API_KEY is not set.
            AudioTranscriptionError:      if the API call fails.
        """
        if not self.is_available():
            raise AudioServiceUnavailableError(
                "Audio transcription requires GROQ_API_KEY to be set."
            )

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_AUDIO_FORMATS:
            raise AudioTranscriptionError(
                f"Unsupported audio format: {ext}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
            )

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_AUDIO_SIZE_MB:
            raise AudioTranscriptionError(
                f"Audio file is too large ({file_size_mb:.1f} MB). "
                f"Maximum allowed: {MAX_AUDIO_SIZE_MB} MB."
            )

        try:
            from groq import Groq

            client = Groq(api_key=settings.GROQ_API_KEY)

            with open(file_path, "rb") as f:
                kwargs = {
                    "file": (os.path.basename(file_path), f),
                    "model": WHISPER_MODEL,
                    "response_format": "text",
                }
                if language:
                    kwargs["language"] = language

                transcription = client.audio.transcriptions.create(**kwargs)

            # Groq returns a plain string when response_format="text"
            text = transcription if isinstance(transcription, str) else str(transcription)
            text = text.strip()

            if not text:
                raise AudioTranscriptionError(
                    "Whisper returned an empty transcription. "
                    "The audio may be silent or too short."
                )

            logger.info(
                f"[AUDIO] Transcribed file={os.path.basename(file_path)} "
                f"size={file_size_mb:.2f}MB words={len(text.split())}"
            )
            return text

        except (AudioServiceUnavailableError, AudioTranscriptionError):
            raise
        except Exception as e:
            logger.warning(f"[AUDIO] Transcription failed: {e}")
            raise AudioTranscriptionError(f"Audio transcription failed: {e}") from e

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe raw audio bytes (without saving to disk).

        Writes to a temp file and delegates to transcribe().
        """
        import tempfile

        ext = os.path.splitext(filename)[1].lower() or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe(tmp_path, language=language)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


audio_service = AudioService()
