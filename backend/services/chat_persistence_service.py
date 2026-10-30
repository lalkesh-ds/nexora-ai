"""
ChatPersistenceService: Stores and retrieves conversations and messages
from Supabase PostgreSQL (with strict per-user ownership enforcement and RLS),
with a persistent, durable SQLite fallback for offline or unconfigured environments.

All operations:
- Accept user_id from verified JWT (never from untrusted request body).
- Enforce strict per-user ownership on read, write, rename, archive, and delete.
- Prevent duplicate messages caused by retries or double clicks (idempotency check).
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status

from backend.config import settings
from backend.db.supabase_client import get_supabase, is_supabase_configured
from backend.logger import logger

_VALID_ROLES = {"user", "assistant", "system", "tool"}

_SQLITE_INIT = """
CREATE TABLE IF NOT EXISTS persistent_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Chat',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_p_conv_user ON persistent_conversations(user_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS persistent_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations TEXT,
    metadata TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES persistent_conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_p_msg_conv ON persistent_messages(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_p_msg_user ON persistent_messages(user_id);
"""


@contextmanager
def _sqlite_db():
    conn = sqlite3.connect(settings.SESSION_STORE_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SQLITE_INIT)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class ChatPersistenceService:

    # ------------------------------------------------------------------ #
    # Conversations
    # ------------------------------------------------------------------ #

    def create_conversation(self, user_id: str, title: str, conv_status: str = "active") -> dict:
        """Create a new conversation owned by user_id."""
        clean_title = (title or "New Chat")[:120].strip() or "New Chat"

        if is_supabase_configured():
            try:
                db = get_supabase()
                row_data = {"user_id": user_id, "title": clean_title, "status": conv_status}
                try:
                    res = db.table("conversations").insert(row_data).execute()
                except Exception:
                    # Fallback without status if migration 002 is not yet applied
                    res = db.table("conversations").insert({"user_id": user_id, "title": clean_title}).execute()
                if res and res.data:
                    item = dict(res.data[0])
                    item["_source"] = "supabase"
                    return item
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase create_conversation failed (falling back to SQLite): {exc}")

        # SQLite engine fallback
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with _sqlite_db() as c:
            c.execute(
                "INSERT INTO persistent_conversations (id, user_id, title, status, created_at, updated_at, last_message_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (conv_id, user_id, clean_title, conv_status, now, now, now),
            )
        return {
            "id": conv_id,
            "user_id": user_id,
            "title": clean_title,
            "status": conv_status,
            "created_at": now,
            "updated_at": now,
            "last_message_at": now,
            "_source": "sqlite",
        }

    def get_conversations(self, user_id: str, limit: int = 50, include_archived: bool = False) -> list[dict]:
        """List conversations belonging to user_id, ordered by most recent activity."""
        sb_convs = []
        if is_supabase_configured():
            try:
                db = get_supabase()
                query = (
                    db.table("conversations")
                    .select("id, title, created_at, updated_at, last_message_at")
                    .eq("user_id", user_id)
                )
                res = query.order("last_message_at", desc=True, nullsfirst=False).limit(limit).execute()
                sb_convs = res.data or []
                for sc in sb_convs:
                    sc["_source"] = "supabase"
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase get_conversations failed: {exc}")

        # SQLite conversations
        sqlite_convs = []
        try:
            with _sqlite_db() as c:
                if include_archived:
                    rows = c.execute(
                        "SELECT id, title, status, created_at, updated_at, last_message_at FROM persistent_conversations "
                        "WHERE user_id = ? ORDER BY last_message_at DESC LIMIT ?",
                        (user_id, limit),
                    ).fetchall()
                else:
                    rows = c.execute(
                        "SELECT id, title, status, created_at, updated_at, last_message_at FROM persistent_conversations "
                        "WHERE user_id = ? AND status != 'archived' ORDER BY last_message_at DESC LIMIT ?",
                        (user_id, limit),
                    ).fetchall()
                for r in rows:
                    d = dict(r)
                    d["_source"] = "sqlite"
                    sqlite_convs.append(d)
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite get_conversations failed: {sq_err}")

        # Combine, dedup by id, order by last_message_at descending
        seen_ids = set()
        combined = []
        for c in sb_convs + sqlite_convs:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                combined.append(c)

        combined.sort(key=lambda x: x.get("last_message_at") or x.get("created_at") or "", reverse=True)
        return combined[:limit]

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[dict]:
        """Get a single conversation — returns None if not found or not owned by user."""
        if is_supabase_configured():
            try:
                db = get_supabase()
                res = (
                    db.table("conversations")
                    .select("*")
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if res and res.data and len(res.data) > 0:
                    conv = dict(res.data[0])
                    conv["_source"] = "supabase"
                    return conv
            except Exception as exc:
                logger.debug(f"[Persistence] Supabase get_conversation query note: {exc}")

        # Check SQLite fallback
        try:
            with _sqlite_db() as c:
                row = c.execute(
                    "SELECT * FROM persistent_conversations WHERE id = ? AND user_id = ?",
                    (conversation_id, user_id),
                ).fetchone()
                if row:
                    conv = dict(row)
                    conv["_source"] = "sqlite"
                    return conv
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite get_conversation failed: {sq_err}")

        return None

    def update_conversation_title(self, user_id: str, conversation_id: str, title: str) -> bool:
        """Rename a conversation. Returns True on success."""
        clean_title = (title or "Untitled")[:120].strip() or "Untitled"
        updated = False

        if is_supabase_configured():
            try:
                db = get_supabase()
                res = (
                    db.table("conversations")
                    .update({"title": clean_title, "updated_at": "now()"})
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if res and res.data and len(res.data) > 0:
                    updated = True
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase update_conversation_title failed: {exc}")

        # Also update SQLite if present
        try:
            now = datetime.now(timezone.utc).isoformat()
            with _sqlite_db() as c:
                cur = c.execute(
                    "UPDATE persistent_conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (clean_title, now, conversation_id, user_id),
                )
                if cur.rowcount > 0:
                    updated = True
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite update_conversation_title failed: {sq_err}")

        return updated

    def archive_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Archive a conversation. Returns True on success."""
        updated = False
        if is_supabase_configured():
            try:
                db = get_supabase()
                res = (
                    db.table("conversations")
                    .update({"status": "archived", "updated_at": "now()"})
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if res and res.data and len(res.data) > 0:
                    updated = True
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase archive_conversation failed: {exc}")

        try:
            now = datetime.now(timezone.utc).isoformat()
            with _sqlite_db() as c:
                cur = c.execute(
                    "UPDATE persistent_conversations SET status = 'archived', updated_at = ? WHERE id = ? AND user_id = ?",
                    (now, conversation_id, user_id),
                )
                if cur.rowcount > 0:
                    updated = True
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite archive_conversation failed: {sq_err}")

        return updated

    def update_last_message_at(self, user_id: str, conversation_id: str) -> None:
        """Update last_message_at timestamp on a conversation."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if is_supabase_configured():
            try:
                db = get_supabase()
                db.table("conversations").update({"last_message_at": "now()"}).eq("id", conversation_id).eq("user_id", user_id).execute()
            except Exception as exc:
                logger.debug(f"[Persistence] Supabase update_last_message_at note: {exc}")

        try:
            with _sqlite_db() as c:
                c.execute(
                    "UPDATE persistent_conversations SET last_message_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (now_iso, now_iso, conversation_id, user_id),
                )
        except Exception:
            pass

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation and all its messages (via CASCADE). Returns True on success."""
        deleted = False
        if is_supabase_configured():
            try:
                db = get_supabase()
                res = (
                    db.table("conversations")
                    .delete()
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if res and res.data and len(res.data) > 0:
                    deleted = True
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase delete_conversation failed: {exc}")

        try:
            with _sqlite_db() as c:
                c.execute("DELETE FROM persistent_messages WHERE conversation_id = ? AND user_id = ?", (conversation_id, user_id))
                cur = c.execute("DELETE FROM persistent_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
                if cur.rowcount > 0:
                    deleted = True
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite delete_conversation failed: {sq_err}")

        return deleted

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
        msg_status: str = "completed",
    ) -> dict:
        """
        Insert a message. Validates ownership first.
        Never persists messages for conversations the user doesn't own.
        Includes idempotency guard against double-clicks/retries.
        """
        if role not in _VALID_ROLES:
            raise ValueError(f"Invalid role: {role!r}. Must be one of {_VALID_ROLES}.")

        # Verify ownership before inserting
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        meta = dict(metadata or {})
        meta.setdefault("status", msg_status)

        # Idempotency / Double-click check: check existing messages in this conversation
        existing_messages = self.get_messages(user_id, conversation_id, limit=3)
        if existing_messages:
            last_msg = existing_messages[-1]
            if (
                last_msg.get("role") == role
                and last_msg.get("content") == (content or "")
                and last_msg.get("status", "completed") == msg_status
            ):
                logger.info(f"[Persistence] Deduplicated identical message in conv={conversation_id}")
                return last_msg

        source = conv.get("_source", "supabase" if is_supabase_configured() else "sqlite")

        if source == "supabase" and is_supabase_configured():
            try:
                db = get_supabase()
                row = {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "role": role,
                    "content": content or "",
                    "citations": citations or {},
                    "metadata": meta,
                }
                try:
                    res = db.table("messages").insert({**row, "status": msg_status}).execute()
                except Exception:
                    res = db.table("messages").insert(row).execute()
                if res and res.data:
                    return res.data[0]
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase add_message failed (falling back to SQLite): {exc}")

        # SQLite storage
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with _sqlite_db() as c:
            c.execute(
                "INSERT INTO persistent_messages (id, conversation_id, user_id, role, content, citations, metadata, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    msg_id,
                    conversation_id,
                    user_id,
                    role,
                    content or "",
                    json.dumps(citations or {}),
                    json.dumps(meta),
                    msg_status,
                    now,
                ),
            )
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content or "",
            "citations": citations or {},
            "metadata": meta,
            "status": msg_status,
            "created_at": now,
        }

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
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return []

        source = conv.get("_source")

        if source != "sqlite" and is_supabase_configured():
            try:
                db = get_supabase()
                try:
                    res = (
                        db.table("messages")
                        .select("id, role, content, citations, metadata, status, created_at")
                        .eq("conversation_id", conversation_id)
                        .order("created_at", desc=False)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                except Exception:
                    res = (
                        db.table("messages")
                        .select("id, role, content, citations, metadata, created_at")
                        .eq("conversation_id", conversation_id)
                        .order("created_at", desc=False)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                data = res.data or []
                if data:
                    for m in data:
                        if "status" not in m:
                            m["status"] = (m.get("metadata") or {}).get("status", "completed")
                    return data
            except Exception as exc:
                logger.warning(f"[Persistence] Supabase get_messages note: {exc}")

        # SQLite fallback / SQLite source
        try:
            with _sqlite_db() as c:
                rows = c.execute(
                    "SELECT id, role, content, citations, metadata, status, created_at FROM persistent_messages "
                    "WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                    (conversation_id, limit, offset),
                ).fetchall()
                out = []
                for r in rows:
                    item = dict(r)
                    if item.get("citations") and isinstance(item["citations"], str):
                        try:
                            item["citations"] = json.loads(item["citations"])
                        except Exception:
                            pass
                    if item.get("metadata") and isinstance(item["metadata"], str):
                        try:
                            item["metadata"] = json.loads(item["metadata"])
                        except Exception:
                            pass
                    out.append(item)
                return out
        except Exception as sq_err:
            logger.warning(f"[Persistence] SQLite get_messages failed: {sq_err}")
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
