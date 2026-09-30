import requests

try:
    from utils.config import API_URL
except ImportError:
    try:
        from config import API_URL
    except ImportError:
        API_URL = "http://localhost:8000"

TIMEOUT = 180


# ---- Documents (new multimodal upload: pdf, docx, txt, csv, xlsx, images) ----
def upload_documents_api(files):
    files_payload = [("files", (f.name, f.read(), f.type or "application/octet-stream")) for f in files]
    return requests.post(f"{API_URL}/documents/upload", files=files_payload, timeout=TIMEOUT)


def list_documents_api():
    return requests.get(f"{API_URL}/documents", timeout=TIMEOUT)


def delete_document_api(document_id):
    return requests.delete(f"{API_URL}/documents/{document_id}", timeout=TIMEOUT)


# ---- Conversation sessions ----
def create_session_api():
    return requests.post(f"{API_URL}/conversation/session", timeout=TIMEOUT)


# ---- Main query endpoint (intelligent router: general/doc/web/hybrid) ----
def query_api(question, session_id=None, document_ids=None, mode="AUTO"):
    payload = {
        "question": question,
        "session_id": session_id,
        "document_ids": document_ids or None,
        "mode": mode,
    }
    return requests.post(f"{API_URL}/query", json=payload, timeout=TIMEOUT)


# ---- Direct image/vision Q&A ----
def vision_query_api(image_file, question):
    files = {"image": (image_file.name, image_file.read(), image_file.type or "image/png")}
    data = {"question": question}
    return requests.post(f"{API_URL}/vision/query", files=files, data=data, timeout=TIMEOUT)


# ---- Legacy aliases kept so any older calling code doesn't break ----
def upload_pdfs_api(files):
    return upload_documents_api(files)


def ask_question(question, session_id=None):
    return query_api(question, session_id=session_id)
