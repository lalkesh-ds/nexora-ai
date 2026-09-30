import streamlit as st


def render_history_download():
    messages = st.session_state.get("messages") or []
    chat_text = "\n\n".join(f"{m['role'].upper()}: {m.get('content', '')}" for m in messages)
    st.download_button(
        "Download chat history",
        chat_text,
        file_name="chat_history.txt",
        mime="text/plain",
        icon=":material/download:",
        use_container_width=True,
        disabled=not messages,
        key="nx_download_history",
    )
