"""
Legacy endpoint, kept for backward compatibility with existing frontend
code. New integrations should use POST /documents/upload instead, which
returns richer per-file status and supports more file types.
"""
from typing import List

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logger import logger
from backend.services.document_service import document_service
from backend.utils.security import UnsafeFileError, read_upload_safely

router = APIRouter()


@router.post("/upload_pdfs/")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    try:
        logger.info("Received uploaded files (legacy /upload_pdfs/ endpoint)")
        documents = []
        for file in files:
            try:
                saved_path = await read_upload_safely(file, settings.UPLOAD_DIR)
            except UnsafeFileError as e:
                documents.append({"filename": file.filename, "status": "rejected", "error": str(e)})
                continue
            record = document_service.ingest(saved_path, file.filename)
            documents.append(record)

        failed = [d for d in documents if d.get("status") != "completed"]
        if failed and len(failed) == len(documents):
            return JSONResponse(
                status_code=500,
                content={"error": "All files failed to process.", "documents": documents},
            )

        logger.info("Document(s) added to vectorstore")
        return {"messages": "Files processed and vectorstore updated", "documents": documents}

    except Exception as e:
        logger.exception("Error during PDF upload")
        return JSONResponse(status_code=500, content={"error": str(e)})
