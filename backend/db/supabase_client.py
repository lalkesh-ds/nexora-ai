"""
Supabase client singleton for privileged backend operations.

Uses the service-role key exclusively on the server.
Never expose this client or its key to browser code.
"""
from __future__ import annotations

from typing import Optional
from backend.config import settings
from backend.logger import logger

_supabase_client = None
_init_error: Optional[str] = None


def get_supabase():
    """
    Returns the Supabase service-role client singleton.
    Raises RuntimeError if Supabase is not configured.
    """
    global _supabase_client, _init_error

    if _supabase_client is not None:
        return _supabase_client

    if _init_error:
        raise RuntimeError(_init_error)

    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY

    if not url or not key:
        _init_error = "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        logger.warning(f"[Supabase] {_init_error}")
        raise RuntimeError(_init_error)

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        logger.info(f"[Supabase] Client initialized for {url}")
        return _supabase_client
    except Exception as exc:
        _init_error = f"Failed to initialize Supabase client: {exc}"
        logger.error(f"[Supabase] {_init_error}")
        raise RuntimeError(_init_error) from exc


def is_supabase_configured() -> bool:
    """Non-raising check whether Supabase is configured."""
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)
