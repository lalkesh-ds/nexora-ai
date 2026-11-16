"""
Unit tests for newly added features:
- QueryPlanner
- LongTermMemoryService
- AdditionalToolRouter
- AudioService / Audio Routes
- Streaming Generator
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.services.query_planner import query_planner, PlanResult
from backend.services.long_term_memory import long_term_memory
from backend.services.tool_router import additional_tool_router
from backend.services.audio_service import audio_service


def test_query_planner_simple_passthrough():
    result = query_planner.plan("What is the capital of France?")
    assert not result.is_complex
    assert len(result.sub_queries) == 1
    assert result.sub_queries[0] == "What is the capital of France?"


def test_query_planner_multi_question_split():
    result = query_planner.plan("What is paracetamol? And what is its maximum dosage?")
    assert result.is_complex
    assert len(result.sub_queries) >= 2


def test_tool_router_calculator():
    res = additional_tool_router.execute_tool("calculator", expression="25 * 4 + 10")
    assert res.success
    assert res.output == "110"


def test_tool_router_database_stats():
    res = additional_tool_router.execute_tool("database", query_type="document_stats")
    assert res.success
    assert "total_chunks_indexed" in res.output


def test_long_term_memory_roundtrip():
    user_id = "test_user_memory_123"
    long_term_memory.update(
        user_id=user_id,
        question="I am allergic to penicillin and aspirin",
        answer="Noted, you have allergies to penicillin and aspirin.",
    )
    relevant = long_term_memory.retrieve_relevant(user_id, "penicillin dosage")
    assert "penicillin" in relevant.lower() or "aspirin" in relevant.lower()


def test_audio_service_formats():
    from backend.services.audio_service import SUPPORTED_AUDIO_FORMATS
    assert ".mp3" in SUPPORTED_AUDIO_FORMATS
    assert ".wav" in SUPPORTED_AUDIO_FORMATS
    assert ".m4a" in SUPPORTED_AUDIO_FORMATS
    assert ".webm" in SUPPORTED_AUDIO_FORMATS
