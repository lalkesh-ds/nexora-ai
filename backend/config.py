"""
Central configuration for Nexora AI backend.

Every external provider (LLM, embeddings, vector store, web search) is
selected here so it can be swapped via environment variables without
touching business logic.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # ---- LLM ----
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    LLM_ROUTER_MODEL = os.getenv("LLM_ROUTER_MODEL", LLM_MODEL)

    # ---- Embeddings ----
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

    # ---- Vector store ----
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "medicalindex")

    # ---- Vision / OCR ----
    # "groq_vision" | "gemini_vision" | "tesseract" (offline fallback, no key needed)
    VISION_PROVIDER = os.getenv("VISION_PROVIDER", "tesseract")
    GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash")
    OCR_MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("OCR_MIN_TEXT_CHARS_PER_PAGE", "20"))
    # On Windows, pytesseract needs the actual Tesseract-OCR.exe location if
    # it isn't on PATH. e.g. C:\Program Files\Tesseract-OCR\tesseract.exe
    TESSERACT_CMD = os.getenv("TESSERACT_CMD")

    # ---- Web search ----
    # "tavily" | "serper" | "none"
    WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "none")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))

    # ---- Ingestion / files ----
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploaded_docs")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".txt", ".csv", ".xlsx",
        ".jpg", ".jpeg", ".png", ".webp",
    }

    # ---- Retrieval ----
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
    RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "8"))
    RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "4"))
    MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.15"))
    MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "2"))
    MAX_VERIFICATION_REPAIRS = int(os.getenv("MAX_VERIFICATION_REPAIRS", "1"))

    # ---- Conversation ----
    MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))
    SESSION_STORE_PATH = os.getenv("SESSION_STORE_PATH", "./sessions.db")

    # ---- Caching ----
    CACHE_DIR = os.getenv("CACHE_DIR", "./.cache")
    DOC_HASH_STORE_PATH = os.getenv("DOC_HASH_STORE_PATH", "./doc_index.json")

    # ---- Feature flags ----
    ENABLE_WEB_SEARCH = _bool("ENABLE_WEB_SEARCH", WEB_SEARCH_PROVIDER != "none")


settings = Settings()
