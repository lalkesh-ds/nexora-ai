"""
Legacy endpoint, kept for backward compatibility. Internally now delegates
to the central AI orchestrator, then maps the result back onto the old
{"response": ..., "sources": [...]} shape so existing frontend code keeps working.
New integrations should use POST /query instead.
"""
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from backend.logger import logger
from backend.services.orchestrator_service import orchestrator_service

router = APIRouter()


@router.post("/ask/")
async def ask_question(question: str = Form(...), session_id: str = Form(default=None)):
    try:
        logger.info(f"user query (legacy /ask/ endpoint): {question}")
        result = orchestrator_service.orchestrate(question=question, session_id=session_id)
        logger.info("query successful")
        return {
            "response": result.answer,
            "sources": [c.filename for c in result.document_citations],
            "route_used": result.route_used,
            "session_id": result.session_id,
            "document_citations": [c.model_dump() for c in result.document_citations],
            "web_citations": [c.model_dump() for c in result.web_citations],
        }

    except Exception as e:
        logger.exception("Error processing question")
        return JSONResponse(status_code=500, content={"error": str(e)})
