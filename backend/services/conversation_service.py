"""
ConversationService: session IDs, turn history, and per-session document
selection - backed by SQLite so it survives process restarts without
adding a new infra dependency.

Only the last MAX_HISTORY_TURNS turns are ever returned to the caller, so
we never resend a full, ever-growing transcript to the LLM.

Active document tracking: the `sessions.document_ids` column stores a
comma-separated list of the document_ids most recently uploaded or
explicitly selected in this session. The router uses this as a fallback
"what is the user probably talking about" signal when a query doesn't
name a document_id explicitly - this is what makes "I just uploaded an
image, now ask a follow-up about it without repeating the id" work.
"""
import sqlite3
import uuid
from contextlib import contextmanager
from typing import List, Optional

from backend.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    document_ids TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.SESSION_STORE_PATH)
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class ConversationService:
    def create_session(self) -> str:
        session_id = uuid.uuid4().hex
        with _conn() as c:
            c.execute("INSERT INTO sessions (session_id) VALUES (?)", (session_id,))
        return session_id

    def ensure_session(self, session_id: Optional[str]) -> str:
        if not session_id:
            return self.create_session()
        with _conn() as c:
            row = c.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                return session_id
            c.execute("INSERT INTO sessions (session_id) VALUES (?)", (session_id,))
        return session_id

    def add_turn(self, session_id: str, role: str, content: str):
        with _conn() as c:
            c.execute(
                "INSERT INTO turns (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def get_history(self, session_id: str, limit: int = None) -> List[dict]:
        limit = limit or settings.MAX_HISTORY_TURNS
        with _conn() as c:
            rows = c.execute(
                "SELECT role, content FROM turns WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [{"role": r, "content": ct} for r, ct in reversed(rows)]

    def history_as_text(self, session_id: str) -> str:
        turns = self.get_history(session_id)
        return "\n".join(f"{t['role']}: {t['content']}" for t in turns)

    def set_active_documents(self, session_id: str, document_ids: List[str]):
        """Record which document(s) this session is currently 'looking at'.
        Called after a successful upload (with a session_id) or when a
        client explicitly selects document_ids on a /query call."""
        if not document_ids:
            return
        joined = ",".join(document_ids)
        with _conn() as c:
            c.execute(
                "UPDATE sessions SET document_ids = ? WHERE session_id = ?",
                (joined, session_id),
            )

    def get_active_documents(self, session_id: str) -> List[str]:
        with _conn() as c:
            row = c.execute(
                "SELECT document_ids FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row or not row[0]:
            return []
        return [d for d in row[0].split(",") if d]


conversation_service = ConversationService()
