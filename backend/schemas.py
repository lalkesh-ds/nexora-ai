from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    source_type: str
    status: str
    pages: Optional[int] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    documents: List[DocumentInfo]


class SourceCitation(BaseModel):
    filename: str
    document_id: str
    page_number: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class WebCitation(BaseModel):
    title: Optional[str] = None
    url: str
    snippet: Optional[str] = None


class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None  # Supabase persistent conversation id
    document_ids: Optional[List[str]] = None  # None/empty = search all documents
    mode: Optional[
        Literal["AUTO", "GENERAL_LLM", "DOCUMENT_RAG", "VISION", "WEB_SEARCH", "HYBRID"]
    ] = "AUTO"


class EvidenceBreakdown(BaseModel):
    from_documents: bool = False
    from_web: bool = False
    from_general_knowledge: bool = False


class RoutingDecision(BaseModel):
    intent: Literal[
        "general_knowledge",
        "document_qa",
        "web_research",
        "image_qa",
        "hybrid",
        "calculation",
        "code_assistance",
    ] = "general_knowledge"
    sources: List[str] = Field(default_factory=lambda: ["llm"])
    selected_tools: List[str] = Field(default_factory=list)
    web_required: bool = False
    document_required: bool = False
    vision_required: bool = False
    requires_web: bool = False
    requires_document_retrieval: bool = False
    requires_vision: bool = False
    requires_calculation: bool = False
    requires_code_execution: bool = False
    requires_freshness: bool = False
    confidence: float = 1.0
    reason: Optional[str] = None
    reasoning: Optional[str] = None
    search_query: Optional[str] = None
    verification_required: bool = True
    fallback_sources: List[str] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if self.web_required and not self.requires_web:
            self.requires_web = True
        elif self.requires_web and not self.web_required:
            self.web_required = True

        if self.document_required and not self.requires_document_retrieval:
            self.requires_document_retrieval = True
        elif self.requires_document_retrieval and not self.document_required:
            self.document_required = True

        if self.vision_required and not self.requires_vision:
            self.requires_vision = True
        elif self.requires_vision and not self.vision_required:
            self.vision_required = True

        if self.reason and not self.reasoning:
            self.reasoning = self.reason
        elif self.reasoning and not self.reason:
            self.reason = self.reasoning

        if not self.selected_tools:
            tools = []
            if self.requires_web or self.web_required:
                tools.append("web_search")
            if self.requires_document_retrieval or self.document_required:
                tools.append("document_retriever")
            if self.requires_vision or self.vision_required:
                tools.append("vision_analyzer")
            if self.requires_calculation:
                tools.append("calculator")
            if self.requires_code_execution:
                tools.append("code_execution")
            self.selected_tools = tools

    def to_legacy_route(self) -> str:
        mapping = {
            "general_knowledge": "GENERAL_LLM",
            "document_qa": "DOCUMENT_RAG",
            "web_research": "WEB_SEARCH",
            "image_qa": "VISION",
            "hybrid": "HYBRID",
            "calculation": "GENERAL_LLM",
            "code_assistance": "GENERAL_LLM",
        }
        return mapping.get(self.intent, "GENERAL_LLM")


class VerificationResult(BaseModel):
    passed: bool = True
    answer_relevance: float = 1.0
    evidence_grounding: float = 1.0
    faithfulness: float = 1.0
    citation_support: float = 1.0
    evidence_coverage: float = 1.0
    unsupported_claims: List[str] = Field(default_factory=list)
    hallucination_risk: Literal["low", "medium", "high"] = "low"
    is_grounded: bool = True
    confidence_score: float = 1.0
    repair_action: Optional[str] = None
    repair_reason: Optional[str] = None
    repair_attempts: int = 0


class QueryResponse(BaseModel):
    answer: str
    route_used: str
    session_id: str
    document_citations: List[SourceCitation] = Field(default_factory=list)
    web_citations: List[WebCitation] = Field(default_factory=list)
    evidence: EvidenceBreakdown = Field(default_factory=EvidenceBreakdown)
    warnings: List[str] = Field(default_factory=list)
    # Populated only when route_used == "VISION": which image was looked at,
    # and whether the vision LLM answered directly or we fell back to OCR.
    vision_document_id: Optional[str] = None
    used_vision_llm: Optional[bool] = None
    routing: Optional[RoutingDecision] = None
    verification: Optional[VerificationResult] = None
    trace_id: Optional[str] = None


class VisionQueryResponse(BaseModel):
    answer: str
    extracted_text: Optional[str] = None
    used_ocr: bool = False
    warnings: List[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    role: str
    content: str


class ConversationHistory(BaseModel):
    session_id: str
    turns: List[ConversationTurn]
