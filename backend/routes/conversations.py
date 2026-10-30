"""
Conversations router: persistent chat history with strict per-user isolation.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_verified_auth
from backend.services.chat_persistence_service import chat_persistence
from backend.db.supabase_client import is_supabase_configured

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=120)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class AddMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|tool)$")
    content: str
    citations: Optional[dict] = None
    metadata: Optional[dict] = None


def _check_supabase():
    # Persistence is always operational via Supabase or durable local SQLite engine
    pass


@router.get("")
async def list_conversations(limit: int = Query(50, ge=1, le=200), user: dict = Depends(require_verified_auth)):
    _check_supabase()
    return {"conversations": chat_persistence.get_conversations(user["user_id"], limit=limit)}


@router.post("", status_code=201)
async def create_conversation(payload: CreateConversationRequest, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    conv = chat_persistence.create_conversation(user["user_id"], payload.title)
    return {"conversation": conv}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    conv = chat_persistence.get_conversation(user["user_id"], conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = chat_persistence.get_messages(user["user_id"], conversation_id)
    return {"conversation": conv, "messages": messages}


@router.put("/{conversation_id}")
async def rename_conversation(conversation_id: str, payload: RenameConversationRequest, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    ok = chat_persistence.update_conversation_title(user["user_id"], conversation_id, payload.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "Renamed."}


@router.post("/{conversation_id}/archive")
async def archive_conversation(conversation_id: str, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    ok = chat_persistence.archive_conversation(user["user_id"], conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "Archived."}


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    ok = chat_persistence.delete_conversation(user["user_id"], conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return None


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_verified_auth),
):
    _check_supabase()
    conv = chat_persistence.get_conversation(user["user_id"], conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = chat_persistence.get_messages(user["user_id"], conversation_id, limit=limit, offset=offset)
    return {"messages": messages, "offset": offset, "limit": limit}


@router.post("/{conversation_id}/messages", status_code=201)
async def add_message(conversation_id: str, payload: AddMessageRequest, user: dict = Depends(require_verified_auth)):
    _check_supabase()
    msg = chat_persistence.add_message(
        conversation_id=conversation_id, user_id=user["user_id"],
        role=payload.role, content=payload.content,
        citations=payload.citations, metadata=payload.metadata,
    )
    return {"message": msg}
