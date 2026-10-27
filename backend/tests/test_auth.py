"""
Tests for Nexora AI authentication and conversation persistence.
All Supabase calls are mocked — no live Supabase, email delivery, or LLM required.
"""
from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt

# ------------------------------------------------------------------ #
# JWT helpers
# ------------------------------------------------------------------ #
TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long!!"
TEST_USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TEST_USER_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEST_CONV  = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _token(user_id: str, email: str = "u@test.com", confirmed: bool = True, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id, "email": email,
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
        "iat": now - 100,
        "exp": (now - 1) if expired else (now + 3600),
        "role": "authenticated",
    }
    if confirmed:
        payload["email_confirmed_at"] = "2024-01-01T00:00:00Z"
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


# Patch settings at module level for JWT validator tests
_settings_patch = {
    "backend.config.settings.SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "backend.config.settings.SUPABASE_URL": "https://test.supabase.co",
    "backend.config.settings.SUPABASE_ANON_KEY": "test-anon",
    "backend.config.settings.SUPABASE_SERVICE_ROLE_KEY": "test-service-role",
    "backend.config.settings.FRONTEND_URL": "http://localhost:5173",
}


def _patch_settings():
    """Context manager: patch all Supabase settings on the live Settings instance."""
    patches = [patch(k, v) for k, v in _settings_patch.items()]
    return patches


# ================================================================== #
# 1. Signup success
# ================================================================== #
def test_signup_success(client):
    user_mock = MagicMock(id=TEST_USER_A, email="new@test.com")
    with patch("backend.routes.auth._get_auth_client") as m:
        m.return_value.auth.sign_up.return_value = MagicMock(user=user_mock)
        r = client.post("/auth/signup", json={"email": "new@test.com", "password": "Secure123!", "full_name": "Ada"})
    assert r.status_code == 201
    assert "created" in r.json()["message"].lower()


# ================================================================== #
# 2. Signup duplicate — neutral message (201, no account info leaked)
# ================================================================== #
def test_signup_duplicate_neutral(client):
    with patch("backend.routes.auth._get_auth_client") as m:
        m.return_value.auth.sign_up.side_effect = Exception("User already registered")
        r = client.post("/auth/signup", json={"email": "dup@test.com", "password": "Secure123!", "full_name": "Dup"})
    # Neutral: doesn't reveal whether account exists; always succeeds (201)
    assert r.status_code in (200, 201)
    body = r.json()["message"].lower()
    assert any(kw in body for kw in ("sent", "verification", "new", "created"))


# ================================================================== #
# 3. Signup weak password (422)
# ================================================================== #
def test_signup_weak_password(client):
    r = client.post("/auth/signup", json={"email": "u@test.com", "password": "abc", "full_name": "A"})
    assert r.status_code == 422


# ================================================================== #
# 4. Login success → tokens returned
# ================================================================== #
def test_login_success(client):
    session = MagicMock(access_token="tok", refresh_token="ref", expires_in=3600)
    user = MagicMock(id=TEST_USER_A, email="a@test.com", email_confirmed_at="2024-01-01", user_metadata={"full_name": "Ada"})
    with patch("backend.routes.auth._get_auth_client") as m:
        m.return_value.auth.sign_in_with_password.return_value = MagicMock(session=session, user=user)
        r = client.post("/auth/login", json={"email": "a@test.com", "password": "correct"})
    assert r.status_code == 200
    assert "access_token" in r.json()


# ================================================================== #
# 5. Login wrong password → 401
# ================================================================== #
def test_login_wrong_password(client):
    with patch("backend.routes.auth._get_auth_client") as m:
        m.return_value.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
        r = client.post("/auth/login", json={"email": "a@test.com", "password": "wrong"})
    assert r.status_code == 401


# ================================================================== #
# 6. Valid JWT accepted
# ================================================================== #
def test_valid_jwt_accepted(client):
    with patch("backend.auth.jwt_validator.settings") as ms:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {_token(TEST_USER_A)}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == TEST_USER_A


# ================================================================== #
# 7. Expired JWT → 401
# ================================================================== #
def test_expired_jwt_rejected(client):
    with patch("backend.auth.jwt_validator.settings") as ms:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {_token(TEST_USER_A, expired=True)}"})
    assert r.status_code == 401


# ================================================================== #
# 8. Malformed JWT → 401
# ================================================================== #
def test_malformed_jwt_rejected(client):
    with patch("backend.auth.jwt_validator.settings") as ms:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert r.status_code == 401


# ================================================================== #
# 9. Missing JWT → 401
# ================================================================== #
def test_missing_jwt_rejected(client):
    with patch("backend.auth.jwt_validator.settings") as ms:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/auth/me")
    assert r.status_code == 401


# ================================================================== #
# 10. Unverified user blocked from /conversations → 403
# ================================================================== #
def test_unverified_user_blocked(client):
    tok = _token(TEST_USER_A, confirmed=False)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/conversations", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


# ================================================================== #
# 11. Verified user can access /conversations
# ================================================================== #
def test_verified_user_accesses_conversations(client):
    tok = _token(TEST_USER_A)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.get_conversations", return_value=[]):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/conversations", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["conversations"] == []


# ================================================================== #
# 12. User A lists their own conversations
# ================================================================== #
def test_user_a_lists_own_conversations(client):
    tok = _token(TEST_USER_A, email="a@test.com")
    convs = [{"id": TEST_CONV, "title": "My Chat", "created_at": "2024-01-01"}]
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.get_conversations", return_value=convs) as fn:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get("/conversations", headers={"Authorization": f"Bearer {tok}"})
        fn.assert_called_once_with(TEST_USER_A, limit=50)
    assert len(r.json()["conversations"]) == 1


# ================================================================== #
# 13. User B cannot read User A's conversation → 404
# ================================================================== #
def test_user_b_cannot_read_user_a_convo(client):
    tok_b = _token(TEST_USER_B, email="b@test.com")
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.get_conversation", return_value=None):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get(f"/conversations/{TEST_CONV}", headers={"Authorization": f"Bearer {tok_b}"})
    assert r.status_code == 404


# ================================================================== #
# 14. Create conversation
# ================================================================== #
def test_create_conversation(client):
    tok = _token(TEST_USER_A)
    conv = {"id": TEST_CONV, "title": "Test Conv", "created_at": "2024-01-01"}
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.create_conversation", return_value=conv):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.post("/conversations", json={"title": "Test Conv"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201
    assert r.json()["conversation"]["id"] == TEST_CONV


# ================================================================== #
# 15. Delete own conversation → 204
# ================================================================== #
def test_delete_own_conversation(client):
    tok = _token(TEST_USER_A)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.delete_conversation", return_value=True):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.delete(f"/conversations/{TEST_CONV}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204


# ================================================================== #
# 16. Delete another user's conversation → 404
# ================================================================== #
def test_delete_other_user_convo_404(client):
    tok_b = _token(TEST_USER_B)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.delete_conversation", return_value=False):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.delete(f"/conversations/{TEST_CONV}", headers={"Authorization": f"Bearer {tok_b}"})
    assert r.status_code == 404


# ================================================================== #
# 17. Add message to own conversation → 201
# ================================================================== #
def test_add_message_own_convo(client):
    tok = _token(TEST_USER_A)
    msg = {"id": "msg-1", "role": "user", "content": "Hi", "created_at": "2024-01-01"}
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.add_message", return_value=msg):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.post(
            f"/conversations/{TEST_CONV}/messages",
            json={"role": "user", "content": "Hi"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r.status_code == 201


# ================================================================== #
# 18. Cross-user message access rejected → 404
# ================================================================== #
def test_cross_user_message_rejected(client):
    tok_b = _token(TEST_USER_B)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.conversations.is_supabase_configured", return_value=True), \
         patch("backend.services.chat_persistence_service.chat_persistence.get_conversation", return_value=None):
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        r = client.get(f"/conversations/{TEST_CONV}/messages", headers={"Authorization": f"Bearer {tok_b}"})
    assert r.status_code == 404


# ================================================================== #
# 19. Forgot password → always 200, neutral message
# ================================================================== #
def test_forgot_password_always_200(client):
    with patch("backend.routes.auth._get_auth_client") as m:
        m.return_value.auth.reset_password_for_email.return_value = None
        r = client.post("/auth/forgot-password", json={"email": "anyone@test.com"})
    assert r.status_code == 200
    assert "password reset link" in r.json()["message"].lower()


# ================================================================== #
# 20. /query without auth still works (backward compat) — must not 401
# ================================================================== #
def test_query_unauthenticated_works(client):
    from backend.schemas import QueryResponse, EvidenceBreakdown
    mock_resp = QueryResponse(answer="Lists are mutable.", route_used="GENERAL_LLM", session_id="s")
    with patch("backend.services.orchestrator_service.orchestrator_service.handle_query_request", return_value=mock_resp):
        r = client.post("/query", json={"question": "What is a list?"})
    assert r.status_code != 401


# ================================================================== #
# 21. Reset password updates successfully with valid JWT
# ================================================================== #
def test_reset_password_success(client):
    tok = _token(TEST_USER_A)
    with patch("backend.auth.jwt_validator.settings") as ms, \
         patch("backend.routes.auth._get_auth_client") as m:
        ms.SUPABASE_JWT_SECRET = TEST_JWT_SECRET
        m.return_value.auth.update_user.return_value = MagicMock()
        r = client.post(
            "/auth/reset-password",
            json={"new_password": "NewSecurePassword123!"},
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r.status_code == 200
    assert "updated" in r.json()["message"].lower()
