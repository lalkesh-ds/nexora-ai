from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Request, Depends
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logger import logger
from backend.schemas import UploadResponse, DocumentInfo
from backend.services.document_service import document_service
from backend.services.conversation_service import conversation_service
from backend.utils.security import UnsafeFileError, read_upload_safely
from backend.auth.jwt_validator import try_get_current_user
from backend.db.supabase_client import get_supabase, is_supabase_configured

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
):
    """Multimodal ingestion: text/scanned PDFs, DOCX, TXT, CSV, XLSX, images.

    Returns HTTP 200 only if every file ingested successfully, 207 if some
    succeeded and some failed/were rejected, and 422 if every file failed.

    Authenticated requests: document ownership is recorded in the
    `user_documents` Supabase table so users only see/delete their own files.
    Unauthenticated requests: documents go into the shared global pool
    (backward-compatible with legacy usage).

    If session_id is provided, successfully ingested document_ids become
    this session's "active documents" so a later /query without an
    explicit document_ids list can still resolve "the thing I just uploaded".
    """
    user = try_get_current_user(request)
    user_id = user["user_id"] if user else None

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
        doc_id = record.get("document_id", "")
        results.append(DocumentInfo(
            document_id=doc_id,
            filename=record.get("filename", file.filename),
            source_type=record.get("source_type", "unknown"),
            status=status,
            pages=record.get("pages"),
            error=record.get("error"),
        ))
        if status == "completed":
            succeeded_ids.append(doc_id)
            # Persist ownership record for authenticated users
            if user_id and doc_id:
                _register_user_document(
                    user_id=user_id,
                    document_id=doc_id,
                    filename=record.get("filename", file.filename),
                    source_type=record.get("source_type", "unknown"),
                    conversation_id=conversation_id,
                    pages=record.get("pages"),
                )

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


def _register_user_document(
    user_id: str,
    document_id: str,
    filename: str,
    source_type: str,
    conversation_id: Optional[str],
    pages: Optional[int],
):
    """Upsert a row in user_documents (Supabase) for document ownership tracking."""
    if not is_supabase_configured():
        return
    try:
        sb = get_supabase()
        sb.table("user_documents").upsert({
            "user_id": user_id,
            "document_id": document_id,
            "filename": filename,
            "source_type": source_type,
            "conversation_id": conversation_id,
            "pages": pages,
            "status": "completed",
        }).execute()
    except Exception as e:
        logger.warning(f"[Documents] Could not register user_document ownership: {e}")


@router.get("", response_model=UploadResponse)
async def list_documents(request: Request):
    """List documents. If authenticated, returns only the caller's documents."""
    user = try_get_current_user(request)

    if user and is_supabase_configured():
        records = _list_user_documents(user["user_id"])
    else:
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


def _list_user_documents(user_id: str) -> list:
    """Return all user_documents rows for this user, merged with local registry."""
    try:
        sb = get_supabase()
        res = sb.table("user_documents").select("*").eq("user_id", user_id).execute()
        rows = res.data or []
        # Enrich with local registry (for status/error fields)
        enriched = []
        for row in rows:
            local = document_service.get_document(row.get("document_id", ""))
            if local:
                enriched.append({**row, **local})
            else:
                enriched.append(row)
        return enriched
    except Exception as e:
        logger.warning(f"[Documents] Supabase list failed, falling back to global list: {e}")
        return document_service.list_documents()


@router.get("/{document_id}/status", response_model=DocumentInfo)
async def get_document_status(document_id: str, request: Request):
    user = try_get_current_user(request)
    record = document_service.get_document(document_id)
    if not record:
        return JSONResponse(status_code=404, content={"error": "document not found"})
    # If authenticated, verify ownership
    if user and not _user_owns_document(user["user_id"], document_id):
        return JSONResponse(status_code=403, content={"error": "access denied"})
    return DocumentInfo(
        document_id=record.get("document_id", ""),
        filename=record.get("filename", ""),
        source_type=record.get("source_type", "unknown"),
        status=record.get("status", "unknown"),
        pages=record.get("pages"),
        error=record.get("error"),
    )


def _user_owns_document(user_id: str, document_id: str) -> bool:
    """Check if user_id is associated with document_id in user_documents. 
    Defaults to True if Supabase unavailable (backward-compat for unauthenticated uploads)."""
    if not is_supabase_configured():
        return True
    try:
        sb = get_supabase()
        res = sb.table("user_documents").select("document_id").eq("user_id", user_id).eq("document_id", document_id).execute()
        return bool(res.data)
    except Exception:
        return True  # Fail open to avoid breaking unregistered legacy documents


@router.delete("/{document_id}")
async def delete_document(document_id: str, request: Request):
    user = try_get_current_user(request)
    # Ownership check for authenticated users
    if user and not _user_owns_document(user["user_id"], document_id):
        return JSONResponse(status_code=403, content={"error": "access denied"})
    try:
        document_service.delete_document(document_id)
        # Remove ownership record
        if user and is_supabase_configured():
            try:
                get_supabase().table("user_documents").delete().eq("document_id", document_id).eq("user_id", user["user_id"]).execute()
            except Exception as e:
                logger.warning(f"[Documents] Could not remove user_documents record: {e}")
        return {"message": f"document {document_id} deleted"}
    except Exception as e:
        logger.exception("Error deleting document")
        return JSONResponse(status_code=500, content={"error": str(e)})
