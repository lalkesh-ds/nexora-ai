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
    ] = "general_knowledge"
    sources: List[str] = Field(default_factory=lambda: ["llm"])
    web_required: bool = False
    document_required: bool = False
    vision_required: bool = False
    confidence: float = 1.0
    reasoning: Optional[str] = None
    fallback_sources: List[str] = Field(default_factory=list)

    def to_legacy_route(self) -> str:
        mapping = {
            "general_knowledge": "GENERAL_LLM",
            "document_qa": "DOCUMENT_RAG",
            "web_research": "WEB_SEARCH",
            "image_qa": "VISION",
            "hybrid": "HYBRID",
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
