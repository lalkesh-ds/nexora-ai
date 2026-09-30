from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logger import logger
from backend.schemas import UploadResponse, DocumentInfo
from backend.services.document_service import document_service
from backend.services.conversation_service import conversation_service
from backend.utils.security import UnsafeFileError, read_upload_safely

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
):
    """Multimodal ingestion: text/scanned PDFs, DOCX, TXT, CSV, XLSX, images.

    Returns HTTP 200 only if every file ingested successfully, 207 if some
    succeeded and some failed/were rejected, and 422 if every file failed -
    a caller that only checks `response.status_code == 200` will correctly
    see a failed upload as NOT successful (previously this endpoint always
    returned 200 regardless of ingestion outcome).

    If session_id is provided, successfully ingested document_ids become
    this session's "active documents" so a later /query without an
    explicit document_ids list can still resolve "the thing I just
    uploaded".
    """
    results = []
    succeeded_ids = []
    for file in files:
        try:
            saved_path = await read_upload_safely(file, settings.UPLOAD_DIR)
        except UnsafeFileError as e:
            logger.warning(f"Rejected upload '{file.filename}': {e}")
            results.append(DocumentInfo(
                document_id="", filename=file.filename, source_type="unknown",
                status="rejected", error=str(e),
            ))
            continue

        record = document_service.ingest(saved_path, file.filename)
        status = record.get("status", "failed")
        results.append(DocumentInfo(
            document_id=record.get("document_id", ""),
            filename=record.get("filename", file.filename),
            source_type=record.get("source_type", "unknown"),
            status=status,
            pages=record.get("pages"),
            error=record.get("error"),
        ))
        if status == "completed":
            succeeded_ids.append(record.get("document_id", ""))

    if session_id and succeeded_ids:
        conversation_service.set_active_documents(session_id, succeeded_ids)

    body = UploadResponse(documents=results).model_dump()
    if succeeded_ids and len(succeeded_ids) == len(results):
        status_code = 200
    elif succeeded_ids:
        status_code = 207
    else:
        status_code = 422
    return JSONResponse(status_code=status_code, content=body)


@router.get("", response_model=UploadResponse)
async def list_documents():
    records = document_service.list_documents()
    return UploadResponse(documents=[
        DocumentInfo(
            document_id=r.get("document_id", ""),
            filename=r.get("filename", ""),
            source_type=r.get("source_type", "unknown"),
            status=r.get("status", "unknown"),
            pages=r.get("pages"),
            error=r.get("error"),
        ) for r in records
    ])


@router.get("/{document_id}/status", response_model=DocumentInfo)
async def get_document_status(document_id: str):
    record = document_service.get_document(document_id)
    if not record:
        return JSONResponse(status_code=404, content={"error": "document not found"})
    return DocumentInfo(
        document_id=record.get("document_id", ""),
        filename=record.get("filename", ""),
        source_type=record.get("source_type", "unknown"),
        status=record.get("status", "unknown"),
        pages=record.get("pages"),
        error=record.get("error"),
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    try:
        document_service.delete_document(document_id)
        return {"message": f"document {document_id} deleted"}
    except Exception as e:
        logger.exception("Error deleting document")
        return JSONResponse(status_code=500, content={"error": str(e)})
