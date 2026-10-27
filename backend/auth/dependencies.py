"""
FastAPI dependency functions for authentication.
"""
from fastapi import Depends, HTTPException, status, Request
from backend.auth.jwt_validator import get_current_user


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Require a valid, authenticated user. Email does NOT need to be verified."""
    return user


def require_verified_auth(user: dict = Depends(get_current_user)) -> dict:
    """Require a valid authenticated user whose email has been verified."""
    if not user.get("email_confirmed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address is not verified. Please verify your email before accessing this resource.",
        )
    return user
