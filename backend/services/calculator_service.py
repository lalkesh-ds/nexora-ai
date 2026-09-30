"""
CalculatorService: deterministic evaluation of numeric expressions extracted
from OCR/vision text, so arithmetic isn't left to LLM token prediction.

Uses sympy's safe parser (no `eval`, no arbitrary code execution).
"""
import re
from typing import List, Optional

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from backend.logger import logger

_transformations = standard_transformations + (implicit_multiplication_application,)

# A conservative pattern for "looks like a calculable expression":
# digits, operators, parentheses, decimal points - nothing else.
_EXPR_PATTERN = re.compile(r"^[\d\s+\-*/^().%]+$")


class CalculatorService:
    def looks_like_expression(self, text: str) -> bool:
        return bool(text) and bool(_EXPR_PATTERN.match(text.strip()))

    def evaluate(self, expression: str) -> Optional[str]:
        try:
            expr = expression.replace("^", "**")
            result = parse_expr(expr, transformations=_transformations, evaluate=True)
            value = sympy.simplify(result)
            return str(value)
        except Exception as e:
            logger.warning(f"Deterministic evaluation failed for '{expression}': {e}")
            return None

    def extract_and_evaluate(self, text: str) -> List[dict]:
        """Find candidate arithmetic expressions in free text and evaluate each
        deterministically. Returns a list of {"expression": ..., "result": ...}.
        """
        candidates = re.findall(r"[\d.\s+\-*/^()]{3,}", text or "")
        results = []
        for c in candidates:
            c = c.strip().rstrip("=").strip()
            if not c or not any(ch.isdigit() for ch in c):
                continue
            if not any(op in c for op in "+-*/^"):
                continue
            value = self.evaluate(c)
            if value is not None:
                results.append({"expression": c, "result": value})
        return results


calculator_service = CalculatorService()
