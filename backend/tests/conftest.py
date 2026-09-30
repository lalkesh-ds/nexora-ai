"""
Shared fixtures. All external providers (Pinecone, Groq, Google embeddings,
web search) are mocked so the suite runs with zero API keys / network
access, per the container's egress restrictions. This validates our own
logic (routing, chunking, OCR fallback, security, citations) without
depending on live third-party services.
"""
import os
import sys
import shutil
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

TEST_DIR = tempfile.mkdtemp(prefix="nexora_test_")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_DIR, "uploads")
os.environ["DOC_HASH_STORE_PATH"] = os.path.join(TEST_DIR, "doc_index.json")
os.environ["SESSION_STORE_PATH"] = os.path.join(TEST_DIR, "sessions.db")
os.environ["CACHE_DIR"] = os.path.join(TEST_DIR, "cache")


@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield
    shutil.rmtree(TEST_DIR, ignore_errors=True)


class FakeChatResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    """Deterministic stand-in for ChatGroq. Echoes a recognizable answer so
    tests can assert on routing/evidence without needing a real model."""
    def invoke(self, prompt):
        text = prompt if isinstance(prompt, str) else str(prompt)
        if "[DOCUMENT CONTEXT]" in text:
            return FakeChatResponse("FAKE_ANSWER: based on the document context.")
        if "[WEB CONTEXT]" in text:
            return FakeChatResponse("FAKE_ANSWER: based on the web context.")
        return FakeChatResponse("FAKE_ANSWER: based on general knowledge.")


@pytest.fixture(autouse=True)
def patch_external_services(monkeypatch):
    import backend.services.embedding_service as es
    import backend.services.vectorstore_service as vs
    import backend.services.llm_provider as lp

    # In-memory fake vector store shared across a test.
    fake_store = {"vectors": []}

    def fake_embed_documents(texts):
        return [[float(len(t) % 7)] * 4 for t in texts]

    def fake_embed_query(text):
        return [float(len(text) % 7)] * 4

    def fake_upsert(ids, vectors, metadatas):
        for i, v, m in zip(ids, vectors, metadatas):
            fake_store["vectors"].append({"id": i, "values": v, "metadata": m})

    def fake_query(vector, top_k=8, document_ids=None):
        matches = fake_store["vectors"]
        if document_ids:
            matches = [m for m in matches if m["metadata"].get("document_id") in document_ids]
        # naive "similarity": everything matches with a decent score so tests
        # can exercise relevance filtering deterministically.
        return [
            {"metadata": m["metadata"], "score": 0.9}
            for m in matches[:top_k]
        ]

    monkeypatch.setattr(es.embedding_service, "embed_documents", fake_embed_documents)
    monkeypatch.setattr(es.embedding_service, "embed_query", fake_embed_query)
    monkeypatch.setattr(vs.vectorstore_service, "upsert", fake_upsert)
    monkeypatch.setattr(vs.vectorstore_service, "query", fake_query)
    fake_factory = lambda *a, **kw: FakeLLM()
    monkeypatch.setattr(lp, "get_chat_llm", fake_factory)

    # These modules imported get_chat_llm by name at module load time, so
    # patching the source module alone won't reach their already-bound
    # reference - patch each call site too.
    import backend.services.answer_service as ans
    monkeypatch.setattr(ans, "get_chat_llm", fake_factory)
    try:
        import backend.routes.vision as vision_route
        monkeypatch.setattr(vision_route, "get_chat_llm", fake_factory)
    except Exception:
        pass

    yield fake_store
