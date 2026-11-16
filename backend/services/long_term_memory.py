"""
Long-Term Memory Service for Nexora AI.

Stores cross-session user knowledge: topic summaries, preferences, and
frequently-asked subjects, so the assistant can provide context-aware
answers even in a fresh session.

Storage: SQLite (same DB as sessions) — no new infrastructure needed.

Schema:
  user_memory(user_id, topic, summary, turn_count, last_updated)

The memory is retrieved at query time by matching the current question
keywords against stored topics (fast in-process trie/set lookup), then
injected as a [USER MEMORY] context block into the prompt — exactly like
document or web context.

Memory is updated after EVERY successful assistant turn (async, non-blocking).
A rolling summary prevents unbounded growth: when turn_count exceeds
MAX_TURNS_PER_TOPIC, the existing summary is condensed with the new turn.
"""
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

from backend.config import settings
from backend.logger import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    turn_count INTEGER DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_user_memory_user ON user_memory(user_id);
"""

_STOP_WORDS = {
    "what", "is", "the", "and", "or", "in", "on", "for", "with", "a",
    "an", "to", "of", "about", "this", "that", "it", "are", "was", "were",
    "be", "been", "have", "has", "do", "does", "did", "can", "could",
    "would", "should", "tell", "me", "explain", "how", "why", "please",
    "give", "list", "describe", "show",
}

MAX_TURNS_PER_TOPIC = 5
MAX_MEMORY_TOPICS = 20   # per user
MAX_INJECT_TOPICS = 3    # max topics to inject per query


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.SESSION_STORE_PATH)
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class LongTermMemoryService:
    """Cross-session user memory backed by SQLite."""

    def __init__(self):
        self._lock = threading.Lock()
        # Ensure tables exist on startup
        try:
            with _conn():
                pass
        except Exception as e:
            logger.warning(f"[LTM] Schema init warning: {e}")

    # ------------------------------------------------------------------
    # Read / Retrieval
    # ------------------------------------------------------------------

    def retrieve_relevant(self, user_id: str, question: str) -> str:
        """
        Return a formatted memory block relevant to the question,
        or empty string if nothing relevant is found.
        """
        if not user_id:
            return ""

        keywords = self._extract_keywords(question)
        if not keywords:
            return ""

        memories = self._fetch_memories(user_id)
        if not memories:
            return ""

        # Score each stored topic by keyword overlap with the question
        scored = []
        for mem in memories:
            topic_words = set(re.findall(r"\w+", mem["topic"].lower()))
            summary_words = set(re.findall(r"\w+", mem["summary"].lower()))
            overlap = len(keywords & (topic_words | summary_words))
            if overlap > 0:
                scored.append((overlap, mem))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [m for _, m in scored[:MAX_INJECT_TOPICS]]

        lines = []
        for m in top:
            lines.append(
                f"- Topic: {m['topic']}\n  Summary: {m['summary']}"
                f" (last discussed: {m['last_updated'][:10]})"
            )

        return "[USER MEMORY — Prior Conversation Context]\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # Write / Update
    # ------------------------------------------------------------------

    def update(
        self,
        user_id: str,
        question: str,
        answer: str,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Update long-term memory with a completed QA turn.
        Called asynchronously — errors must not propagate to the caller.
        """
        if not user_id:
            return
        try:
            topic = self._extract_topic(question)
            if not topic:
                return
            self._upsert_memory(user_id, topic, question, answer)
        except Exception as e:
            logger.debug(f"[LTM] Memory update warning (non-fatal): {e}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> set:
        words = re.findall(r"\w+", text.lower())
        return {w for w in words if w not in _STOP_WORDS and len(w) > 2}

    def _extract_topic(self, question: str) -> str:
        """
        Extract a short topic label (3-5 words) from a question.
        Uses noun-phrase heuristics; falls back to first 5 content words.
        """
        keywords = list(self._extract_keywords(question))
        if not keywords:
            return ""
        # Take up to 4 most significant words (longer = more specific)
        keywords.sort(key=len, reverse=True)
        topic = " ".join(keywords[:4]).lower()
        return topic[:80]  # hard cap

    def _fetch_memories(self, user_id: str) -> List[Dict]:
        try:
            with _conn() as c:
                rows = c.execute(
                    "SELECT topic, summary, turn_count, last_updated "
                    "FROM user_memory WHERE user_id = ? "
                    "ORDER BY last_updated DESC LIMIT ?",
                    (user_id, MAX_MEMORY_TOPICS),
                ).fetchall()
            return [
                {
                    "topic": r[0],
                    "summary": r[1],
                    "turn_count": r[2],
                    "last_updated": r[3],
                }
                for r in rows
            ]
        except Exception as e:
            logger.debug(f"[LTM] Fetch warning: {e}")
            return []

    def _upsert_memory(
        self, user_id: str, topic: str, question: str, answer: str
    ) -> None:
        with self._lock:
            with _conn() as c:
                existing = c.execute(
                    "SELECT id, summary, turn_count FROM user_memory "
                    "WHERE user_id = ? AND topic = ?",
                    (user_id, topic),
                ).fetchone()

                if existing:
                    mem_id, old_summary, turn_count = existing
                    new_count = turn_count + 1
                    if new_count > MAX_TURNS_PER_TOPIC:
                        # Condense: merge old summary with new turn
                        new_summary = self._condense(old_summary, question, answer)
                        new_count = MAX_TURNS_PER_TOPIC  # reset counter
                    else:
                        # Append the gist of this turn
                        gist = answer[:200].strip()
                        new_summary = f"{old_summary} | {gist}"[:600]
                    c.execute(
                        "UPDATE user_memory SET summary=?, turn_count=?, last_updated=? "
                        "WHERE id=?",
                        (new_summary, new_count, datetime.utcnow().isoformat(), mem_id),
                    )
                else:
                    # Enforce per-user topic cap (evict oldest)
                    count = c.execute(
                        "SELECT COUNT(*) FROM user_memory WHERE user_id=?", (user_id,)
                    ).fetchone()[0]
                    if count >= MAX_MEMORY_TOPICS:
                        c.execute(
                            "DELETE FROM user_memory WHERE id = ("
                            "  SELECT id FROM user_memory WHERE user_id=? "
                            "  ORDER BY last_updated ASC LIMIT 1)",
                            (user_id,),
                        )
                    gist = answer[:300].strip()
                    c.execute(
                        "INSERT INTO user_memory(user_id, topic, summary, turn_count, last_updated) "
                        "VALUES(?,?,?,1,?)",
                        (user_id, topic, gist, datetime.utcnow().isoformat()),
                    )

    def _condense(self, old_summary: str, question: str, new_answer: str) -> str:
        """Condense old summary + new turn into a fresh summary using LLM."""
        try:
            from backend.services.llm_provider import get_chat_llm

            llm = get_chat_llm(temperature=0.0)
            prompt = (
                "You are summarizing a user's conversation history for memory. "
                "Merge the existing memory and the new QA turn into a single concise summary (max 250 words).\n\n"
                f"Existing memory:\n{old_summary}\n\n"
                f"New question: {question}\n"
                f"New answer (excerpt): {new_answer[:300]}\n\n"
                "Merged summary:"
            )
            resp = llm.invoke(prompt)
            return (resp.content or old_summary)[:600]
        except Exception:
            return (old_summary + " | " + new_answer[:200])[:600]


long_term_memory = LongTermMemoryService()
