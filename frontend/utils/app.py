import streamlit as st
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR))

from components.upload import render_uploader
from components.history_download import render_history_download
from components.chatUI import render_chat




render_uploader()
render_chat()
render_history_download()