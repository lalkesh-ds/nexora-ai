from typing import List

from backend.schemas import SourceCitation, WebCitation
from backend.services.document_service import document_registry


class CitationService:
    def from_chunks(self, chunks) -> List[SourceCitation]:
        """Convert retrieved document chunks into validated SourceCitation objects.
        Filters out any chunks with unresolvable or 'unknown' filenames and deduplicates citations."""
        citations = []
        seen = set()
        for c in chunks:
            metadata = getattr(c, "metadata", {}) or {}
            doc_id = (metadata.get("document_id") or "").strip()
            filename = (metadata.get("filename") or "").strip()

            # If filename is missing or 'unknown', attempt resolution via document_registry
            if (not filename or filename.lower() in ("unknown", "none", "untitled")) and doc_id:
                rec = document_registry.get(doc_id)
                if rec and rec.get("filename"):
                    filename = rec["filename"].strip()

            # Never output 'unknown' or unverified placeholder filenames as valid citations
            if not filename or filename.lower() in ("unknown", "none", "untitled"):
                continue

            page_number = metadata.get("page_number")
            key = (doc_id, filename, page_number)
            if key in seen:
                continue
            seen.add(key)

            snippet = (getattr(c, "text", "") or "")[:240].strip()
            score = round(float(getattr(c, "score", 0.0) or 0.0), 4)

            citations.append(SourceCitation(
                filename=filename,
                document_id=doc_id,
                page_number=page_number,
                snippet=snippet,
                score=score,
            ))
        return citations

    def from_web_results(self, results) -> List[WebCitation]:
        """Convert web search results into validated WebCitation objects.
        Supports both WebSearchResult objects and dictionaries.
        Validates URL formatting and filters out invalid or duplicate citations."""
        valid = []
        seen_urls = set()
        for r in results:
            if isinstance(r, dict):
                url = (r.get("url") or r.get("link") or "").strip()
                title = (r.get("title") or "").strip()
                snippet = (r.get("snippet") or "").strip()
            else:
                url = (getattr(r, "url", "") or getattr(r, "link", "") or "").strip()
                title = (getattr(r, "title", "") or "").strip()
                snippet = (getattr(r, "snippet", "") or "").strip()

            if not url or url.startswith("javascript:") or "unknown" in url.lower():
                continue
            if not url.startswith(("http://", "https://")):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            valid.append(WebCitation(
                title=title or url,
                url=url,
                snippet=snippet[:240]
            ))
        return valid


citation_service = CitationService()
