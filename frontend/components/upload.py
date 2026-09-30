import requests
import streamlit as st

from components import theme
from components.theme import esc
from utils.api import upload_documents_api, delete_document_api

SUPPORTED_TYPES = ["pdf", "docx", "txt", "csv", "xlsx", "jpg", "jpeg", "png", "webp"]
IMAGE_TYPES = {"jpg", "jpeg", "png", "webp"}


def ext_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def is_image(name: str) -> bool:
    return ext_of(name) in IMAGE_TYPES


# ------------------------------------------------------------- ingestion ----
def ingest_documents(files):
    """Send files through the existing upload endpoint and record the result.

    Returns (accepted, issues): `accepted` are documents now searchable,
    `issues` are {"filename","status","error"} entries for anything rejected/failed.
    """
    ss = st.session_state
    names = [f.name for f in files]
    try:
        response = upload_documents_api(files)
    except requests.RequestException:
        ss.backend_ok = False
        return [], [{"filename": n, "status": "failed", "error": "Couldn't reach the Nexora API."} for n in names]

    ss.backend_ok = True
    if response.status_code != 200:
        msg = (response.text or "Upload failed").strip().replace("\n", " ")[:160]
        return [], [{"filename": n, "status": "failed", "error": msg} for n in names]

    accepted, issues = [], []
    for doc in response.json().get("documents", []):
        name = doc.get("filename", "unknown")
        status = doc.get("status", "unknown")
        if status == "completed" and doc.get("document_id"):
            rec = {"filename": name, "status": "completed", "pages": doc.get("pages")}
            ss.documents[doc["document_id"]] = rec
            ss.document_ids[doc["document_id"]] = name
            accepted.append(rec)
        else:
            issues.append({
                "filename": name,
                "status": "rejected" if status == "rejected" else "failed",
                "error": str(doc.get("error") or ("Rejected" if status == "rejected" else "Processing failed"))[:160],
            })
    return accepted, issues


def _delete(doc_id: str):
    ss = st.session_state
    try:
        resp = delete_document_api(doc_id)
        ok = resp.status_code in (200, 202, 204)
    except requests.RequestException:
        ok = False
    if ok:
        ss.documents.pop(doc_id, None)
        ss.document_ids.pop(doc_id, None)
        if "scope_ids" in ss:
            ss.scope_ids = [i for i in ss.scope_ids if i != doc_id]
    else:
        ss.upload_issues = [{"filename": ss.documents.get(doc_id, {}).get("filename", "document"),
                             "status": "failed", "error": "Couldn't remove this document."}]


# --------------------------------------------------------------- cards ------
_STATUS = {"completed": ("Ready", "ok"), "rejected": ("Rejected", "warn"), "failed": ("Failed", "err")}


def _doc_card(name, status="completed", pages=None, error=None, busy=False):
    ic, tint = theme.file_kind(name)
    label, cls = ("Processing", "") if busy else _STATUS.get(status, (str(status).title(), "warn"))
    bits = [f'<span class="nx-st {cls}">{esc(label)}</span>']
    if not busy and pages not in (None, "", 0):
        try:
            n = int(pages)
            bits.append(f"{n} page{'s' if n != 1 else ''}")
        except (TypeError, ValueError):
            pass
    if error and not busy:
        bits = [f'<span class="nx-st {cls}">{esc(error)}</span>']
    return theme.html(
        f'<div class="nx-doc{" busy" if busy else ""}">'
        f'<div class="nx-doc-ic {tint}">{theme.icon(ic, 16)}</div>'
        f'<div class="nx-doc-body"><div class="nx-doc-name" title="{esc(name)}">{esc(name)}</div>'
        f'<div class="nx-doc-meta">{" · ".join(bits)}</div></div></div>'
    )


def _section_title(text, count=None):
    badge = f'<span class="nx-count">{count}</span>' if count else ""
    st.markdown(f'<div class="nx-side-title"><span>{esc(text)}</span>{badge}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------ sidebar UI ----
def render_uploader():
    """Sidebar 'Documents' section: uploader + document cards."""
    ss = st.session_state
    docs = ss.documents
    _section_title("Documents", len(docs))

    with st.expander(":material/upload_file: Add files", expanded=not docs):
        files = st.file_uploader(
            "Upload files",
            type=SUPPORTED_TYPES,
            accept_multiple_files=True,
            label_visibility="collapsed",
            key=f"uploader_{ss.uploader_key}",
        )
        st.caption("PDF (text or scanned), DOCX, TXT, CSV, XLSX, or images.")
        clicked = st.button("Upload & index", type="primary", use_container_width=True,
                            disabled=not files, key="nx_upload_btn")

    busy = st.empty()

    if clicked and files:
        busy.markdown("".join(_doc_card(f.name, busy=True) for f in files), unsafe_allow_html=True)
        _, issues = ingest_documents(files)
        ss.upload_issues = issues
        ss.uploader_key += 1
        st.rerun()

    for issue in ss.upload_issues:
        st.markdown(_doc_card(issue["filename"], issue["status"], error=issue["error"]), unsafe_allow_html=True)

    if not docs and not ss.upload_issues:
        st.markdown(
            '<div class="nx-empty-note">No documents yet. Add files above to build your knowledge base.</div>',
            unsafe_allow_html=True,
        )

    for doc_id, d in list(docs.items()):
        c1, c2 = st.columns([7, 1.4], vertical_alignment="center", gap="small")
        c1.markdown(_doc_card(d["filename"], d.get("status", "completed"), d.get("pages")), unsafe_allow_html=True)
        c2.button("", icon=":material/close:", key=f"nx_del_{doc_id}", help="Remove document",
                  on_click=_delete, args=(doc_id,))


def render_knowledge_sources():
    """Sidebar 'Knowledge Sources': choose which documents Nexora searches."""
    ss = st.session_state
    _section_title("Knowledge sources")
    docs = ss.documents
    if docs:
        picked = st.multiselect(
            "Search scope",
            options=list(docs.keys()),
            format_func=lambda i: docs[i]["filename"],
            placeholder="All documents",
            key="scope_ids",
            label_visibility="collapsed",
        )
        ss.selected_document_ids = list(picked)
    else:
        ss.selected_document_ids = []
    scope = f"{len(ss.selected_document_ids)} selected" if ss.selected_document_ids else "All documents"
    st.markdown(
        f'<div class="nx-src-row"><span>{theme.icon("doc", 14)}&nbsp; Documents</span><b>{esc(scope if docs else "None")}</b></div>'
        f'<div class="nx-src-row" style="margin-top:.4rem"><span>{theme.icon("globe", 14)}&nbsp; Web research</span><b>Auto</b></div>',
        unsafe_allow_html=True,
    )
