"""
Phase 2 Automated Verification Tests:
Permanent Chat History, Conversation Lifecycle, Ownership, Error Recovery & Idempotency.
"""
from __future__ import annotations

import time
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt

from backend.schemas import QueryResponse

TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long!!"
USER_ALICE = "11111111-1111-1111-1111-111111111111"
USER_BOB   = "22222222-2222-2222-2222-222222222222"


def _token(user_id: str, email: str = "alice@test.com") -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
        "iat": now - 10,
        "exp": now + 3600,
        "role": "authenticated",
        "email_confirmed_at": "2024-01-01T00:00:00Z",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def client(tmp_path):
    from backend.main import app
    from backend.config import settings

    test_db = str(tmp_path / "test_sessions.db")
    orig_path = settings.SESSION_STORE_PATH
    orig_secret = settings.SUPABASE_JWT_SECRET
    orig_sb_url = settings.SUPABASE_URL
    orig_sb_key = settings.SUPABASE_SERVICE_ROLE_KEY

    settings.SESSION_STORE_PATH = test_db
    settings.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
    # Explicitly test SQLite persistence engine in isolation
    settings.SUPABASE_URL = ""
    settings.SUPABASE_SERVICE_ROLE_KEY = ""

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    settings.SESSION_STORE_PATH = orig_path
    settings.SUPABASE_JWT_SECRET = orig_secret
    settings.SUPABASE_URL = orig_sb_url
    settings.SUPABASE_SERVICE_ROLE_KEY = orig_sb_key


def test_sqlite_fallback_lifecycle(client):
    """Verify full conversation & message persistence via SQLite engine without Supabase."""
    tok = _token(USER_ALICE)

    # 1. Create a conversation
    r = client.post(
        "/conversations",
        json={"title": "Q3 Financials"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    conv = r.json()["conversation"]
    conv_id = conv["id"]
    assert conv["title"] == "Q3 Financials"

    # 2. Add user message
    r2 = client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "What was the operating margin?"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 201
    msg1 = r2.json()["message"]
    assert msg1["role"] == "user"
    assert msg1["status"] == "completed"

    # 3. Add assistant message
    r3 = client.post(
        f"/conversations/{conv_id}/messages",
        json={
            "role": "assistant",
            "content": "The operating margin was 24.5%.",
            "citations": {"document_citations": [{"filename": "q3.pdf", "page": 4}]},
            "metadata": {"route_used": "DOCUMENT_RAG"},
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r3.status_code == 201

    # 4. Fetch messages and verify sequence and ordering
    r4 = client.get(
        f"/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r4.status_code == 200
    messages = r4.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["citations"]["document_citations"][0]["filename"] == "q3.pdf"

    # 5. Rename conversation
    r5 = client.put(
        f"/conversations/{conv_id}",
        json={"title": "Renamed Q3 Review"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r5.status_code == 200

    # 6. Archive conversation
    r6 = client.post(
        f"/conversations/{conv_id}/archive",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r6.status_code == 200


def test_cross_user_isolation(client):
    """User Bob cannot read, modify, or delete Alice's conversation."""
    tok_alice = _token(USER_ALICE)
    tok_bob = _token(USER_BOB, email="bob@test.com")

    # Alice creates conversation
    r = client.post(
        "/conversations",
        json={"title": "Alice's Secret Project"},
        headers={"Authorization": f"Bearer {tok_alice}"},
    )
    conv_id = r.json()["conversation"]["id"]

    # Bob tries to read Alice's conversation -> 404
    r_bob = client.get(
        f"/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {tok_bob}"},
    )
    assert r_bob.status_code == 404

    # Bob tries to rename Alice's conversation -> 404
    r_rename = client.put(
        f"/conversations/{conv_id}",
        json={"title": "Hacked Title"},
        headers={"Authorization": f"Bearer {tok_bob}"},
    )
    assert r_rename.status_code == 404

    # Bob tries to delete Alice's conversation -> 404
    r_del = client.delete(
        f"/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {tok_bob}"},
    )
    assert r_del.status_code == 404


def test_failed_llm_call_preserves_user_message(client):
    """When the LLM pipeline raises an error, the user's message is preserved and the failure is recorded."""
    tok = _token(USER_ALICE)

    # Alice starts query with LLM failing
    with patch(
        "backend.services.orchestrator_service.orchestrator_service.handle_query_request",
        side_effect=RuntimeError("Groq service timeout"),
    ):
        r = client.post(
            "/query",
            json={"question": "Analyze the quarterly trends"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 500

    # Alice lists conversations to find the created conversation
    r_list = client.get("/conversations", headers={"Authorization": f"Bearer {tok}"})
    assert r_list.status_code == 200
    convs = r_list.json()["conversations"]
    assert len(convs) == 1
    conv_id = convs[0]["id"]

    # Fetch messages: user message must be present, and assistant must have status='failed'
    r_msgs = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {tok}"})
    assert r_msgs.status_code == 200
    msgs = r_msgs.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Analyze the quarterly trends"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["status"] == "failed"


def test_idempotent_duplicate_prevention(client):
    """Duplicate submissions in rapid succession do not produce duplicate messages."""
    tok = _token(USER_ALICE)

    r = client.post(
        "/conversations",
        json={"title": "Double Click Test"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    conv_id = r.json()["conversation"]["id"]

    # First message
    client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Calculate the total revenue"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    # Rapid duplicate submission (simulating double click)
    client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Calculate the total revenue"},
        headers={"Authorization": f"Bearer {tok}"},
    )

    r_msgs = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {tok}"})
    msgs = r_msgs.json()["messages"]
    assert len(msgs) == 1
