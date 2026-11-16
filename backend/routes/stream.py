"""
SSE Streaming endpoint for Nexora AI.

Streams the AI answer token-by-token using Server-Sent Events (SSE).
The frontend receives partial answer chunks in real time — users see
the response appearing as the LLM generates it, dramatically reducing
perceived latency.

Endpoint: POST /query/stream
Request body: same as POST /query (QueryRequest JSON)
Response:  Content-Type: text/event-stream

Event format:
  data: {"type": "token",   "content": "word "}
  data: {"type": "meta",    "route_used": "...", "session_id": "...", ...}
  data: {"type": "done"}
  data: {"type": "error",   "message": "..."}

The streaming pipeline:
  1. Build the full prompt via the existing orchestrator/answer logic
  2. Stream LLM tokens directly to the client
  3. After full generation, emit a final "meta" event with citations,
     routing decision, and verification summary
"""
import json
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.logger import logger
from backend.schemas import QueryRequest

from backend.auth.jwt_validator import try_get_current_user

router = APIRouter(tags=["streaming"])


async def _token_stream(
    question: str,
    session_id: Optional[str],
    document_ids: Optional[list],
    mode: Optional[str],
    user_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Core streaming generator. Yields SSE-formatted data lines.
    """
    import asyncio

    try:
        # --- Step 1: Run the full orchestration pipeline in a thread ---
        # We use the existing synchronous orchestrator but intercept
        # just the LLM call to stream it.
        from backend.services.conversation_service import conversation_service
        from backend.services.query_router import query_router, ResolvedDocument
        from backend.services.web_search_service import web_search_service
        from backend.services.document_service import document_service
        from backend.services.retriever_service import retriever_service
        from backend.services.citation_service import citation_service
        from backend.services.llm_provider import get_chat_llm
        from backend.utils.security import neutralize_untrusted_text
        from backend.services.query_planner import query_planner
        from backend.services.answer_service import _SYSTEM_PREAMBLE
        from backend.config import settings

        # Conversation / session setup
        session_id_resolved = conversation_service.ensure_session(session_id)

        # Document context
        if document_ids:
            conversation_service.set_active_documents(session_id_resolved, document_ids)
        target_ids = document_ids or conversation_service.get_active_documents(session_id_resolved)
        resolved_documents = []
        for doc_id in target_ids:
            record = document_service.get_document(doc_id)
            if record:
                resolved_documents.append(
                    ResolvedDocument(doc_id, record.get("source_type", ""), record.get("status", ""))
                )
        all_docs = document_service.list_documents()
        has_any_documents = any(d.get("status") == "completed" for d in all_docs)

        # Query planner (pre-routing)
        history_text = conversation_service.history_as_text(session_id_resolved)
        plan = query_planner.plan(question, history=history_text)
        active_question = plan.primary_query

        # Routing decision
        decision = query_router.route_decision(
            question=active_question,
            resolved_documents=resolved_documents,
            has_any_documents=has_any_documents,
            web_search_available=web_search_service.is_available(),
            forced_mode=mode,
            explicit_doc_selection=bool(document_ids),
        )

        route = decision.to_legacy_route()
        context_blocks = []
        doc_citations = []
        web_citations = []

        # --- Step 2: Gather context (same logic as AnswerService) ---
        rag_doc_ids = None
        if decision.document_required:
            rag_doc_ids = document_ids or [d.document_id for d in resolved_documents] or None

        if decision.document_required:
            retrieval_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: retriever_service.retrieve_with_crag(
                    question=active_question,
                    history=history_text,
                    document_ids=rag_doc_ids,
                ),
            )
            chunks = retrieval_result.chunks
            if chunks and retrieval_result.evidence_quality in ("high", "medium"):
                doc_citations = citation_service.from_chunks(chunks)
                doc_text = "\n\n".join(
                    f"(filename: {c.metadata.get('filename')}, page: {c.metadata.get('page_number')})\n"
                    f"{neutralize_untrusted_text(c.text)}"
                    for c in chunks
                )
                context_blocks.append(f"[DOCUMENT CONTEXT]\n{doc_text}\n[/DOCUMENT CONTEXT]")

        if decision.web_required:
            search_query = decision.search_query or active_question
            web_evidence = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: web_search_service.search_evidence(search_query),
            )
            if web_evidence.status == "success" and web_evidence.results:
                web_citations = citation_service.from_web_results(web_evidence.results)
                web_text = "\n\n".join(
                    f"Title: {r.title}\nSource: {r.url}\nDate: {r.published_date or 'Undated'}\n"
                    f"{neutralize_untrusted_text(r.snippet)}"
                    for r in web_evidence.results
                )
                context_blocks.append(f"[WEB CONTEXT]\n{web_text}\n[/WEB CONTEXT]")

        # --- Step 3: Build prompt ---
        parts = [_SYSTEM_PREAMBLE]
        if history_text:
            parts.append(f"[CONVERSATION HISTORY]\n{history_text}\n[/CONVERSATION HISTORY]")
        parts.extend(context_blocks)
        parts.append(f"User question: {active_question}\n\nAnswer:")
        full_prompt = "\n\n".join(parts)

        # --- Step 4: Stream LLM tokens ---
        llm = get_chat_llm()
        full_answer = ""

        for chunk in llm.stream(full_prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                full_answer += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # --- Step 5: Save to conversation history ---
        conversation_service.add_turn(session_id_resolved, "user", question)
        conversation_service.add_turn(session_id_resolved, "assistant", full_answer)

        # --- Step 6: Emit final metadata event ---
        meta = {
            "type": "meta",
            "session_id": session_id_resolved,
            "route_used": route,
            "document_citations": [c.model_dump() for c in doc_citations],
            "web_citations": [c.model_dump() for c in web_citations],
            "is_complex_query": plan.is_complex,
        }
        yield f"data: {json.dumps(meta)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.exception("[STREAM] Error during streaming generation")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.post("/query/stream")
async def stream_query(payload: QueryRequest, request: Request):
    """
    Streaming version of POST /query.
    Returns a Server-Sent Events stream of answer tokens.
    """
    logger.info(f"[STREAM] question={payload.question!r} session={payload.session_id}")

    user = try_get_current_user(request)
    user_id = user["user_id"] if user else None

    return StreamingResponse(
        _token_stream(
            question=payload.question,
            session_id=payload.session_id,
            document_ids=payload.document_ids,
            mode=payload.mode,
            user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
