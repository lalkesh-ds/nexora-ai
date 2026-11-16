"""
AI Orchestrator for Nexora AI.

Architecture Flow:
  User Request
  -> Conversation Context + Long-Term Memory
  -> Query Planner       (decompose complex/multi-part questions)
  -> Query Understanding (FreshnessService + intent signals)
  -> Intelligent Router  (typed RoutingDecision)
  -> Parallel Tool Execution (Doc RAG + Web Search concurrently)
  -> Answer Generation + Verification + Repair
  -> Long-Term Memory Update (async, non-blocking)
  -> Response
"""
import asyncio
import concurrent.futures
from typing import List, Optional

from backend.logger import logger
from backend.schemas import QueryRequest, QueryResponse, RoutingDecision
from backend.services.conversation_service import conversation_service
from backend.services.document_service import document_service
from backend.services.web_search_service import web_search_service
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.answer_service import answer_service
from backend.services.query_planner import query_planner
from backend.services.long_term_memory import long_term_memory

# Thread pool for running parallel retrieval tasks
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="nexora-retrieval")


class AIOrchestrator:
    def orchestrate(
        self,
        question: str,
        session_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        mode: Optional[str] = "AUTO",
        user_id: Optional[str] = None,
    ) -> QueryResponse:
        """
        Central orchestration: resolves context, plans the query,
        makes structured routing decisions, and coordinates tool execution.
        """
        # 1. Conversation Context
        session_id = conversation_service.ensure_session(session_id)

        # 2. Document Context Resolution
        explicit_doc_selection = bool(document_ids)
        if document_ids:
            conversation_service.set_active_documents(session_id, document_ids)
        target_ids = document_ids or conversation_service.get_active_documents(session_id)

        resolved_documents: List[ResolvedDocument] = []
        for doc_id in target_ids:
            record = document_service.get_document(doc_id)
            if record:
                resolved_documents.append(
                    ResolvedDocument(doc_id, record.get("source_type", ""), record.get("status", ""))
                )

        all_docs = document_service.list_documents()
        has_any_documents = any(d.get("status") == "completed" for d in all_docs)

        # 3. Long-Term Memory retrieval (non-blocking — empty string on failure)
        memory_context = ""
        if user_id:
            try:
                memory_context = long_term_memory.retrieve_relevant(user_id, question)
            except Exception as e:
                logger.debug(f"[ORCHESTRATOR] Long-term memory retrieval warning: {e}")

        # 4. Conversation history
        history_text = conversation_service.history_as_text(session_id)

        # 5. Query Planner — decompose complex multi-part questions BEFORE routing
        plan = query_planner.plan(question, history=history_text)

        if plan.is_complex and len(plan.sub_queries) >= 2:
            logger.info(
                f"[ORCHESTRATOR] Complex query detected. "
                f"Decomposed into {len(plan.sub_queries)} sub-queries. "
                f"Strategy: {plan.synthesis_strategy}"
            )
            # Execute the primary sub-query through the full pipeline
            # and return the synthesized result
            return self._handle_complex_query(
                plan=plan,
                session_id=session_id,
                document_ids=document_ids,
                resolved_documents=resolved_documents,
                has_any_documents=has_any_documents,
                explicit_doc_selection=explicit_doc_selection,
                mode=mode,
                memory_context=memory_context,
                user_id=user_id,
            )

        # 6. Single-question flow: routing + answer
        active_question = plan.primary_query

        decision: RoutingDecision = query_router.route_decision(
            question=active_question,
            resolved_documents=resolved_documents,
            has_any_documents=has_any_documents,
            web_search_available=web_search_service.is_available(),
            forced_mode=mode,
            explicit_doc_selection=explicit_doc_selection,
        )

        logger.info(
            f"[ORCHESTRATOR] question={active_question!r} intent={decision.intent} "
            f"sources={decision.sources} web={decision.web_required} "
            f"doc={decision.document_required} confidence={decision.confidence:.2f} "
            f"reasoning={decision.reasoning!r}"
        )

        # 7. Scope document IDs for RAG
        rag_doc_ids = None
        if decision.document_required:
            rag_doc_ids = document_ids or [d.document_id for d in resolved_documents] or None

        # 8. Answer generation (with injected memory context)
        result = answer_service.answer(
            question=active_question,
            session_id=session_id,
            document_ids=rag_doc_ids,
            resolved_documents=resolved_documents,
            routing_decision=decision,
            memory_context=memory_context,
        )

        # 9. Update long-term memory asynchronously (fire-and-forget)
        if user_id and result.answer:
            _executor.submit(
                long_term_memory.update,
                user_id,
                active_question,
                result.answer,
                session_id,
            )

        return result

    def _handle_complex_query(
        self,
        plan,
        session_id: str,
        document_ids,
        resolved_documents,
        has_any_documents,
        explicit_doc_selection,
        mode,
        memory_context: str,
        user_id: Optional[str],
    ) -> QueryResponse:
        """
        Execute sub-queries in parallel (where the router allows) and
        synthesize the results into one coherent response.
        """
        sub_queries = plan.sub_queries
        sub_answers = []

        if plan.synthesis_strategy in ("parallel", "compare"):
            # Run sub-queries concurrently
            futures = {}
            for sq in sub_queries:
                decision = query_router.route_decision(
                    question=sq,
                    resolved_documents=resolved_documents,
                    has_any_documents=has_any_documents,
                    web_search_available=web_search_service.is_available(),
                    forced_mode=mode,
                    explicit_doc_selection=explicit_doc_selection,
                )
                rag_doc_ids = None
                if decision.document_required:
                    rag_doc_ids = document_ids or [d.document_id for d in resolved_documents] or None

                future = _executor.submit(
                    answer_service.answer,
                    sq,
                    None,  # route
                    session_id,
                    rag_doc_ids,
                    resolved_documents,
                    decision,
                    memory_context,
                )
                futures[sq] = future

            for sq in sub_queries:
                try:
                    r = futures[sq].result(timeout=90)
                    sub_answers.append(r.answer)
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Sub-query failed: {sq!r} — {e}")
                    sub_answers.append(f"(Could not answer: {sq})")

        else:  # sequential
            for sq in sub_queries:
                decision = query_router.route_decision(
                    question=sq,
                    resolved_documents=resolved_documents,
                    has_any_documents=has_any_documents,
                    web_search_available=web_search_service.is_available(),
                    forced_mode=mode,
                    explicit_doc_selection=explicit_doc_selection,
                )
                rag_doc_ids = None
                if decision.document_required:
                    rag_doc_ids = document_ids or [d.document_id for d in resolved_documents] or None
                try:
                    r = answer_service.answer(
                        question=sq,
                        session_id=session_id,
                        document_ids=rag_doc_ids,
                        resolved_documents=resolved_documents,
                        routing_decision=decision,
                        memory_context=memory_context,
                    )
                    sub_answers.append(r.answer)
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Sequential sub-query failed: {sq!r} — {e}")
                    sub_answers.append(f"(Could not answer: {sq})")

        # Synthesize sub-answers
        final_answer = query_planner.synthesize(plan.original_question, sub_answers, plan)

        # Save to conversation
        conversation_service.add_turn(session_id, "user", plan.original_question)
        conversation_service.add_turn(session_id, "assistant", final_answer)

        # Update long-term memory
        if user_id and final_answer:
            _executor.submit(
                long_term_memory.update,
                user_id,
                plan.original_question,
                final_answer,
                session_id,
            )

        # Return using the last successful sub-query's QueryResponse structure
        from backend.schemas import QueryResponse, EvidenceBreakdown
        return QueryResponse(
            answer=final_answer,
            route_used="COMPLEX_MULTI_PART",
            session_id=session_id,
            evidence=EvidenceBreakdown(from_general_knowledge=True),
            warnings=[f"Answer synthesized from {len(sub_answers)} sub-questions."],
        )

    def handle_query_request(self, payload: QueryRequest, user_id: Optional[str] = None) -> QueryResponse:
        return self.orchestrate(
            question=payload.question,
            session_id=payload.session_id,
            document_ids=payload.document_ids,
            mode=payload.mode,
            user_id=user_id,
        )


orchestrator_service = AIOrchestrator()
