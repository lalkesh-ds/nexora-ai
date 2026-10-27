"""
Auth router: wraps Supabase Auth for signup, login, logout, token refresh,
password recovery, and user info.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field

from backend.config import settings
from backend.auth.dependencies import require_auth
from backend.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_client():
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_ANON_KEY
    if not url or not key:
        raise HTTPException(status_code=503, detail="Authentication service is not configured.")
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Auth client init failed: {exc}")


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


@router.post("/signup", status_code=201)
async def signup(payload: SignupRequest):
    client = _get_auth_client()
    try:
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        res = client.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": {
                "data": {"full_name": payload.full_name},
                "email_redirect_to": f"{frontend_url}/auth/callback",
            },
        })
    except Exception as exc:
        err_str = str(exc).lower()
        if "already registered" in err_str or "already exists" in err_str or "unique" in err_str:
            return {"message": "If this email is new, a verification email has been sent."}
        logger.error(f"[Auth] Signup error: {exc}")
        raise HTTPException(status_code=400, detail="Registration failed. Please try again.")

    if res.user is None:
        raise HTTPException(status_code=400, detail="Registration failed. Please try again.")

    return {
        "message": "Account created. Please check your email to verify your account.",
        "user_id": res.user.id,
        "email": res.user.email,
    }


@router.post("/login")
async def login(payload: LoginRequest):
    client = _get_auth_client()
    try:
        res = client.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
    except Exception as exc:
        err_str = str(exc).lower()
        if "invalid login" in err_str or "invalid credentials" in err_str:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        if "email not confirmed" in err_str:
            raise HTTPException(status_code=403, detail="Email not confirmed. Please verify your email.")
        logger.error(f"[Auth] Login error: {exc}")
        raise HTTPException(status_code=401, detail="Sign in failed.")

    if not res.session:
        raise HTTPException(status_code=401, detail="Sign in failed — no session created.")

    return {
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "token_type": "bearer",
        "expires_in": res.session.expires_in,
        "user": {
            "id": res.user.id,
            "email": res.user.email,
            "full_name": (res.user.user_metadata or {}).get("full_name", ""),
            "email_confirmed": res.user.email_confirmed_at is not None,
        },
    }


@router.post("/logout", status_code=204)
async def logout(user: dict = Depends(require_auth)):
    logger.info(f"[Auth] Logout for user_id={user['user_id']}")
    return None


@router.post("/refresh")
async def refresh_token(payload: RefreshRequest):
    client = _get_auth_client()
    try:
        res = client.auth.refresh_session(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token refresh failed. Please sign in again.")
    if not res.session:
        raise HTTPException(status_code=401, detail="Token refresh failed.")
    return {
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "expires_in": res.session.expires_in,
    }


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    client = _get_auth_client()
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
    try:
        client.auth.reset_password_for_email(
            payload.email,
            options={"redirect_to": f"{frontend_url}/reset-password"},
        )
    except Exception as exc:
        logger.warning(f"[Auth] Password reset request error (not shown to user): {exc}")
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, user: dict = Depends(require_auth)):
    try:
        from backend.db.supabase_client import get_supabase, is_supabase_configured
        if is_supabase_configured():
            admin_client = get_supabase()
            admin_client.auth.admin.update_user_by_id(user["user_id"], {"password": payload.new_password})
        else:
            client = _get_auth_client()
            client.auth.update_user({"password": payload.new_password})
    except Exception as exc:
        err_str = str(exc).lower()
        if "expired" in err_str or "invalid" in err_str:
            raise HTTPException(status_code=401, detail="Password reset link has expired.")
        raise HTTPException(status_code=400, detail="Failed to update password.")
    logger.info(f"[Auth] Password updated for user_id={user['user_id']}")
    return {"message": "Password updated successfully."}


@router.get("/me")
async def get_me(user: dict = Depends(require_auth)):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "email_confirmed": user["email_confirmed"],
    }
