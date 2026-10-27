"""
JWT validation for Nexora AI backend.

Validates Supabase-issued JWTs using the project's JWT secret (HS256).
The secret is the raw JWT Secret from Supabase → Project Settings → API.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Request, HTTPException, status
from jose import jwt, JWTError, ExpiredSignatureError

from backend.config import settings
from backend.logger import logger


def _extract_bearer(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    return token if token else None


def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency: validates the Supabase JWT and returns user dict.

    Returns:
        {
            "user_id": str,
            "email": str,
            "email_confirmed": bool,
            "role": str,
        }

    Raises:
        HTTPException 401 if token missing, expired, or invalid.
    """
    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_secret = settings.SUPABASE_JWT_SECRET
    if not jwt_secret:
        logger.warning("[JWT] SUPABASE_JWT_SECRET is not configured — rejecting all authenticated requests.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        )

    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.debug(f"[JWT] Decode failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub", "")
    email: str = payload.get("email", "")
    email_confirmed: bool = bool(payload.get("email_confirmed_at") or payload.get("email_verified"))

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain a valid user identifier.",
        )

    return {
        "user_id": user_id,
        "email": email,
        "email_confirmed": email_confirmed,
        "role": payload.get("role", "authenticated"),
    }


def try_get_current_user(request: Request) -> Optional[dict]:
    """
    Non-raising version — returns None if no valid token is present.
    Used for endpoints that support optional authentication (backward compat).
    """
    try:
        return get_current_user(request)
    except HTTPException:
        return None
