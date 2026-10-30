from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.logger import logger
from backend.schemas import QueryRequest, QueryResponse
from backend.services.orchestrator_service import orchestrator_service
from backend.auth.jwt_validator import try_get_current_user
from backend.services.chat_persistence_service import chat_persistence

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, request: Request):
    """
    Main AI query endpoint. Supports authenticated persistent chat and
    unauthenticated requests (backward compatible).
    
    Persistence invariant:
    1. Authenticated user messages are committed to the persistent store immediately.
    2. Completed assistant responses are saved on success.
    3. If the AI pipeline fails, the failure state is persisted for the assistant turn,
       preventing loss of the user's inquiry.
    4. The persistent conversation_id is returned in the QueryResponse.
    """
    user = try_get_current_user(request)
    conversation_id = getattr(payload, "conversation_id", None)

    # 1. Immediate persistence for authenticated requests
    if user:
        user_id = user["user_id"]
        try:
            # Validate or create conversation
            if conversation_id:
                conv = chat_persistence.get_conversation(user_id, conversation_id)
                if not conv:
                    conversation_id = None
            if not conversation_id:
                title = chat_persistence.generate_title(payload.question)
                conv = chat_persistence.create_conversation(user_id, title)
                conversation_id = conv.get("id")

            if conversation_id:
                # Save user inquiry immediately before running heavy model work
                chat_persistence.add_message(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role="user",
                    content=payload.question,
                    msg_status="completed",
                )
        except Exception as persist_err:
            logger.warning(f"[Query] Pre-execution chat persistence failed (non-fatal): {persist_err}")

    # 2. Execute Orchestration
    try:
        response = orchestrator_service.handle_query_request(payload)
    except Exception as e:
        logger.exception("Error handling /query")
        # Persist assistant failure state if authenticated
        if user and conversation_id:
            try:
                chat_persistence.add_message(
                    conversation_id=conversation_id,
                    user_id=user["user_id"],
                    role="assistant",
                    content="I encountered an internal error while processing your request. Please try again.",
                    metadata={"error": str(e)[:180]},
                    msg_status="failed",
                )
                chat_persistence.update_last_message_at(user["user_id"], conversation_id)
            except Exception as f_err:
                logger.warning(f"[Query] Assistant failure persistence failed: {f_err}")
        return JSONResponse(
            status_code=500,
            content={"error": "An error occurred while generating your response. Please try again."},
        )

    # 3. Persist completed assistant response
    if user and conversation_id:
        try:
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
                msg_status="completed",
            )
            chat_persistence.update_last_message_at(user["user_id"], conversation_id)
            response.conversation_id = conversation_id
        except Exception as post_err:
            logger.warning(f"[Query] Post-execution assistant persistence failed: {post_err}")

    return response
