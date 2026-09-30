"""
QueryRouter: determines user intent and produces a structured RoutingDecision.

Routes / Intents:
  - general_knowledge (sources: ["llm"])
  - document_qa       (sources: ["document", "llm"])
  - web_research      (sources: ["web", "llm"])
  - image_qa          (sources: ["vision", "llm"])
  - hybrid            (sources: ["document", "web", "llm"])

Core Rules:
  1. Explicit web search requests MUST route to web_research.
  2. Failure to find document information must not terminate the request (handled via fallback_sources).
  3. General knowledge questions must NOT automatically trigger document RAG even if documents exist.
  4. Current / time-sensitive questions are routed to web_research.
  5. Images route to image_qa (vision) rather than pure OCR/document text retrieval.
  6. Hybrid questions route to multiple sources (document + web + llm).
"""
import re
from typing import List, Optional

from backend.logger import logger
from backend.schemas import RoutingDecision

_EXPLICIT_WEB_PATTERNS = re.compile(
    r"\b("
    r"search (the )?(web|internet)|"
    r"search online|"
    r"look (this |it )?up( online)?|"
    r"find the latest information|"
    r"check current information|"
    r"google (this|it|for)?|"
    r"web search|"
    r"browse (the )?web|"
    r"find online|"
    r"check (the )?internet|"
    r"search google"
    r")\b",
    re.I,
)

_TEMPORAL_PATTERNS = re.compile(
    r"\b("
    r"today|latest|current|currently|now|recent|recently|this (week|month|year)|"
    r"news|breaking news|stock price|exchange rate|weather|score|"
    r"who (is|won)|release date|new version|update(d)? on|"
    r"up to date|up-to-date|fresh information|"
    r"newly\s+(launched|released|announced|created|introduced|unveiled)|"
    r"(recently|newly|just)\s+(launched|released|announced|published|developed)|"
    r"new\s+(model|feature|technology|update|announcement)|"
    r"launched|announcement|upcoming|brand new|202[4-9]"
    r")\b",
    re.I,
)

_IMAGE_PATTERNS = re.compile(
    r"\b("
    r"image|picture|photo|photograph|drawing|diagram|chart|screenshot|"
    r"visual|see|look|show|face|person|animal|who is (this|in|that)|"
    r"what is (this|in this|shown)|describe (this|the)|read (this|the)|"
    r"written (in|on)|signature|text (in|on)|"
    r"in this (image|picture|photo)|look at this|"
    r"sign|board|handwriting|handwritten"
    r")\b",
    re.I,
)

_DOC_PATTERNS = re.compile(
    r"\b("
    r"document|uploaded|pdf|attached|"
    r"(this|the)\s+(file|paper|report|assignment|document|pdf)|"
    r"according to (the|this)|"
    r"(in|from)\s+(the|this)\s+(document|file|pdf|report|paper)|"
    r"page \d+|"
    r"summarize\s+(this|the\s+(document|file|pdf|report))"
    r")\b",
    re.I,
)

_GENERAL_GREETINGS = re.compile(
    r"^(hi|hello|hey|good (morning|afternoon|evening)|greetings)[\s,!.]*(how are you( today)?|how('s| is) it going|what's up)?[\s.?!]*$|"
    r"^(how are you( today)?|how('s| is) it going|what('s| is) up|who are you|what can you do)[\s.?!]*$",
    re.I,
)

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class ResolvedDocument:
    """Minimal view of a document record the router needs to decide routing."""

    def __init__(self, document_id: str, source_type: str, status: str):
        self.document_id = document_id
        self.source_type = (source_type or "").lower()
        self.status = status

    @property
    def is_image(self) -> bool:
        return self.source_type in IMAGE_EXTENSIONS


class QueryRouter:
    def route_decision(
        self,
        question: str,
        resolved_documents: List[ResolvedDocument],
        has_any_documents: bool,
        web_search_available: bool,
        forced_mode: Optional[str] = None,
        explicit_doc_selection: bool = False,
    ) -> RoutingDecision:
        """Analyze user query and context, returning a structured RoutingDecision."""
        # 1. Forced mode overrides
        if forced_mode and forced_mode != "AUTO":
            return self._build_forced_decision(forced_mode, web_search_available)

        cleaned_q = question.strip()

        # 2. General greetings / chat
        if _GENERAL_GREETINGS.match(cleaned_q):
            return RoutingDecision(
                intent="general_knowledge",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                confidence=1.0,
                reasoning="General greeting or conversational query.",
                fallback_sources=[],
            )

        # 3. Intent signals
        is_explicit_web = bool(_EXPLICIT_WEB_PATTERNS.search(cleaned_q))
        is_temporal = bool(_TEMPORAL_PATTERNS.search(cleaned_q))
        wants_doc = bool(_DOC_PATTERNS.search(cleaned_q))

        image_docs = [d for d in resolved_documents if d.is_image and d.status == "completed"]
        text_docs = [d for d in resolved_documents if not d.is_image and d.status == "completed"]

        # Rule 1 & 6: Explicit web search request (must never be blocked by document RAG)
        if is_explicit_web:
            # Check if user also explicitly asked to cross-reference with document
            if wants_doc and text_docs:
                return RoutingDecision(
                    intent="hybrid",
                    sources=["document", "web", "llm"],
                    web_required=True,
                    document_required=True,
                    vision_required=False,
                    confidence=0.95,
                    reasoning="Explicit web search combined with document query.",
                    fallback_sources=["web", "llm"],
                )
            return RoutingDecision(
                intent="web_research",
                sources=["web", "llm"],
                web_required=True,
                document_required=False,
                vision_required=False,
                confidence=0.98,
                reasoning="Explicit web search query requested by user.",
                fallback_sources=["llm"],
            )

        # Rule 5: Active image document present with no conflicting text documents
        wants_image = bool(_IMAGE_PATTERNS.search(cleaned_q))
        if image_docs and not text_docs and not is_temporal:
            if wants_image or explicit_doc_selection:
                return RoutingDecision(
                    intent="image_qa",
                    sources=["vision", "llm"],
                    web_required=False,
                    document_required=False,
                    vision_required=True,
                    confidence=0.95,
                    reasoning="Active image document in context requiring visual inspection.",
                    fallback_sources=["llm"],
                )

        # Rule 6: Hybrid requests (both document and temporal/live web needed)
        if (wants_doc or explicit_doc_selection) and text_docs and is_temporal:
            return RoutingDecision(
                intent="hybrid",
                sources=["document", "web", "llm"],
                web_required=True,
                document_required=True,
                vision_required=False,
                confidence=0.9,
                reasoning="Query combines document content with current/fresh web information.",
                fallback_sources=["web", "llm"],
            )

        # Rule 4: Temporal / live external knowledge question
        if is_temporal:
            return RoutingDecision(
                intent="web_research",
                sources=["web", "llm"],
                web_required=True,
                document_required=False,
                vision_required=False,
                confidence=0.9,
                reasoning="Time-sensitive or current news query requiring live web data.",
                fallback_sources=["llm"],
            )

        # Rule 3: Document QA vs General Knowledge
        # A question is document QA if:
        # a) User explicitly passed document_ids for this query, OR
        # b) User query explicitly mentions document keywords AND documents are available.
        if (explicit_doc_selection or wants_doc) and (text_docs or has_any_documents):
            return RoutingDecision(
                intent="document_qa",
                sources=["document", "llm"],
                web_required=False,
                document_required=True,
                vision_required=False,
                confidence=0.9,
                reasoning="Query specifically targets document content.",
                fallback_sources=["web", "llm"] if web_search_available else ["llm"],
            )

        # If image docs and text docs are both selected, let the classifier resolve
        if image_docs and text_docs:
            return self._llm_classify(
                cleaned_q,
                has_any_documents=bool(text_docs or has_any_documents),
                web_search_available=web_search_available,
                has_image_doc=True,
            )

        # If no document was explicitly selected and query does NOT reference documents,
        # it is a general knowledge question (Rule 3).
        if not explicit_doc_selection and not wants_doc:
            return RoutingDecision(
                intent="general_knowledge",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                confidence=0.95,
                reasoning="General question without document or live-web indicators.",
                fallback_sources=[],
            )

        # Ambiguous: consult classifier
        return self._llm_classify(
            cleaned_q,
            has_any_documents=has_any_documents,
            web_search_available=web_search_available,
            has_image_doc=bool(image_docs),
        )

    def route(
        self,
        question: str,
        resolved_documents: List[ResolvedDocument],
        has_any_documents: bool,
        web_search_available: bool,
        forced_mode: Optional[str] = None,
        explicit_doc_selection: bool = False,
    ) -> str:
        """Legacy helper returning route string ('GENERAL_LLM' | 'DOCUMENT_RAG' | ...)."""
        decision = self.route_decision(
            question=question,
            resolved_documents=resolved_documents,
            has_any_documents=has_any_documents,
            web_search_available=web_search_available,
            forced_mode=forced_mode,
            explicit_doc_selection=explicit_doc_selection,
        )
        return decision.to_legacy_route()

    def _build_forced_decision(self, forced_mode: str, web_search_available: bool) -> RoutingDecision:
        mode = forced_mode.upper()
        if mode == "GENERAL_LLM":
            return RoutingDecision(
                intent="general_knowledge",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                confidence=1.0,
                reasoning="Forced mode: GENERAL_LLM",
            )
        if mode == "DOCUMENT_RAG":
            return RoutingDecision(
                intent="document_qa",
                sources=["document", "llm"],
                web_required=False,
                document_required=True,
                vision_required=False,
                confidence=1.0,
                reasoning="Forced mode: DOCUMENT_RAG",
                fallback_sources=["web", "llm"] if web_search_available else ["llm"],
            )
        if mode == "WEB_SEARCH":
            return RoutingDecision(
                intent="web_research",
                sources=["web", "llm"],
                web_required=True,
                document_required=False,
                vision_required=False,
                confidence=1.0,
                reasoning="Forced mode: WEB_SEARCH",
                fallback_sources=["llm"],
            )
        if mode == "VISION":
            return RoutingDecision(
                intent="image_qa",
                sources=["vision", "llm"],
                web_required=False,
                document_required=False,
                vision_required=True,
                confidence=1.0,
                reasoning="Forced mode: VISION",
                fallback_sources=["llm"],
            )
        if mode == "HYBRID":
            return RoutingDecision(
                intent="hybrid",
                sources=["document", "web", "llm"],
                web_required=True,
                document_required=True,
                vision_required=False,
                confidence=1.0,
                reasoning="Forced mode: HYBRID",
                fallback_sources=["web", "llm"],
            )
        return RoutingDecision(
            intent="general_knowledge",
            sources=["llm"],
            confidence=1.0,
            reasoning=f"Unrecognized forced mode {forced_mode}, defaulting to general knowledge",
        )

    def _llm_classify(
        self,
        question: str,
        has_any_documents: bool,
        web_search_available: bool,
        has_image_doc: bool,
    ) -> RoutingDecision:
        """Call LLM classifier for ambiguous queries, with fallback to general_knowledge."""
        try:
            from backend.services.llm_provider import get_chat_llm

            options = ["GENERAL_LLM"]
            if has_any_documents:
                options.append("DOCUMENT_RAG")
            if has_image_doc:
                options.append("VISION")
            if web_search_available:
                options.append("WEB_SEARCH")
            if has_any_documents and web_search_available:
                options.append("HYBRID")

            llm = get_chat_llm(temperature=0.0)
            prompt = (
                "Classify the user's question into exactly one label from this list: "
                f"{options}.\n"
                "- GENERAL_LLM: general knowledge question needing no document or live web data.\n"
                "- DOCUMENT_RAG: specifically requires user's uploaded text documents.\n"
                "- VISION: asks about visual/diagram/image content of an uploaded image.\n"
                "- WEB_SEARCH: needs current/fresh external information from the web.\n"
                "- HYBRID: needs both uploaded documents and live web information.\n"
                f"Question: {question}\n"
                "Reply with only the label."
            )
            resp = llm.invoke(prompt)
            label = (resp.content or "").strip().upper()

            if "VISION" in label and has_image_doc:
                return RoutingDecision(
                    intent="image_qa",
                    sources=["vision", "llm"],
                    vision_required=True,
                    confidence=0.85,
                    reasoning="LLM classifier selected VISION",
                )
            if "WEB_SEARCH" in label and web_search_available:
                return RoutingDecision(
                    intent="web_research",
                    sources=["web", "llm"],
                    web_required=True,
                    confidence=0.85,
                    reasoning="LLM classifier selected WEB_SEARCH",
                    fallback_sources=["llm"],
                )
            if "HYBRID" in label and has_any_documents and web_search_available:
                return RoutingDecision(
                    intent="hybrid",
                    sources=["document", "web", "llm"],
                    document_required=True,
                    web_required=True,
                    confidence=0.85,
                    reasoning="LLM classifier selected HYBRID",
                    fallback_sources=["web", "llm"],
                )
            if "DOCUMENT_RAG" in label and has_any_documents:
                return RoutingDecision(
                    intent="document_qa",
                    sources=["document", "llm"],
                    document_required=True,
                    confidence=0.85,
                    reasoning="LLM classifier selected DOCUMENT_RAG",
                    fallback_sources=["web", "llm"] if web_search_available else ["llm"],
                )
        except Exception as e:
            logger.warning(f"LLM query classification failed, defaulting to general_knowledge: {e}")

        # Safe default: general knowledge assistant
        if has_image_doc:
            return RoutingDecision(
                intent="image_qa",
                sources=["vision", "llm"],
                vision_required=True,
                confidence=0.6,
                reasoning="Classifier fallback: active image document present.",
            )
        return RoutingDecision(
            intent="general_knowledge",
            sources=["llm"],
            confidence=0.7,
            reasoning="Classifier fallback: defaulting to general knowledge assistant.",
        )


query_router = QueryRouter()
