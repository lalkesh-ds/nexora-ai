"""Session state for chats and documents (frontend only; talks to the existing API)."""
import uuid

import streamlit as st

from utils.api import create_session_api, list_documents_api


def new_session_id():
    try:
        resp = create_session_api()
        if resp.status_code == 200:
            st.session_state.backend_ok = True
            return resp.json().get("session_id")
        st.session_state.backend_ok = False
    except Exception:
        st.session_state.backend_ok = False
    return None


def _cid() -> str:
    return uuid.uuid4().hex[:8]


def init_state():
    ss = st.session_state
    ss.setdefault("messages", [])
    ss.setdefault("chats", {})          # chat_id -> {"title", "messages", "session_id"}
    ss.setdefault("chat_order", [])     # most recent first
    ss.setdefault("documents", {})      # document_id -> {"filename","status","pages"}
    ss.setdefault("document_ids", {})   # document_id -> filename (kept for compatibility)
    ss.setdefault("upload_issues", [])
    ss.setdefault("uploader_key", 0)
    ss.setdefault("show_sources", True)
    ss.setdefault("show_verification", True)
    ss.setdefault("backend_ok", None)
    ss.setdefault("selected_document_ids", [])
    ss.setdefault("selected_mode", "AUTO")
    if "current_chat_id" not in ss:
        ss.current_chat_id = _cid()
    if "session_id" not in ss:
        ss.session_id = new_session_id()
    if not ss.get("_docs_synced"):
        ss._docs_synced = True
        sync_documents()
    if not ss.get("_sessions_synced"):
        ss._sessions_synced = True
        sync_recent_sessions()


def sync_recent_sessions():
    """Load persistent sessions from backend so sidebar shows past chats across browser refreshes."""
    ss = st.session_state
    try:
        from utils.api import get_recent_sessions_api
        resp = get_recent_sessions_api()
        if resp.status_code == 200:
            data = resp.json().get("sessions", [])
            for s in data:
                sid = s.get("session_id")
                title = s.get("title", "Previous chat")
                if sid and sid not in ss.chats:
                    ss.chats[sid] = {
                        "title": title,
                        "messages": [],  # loaded on demand when opened
                        "session_id": sid,
                    }
                    if sid not in ss.chat_order:
                        ss.chat_order.append(sid)
    except Exception:
        pass


def sync_documents():
    """Load documents already indexed on the backend (GET /documents). Best effort."""
    try:
        resp = list_documents_api()
    except Exception:
        st.session_state.backend_ok = False
        return
    if resp.status_code != 200:
        return
    st.session_state.backend_ok = True
    try:
        data = resp.json()
    except ValueError:
        return
    items = data.get("documents", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return
    for d in items:
        if not isinstance(d, dict):
            continue
        doc_id = d.get("document_id") or d.get("id")
        name = d.get("filename") or d.get("name")
        if not doc_id or not name:
            continue
        st.session_state.documents.setdefault(
            doc_id, {"filename": name, "status": d.get("status") or "completed", "pages": d.get("pages")}
        )
        st.session_state.document_ids.setdefault(doc_id, name)


def chat_title(messages) -> str:
    for m in messages:
        if m.get("role") == "user":
            text = (m.get("content") or "").strip()
            if not text and m.get("attachments"):
                text = m["attachments"][0]["name"]
            if text:
                text = " ".join(text.split())
                return text if len(text) <= 38 else text[:36].rstrip() + "…"
    return "New conversation"


def stash_current() -> bool:
    """Save the live chat into the recents list. True if a new recents entry was created."""
    ss = st.session_state
    if not ss.messages:
        return False
    cid = ss.current_chat_id
    created = cid not in ss.chats
    ss.chats[cid] = {"title": chat_title(ss.messages), "messages": ss.messages, "session_id": ss.get("session_id")}
    if created:
        ss.chat_order.insert(0, cid)
    return created


def new_chat():
    ss = st.session_state
    if not ss.messages:
        return
    stash_current()
    ss.messages = []
    ss.current_chat_id = _cid()
    ss.session_id = new_session_id()
    ss.pop("_nexora_pending_prompt", None)


def open_chat(cid: str):
    ss = st.session_state
    if cid == ss.current_chat_id or cid not in ss.chats:
        return
    stash_current()
    chat = ss.chats[cid]
    # If messages not yet populated, load them from persistent session turns
    if not chat.get("messages") and chat.get("session_id"):
        try:
            from utils.api import get_session_history_api
            resp = get_session_history_api(chat["session_id"])
            if resp.status_code == 200:
                turns = resp.json().get("turns", [])
                chat["messages"] = [{"role": t["role"], "content": t["content"]} for t in turns]
        except Exception:
            pass
    ss.messages = chat.get("messages", [])
    ss.session_id = chat.get("session_id")
    ss.current_chat_id = cid
