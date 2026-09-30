# backend run = uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.middlewares.exception_handlers import catch_exception_middleware
from backend.routes.upload_pdfs import router as upload_router
from backend.routes.ask_question import router as ask_router
from backend.routes.documents import router as documents_router
from backend.routes.query import router as query_router
from backend.routes.vision import router as vision_router
from backend.routes.conversation import router as conversation_router


app = FastAPI(
    title="Nexora AI API",
    description="Multimodal RAG + OCR/Vision + Web Search + General AI backend",
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# middleware exception handlers
app.middleware("http")(catch_exception_middleware)

# ---- Routers ----
# Legacy (backward compatible)
app.include_router(upload_router)
app.include_router(ask_router)

# New API
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(vision_router)
app.include_router(conversation_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
