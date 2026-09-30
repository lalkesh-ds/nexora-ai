"""
Security helpers used at every trust boundary:

* file uploads (path traversal, oversized files, disallowed types)
* document/web content that gets stuffed into an LLM prompt
  (basic prompt-injection containment)
"""
import os
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from backend.config import settings
from backend.logger import logger


class UnsafeFileError(Exception):
    pass


def sanitize_filename(filename: str) -> str:
    """Strip directory components and dangerous characters.

    Prevents path traversal like '../../etc/passwd' or absolute paths.
    """
    name = os.path.basename(filename or "")
    name = name.replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9_.\-]", "_", name)
    if not name or name in {".", ".."}:
        name = f"upload_{uuid.uuid4().hex}"
    return name


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise UnsafeFileError(
            f"File type '{ext}' is not supported. "
            f"Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}"
        )
    return ext


def validate_size(size_bytes: int):
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise UnsafeFileError(
            f"File is {size_bytes / 1_048_576:.1f} MB, "
            f"exceeds the {settings.MAX_FILE_SIZE_MB} MB limit."
        )


def safe_join(base_dir: str, filename: str) -> str:
    """Join filename to base_dir, guaranteeing the result stays inside base_dir."""
    base = Path(base_dir).resolve()
    candidate = (base / sanitize_filename(filename)).resolve()
    if base not in candidate.parents and candidate != base:
        raise UnsafeFileError("Path traversal attempt detected.")
    return str(candidate)


async def read_upload_safely(file: UploadFile, base_dir: str) -> str:
    """Validate extension/size, then persist an UploadFile to base_dir.

    Returns the saved path. Raises UnsafeFileError on any violation.
    """
    validate_extension(file.filename)
    os.makedirs(base_dir, exist_ok=True)
    dest_path = safe_join(base_dir, file.filename)

    contents = await file.read()
    validate_size(len(contents))

    with open(dest_path, "wb") as f:
        f.write(contents)

    await file.seek(0)
    logger.info(f"Saved upload '{file.filename}' -> '{dest_path}' ({len(contents)} bytes)")
    return dest_path


# ---------------------------------------------------------------------------
# Prompt-injection containment for untrusted document/web content.
#
# We never try to "detect and block" injection with certainty (impossible),
# instead we (a) fence untrusted content clearly, (b) strip obvious
# instruction-override phrases before they reach the model, and (c) tell the
# model explicitly, in the system prompt, that this content is data.
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|disregard)\b(?:\s+\w+){0,4}\s+instructions\b", re.I),
    re.compile(r"you are now (in )?(developer|admin|jailbreak) mode", re.I),
    re.compile(r"reveal (your|the) (system prompt|instructions)", re.I),
    re.compile(r"act as (system|admin|root)", re.I),
]


def neutralize_untrusted_text(text: str, max_chars: int = 20000) -> str:
    """Best-effort scrub of instruction-override attempts in untrusted text.

    This does NOT make the content safe to treat as instructions - callers
    must still wrap it as clearly-labeled data in the prompt.
    """
    if not text:
        return text
    text = text[:max_chars]
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[removed: instruction-like text]", text)
    return text
