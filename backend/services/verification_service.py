"""
Answer Verification and Quality Control Service (Phase 5).

Evaluates candidate LLM answers post-generation for:
  - Answer relevance
  - Evidence grounding
  - Faithfulness
  - Citation / source support
  - Unsupported claims identification
  - Hallucination risk assessment ("low", "medium", "high")
  - Evidence coverage
  - Calculated factual confidence score (strictly computed, never fabricated)

Decision Architecture:
  Evidence -> LLM Answer -> Answer Verifier -> Decision (PASS / FAIL)

  If PASS:
    Returns validated response with verification report.

  If FAIL:
    Returns structured repair request to Orchestrator:
      * regenerate_answer (with strict grounding instructions)
      * retrieve_additional_evidence (re-triggers CRAG expansion)
      * rerun_web_search (re-triggers web search with refined query)
      * clarify (asks user for clarification)
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.config import settings
from backend.logger import logger
from backend.schemas import VerificationResult


# Stop words for relevance and overlap calculations
_STOP_WORDS = {
    "what", "is", "the", "and", "or", "in", "on", "for", "with", "a", "an", "to",
    "of", "about", "this", "that", "it", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "can", "could", "should", "would",
    "may", "might", "must", "shall", "will", "tell", "me", "explain", "how", "why",
    "please", "give", "list", "describe", "show", "during", "indicates", "indicate",
}

# Conversational boilerplate patterns to ignore during claim extraction
_BOILERPLATE_PATTERNS = re.compile(
    r"^(?:sure|certainly|here (?:is|are)|based on|according to|i hope this helps|"
    r"as mentioned|in summary|to summarize|hello|hi)[^.:\n]*[:.]?",
    re.I,
)


def _stem(word: str) -> str:
    """Lightweight suffix stemmer for robust keyword matching."""
    w = word.lower()
    for suff in ("ing", "tion", "sion", "ment", "ated", "ate", "ates", "ed", "es", "s"):
        if w.endswith(suff) and len(w) - len(suff) >= 3:
            return w[:-len(suff)]
    return w


class VerificationService:
    """Post-generation answer verification and quality control engine."""

    def _extract_factual_claims(self, answer: str) -> List[str]:
        """Split answer into individual sentence claims, removing trivial conversational headers."""
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", answer.strip())
        claims = []
        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean or len(s_clean) < 15:
                continue
            # Remove leading pleasantries if present
            s_stripped = _BOILERPLATE_PATTERNS.sub("", s_clean).strip()
            if len(s_stripped) >= 15:
                claims.append(s_stripped)
        return claims or ([answer.strip()] if len(answer.strip()) >= 15 else [])

    def _extract_context_text(self, context_blocks: List[str]) -> str:
        """Strip context block markup tags and combine into single clean reference text."""
        combined = " ".join(context_blocks)
        cleaned = re.sub(r"\[/?(?:DOCUMENT CONTEXT|WEB CONTEXT|WEB CONTEXT \(FALLBACK\))\]", " ", combined)
        cleaned = re.sub(r"\(filename:[^)]+\)", " ", cleaned)
        cleaned = re.sub(r"\(source:[^)]+\)", " ", cleaned)
        cleaned = re.sub(r"\(page:[^)]+\)", " ", cleaned)
        return " ".join(cleaned.split())

    def _calculate_relevance(self, question: str, answer: str) -> float:
        """Calculates relevance of answer to user question based on key query term coverage."""
        q_words = re.findall(r"[a-zA-Z0-9]+", question.lower())
        q_keywords = {_stem(w) for w in q_words if w not in _STOP_WORDS and len(w) > 2}
        if not q_keywords:
            return 1.0

        ans_words = re.findall(r"[a-zA-Z0-9]+", answer.lower())
        ans_stems = {_stem(w) for w in ans_words}
        matched = q_keywords & ans_stems
        relevance = len(matched) / len(q_keywords)
        # Scaled non-linearly to reward semantic relevance
        return round(min(relevance * 1.35, 1.0), 4)

    def _evaluate_grounding(self, claims: List[str], context_text: str) -> Tuple[float, float, List[str]]:
        """Evaluates claim-level evidence grounding and identifies unsupported claims."""
        if not claims or not context_text.strip():
            return 1.0, 1.0, []

        context_lower = context_text.lower()
        context_words = set(re.findall(r"\w+", context_lower))
        context_sentences = [cs.lower() for cs in re.split(r"[.!?]\s+", context_lower) if len(cs) > 10]

        unsupported_claims: List[str] = []

        for claim in claims:
            c_lower = claim.lower()
            c_words = set(re.findall(r"\w+", c_lower))
            keywords = {w for w in c_words if w not in _STOP_WORDS and len(w) > 2}

            # Check for critical specific factual indicators: numbers, units, dosages
            numbers_in_claim = set(re.findall(r"\b\d+(?:\.\d+)?(?:mg|g|ml|%|kg|hours|days|years|mg/dl)?\b", c_lower))

            # If numbers/dosages asserted in claim are completely absent from context
            missing_numbers = [n for n in numbers_in_claim if n not in context_lower]
            if missing_numbers:
                unsupported_claims.append(claim)
                continue

            if not keywords:
                continue

            # Check word overlap with context
            overlap = len(keywords & context_words) / len(keywords)

            # Check maximum overlap with any single context sentence
            best_sentence_overlap = 0.0
            for cs in context_sentences:
                cs_words = set(re.findall(r"\w+", cs))
                if cs_words:
                    sent_overlap = len(keywords & cs_words) / len(keywords)
                    if sent_overlap > best_sentence_overlap:
                        best_sentence_overlap = sent_overlap

            # If less than 40% keywords appear anywhere in context or best sentence overlap < 30%
            if overlap < 0.40 or (best_sentence_overlap < 0.30 and len(keywords) >= 4):
                unsupported_claims.append(claim)

        total = max(len(claims), 1)
        supported = total - len(unsupported_claims)
        grounding_score = round(supported / total, 4)
        faithfulness_score = round(1.0 - (len(unsupported_claims) / total), 4)

        return grounding_score, faithfulness_score, unsupported_claims

    def _evaluate_citations(
        self,
        answer: str,
        route: str,
        document_citations: Optional[List[Any]] = None,
        web_citations: Optional[List[Any]] = None,
    ) -> float:
        """Verifies that citations referenced in the answer match actual provided evidence."""
        # 1. General LLM: should not cite fake documents or pages
        if route == "GENERAL_LLM":
            # Check if answer fabricates document pages or filenames
            fake_doc_cites = re.findall(r"\b(?:page \d+|in the uploaded document|according to the attached file)\b", answer, re.I)
            if fake_doc_cites:
                return 0.0
            return 1.0

        # 2. Document RAG / Hybrid: check cited page numbers
        score = 1.0
        cited_pages = [int(p) for p in re.findall(r"\bpage\s+(\d+)\b", answer, re.I)]
        if cited_pages and document_citations:
            valid_pages = {c.page_number for c in document_citations if getattr(c, "page_number", None) is not None}
            if valid_pages:
                for cp in cited_pages:
                    if cp not in valid_pages:
                        score -= 0.35

        # 3. Web Search: check cited URLs
        cited_urls = re.findall(r"https?://[^\s)\]]+", answer)
        if cited_urls and web_citations:
            valid_urls = {getattr(c, "url", "") for c in web_citations}
            for cu in cited_urls:
                clean_cu = cu.rstrip(".,;")
                if not any(clean_cu.startswith(vu) or vu.startswith(clean_cu) for vu in valid_urls):
                    score -= 0.35

        return round(max(score, 0.0), 4)

    def _calculate_evidence_coverage(self, question: str, context_text: str) -> float:
        """Calculates what portion of question requirements are covered by the evidence context."""
        q_words = set(re.findall(r"\w+", question.lower()))
        keywords = {w for w in q_words if w not in _STOP_WORDS and len(w) > 2}
        if not keywords:
            return 1.0
        if not context_text.strip():
            return 0.0

        ctx_words = set(re.findall(r"\w+", context_text.lower()))
        coverage = len(keywords & ctx_words) / len(keywords)
        return round(min(coverage, 1.0), 4)

    def verify(
        self,
        question: str,
        answer: str,
        route: str,
        context_blocks: Optional[List[str]] = None,
        document_citations: Optional[List[Any]] = None,
        web_citations: Optional[List[Any]] = None,
        repair_attempts: int = 0,
    ) -> VerificationResult:
        """Post-generation verification evaluating relevance, grounding, citations,
        and hallucination risk. Strictly calculates confidence scores."""
        context_blocks = context_blocks or []
        context_text = self._extract_context_text(context_blocks)
        claims = self._extract_factual_claims(answer)

        # 1. Answer Relevance
        relevance = self._calculate_relevance(question, answer)

        # 2. Evidence Grounding & Faithfulness
        if route in ("DOCUMENT_RAG", "WEB_SEARCH", "HYBRID"):
            grounding, faithfulness, unsupported = self._evaluate_grounding(claims, context_text)
            coverage = self._calculate_evidence_coverage(question, context_text)
            is_grounded = (grounding >= 0.70 and len(unsupported) == 0)
        elif route == "VISION":
            grounding, faithfulness, unsupported = self._evaluate_grounding(claims, context_text)
            coverage = 1.0
            is_grounded = (grounding >= 0.60 and len(unsupported) == 0)
        else:  # GENERAL_LLM
            grounding = 1.0
            faithfulness = 1.0
            unsupported = []
            coverage = 1.0
            is_grounded = True

        # 3. Citation Support
        citation_support = self._evaluate_citations(
            answer=answer,
            route=route,
            document_citations=document_citations,
            web_citations=web_citations,
        )

        # 4. Hallucination Risk Assessment
        if len(unsupported) >= 2 or citation_support < 0.60 or grounding < 0.50:
            hallucination_risk = "high"
        elif len(unsupported) == 1 or grounding < 0.75 or citation_support < 0.90:
            hallucination_risk = "medium"
        else:
            hallucination_risk = "low"

        # 5. Calculated Factual Confidence Score (strictly calculated)
        if route in ("DOCUMENT_RAG", "WEB_SEARCH", "HYBRID"):
            raw_conf = (
                (0.40 * grounding)
                + (0.30 * relevance)
                + (0.20 * citation_support)
                + (0.10 * coverage)
            )
            if hallucination_risk == "high":
                raw_conf = min(raw_conf, 0.40)
        elif route == "VISION":
            raw_conf = (0.50 * grounding) + (0.50 * relevance)
            if hallucination_risk == "high":
                raw_conf = min(raw_conf, 0.45)
        else:  # GENERAL_LLM
            raw_conf = (0.60 * relevance) + (0.40 * citation_support)

        confidence_score = round(min(max(raw_conf, 0.05), 1.0), 4)

        # 6. Pass / Fail Decision
        if route in ("DOCUMENT_RAG", "WEB_SEARCH", "HYBRID"):
            passed = (grounding >= 0.70 and relevance >= 0.45 and hallucination_risk != "high")
        elif route == "VISION":
            passed = (grounding >= 0.60 and relevance >= 0.45 and hallucination_risk != "high")
        else:  # GENERAL_LLM
            passed = (relevance >= 0.45 and citation_support >= 0.90)

        # 7. Repair Action Determination (if Failed)
        repair_action = None
        repair_reason = None

        if not passed:
            if route == "DOCUMENT_RAG" and coverage < 0.40:
                repair_action = "retrieve_additional_evidence"
                repair_reason = "Retrieved document evidence lacked coverage of question requirements."
            elif route == "WEB_SEARCH" and coverage < 0.40:
                repair_action = "rerun_web_search"
                repair_reason = "Web search results lacked sufficient coverage of question keywords."
            elif unsupported:
                repair_action = "regenerate_answer"
                repair_reason = f"Answer contained {len(unsupported)} ungrounded claim(s) not supported by context."
            elif relevance < 0.60:
                repair_action = "regenerate_answer"
                repair_reason = "Candidate answer did not adequately address the user query."
            else:
                repair_action = "clarify"
                repair_reason = "Answer quality standards not met; request user clarification."

        result = VerificationResult(
            passed=passed,
            answer_relevance=relevance,
            evidence_grounding=grounding,
            faithfulness=faithfulness,
            citation_support=citation_support,
            evidence_coverage=coverage,
            unsupported_claims=unsupported,
            hallucination_risk=hallucination_risk,
            is_grounded=is_grounded,
            confidence_score=confidence_score,
            repair_action=repair_action,
            repair_reason=repair_reason,
            repair_attempts=repair_attempts,
        )

        logger.info(
            f"[VERIFY] route={route} passed={passed} grounding={grounding:.2f} "
            f"faithfulness={faithfulness:.2f} relevance={relevance:.2f} citations={citation_support:.2f} "
            f"risk={hallucination_risk} conf={confidence_score:.2f} action={repair_action}"
        )

        return result


verification_service = VerificationService()
