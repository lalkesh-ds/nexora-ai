from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.schemas import ConversationHistory, ConversationTurn
from backend.services.conversation_service import conversation_service

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/session")
async def create_session():
    session_id = conversation_service.create_session()
    return {"session_id": session_id}


@router.get("/{session_id}/history", response_model=ConversationHistory)
async def get_history(session_id: str):
    turns = conversation_service.get_history(session_id, limit=1000)
    if not turns:
        return JSONResponse(status_code=404, content={"error": "session not found or empty"})
    return ConversationHistory(
        session_id=session_id,
        turns=[ConversationTurn(**t) for t in turns],
    )
