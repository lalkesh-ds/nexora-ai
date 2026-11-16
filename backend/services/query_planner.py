"""
QueryPlanner: Pre-routing stage that decomposes complex multi-part questions
into focused sub-queries BEFORE the router sees them.

Architecture:
  User Question
  -> Complexity Assessment (is this multi-part / compound?)
  -> If simple: pass through unchanged
  -> If complex: decompose into 2-4 sub-questions
  -> Return PlanResult with sub-queries + synthesis strategy

This runs BEFORE the QueryRouter so the router always sees well-formed,
focused questions rather than compound blobs. The orchestrator then runs
all sub-queries and synthesizes the results.

Performance: uses regex heuristics first; only calls the LLM for
genuinely ambiguous cases to avoid adding latency to simple queries.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from backend.logger import logger


# Patterns that signal a multi-part / compound question
_COMPOUND_PATTERNS = re.compile(
    r"\b("
    r"and\s+(also|additionally|furthermore|moreover|what|how|why|when|where|who)|"
    r"as\s+well\s+as|"
    r"in\s+addition\s+to|"
    r"furthermore|"
    r"also\s+(tell|explain|describe|show|give|list|find)|"
    r"what\s+(are|is)\s+.{5,40}\s+and\s+(what|how|why|when|where|who)|"
    r"(?:first|second|third|finally|lastly)[,.]?\s+\w|"
    r"(?:compare|contrast|difference\s+between)\b.*\band\b"
    r")\b",
    re.I,
)

_QUESTION_SPLITTERS = re.compile(
    r"\?(?:\s+(?:also|and|additionally|furthermore|moreover))?\s+",
    re.I,
)

_MIN_PART_LEN = 10  # sub-query shorter than this is noise


@dataclass
class PlanResult:
    """Result from the QueryPlanner."""
    original_question: str
    is_complex: bool
    sub_queries: List[str] = field(default_factory=list)
    synthesis_strategy: str = "direct"  # "direct" | "sequential" | "parallel" | "compare"
    complexity_reason: str = ""

    @property
    def primary_query(self) -> str:
        """The main/first sub-query to send to the router."""
        return self.sub_queries[0] if self.sub_queries else self.original_question

    def all_queries(self) -> List[str]:
        """All queries to execute (original if simple, sub-queries if complex)."""
        if not self.is_complex or not self.sub_queries:
            return [self.original_question]
        return self.sub_queries


class QueryPlanner:
    """
    Pre-routing query planner. Decomposes complex multi-part questions
    into focused sub-queries before they reach the router.
    """

    def plan(self, question: str, history: Optional[str] = None) -> PlanResult:
        """
        Analyze the question. Return a PlanResult with decomposition
        if the question is complex, or a passthrough for simple queries.
        """
        q = question.strip()

        # Fast path: short questions are almost never multi-part
        word_count = len(q.split())
        if word_count <= 8:
            return PlanResult(
                original_question=q,
                is_complex=False,
                sub_queries=[q],
                synthesis_strategy="direct",
                complexity_reason="Short query — direct passthrough.",
            )

        # Check for multiple question marks (clear multi-part signal)
        q_marks = q.count("?")
        if q_marks >= 2:
            parts = self._split_on_question_marks(q)
            if len(parts) >= 2:
                strategy = "sequential" if len(parts) == 2 else "parallel"
                logger.info(
                    f"[PLANNER] Multi-question detected ({q_marks} '?'). "
                    f"Decomposed into {len(parts)} sub-queries."
                )
                return PlanResult(
                    original_question=q,
                    is_complex=True,
                    sub_queries=parts,
                    synthesis_strategy=strategy,
                    complexity_reason=f"Multiple question marks detected ({q_marks}).",
                )

        # Check regex compound patterns
        if _COMPOUND_PATTERNS.search(q):
            # Try heuristic split first (fast, no LLM)
            parts = self._heuristic_split(q)
            if len(parts) >= 2:
                strategy = self._pick_strategy(q)
                logger.info(
                    f"[PLANNER] Compound query detected via pattern. "
                    f"Decomposed into {len(parts)} sub-queries."
                )
                return PlanResult(
                    original_question=q,
                    is_complex=True,
                    sub_queries=parts,
                    synthesis_strategy=strategy,
                    complexity_reason="Compound conjunction or comparison pattern detected.",
                )

            # Heuristic split failed — use LLM for decomposition
            parts = self._llm_decompose(q, history)
            if parts and len(parts) >= 2:
                strategy = self._pick_strategy(q)
                logger.info(
                    f"[PLANNER] LLM decomposed complex query into {len(parts)} sub-queries."
                )
                return PlanResult(
                    original_question=q,
                    is_complex=True,
                    sub_queries=parts,
                    synthesis_strategy=strategy,
                    complexity_reason="LLM detected multi-part question structure.",
                )

        # Simple question — pass through
        return PlanResult(
            original_question=q,
            is_complex=False,
            sub_queries=[q],
            synthesis_strategy="direct",
            complexity_reason="Single-focus question — direct passthrough.",
        )

    def _split_on_question_marks(self, question: str) -> List[str]:
        """Split on '?' boundaries and clean each part."""
        raw = _QUESTION_SPLITTERS.split(question)
        parts = []
        for p in raw:
            p = p.strip().rstrip("?").strip()
            if len(p) >= _MIN_PART_LEN:
                # Ensure each part ends as a proper question
                if not p.endswith("?"):
                    p = p + "?"
                parts.append(p)
        return parts

    def _heuristic_split(self, question: str) -> List[str]:
        """
        Try splitting on 'and also', conjunction boundaries, or
        punctuation that separates independent clauses.
        """
        # Split on '. Also ', '? Also ', ', also ', 'and also'
        delimiters = [
            r"\?\s+(?:also\s+)?",
            r"\.\s+(?:Also|Additionally|Furthermore|Moreover)\s+",
            r",\s+(?:and\s+)?(?:also|additionally|furthermore)\s+",
            r"\band\s+also\s+",
        ]
        for delim in delimiters:
            parts = re.split(delim, question, flags=re.I)
            cleaned = [p.strip() for p in parts if len(p.strip()) >= _MIN_PART_LEN]
            if len(cleaned) >= 2:
                return cleaned

        # Try splitting on 'and what/how/why/when/where/who'
        m = re.search(
            r"^(.{10,}?)\s+and\s+(what|how|why|when|where|who)\s+(.+)$",
            question,
            re.I | re.S,
        )
        if m:
            part1 = m.group(1).strip()
            part2 = (m.group(2) + " " + m.group(3)).strip()
            if len(part1) >= _MIN_PART_LEN and len(part2) >= _MIN_PART_LEN:
                return [part1, part2]

        return [question]

    def _llm_decompose(self, question: str, history: Optional[str] = None) -> List[str]:
        """Call the LLM to decompose a complex question. Returns [] on failure."""
        try:
            from backend.services.llm_provider import get_chat_llm

            context = f"Conversation history:\n{history}\n\n" if history else ""
            prompt = (
                f"{context}"
                "Break the following complex question into 2 to 4 focused, independent sub-questions "
                "that can each be answered separately. Each sub-question must be standalone "
                "(no pronouns that refer to other sub-questions). "
                "Output ONLY the sub-questions, one per line, with no numbering, bullets, or extra text.\n\n"
                f"Question: {question}"
            )
            llm = get_chat_llm(temperature=0.0)
            resp = llm.invoke(prompt)
            lines = [
                ln.strip().lstrip("-•*0123456789.)").strip()
                for ln in (resp.content or "").split("\n")
                if ln.strip()
            ]
            return [ln for ln in lines if len(ln) >= _MIN_PART_LEN]
        except Exception as e:
            logger.warning(f"[PLANNER] LLM decomposition failed: {e}")
            return []

    def _pick_strategy(self, question: str) -> str:
        """Infer the synthesis strategy from the question text."""
        q_lower = question.lower()
        if any(w in q_lower for w in ("compare", "contrast", "difference between", "vs", "versus")):
            return "compare"
        if any(w in q_lower for w in ("first", "then", "after", "step")):
            return "sequential"
        return "parallel"

    def synthesize(
        self,
        original_question: str,
        sub_answers: List[str],
        plan: PlanResult,
    ) -> str:
        """
        Merge multiple sub-answers into one coherent final answer.
        Only called when plan.is_complex is True and there are ≥ 2 sub-answers.
        """
        if len(sub_answers) == 1:
            return sub_answers[0]

        if plan.synthesis_strategy == "compare":
            combined = "\n\n".join(
                f"**Part {i+1}:** {a}" for i, a in enumerate(sub_answers)
            )
            try:
                from backend.services.llm_provider import get_chat_llm

                llm = get_chat_llm(temperature=0.1)
                prompt = (
                    "You have been given answers to individual parts of a compound question. "
                    "Synthesize them into one well-structured, comparative response.\n\n"
                    f"Original question: {original_question}\n\n"
                    f"Individual answers:\n{combined}\n\n"
                    "Provide a unified comparative answer:"
                )
                resp = llm.invoke(prompt)
                return resp.content or combined
            except Exception as e:
                logger.warning(f"[PLANNER] Synthesis LLM call failed: {e}")
                return combined

        elif plan.synthesis_strategy == "sequential":
            return "\n\n".join(sub_answers)

        else:  # parallel
            return "\n\n".join(sub_answers)


query_planner = QueryPlanner()
