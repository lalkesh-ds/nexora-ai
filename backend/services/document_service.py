"""
DocumentService: turns an uploaded file into embedded, searchable chunks.

Supported inputs: text/scanned PDF, DOCX, TXT, CSV, XLSX, and images
(JPG/JPEG/PNG/WebP - e.g. assignment photos or screenshots).

Every chunk carries metadata: document_id, filename, page_number,
source_type ('text' | 'ocr' | 'vision' | 'table').

Ingestion cache: document_id is a stable content hash of the file bytes,
so the same file always gets the same identity. Whether a cached result
is *reused*, however, also depends on an `extraction_fingerprint`
(VISION_PROVIDER + OCR_MIN_TEXT_CHARS_PER_PAGE + extractor version) that
is stored alongside every completed record. If that fingerprint no
longer matches the current config, the cache is treated as stale and the
file is fully re-extracted - so changing VISION_PROVIDER and
re-uploading the same file actually re-runs the new pipeline instead of
silently returning the old result.
"""
import os
from pathlib import Path
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import settings
from backend.logger import logger
from backend.utils.hashing import hash_file
from backend.utils.cache import document_registry
from backend.services.ocr_vision_service import ocr_vision_service
from backend.services.embedding_service import embedding_service
from backend.services.vectorstore_service import vectorstore_service

# Bump this whenever extraction logic changes in a way that should
# invalidate previously-cached ingestions (independent of provider/env
# changes, which are already covered by VISION_PROVIDER/OCR_MIN_TEXT_CHARS).
_EXTRACTOR_VERSION = "2"


def _extraction_fingerprint() -> str:
    return f"{settings.VISION_PROVIDER}|{settings.OCR_MIN_TEXT_CHARS_PER_PAGE}|v{_EXTRACTOR_VERSION}"


class DocumentPage:
    def __init__(self, page_number: int, text: str, source_type: str):
        self.page_number = page_number
        self.text = text
        self.source_type = source_type


# ---------------------------------------------------------------------------
# Per-format extraction -> list[DocumentPage]
# ---------------------------------------------------------------------------

from backend.services.multimodal_service import multimodal_service


def _extract_pdf(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_pdf(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


def _extract_docx(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_docx(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


def _extract_txt(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_txt(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


def _extract_csv(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_csv(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


def _extract_xlsx(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_xlsx(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


def _extract_image(path: str) -> List[DocumentPage]:
    pages = multimodal_service.process_image(path)
    return [DocumentPage(p.page_number, p.text, p.source_type) for p in pages]


_EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_txt,
    ".csv": _extract_csv,
    ".xlsx": _extract_xlsx,
    ".jpg": _extract_image,
    ".jpeg": _extract_image,
    ".png": _extract_image,
    ".webp": _extract_image,
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _no_content_message(ext: str, page_failures: List[str]) -> str:
    detail = f" Per-page detail: {'; '.join(page_failures)}" if page_failures else ""
    if ext in IMAGE_EXTENSIONS:
        return (
            "No extractable content found in this image. Both the configured "
            f"vision provider and Tesseract OCR returned nothing usable.{detail} "
            "The image may be blank, too low-contrast, or contain no legible "
            "text/handwriting."
        )
    return (
        "No extractable content found across any page of this document. Text "
        f"extraction, vision and OCR all returned empty for every page.{detail} "
        "The file may be corrupt, blank, or entirely unreadable images."
    )


class DocumentService:
    def ingest(self, file_path: str, original_filename: str) -> dict:
        """Ingest one already-saved file. Returns a document registry record."""
        ext = Path(original_filename).suffix.lower()
        content_hash = hash_file(file_path)
        fingerprint = _extraction_fingerprint()

        existing = document_registry.get_by_hash(content_hash)
        if existing and existing.get("status") == "completed" and existing.get("extraction_fingerprint") == fingerprint:
            logger.info(
                f"'{original_filename}' already ingested with the current extraction "
                f"config (document_id={existing['document_id']}, fingerprint={fingerprint}); skipping."
            )
            return existing

        if existing and existing.get("extraction_fingerprint") not in (None, fingerprint):
            logger.info(
                f"'{original_filename}' was previously ingested under a different "
                f"extraction config (old={existing.get('extraction_fingerprint')!r}, "
                f"new={fingerprint!r}) -> re-ingesting."
            )

        document_id = content_hash[:16]

        # Clean up any vectors from a prior ingestion of this exact document_id
        # before re-upserting, so a reprocess never leaves orphaned/duplicate
        # vectors behind (e.g. if the new run produces fewer chunks).
        if existing:
            try:
                vectorstore_service.delete_document(document_id)
            except Exception as e:
                logger.warning(f"Could not clear prior vectors for document_id={document_id}: {e}")

        record = {
            "document_id": document_id,
            "filename": original_filename,
            "source_type": ext.lstrip("."),
            "status": "processing",
            "pages": None,
            "error": None,
            "file_path": file_path,
            "extraction_fingerprint": fingerprint,
            "vision_provider": settings.VISION_PROVIDER,
        }
        document_registry.upsert(content_hash, record)

        try:
            extractor = _EXTRACTORS.get(ext)
            if not extractor:
                raise ValueError(f"Unsupported file type: {ext}")

            pages = extractor(file_path)

            non_empty_pages = [p for p in pages if p.text and p.text.strip()]
            empty_pages = [p for p in pages if not (p.text and p.text.strip())]
            page_failures = [f"page {p.page_number}: no content" for p in empty_pages]

            if not non_empty_pages:
                raise ValueError(_no_content_message(ext, page_failures))

            warnings = []
            if empty_pages:
                warnings.append(
                    f"{len(empty_pages)} of {len(pages)} page(s) produced no extractable "
                    f"content and were skipped: pages {[p.page_number for p in empty_pages]}."
                )
                logger.warning(f"[INGEST] file={original_filename} document_id={document_id} " + warnings[-1])

            method_counts: dict = {}
            for p in non_empty_pages:
                method_counts[p.source_type] = method_counts.get(p.source_type, 0) + 1

            chunks, metadatas = self._chunk_pages(non_empty_pages, document_id, original_filename)
            ids = [f"{document_id}-{i}" for i in range(len(chunks))]

            embeddings = embedding_service.embed_documents(chunks)
            vectorstore_service.upsert(ids, embeddings, metadatas)
            from backend.services.retriever_service import retriever_service
            retriever_service.register_chunks(document_id, chunks, metadatas)

            record.update({
                "status": "completed",
                "pages": len(pages),
                "chunks": len(chunks),
                "extraction_methods": method_counts,
                "warnings": warnings,
                "error": None,
            })
            document_registry.upsert(content_hash, record)
            logger.info(
                f"[INGEST] file={original_filename} document_id={document_id} "
                f"pages={len(pages)} chunks={len(chunks)} methods={method_counts} status=completed"
            )
            return record

        except Exception as e:
            logger.exception(f"Failed to ingest '{original_filename}'")
            record.update({"status": "failed", "error": str(e)})
            document_registry.upsert(content_hash, record)
            logger.info(
                f"[INGEST] file={original_filename} document_id={document_id} status=failed error={e}"
            )
            return record

    def _chunk_pages(self, pages: List[DocumentPage], document_id: str, filename: str):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks, metadatas = [], []
        for page in pages:
            for piece in splitter.split_text(page.text):
                piece = piece.strip()
                if not piece:
                    continue
                chunks.append(piece)
                metadatas.append({
                    "document_id": document_id,
                    "filename": filename,
                    "page_number": page.page_number,
                    "source_type": page.source_type,
                    "text": piece,
                })
        return chunks, metadatas

    def list_documents(self) -> List[dict]:
        return document_registry.list_all()

    def get_document(self, document_id: str) -> Optional[dict]:
        return document_registry.get(document_id)

    def is_image_document(self, document_id: str) -> bool:
        record = self.get_document(document_id)
        if not record:
            return False
        return f".{record.get('source_type', '')}" in IMAGE_EXTENSIONS

    def delete_document(self, document_id: str):
        vectorstore_service.delete_document(document_id)
        from backend.services.retriever_service import retriever_service
        retriever_service.delete_document_chunks(document_id)
        record = document_registry.get(document_id)
        if record:
            for h, rec in list(document_registry._data.items()):
                if rec.get("document_id") == document_id:
                    document_registry.delete(h)


document_service = DocumentService()
