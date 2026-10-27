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
from backend.services.freshness_service import freshness_service

_CALCULATION_PATTERNS = re.compile(
    r"\b("
    r"calculate|computation|cagr|compound annual growth|solve for|evaluate equation|"
    r"percentage\s+of|standard\s+deviation|mean\s+of|median\s+of|convert\s+\d+|"
    r"what\s+is\s+\d+[\s\+\-\*\/]\d+"
    r")\b",
    re.I,
)

_CODE_PATTERNS = re.compile(
    r"\b("
    r"debug|"
    r"write\s+(?:a\s+)?(?:python|javascript|typescript|c\+\+|sql|bash|go|rust|java|react)?\s*(?:script|function|program|class|worker|component|hook|endpoint|algorithm|code|pipeline)|"
    r"write\s+(?:a\s+)?(?:python|javascript|typescript|c\+\+|sql|bash|go|rust|java)\b|"
    r"fix\s+(?:this\s+|the\s+)?(?:bug|error|issue|code|traceback)|"
    r"syntax\s+error|typeerror|attributeerror|valueerror|traceback|regex\s+for|"
    r"how\s+(?:do\s+I|to)\s+(?:implement|code|write|program|build)\b"
    r")\b",
    re.I,
)

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
    r"launched|announcement|upcoming|brand new|202[4-9]|"
    r"gpt-?[5-9]|"
    r"gpt.*(astra|omni|o\d)|"
    r"project\s+astra|"
    r"claude-?[4-9]|"
    r"gemini-?[2-9]|"
    r"llama-?[4-9]|"
    r"deepseek(-r\d|-v\d)?|"
    r"grok-?[2-9]|"
    r"sora\b"
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
    r"document|uploaded|pdf|attached|attachment|"
    r"(this|the|my)\s+(file|paper|report|assignment|document|pdf|notes|record(s)?|prescription|scan|chart)|"
    r"according to (the|this|my)|"
    r"(in|from)\s+(the|this|my)\s+(document|file|pdf|report|paper|notes|record(s)?|attachment)|"
    r"page \d+|"
    r"section \d+|"
    r"what does section \d+ say|"
    r"summarize\s+(this|the|my|uploaded)\b|"
    r"find (the|all)?\s*.*(mentioned|described|listed|stated)\s+(in|from)|"
    r"patient('s)?\s+(notes|record(s)?|chart|history|report|file)|"
    r"extract\s+(from\s+)?(this|the|my)"
    r")\b",
    re.I,
)

_HYBRID_PATTERNS = re.compile(
    r"\b("
    r"(compare|contrast|cross-reference|versus|vs\.?|difference between)\b.*"
    r"\b(guideline(s)?|standard(s)?|web|online|external|published|literature|trial(s)?|market|current|recent|who)"
    r"|"
    r"\b(both|together)\b.*\b(document|pdf|file|report|paper)\b.*\b(web|internet|online|guidelines)"
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

        # 3. Intent signals & Freshness evaluation
        freshness_eval = freshness_service.evaluate(cleaned_q)
        requires_freshness = freshness_eval.get("requires_freshness", False)
        suggested_search_query = freshness_eval.get("suggested_search_query")
        freshness_reasons = freshness_eval.get("reasons", [])

        is_explicit_web = bool(_EXPLICIT_WEB_PATTERNS.search(cleaned_q))
        is_temporal = bool(_TEMPORAL_PATTERNS.search(cleaned_q)) or requires_freshness
        wants_doc = bool(_DOC_PATTERNS.search(cleaned_q))
        wants_calc = bool(_CALCULATION_PATTERNS.search(cleaned_q))
        wants_code = bool(_CODE_PATTERNS.search(cleaned_q))

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
                    requires_freshness=True,
                    search_query=suggested_search_query,
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
                requires_freshness=True,
                search_query=suggested_search_query,
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
                    requires_freshness=False,
                    confidence=0.95,
                    reasoning="Active image document in context requiring visual inspection.",
                    fallback_sources=["llm"],
                )

        # Rule 6: Hybrid requests (both document and temporal/live web/guidelines needed)
        is_hybrid_query = bool(_HYBRID_PATTERNS.search(cleaned_q))
        if (wants_doc or explicit_doc_selection) and (text_docs or has_any_documents) and (is_temporal or is_hybrid_query):
            return RoutingDecision(
                intent="hybrid",
                sources=["document", "web", "llm"],
                web_required=True,
                document_required=True,
                vision_required=False,
                requires_freshness=is_temporal,
                search_query=suggested_search_query,
                confidence=0.92,
                reasoning="Query combines document content with external web/guideline information.",
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
                requires_freshness=True,
                search_query=suggested_search_query,
                confidence=0.92,
                reasoning=f"Time-sensitive or volatile real-world subject: {'; '.join(freshness_reasons) if freshness_reasons else 'freshness required'}.",
                fallback_sources=["llm"],
            )

        # Rule 3: Document QA vs General Knowledge
        if (explicit_doc_selection or wants_doc) and (text_docs or has_any_documents):
            return RoutingDecision(
                intent="document_qa",
                sources=["document", "llm"],
                web_required=False,
                document_required=True,
                vision_required=False,
                requires_freshness=False,
                confidence=0.9,
                reasoning="Query specifically targets document content.",
                fallback_sources=["web", "llm"] if web_search_available else ["llm"],
            )

        # Calculation tool routing
        if wants_calc and not (wants_doc or explicit_doc_selection):
            return RoutingDecision(
                intent="calculation",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                requires_calculation=True,
                requires_freshness=False,
                confidence=0.95,
                reasoning="Mathematical calculation query.",
                fallback_sources=[],
            )

        # Code assistance
        if wants_code and not (wants_doc or explicit_doc_selection):
            return RoutingDecision(
                intent="code_assistance",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                requires_code_execution=True,
                requires_freshness=False,
                confidence=0.95,
                reasoning="Programming and code assistance query.",
                fallback_sources=[],
            )

        # If image docs and text docs are both selected, let the classifier resolve
        if image_docs and text_docs:
            return self._llm_classify(
                cleaned_q,
                has_any_documents=bool(text_docs or has_any_documents),
                web_search_available=web_search_available,
                has_image_doc=True,
            )

        # General knowledge question
        if not explicit_doc_selection and not wants_doc:
            return RoutingDecision(
                intent="general_knowledge",
                sources=["llm"],
                web_required=False,
                document_required=False,
                vision_required=False,
                requires_freshness=False,
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
                "You are the query intent router for Nexora AI, a versatile general-purpose AI assistant.\n"
                f"Classify the user's question into exactly one label from this list: {options}.\n"
                "- GENERAL_LLM: general knowledge, reasoning, coding, history, science, concepts, or stable facts needing no document or live web data.\n"
                "- DOCUMENT_RAG: specifically asks about or requires information from the user's uploaded text documents.\n"
                "- VISION: asks about visual, diagram, chart, or image content of an uploaded image.\n"
                "- WEB_SEARCH: needs current real-world status, breaking news, recent events, or fresh external facts from the live web.\n"
                "- HYBRID: needs both uploaded documents and live external web information.\n"
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
