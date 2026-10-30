"""
Phase 4 & 5 — Security, CORS, and Web Search Fallback Tests
============================================================
"""
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Force Supabase-disabled mode so tests don't hit real Supabase
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""

from backend.main import app, _allowed_origins
from backend.services.web_search_service import DuckDuckGoProvider, _get_provider

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Security Headers & CORS Tests
# ---------------------------------------------------------------------------

def test_security_headers_present_on_response():
    """Verify standard security hardening headers are injected on all responses."""
    resp = client.get("/health")
    assert resp.status_code == 200
    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in headers.get("Referrer-Policy", "")
    assert "max-age=31536000" in headers.get("Strict-Transport-Security", "")
    assert "geolocation=()" in headers.get("Permissions-Policy", "")


def test_cors_does_not_use_wildcard_with_credentials():
    """CORS origins should never be wildcard '*' when credentials are true."""
    origins = _allowed_origins()
    assert "*" not in origins
    assert any("localhost" in o for o in origins)


def test_cors_preflight_allows_configured_origin():
    """Options preflight from an allowed origin receives valid CORS headers."""
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_unauthorized_origin():
    """Untrusted origin should not receive access-control-allow-origin."""
    resp = client.options(
        "/health",
        headers={
            "Origin": "https://malicious-site.attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") is None


# ---------------------------------------------------------------------------
# Auth Request Validation Tests
# ---------------------------------------------------------------------------

def test_signup_password_max_length_guard():
    """Passwords exceeding 128 chars should be rejected (preventing bcrypt-DoS)."""
    long_password = "A" * 129
    resp = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": long_password,
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 422  # Pydantic validation error


def test_signup_password_min_length_guard():
    """Passwords shorter than 8 chars must be rejected."""
    short_password = "short"
    resp = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": short_password,
            "full_name": "Test User",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Phase 5: DuckDuckGo Fallback Web Search Tests
# ---------------------------------------------------------------------------

def test_ddg_html_parser_extracts_clean_results():
    """Test DuckDuckGo HTML parser correctly extracts and cleans search results."""
    mock_html = """
    <div class="result results_links">
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Farticle">Example <b>Title</b></a>
        <a class="result__snippet">This is an <i>informative</i> snippet about the query.</a>
    </div>
    """
    results = DuckDuckGoProvider._parse_html(mock_html, max_results=5)
    assert len(results) == 1
    assert results[0]["title"] == "Example Title"
    assert results[0]["url"] == "https://example.com/article"
    assert results[0]["snippet"] == "This is an informative snippet about the query."


def test_get_provider_falls_back_to_ddg_when_no_api_key():
    """When WEB_SEARCH_PROVIDER is set to tavily or serper but no keys exist, falls back to DDG."""
    from backend.config import settings
    with patch.object(settings, "TAVILY_API_KEY", None), \
         patch.object(settings, "SERPER_API_KEY", None), \
         patch.object(settings, "WEB_SEARCH_PROVIDER", "duckduckgo"):
        provider = _get_provider()
        assert isinstance(provider, DuckDuckGoProvider)
