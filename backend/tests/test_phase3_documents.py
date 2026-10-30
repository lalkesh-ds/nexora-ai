"""
Phase 3 — Document Pipeline Tests
=================================
Tests user-scoped document ownership, access control, upload auth integration,
and upload + query text+file simultaneous handling.

All Supabase calls are mocked so these tests run offline.
"""
import io
import os
import json
import tempfile

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Force Supabase-disabled mode so tests don't hit real Supabase
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""

from backend.main import app

client = TestClient(app, raise_server_exceptions=False)

ALICE_USER_ID = "aaaaaaaa-0000-0000-0000-000000000001"
BOB_USER_ID = "bbbbbbbb-0000-0000-0000-000000000002"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt_user(user_id: str, email: str = "user@example.com", confirmed: bool = True) -> dict:
    return {
        "user_id": user_id,
        "email": email,
        "email_confirmed": confirmed,
        "role": "authenticated",
    }


def _txt_file(content: str = "Hello World test content for chunking purposes.") -> tuple:
    return ("test.txt", io.BytesIO(content.encode()), "text/plain")


# ---------------------------------------------------------------------------
# Test: unauthenticated upload returns 200/207/422
# ---------------------------------------------------------------------------

def test_upload_unauthenticated_accepts_valid_file():
    """Unauthenticated upload of a text file should succeed (backward compat)."""
    name, data, mime = _txt_file()
    with patch("backend.routes.documents.try_get_current_user", return_value=None), \
         patch("backend.services.document_service.document_service.ingest") as mock_ingest:
        mock_ingest.return_value = {
            "document_id": "abc123def456",
            "filename": "test.txt",
            "source_type": "txt",
            "status": "completed",
            "pages": 1,
            "error": None,
        }
        resp = client.post(
            "/documents/upload",
            files={"files": (name, data, mime)},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents"][0]["status"] == "completed"


def test_upload_authenticated_registers_ownership():
    """Authenticated upload: _register_user_document is called with user_id."""
    name, data, mime = _txt_file()
    alice = _make_jwt_user(ALICE_USER_ID)

    with patch("backend.routes.documents.try_get_current_user", return_value=alice), \
         patch("backend.services.document_service.document_service.ingest") as mock_ingest, \
         patch("backend.routes.documents._register_user_document") as mock_register:
        mock_ingest.return_value = {
            "document_id": "doc_alice_001",
            "filename": "test.txt",
            "source_type": "txt",
            "status": "completed",
            "pages": 1,
            "error": None,
        }
        resp = client.post(
            "/documents/upload",
            files={"files": (name, data, mime)},
        )

    assert resp.status_code == 200
    mock_register.assert_called_once()
    call_kwargs = mock_register.call_args.kwargs
    assert call_kwargs["user_id"] == ALICE_USER_ID
    assert call_kwargs["document_id"] == "doc_alice_001"


def test_upload_failed_file_does_not_register_ownership():
    """Failed ingestion must NOT register ownership."""
    name, data, mime = _txt_file()
    alice = _make_jwt_user(ALICE_USER_ID)

    with patch("backend.routes.documents.try_get_current_user", return_value=alice), \
         patch("backend.services.document_service.document_service.ingest") as mock_ingest, \
         patch("backend.routes.documents._register_user_document") as mock_register:
        mock_ingest.return_value = {
            "document_id": "doc_fail",
            "filename": "test.txt",
            "source_type": "txt",
            "status": "failed",
            "pages": None,
            "error": "extraction failed",
        }
        resp = client.post(
            "/documents/upload",
            files={"files": (name, data, mime)},
        )

    # Failed upload → 422
    assert resp.status_code == 422
    # Ownership MUST NOT be registered
    mock_register.assert_not_called()


# ---------------------------------------------------------------------------
# Test: list_documents returns only the user's docs when authenticated
# ---------------------------------------------------------------------------

def test_list_documents_authenticated_returns_own_docs():
    """Authenticated GET /documents uses _list_user_documents (not global list)."""
    alice = _make_jwt_user(ALICE_USER_ID)

    with patch("backend.routes.documents.try_get_current_user", return_value=alice), \
         patch("backend.routes.documents.is_supabase_configured", return_value=True), \
         patch("backend.routes.documents._list_user_documents") as mock_list:
        mock_list.return_value = [
            {"document_id": "alice_doc", "filename": "alice.txt", "source_type": "txt",
             "status": "completed", "pages": 1, "error": None}
        ]
        resp = client.get("/documents")

    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["document_id"] == "alice_doc"
    mock_list.assert_called_once_with(ALICE_USER_ID)


def test_list_documents_unauthenticated_returns_global_list():
    """Unauthenticated GET /documents returns global list (backward compat)."""
    with patch("backend.routes.documents.try_get_current_user", return_value=None), \
         patch("backend.services.document_service.document_service.list_documents") as mock_global:
        mock_global.return_value = [
            {"document_id": "global_doc", "filename": "shared.txt", "source_type": "txt",
             "status": "completed", "pages": 2, "error": None}
        ]
        resp = client.get("/documents")

    assert resp.status_code == 200
    docs = resp.json()["documents"]
    assert docs[0]["document_id"] == "global_doc"


# ---------------------------------------------------------------------------
# Test: delete — cross-user access prevention (IDOR)
# ---------------------------------------------------------------------------

def test_delete_document_denied_for_non_owner():
    """Bob CANNOT delete Alice's document."""
    bob = _make_jwt_user(BOB_USER_ID, email="bob@example.com")

    with patch("backend.routes.documents.try_get_current_user", return_value=bob), \
         patch("backend.routes.documents._user_owns_document", return_value=False):
        resp = client.delete("/documents/alice_private_doc")

    assert resp.status_code == 403


def test_delete_document_allowed_for_owner():
    """Alice CAN delete her own document."""
    alice = _make_jwt_user(ALICE_USER_ID)

    with patch("backend.routes.documents.try_get_current_user", return_value=alice), \
         patch("backend.routes.documents._user_owns_document", return_value=True), \
         patch("backend.routes.documents.is_supabase_configured", return_value=False), \
         patch("backend.services.document_service.document_service.delete_document"):
        resp = client.delete("/documents/alice_private_doc")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: get document status — cross-user access prevention
# ---------------------------------------------------------------------------

def test_get_document_status_denied_for_non_owner():
    """Bob cannot see Alice's document status."""
    bob = _make_jwt_user(BOB_USER_ID, email="bob@example.com")

    with patch("backend.routes.documents.try_get_current_user", return_value=bob), \
         patch("backend.services.document_service.document_service.get_document") as mock_get, \
         patch("backend.routes.documents._user_owns_document", return_value=False):
        mock_get.return_value = {
            "document_id": "alice_doc", "filename": "alice.pdf",
            "source_type": "pdf", "status": "completed",
        }
        resp = client.get("/documents/alice_doc/status")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test: unsafe file rejection still works with auth
# ---------------------------------------------------------------------------

def test_upload_unsafe_file_rejected_regardless_of_auth():
    """Dangerous file extensions are rejected even for authenticated users."""
    alice = _make_jwt_user(ALICE_USER_ID)

    from backend.utils.security import UnsafeFileError

    with patch("backend.routes.documents.try_get_current_user", return_value=alice), \
         patch("backend.utils.security.read_upload_safely",
               side_effect=UnsafeFileError("extension .exe not allowed")):
        resp = client.post(
            "/documents/upload",
            files={"files": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )

    assert resp.status_code == 422
    doc = resp.json()["documents"][0]
    assert doc["status"] == "rejected"


# ---------------------------------------------------------------------------
# Test: _user_owns_document returns True when Supabase is disabled (fail-open)
# ---------------------------------------------------------------------------

def test_user_owns_document_fail_open_when_supabase_disabled():
    """When Supabase is not configured, _user_owns_document returns True."""
    from backend.routes.documents import _user_owns_document
    with patch("backend.routes.documents.is_supabase_configured", return_value=False):
        assert _user_owns_document("any_user", "any_doc") is True
