# backend run = uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.logger import logger, request_id_var
from backend.middlewares.exception_handlers import catch_exception_middleware
from backend.routes.upload_pdfs import router as upload_router
from backend.routes.ask_question import router as ask_router
from backend.routes.documents import router as documents_router
from backend.routes.query import router as query_router
from backend.routes.vision import router as vision_router
from backend.routes.conversation import router as conversation_router
from backend.routes.auth import router as auth_router
from backend.routes.conversations import router as conversations_router


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# ---------------------------------------------------------------------------
# CORS — never use wildcard with credentials; read allowed origins from env
# ---------------------------------------------------------------------------
def _allowed_origins() -> list[str]:
    """
    Build the CORS allow-list from CORS_ORIGINS (comma-separated) env var.
    Falls back to FRONTEND_URL and localhost defaults if the variable is absent.
    """
    raw = os.getenv("CORS_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    defaults = {
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8501",  # Streamlit
        frontend_url,
    }
    return list(defaults)


app = FastAPI(
    title="Nexora AI API",
    description="Multimodal RAG + OCR/Vision + Web Search + General AI backend",
)

# Attach the rate-limiter state and handler to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit origins, NOT wildcard, with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add hardening headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # HSTS: only set over HTTPS. When running locally over HTTP this header is
    # ignored by browsers, so it is safe to always include it.
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def tracing_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
    token = request_id_var.set(trace_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        request_id_var.reset(token)


# Exception handler middleware
app.middleware("http")(catch_exception_middleware)

# ---- Routers ----
# Legacy (backward compatible)
app.include_router(upload_router)
app.include_router(ask_router)

# Core API
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(vision_router)
app.include_router(conversation_router)

# Authentication & persistent chat history
app.include_router(auth_router)
app.include_router(conversations_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Optional React App static mounting if built
_react_dist = Path(__file__).resolve().parent.parent / "frontend-react" / "dist"
if _react_dist.exists():
    app.mount("/app", StaticFiles(directory=str(_react_dist), html=True), name="react_app")
