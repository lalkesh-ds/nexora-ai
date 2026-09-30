"""
AI Orchestrator for Nexora AI.

Architecture Flow:
  User Request
  -> Conversation Context
  -> Query Understanding
  -> Intelligent Router (producing typed RoutingDecision)
  -> Selected Tool(s) / Fallback Coordination
  -> Response Generation
"""
from typing import List, Optional

from backend.logger import logger
from backend.schemas import QueryRequest, QueryResponse, RoutingDecision
from backend.services.conversation_service import conversation_service
from backend.services.document_service import document_service
from backend.services.web_search_service import web_search_service
from backend.services.query_router import query_router, ResolvedDocument
from backend.services.answer_service import answer_service


class AIOrchestrator:
    def orchestrate(
        self,
        question: str,
        session_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        mode: Optional[str] = "AUTO",
    ) -> QueryResponse:
        """Central orchestration: resolves context, understands query intent,
        makes structured routing decisions, and coordinates tool execution."""
        # 1. Conversation Context
        session_id = conversation_service.ensure_session(session_id)

        # 2. Document Context Resolution
        explicit_doc_selection = bool(document_ids)
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

        # 3. Query Understanding & Routing Decision
        decision: RoutingDecision = query_router.route_decision(
            question=question,
            resolved_documents=resolved_documents,
            has_any_documents=has_any_documents,
            web_search_available=web_search_service.is_available(),
            forced_mode=mode,
            explicit_doc_selection=explicit_doc_selection,
        )

        logger.info(
            f"[ORCHESTRATOR] question={question!r} intent={decision.intent} sources={decision.sources} "
            f"web_required={decision.web_required} doc_required={decision.document_required} "
            f"vision_required={decision.vision_required} confidence={decision.confidence:.2f} "
            f"reasoning={decision.reasoning!r}"
        )

        # 4. Scope document IDs to document-dependent tools only
        rag_doc_ids = None
        if decision.document_required:
            rag_doc_ids = document_ids or [d.document_id for d in resolved_documents] or None

        # 5. Tool Selection & Response Generation
        result = answer_service.answer(
            question=question,
            session_id=session_id,
            document_ids=rag_doc_ids,
            resolved_documents=resolved_documents,
            routing_decision=decision,
        )

        return result

    def handle_query_request(self, payload: QueryRequest) -> QueryResponse:
        return self.orchestrate(
            question=payload.question,
            session_id=payload.session_id,
            document_ids=payload.document_ids,
            mode=payload.mode,
        )


orchestrator_service = AIOrchestrator()
