from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.logger import logger
from backend.schemas import QueryRequest, QueryResponse
from backend.services.orchestrator_service import orchestrator_service
from backend.auth.jwt_validator import try_get_current_user
from backend.db.supabase_client import is_supabase_configured

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, request: Request):
    """
    Main AI query endpoint. Works unauthenticated (backward compatible).
    When a valid Bearer token is present and Supabase is configured,
    the conversation and messages are persisted to PostgreSQL.
    """
    try:
        response = orchestrator_service.handle_query_request(payload)
    except Exception as e:
        logger.exception("Error handling /query")
        return JSONResponse(status_code=500, content={"error": str(e)})

    # Optional persistence — non-blocking, never breaks the AI response
    if is_supabase_configured():
        user = try_get_current_user(request)
        if user and user.get("email_confirmed"):
            try:
                from backend.services.chat_persistence_service import chat_persistence

                conversation_id = getattr(payload, "conversation_id", None)

                # Create or validate conversation
                if not conversation_id:
                    title = chat_persistence.generate_title(payload.question)
                    conv = chat_persistence.create_conversation(user["user_id"], title)
                    conversation_id = conv.get("id")
                else:
                    existing = chat_persistence.get_conversation(user["user_id"], conversation_id)
                    if not existing:
                        conversation_id = None  # Don't persist if not owned

                if conversation_id:
                    # Persist user message
                    chat_persistence.add_message(
                        conversation_id=conversation_id,
                        user_id=user["user_id"],
                        role="user",
                        content=payload.question,
                    )
                    # Persist assistant response
                    citations_data = {
                        "document_citations": [c.model_dump() for c in (response.document_citations or [])],
                        "web_citations": [c.model_dump() for c in (response.web_citations or [])],
                    }
                    metadata = {
                        "route_used": response.route_used,
                        "warnings": response.warnings or [],
                        "verification": response.verification.model_dump() if response.verification else None,
                    }
                    chat_persistence.add_message(
                        conversation_id=conversation_id,
                        user_id=user["user_id"],
                        role="assistant",
                        content=response.answer,
                        citations=citations_data,
                        metadata=metadata,
                    )
                    # Update timestamp
                    chat_persistence.update_last_message_at(user["user_id"], conversation_id)
            except Exception as persist_err:
                # Persistence failure must never break the AI response
                logger.warning(f"[Query] Chat persistence failed (non-fatal): {persist_err}")

    return response
