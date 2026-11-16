"""
Additional Tool Router for Nexora AI.

Target Flow:
       ADDITIONAL TOOL ROUTER
                 |
  +--------------+---------------+
  |              |               |
  v              v               v
PYTHON         EXTERNAL API     VISION
CALCULATOR      DATABASE       IMAGE ANALYSIS
  |              |               |
  +--------------+---------------+
                 |
                 v
        EVIDENCE AGGREGATOR

This service provides a modular dispatch layer for non-retrieval tools:
- Python Calculator: deterministic math evaluation via sympy / safe python sandbox
- Vision Analysis: multimodal image inspection and OCR
- External API / Database: database queries (session, document stats, custom endpoints)
"""
from typing import Any, Dict, List, Optional
from backend.logger import logger
from backend.services.calculator_service import calculator_service
from backend.services.ocr_vision_service import ocr_vision_service


class ToolExecutionResult:
    def __init__(self, tool_name: str, success: bool, output: Any, metadata: Optional[Dict[str, Any]] = None):
        self.tool_name = tool_name
        self.success = success
        self.output = output
        self.metadata = metadata or {}


class AdditionalToolRouter:
    """Dispatches execution to specialized auxiliary tools and aggregates results."""

    def __init__(self):
        self._tools = {
            "calculator": self._execute_calculator,
            "vision": self._execute_vision,
            "database": self._execute_database_query,
        }

    def execute_tool(self, tool_name: str, **kwargs) -> ToolExecutionResult:
        """Route and execute a specific auxiliary tool."""
        handler = self._tools.get(tool_name)
        if not handler:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output=f"Tool '{tool_name}' not recognized.",
            )
        try:
            return handler(**kwargs)
        except Exception as e:
            logger.warning(f"[TOOL_ROUTER] Failed executing {tool_name}: {e}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output=str(e),
            )

    def _execute_calculator(self, expression: str = "", text: str = "") -> ToolExecutionResult:
        """Evaluate mathematical expressions deterministically."""
        if expression:
            val = calculator_service.evaluate(expression)
            if val is not None:
                return ToolExecutionResult(
                    tool_name="calculator",
                    success=True,
                    output=val,
                    metadata={"expression": expression},
                )
        if text:
            extracted = calculator_service.extract_and_evaluate(text)
            return ToolExecutionResult(
                tool_name="calculator",
                success=bool(extracted),
                output=extracted,
            )
        return ToolExecutionResult(tool_name="calculator", success=False, output="No expression or text provided")

    def _execute_vision(self, pil_image, question: str = "") -> ToolExecutionResult:
        """Execute multimodal vision / OCR extraction on an image."""
        extracted_or_ans, used_vision_llm, failure_reason = ocr_vision_service.answer_image_question(
            pil_image, question or "Describe this image in detail."
        )
        return ToolExecutionResult(
            tool_name="vision",
            success=bool(extracted_or_ans),
            output=extracted_or_ans,
            metadata={"used_vision_llm": used_vision_llm, "failure_reason": failure_reason},
        )

    def _execute_database_query(self, query_type: str = "document_stats", **kwargs) -> ToolExecutionResult:
        """Inspect internal SQLite databases for sessions, documents, and memory."""
        import sqlite3
        from backend.config import settings
        try:
            with sqlite3.connect(settings.SESSION_STORE_PATH) as conn:
                cursor = conn.cursor()
                if query_type == "document_stats":
                    row = cursor.execute("SELECT COUNT(*) FROM document_chunks").fetchone()
                    chunk_count = row[0] if row else 0
                    return ToolExecutionResult(
                        tool_name="database",
                        success=True,
                        output={"total_chunks_indexed": chunk_count},
                    )
                elif query_type == "session_turns":
                    session_id = kwargs.get("session_id")
                    if not session_id:
                        return ToolExecutionResult(tool_name="database", success=False, output="session_id required")
                    rows = cursor.execute(
                        "SELECT role, content, created_at FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT 10",
                        (session_id,),
                    ).fetchall()
                    return ToolExecutionResult(
                        tool_name="database",
                        success=True,
                        output=[{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows],
                    )
                else:
                    return ToolExecutionResult(tool_name="database", success=False, output=f"Unknown query_type {query_type}")
        except Exception as e:
            return ToolExecutionResult(tool_name="database", success=False, output=str(e))


additional_tool_router = AdditionalToolRouter()
