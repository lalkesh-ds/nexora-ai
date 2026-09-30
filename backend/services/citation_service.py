from typing import List

from backend.schemas import SourceCitation, WebCitation


class CitationService:
    def from_chunks(self, chunks) -> List[SourceCitation]:
        citations = []
        for c in chunks:
            citations.append(SourceCitation(
                filename=c.metadata.get("filename", "unknown"),
                document_id=c.metadata.get("document_id", ""),
                page_number=c.metadata.get("page_number"),
                snippet=c.text[:240],
                score=round(c.score, 4),
            ))
        return citations

    def from_web_results(self, results) -> List[WebCitation]:
        return [
            WebCitation(title=r.title or None, url=r.url, snippet=(r.snippet or "")[:240])
            for r in results
        ]


citation_service = CitationService()
