import streamlit as st
from pathlib import Path
from utils.api import ask_question


# Path to Nexora AI avatar
NEXORA_AVATAR = Path(__file__).resolve().parent.parent / "assets" / "nexora.png"


def _avatar():
    """Return the avatar path if the asset actually exists, else fall back
    to Streamlit's default assistant icon instead of crashing the app."""
    return str(NEXORA_AVATAR) if NEXORA_AVATAR.exists() else None


SUGGESTED_PROMPTS = [
    "Summarize the key points of my uploaded documents",
    "What questions should I be asking this data?",
    "Find the most relevant section for pricing details",
]

# Ways of using the same document Q&A pipeline, shown as entry points
# on the empty state. These describe the existing capability, not new features.
CAPABILITIES = [
    ("layers", "Summarize", "Get the key points from your uploaded documents."),
    ("target", "Extract", "Pull specific facts, figures or sections on demand."),
    ("overlap", "Compare", "See how information relates across documents."),
]


_ICONS = {
    "layers": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3.5 3 8l9 4.5 9-4.5-9-4.5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M3 12.5 12 17l9-4.5" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M3 16.5 12 21l9-4.5" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    "target": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="8.25" stroke="currentColor" stroke-width="1.4"/><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.4"/><circle cx="12" cy="12" r="0.75" fill="currentColor"/></svg>',
    "overlap": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="9.5" cy="12" r="6" stroke="currentColor" stroke-width="1.4"/><circle cx="14.5" cy="12" r="6" stroke="currentColor" stroke-width="1.4"/></svg>',
    "doc": '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 20V4a.5.5 0 0 1 .5-.5H7Z" stroke="currentColor" stroke-width="1.3"/><path d="M14 3.5V8h4" stroke="currentColor" stroke-width="1.3"/></svg>',
}


def _icon(name: str) -> str:
    return f'<span class="nx-icon">{_ICONS.get(name, "")}</span>'


def _mark(uid: str, size: int = 28) -> str:
    """Brand mark SVG. Each call gets a unique gradient id so multiple
    copies on the same page never collide. Built as one physical line so
    it never introduces stray indentation when interpolated elsewhere."""
    grad_id = f"nxMarkGrad-{uid}"
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{grad_id}" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#22D3EE"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs>'
        f'<circle cx="16" cy="16" r="10.5" stroke="url(#{grad_id})" stroke-width="1.6"/>'
        f'<circle cx="16" cy="16" r="4.5" stroke="url(#{grad_id})" stroke-width="1.6"/>'
        f'<circle cx="16" cy="5.2" r="1.6" fill="#22D3EE"/>'
        f'<circle cx="24.8" cy="21" r="1.6" fill="#8B5CF6"/></svg>'
    )


def _inject_styles():
    """Nexora theme. Everything here is either a plain color/spacing rule
    or normal in-flow content — deliberately no position:fixed overlays,
    no :has() selectors, and no duplicate element ids, since those are
    the patterns that can silently break rendering in some environments."""
    if st.session_state.get("_nexora_styles_loaded"):
        return

    st.session_state["_nexora_styles_loaded"] = True

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

        :root {
            --nx-bg: #080B12;
            --nx-surface: #0F141D;
            --nx-text: #F5F7FA;
            --nx-muted: #8B95A7;
            --nx-cyan: #22D3EE;
            --nx-violet: #8B5CF6;
            --nx-border: rgba(255,255,255,0.10);
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Depth: painted as the element's own background, so it can
           never sit above content the way a position:fixed layer can. */
        .stApp {
            background-color: var(--nx-bg);
            background-image:
                radial-gradient(760px 420px at 14% -6%, rgba(34,211,238,0.08), transparent 60%),
                radial-gradient(620px 460px at 100% 18%, rgba(139,92,246,0.07), transparent 55%);
            background-attachment: fixed;
        }

        .block-container {
            max-width: 780px;
            padding-top: 2rem;
            padding-bottom: 6rem;
        }

        .nx-icon svg {
            display: block;
        }

        h1, h2, h3, p, span, li, label {
            color: var(--nx-text);
        }

        /* ---- Header ---- */
        .nx-title {
            font-family: 'Manrope', sans-serif;
            font-weight: 800;
            font-size: 1.4rem;
            letter-spacing: -0.01em;
            margin: 0;
        }

        .nx-subtitle {
            color: var(--nx-muted);
            font-size: 0.92rem;
            margin: 0.1rem 0 0 0;
        }

        .nx-status {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.82rem;
            color: var(--nx-muted);
            border: 1px solid var(--nx-border);
            border-radius: 999px;
            padding: 0.3rem 0.75rem;
            background: var(--nx-surface);
        }

        .nx-status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #34D399;
        }

        /* ---- Empty state ---- */
        .nx-empty h2 {
            font-family: 'Manrope', sans-serif;
            font-weight: 700;
            font-size: 1.6rem;
            margin: 1rem 0 0.5rem 0;
        }

        .nx-empty p {
            color: var(--nx-muted);
            font-size: 0.96rem;
            max-width: 30rem;
            margin: 0 auto;
        }

        /* ---- Capability cards (Streamlit-native bordered containers) ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
            border-color: var(--nx-border) !important;
            background: var(--nx-surface);
            transition: border-color 0.15s ease;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: rgba(34,211,238,0.35) !important;
        }

        .nx-cap-icon {
            color: var(--nx-cyan);
            width: 20px;
            height: 20px;
            margin-bottom: 0.4rem;
        }

        /* ---- Suggested prompts / buttons ---- */
        .stButton button {
            border-radius: 10px !important;
            border: 1px solid var(--nx-border) !important;
            background: var(--nx-surface) !important;
            color: var(--nx-text) !important;
            text-align: left !important;
            white-space: normal !important;
            height: auto !important;
            padding: 0.7rem 0.9rem !important;
            transition: border-color 0.15s ease, color 0.15s ease;
        }

        .stButton button:hover {
            border-color: rgba(34,211,238,0.45) !important;
            color: var(--nx-cyan) !important;
        }

        /* ---- Chat ---- */
        div[data-testid="stChatMessageContent"] {
            font-size: 0.95rem;
            line-height: 1.6;
        }

        .nx-sources {
            color: var(--nx-muted);
            font-size: 0.82rem;
            margin-top: 0.35rem;
        }

        .nx-sources .nx-icon {
            width: 13px;
            height: 13px;
            vertical-align: -2px;
            margin-right: 0.3rem;
            display: inline-block;
        }

        /* ---- Composer ---- */
        [data-testid="stChatInput"] textarea {
            border: 1px solid var(--nx-border) !important;
            border-radius: 14px !important;
            background: var(--nx-surface) !important;
            color: var(--nx-text) !important;
        }

        [data-testid="stChatInput"] textarea:focus {
            border-color: rgba(34,211,238,0.5) !important;
            box-shadow: 0 0 0 3px rgba(34,211,238,0.08) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header():
    col_logo, col_status = st.columns([5, 2])

    with col_logo:
        st.markdown(
            '<div style="display:flex; align-items:center; gap:0.6rem;">'
            + _mark('header')
            + '<div><p class="nx-title">Nexora</p>'
            '<p class="nx-subtitle">Your intelligent knowledge workspace</p>'
            "</div></div>",
            unsafe_allow_html=True,
        )

    with col_status:
        st.markdown(
            '<div style="text-align:right; padding-top:0.35rem;">'
            '<span class="nx-status"><span class="nx-status-dot"></span> Online</span>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.write("")


def _render_capabilities():
    cols = st.columns(3)
    for col, (icon_name, title, desc) in zip(cols, CAPABILITIES):
        with col:
            with st.container(border=True):
                st.markdown(
                    f'<div class="nx-cap-icon">{_icon(icon_name)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{title}**")
                st.caption(desc)


def _render_empty_state():
    st.markdown(
        '<div class="nx-empty" style="text-align:center;">'
        + _mark('empty', size=40)
        + "<h2>Welcome to Nexora</h2>"
        "<p>Ask a question about the documents you've shared, and "
        "Nexora will find the answer for you.</p></div>",
        unsafe_allow_html=True,
    )

    st.write("")
    _render_capabilities()

    st.write("")
    st.caption("Or try asking")

    cols = st.columns(len(SUGGESTED_PROMPTS))
    for col, prompt in zip(cols, SUGGESTED_PROMPTS):
        with col:
            if st.button(prompt, key=f"suggested_{prompt}", use_container_width=True):
                st.session_state["_nexora_pending_prompt"] = prompt
                st.rerun()


def _render_sources(sources):
    # Filter out empty/whitespace-only entries so we never render stray
    # separators when the backend returns blank source names.
    clean = [s for s in (sources or []) if isinstance(s, str) and s.strip()]
    if not clean:
        return

    st.markdown(
        f'<div class="nx-sources">{_icon("doc")}Sources: {" · ".join(clean)}</div>',
        unsafe_allow_html=True,
    )


def render_chat():
    _inject_styles()
    _render_header()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Empty state only shows before the first message exists
    if not st.session_state.messages:
        _render_empty_state()

    # Render existing chat history
    for msg in st.session_state.messages:

        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=_avatar()):
                st.markdown(msg["content"])
                _render_sources(msg.get("sources", []))

        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    # Pick up a suggested-prompt click, otherwise wait for typed input
    pending = st.session_state.pop("_nexora_pending_prompt", None)

    user_input = st.chat_input("Message Nexora about your documents...") or pending

    if user_input:

        # User message
        with st.chat_message("user"):
            st.markdown(user_input)

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        # Assistant response
        with st.chat_message("assistant", avatar=_avatar()):
            with st.spinner("Thinking..."):
                response = ask_question(user_input)

            if response.status_code == 200:
                data = response.json()

                answer = data["response"]
                sources = data.get("sources", [])

                st.markdown(answer)
                _render_sources(sources)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    }
                )

            else:
                st.error(f"Something went wrong. Error: {response.text}")