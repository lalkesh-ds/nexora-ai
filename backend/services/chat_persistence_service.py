"""
ChatPersistenceService: Stores and retrieves conversations and messages
from Supabase PostgreSQL with strict per-user ownership enforcement.

All operations:
- Accept user_id from verified JWT (never from request body).
- Use the service-role client with explicit user_id filters for full
  ownership control (RLS provides additional database-level isolation).
"""
from __future__ import annotations

import re
from typing import Optional
from fastapi import HTTPException, status

from backend.db.supabase_client import get_supabase, is_supabase_configured
from backend.logger import logger

_VALID_ROLES = {"user", "assistant", "tool"}


def _require_supabase():
    if not is_supabase_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat persistence is not available — Supabase is not configured.",
        )
    return get_supabase()


class ChatPersistenceService:

    # ------------------------------------------------------------------ #
    # Conversations
    # ------------------------------------------------------------------ #

    def create_conversation(self, user_id: str, title: str) -> dict:
        """Create a new conversation owned by user_id."""
        db = _require_supabase()
        clean_title = (title or "New Chat")[:120].strip() or "New Chat"
        try:
            res = (
                db.table("conversations")
                .insert({"user_id": user_id, "title": clean_title})
                .execute()
            )
            return res.data[0] if res.data else {}
        except Exception as exc:
            logger.error(f"[Persistence] create_conversation failed: {exc}")
            raise HTTPException(status_code=503, detail="Failed to create conversation.")

    def get_conversations(self, user_id: str, limit: int = 50) -> list[dict]:
        """List conversations belonging to user_id, ordered by most recent activity."""
        db = _require_supabase()
        try:
            res = (
                db.table("conversations")
                .select("id, title, created_at, updated_at, last_message_at")
                .eq("user_id", user_id)
                .order("last_message_at", desc=True, nullsfirst=False)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error(f"[Persistence] get_conversations failed: {exc}")
            return []

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[dict]:
        """Get a single conversation — returns None if not found or not owned by user."""
        db = _require_supabase()
        try:
            res = (
                db.table("conversations")
                .select("*")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            return res.data
        except Exception as exc:
            logger.error(f"[Persistence] get_conversation failed: {exc}")
            return None

    def update_conversation_title(self, user_id: str, conversation_id: str, title: str) -> bool:
        """Rename a conversation. Returns True on success."""
        db = _require_supabase()
        clean_title = (title or "Untitled")[:120].strip() or "Untitled"
        try:
            res = (
                db.table("conversations")
                .update({"title": clean_title})
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )
            return len(res.data) > 0
        except Exception as exc:
            logger.error(f"[Persistence] update_conversation_title failed: {exc}")
            return False

    def update_last_message_at(self, user_id: str, conversation_id: str) -> None:
        """Update last_message_at timestamp on a conversation."""
        db = _require_supabase()
        try:
            db.table("conversations").update({"last_message_at": "now()"}).eq("id", conversation_id).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.warning(f"[Persistence] update_last_message_at failed: {exc}")

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation and all its messages (via CASCADE). Returns True on success."""
        db = _require_supabase()
        try:
            res = (
                db.table("conversations")
                .delete()
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )
            return len(res.data) > 0
        except Exception as exc:
            logger.error(f"[Persistence] delete_conversation failed: {exc}")
            return False

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        citations: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Insert a message. Validates ownership first.
        Never persists messages for conversations the user doesn't own.
        """
        if role not in _VALID_ROLES:
            raise ValueError(f"Invalid role: {role!r}. Must be one of {_VALID_ROLES}.")

        db = _require_supabase()

        # Verify ownership before inserting
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        try:
            row = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content or "",
            }
            if citations:
                row["citations"] = citations
            if metadata:
                row["metadata"] = metadata

            res = db.table("messages").insert(row).execute()
            return res.data[0] if res.data else {}
        except Exception as exc:
            logger.error(f"[Persistence] add_message failed: {exc}")
            raise HTTPException(status_code=503, detail="Failed to persist message.")

    def get_messages(
        self,
        user_id: str,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Return messages for a conversation. Enforces ownership via conversation lookup.
        Returns [] if conversation doesn't belong to user_id.
        """
        db = _require_supabase()

        # Verify ownership
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return []

        try:
            res = (
                db.table("messages")
                .select("id, role, content, citations, metadata, created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.error(f"[Persistence] get_messages failed: {exc}")
            return []

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def generate_title(self, first_message: str) -> str:
        """Generate a conversation title from the first user message."""
        clean = re.sub(r"[*_`#>\[\]()]", "", first_message)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:60] if len(clean) > 3 else "New Chat"


chat_persistence = ChatPersistenceService()
