from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.logger import logger
from backend.schemas import QueryRequest, QueryResponse
from backend.services.orchestrator_service import orchestrator_service

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    try:
        return orchestrator_service.handle_query_request(payload)
    except Exception as e:
        logger.exception("Error handling /query")
        return JSONResponse(status_code=500, content={"error": str(e)})
