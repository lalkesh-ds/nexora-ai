"""Turn whatever the backend sends as "citations" into lightweight source info.

Only a file name and page number are ever extracted. Document text
(`page_content`), file bytes and other payload are never read or returned, so
a raw LangChain Document / UploadedFile / PDF object can't leak into the UI no
matter what shape a citation arrives in (dict, plain string, Document repr, or
an object with a `.metadata` attribute).
"""
import ntpath
import re

_NAME_KEYS = ("filename", "file_name", "source", "name", "title")
_PAGE_KEYS = ("page_number", "page", "page_label")
_MAX_NAME = 120

_SRC_RE = re.compile(r"""['"](?:filename|file_name|source)['"]\s*:\s*['"]([^'"]+)['"]""")
_PAGE_RE = re.compile(r"""['"](?:page_number|page|page_label)['"]\s*:\s*['"]?(\d+)""")
_PAGE_HINT_RE = re.compile(r"(?:\(\s*p\.?\s*(\d+)\s*\)|\bpage\s+(\d+)\b|\bp\.\s*(\d+)\b)", re.I)


def _base(name) -> str:
    name = str(name).strip()
    if not name:
        return ""
    return ntpath.basename(name.replace("\\", "/").rstrip("/")) or ""


def _as_page(value):
    try:
        n = int(str(value).strip())
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _from_mapping(m):
    meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
    name = next((m.get(k) or meta.get(k) for k in _NAME_KEYS if m.get(k) or meta.get(k)), "")
    page = next((m.get(k) if m.get(k) is not None else meta.get(k) for k in _PAGE_KEYS
                 if m.get(k) is not None or meta.get(k) is not None), None)
    return _base(name), _as_page(page)


def _from_string(s: str):
    s = s.strip()
    if not s:
        return "", None
    if "page_content" in s or "metadata=" in s or "Document(" in s:
        m = _SRC_RE.search(s)
        p = _PAGE_RE.search(s)
        return (_base(m.group(1)) if m else ""), (_as_page(p.group(1)) if p else None)
    if len(s) > _MAX_NAME or "\n" in s:
        return "", None
    page = None
    hint = _PAGE_HINT_RE.search(s)
    if hint:
        page = _as_page(next(g for g in hint.groups() if g))
        s = _PAGE_HINT_RE.sub("", s).strip(" ·-–—,:;")
    return _base(s), page


def _one(c):
    if isinstance(c, dict):
        return _from_mapping(c)
    if isinstance(c, str):
        return _from_string(c)
    meta = getattr(c, "metadata", None)  # LangChain Document: metadata only, never page_content
    if isinstance(meta, dict):
        return _from_mapping({"metadata": meta})
    return "", None


def normalize_doc_citations(citations):
    """-> [(filename, [pages...])] de-duplicated, order of first appearance."""
    if isinstance(citations, (dict, str)) or not hasattr(citations, "__iter__"):
        citations = [citations] if citations else []
    found = {}
    for c in citations:
        name, page = _one(c)
        if not name:
            continue
        name = name[:_MAX_NAME]
        pages = found.setdefault(name, [])
        if page and page not in pages:
            pages.append(page)
    return [(n, sorted(p)) for n, p in found.items()]


def normalize_web_citations(citations):
    """-> [(title, url)] for http(s) links only, de-duplicated by url."""
    if isinstance(citations, dict):
        citations = [citations]
    seen, out = set(), []
    for w in citations or []:
        if not isinstance(w, dict):
            continue
        url = str(w.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        title = str(w.get("title") or "").strip()[:100] or re.sub(r"^https?://(www\.)?", "", url)[:60]
        out.append((title, url))
    return out


def format_pages(pages) -> str:
    if not pages:
        return ""
    if len(pages) == 1:
        return f"Page {pages[0]}"
    return "Pages " + ", ".join(str(p) for p in pages)


def normalize_detailed_doc_citations(citations):
    """Returns list of rich dicts: {"filename": ..., "pages": [...], "snippets": [...], "score": ...}"""
    if not citations:
        return []
    items = []
    seen = {}
    for c in citations:
        if isinstance(c, dict):
            fn = c.get("filename") or "Document"
            pg = c.get("page_number")
            snip = c.get("snippet") or ""
            score = c.get("score")
        else:
            fn = getattr(c, "filename", "Document")
            pg = getattr(c, "page_number", None)
            snip = getattr(c, "snippet", "")
            score = getattr(c, "score", None)

        if fn not in seen:
            entry = {"filename": fn, "pages": [], "snippets": [], "score": score}
            seen[fn] = entry
            items.append(entry)
        if pg and pg not in seen[fn]["pages"]:
            seen[fn]["pages"].append(pg)
        if snip and snip not in seen[fn]["snippets"]:
            seen[fn]["snippets"].append(snip)
    return items


def normalize_detailed_web_citations(citations):
    """Returns list of rich dicts: {"title": ..., "url": ..., "snippet": ...}"""
    if not citations:
        return []
    items = []
    seen = set()
    for c in citations:
        if isinstance(c, dict):
            url = c.get("url", "")
            title = c.get("title") or url
            snip = c.get("snippet") or ""
        else:
            url = getattr(c, "url", "")
            title = getattr(c, "title", None) or url
            snip = getattr(c, "snippet", "")
        if url and url not in seen:
            seen.add(url)
            items.append({"title": title, "url": url, "snippet": snip})
    return items
