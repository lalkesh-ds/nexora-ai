import streamlit as st

from components import theme, state
from components.history_download import render_history_download
from components.theme import esc
from components.upload import render_uploader, render_knowledge_sources
from utils.config import API_URL


def _recent_chats():
    ss = st.session_state
    state.stash_current()
    st.markdown('<div class="nx-side-title"><span>Recent chats</span></div>', unsafe_allow_html=True)
    if not ss.chat_order:
        st.markdown('<div class="nx-empty-note">Your conversations will appear here.</div>', unsafe_allow_html=True)
        return
    for cid in ss.chat_order[:8]:
        chat = ss.chats[cid]
        active = cid == ss.current_chat_id
        st.button(
            chat["title"],
            key=f"nx_recent_{'active_' if active else ''}{cid}",
            icon=":material/chat_bubble:" if active else ":material/chat_bubble_outline:",
            on_click=state.open_chat,
            args=(cid,),
            use_container_width=True,
        )


def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="nx-brand">' + theme.brand_mark("side", 36) +
            '<div><div class="nx-brand-name">NEXORA</div>'
            '<div class="nx-brand-tag">Multimodal Knowledge Intelligence</div></div></div>',
            unsafe_allow_html=True,
        )
        st.button("New chat", key="nx_new", icon=":material/add:", type="primary",
                  on_click=state.new_chat, use_container_width=True)

        _recent_chats()

        st.markdown('<div class="nx-side-title"><span>Execution Mode</span></div>', unsafe_allow_html=True)
        mode_labels = {
            "AUTO": "🤖 Auto · Intelligent Router",
            "WEB_SEARCH": "🌐 Live Web Research",
            "DOCUMENT_RAG": "📄 Document Intelligence",
            "HYBRID": "🔀 Hybrid (Docs + Web)",
            "GENERAL_LLM": "🧠 General Knowledge",
        }
        current_mode = st.session_state.get("selected_mode", "AUTO")
        mode_keys = list(mode_labels.keys())
        default_idx = mode_keys.index(current_mode) if current_mode in mode_keys else 0
        selected = st.selectbox(
            "Mode",
            options=mode_keys,
            format_func=lambda k: mode_labels[k],
            index=default_idx,
            key="selected_mode",
            label_visibility="collapsed",
        )

        render_uploader()
        render_knowledge_sources()

        st.markdown('<div class="nx-side-title"><span>Settings</span></div>', unsafe_allow_html=True)
        with st.expander(":material/settings: Preferences"):
            st.toggle("Show source citations", key="show_sources")
            st.toggle("Show verification & grounding", key="show_verification")
            render_history_download()
            st.caption(f"API · {API_URL}")
