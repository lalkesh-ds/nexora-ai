import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR))

import streamlit as st

from components import theme, state
from components.chatUI import render_chat
from components.sidebar import render_sidebar

st.set_page_config(
    page_title="Nexora · Multimodal Knowledge Intelligence",
    page_icon=theme.page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    theme.inject_styles()
    state.init_state()
    render_sidebar()
    render_chat()


# Assigned so Streamlit's "magic" never treats a bare call's return value as something to render.
_ = main()
