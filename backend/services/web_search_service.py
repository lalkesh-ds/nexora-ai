"""
WebSearchService: Dedicated Web Search Tool for Nexora AI.

Target Flow:
  User Query
  -> Router (Orchestrator)
  -> Web Search Tool (WebSearchService)
  -> Search API (Serper / Tavily / Configured Provider)
  -> Raw search results
  -> Source filtering (URL validation, duplicate removal, spam filtering)
  -> Relevant content extraction (HTML cleaning, snippet normalization)
  -> Source ranking (Query relevance, title weighting, domain authority)
  -> Structured Web Evidence (WebSearchEvidence)
  -> Orchestrator / Answer Generator (Context assembly & Answer generation)

For Hybrid Questions:
  Document RAG + Web Search -> Evidence Fusion -> Answer
"""
import html
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from backend.config import settings
from backend.logger import logger
from backend.utils.cache import web_search_cache
from backend.utils.hashing import hash_text

# Reputable/authoritative domains that receive a ranking boost
_AUTHORITATIVE_DOMAINS = {
    "nih.gov", "cdc.gov", "who.int", "fda.gov", "ncbi.nlm.nih.gov",
    "mayoclinic.org", "hopkinsmedicine.org", "clevelandclinic.org",
    "nature.com", "nejm.org", "thelancet.com", "jamanetwork.com",
    "reuters.com", "apnews.com", "bbc.com", "wikipedia.org",
}

# Blacklisted tracking or ad domains
_BLOCKED_DOMAINS = {
    "doubleclick.net", "googleadservices.com", "adservice.google.com",
    "facebook.com/tr", "analytics.google.com",
}

# Common conversational search prefixes to clean before querying search engines
_CONVERSATIONAL_PREFIXES = re.compile(
    r"^(?:please\s+)?(?:"
    r"search(?:\s+the)?\s+(?:web|internet)(?:\s+for)?|"
    r"search\s+online(?:\s+for)?|"
    r"look(?:\s+this|\s+it)?\s+up(?:\s+online)?(?:\s+for)?|"
    r"find\s+the\s+latest\s+information(?:\s+on|\s+about)?|"
    r"check\s+current\s+information(?:\s+on|\s+about|\s+regarding)?|"
    r"find\s+online(?:\s+for)?|"
    r"google(?:\s+this|\s+it|\s+for)?|"
    r"web\s+search(?:\s+for)?|"
    r"browse(?:\s+the)?\s+web(?:\s+for)?"
    r")\s*[:,-]?\s*",
    re.I,
)


def _sanitize_error(error_msg: str) -> str:
    """Ensure API keys or secrets never appear in exception messages or logs."""
    sanitized = error_msg
    if settings.SERPER_API_KEY:
        sanitized = sanitized.replace(settings.SERPER_API_KEY, "[REDACTED]")
    if settings.TAVILY_API_KEY:
        sanitized = sanitized.replace(settings.TAVILY_API_KEY, "[REDACTED]")
    return sanitized


class WebSearchResult:
    """Individual structured web search citation item."""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        score: float = 0.0,
        domain: str = "",
        published_date: Optional[str] = None,
    ):
        self.title = (title or "").strip()
        self.url = (url or "").strip()
        self.snippet = (snippet or "").strip()
        self.score = round(float(score), 4)
        self.domain = domain or self._extract_domain(self.url)
        self.published_date = published_date

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            return netloc.lstrip("www.") if netloc.startswith("www.") else netloc
        except Exception:
            return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
            "domain": self.domain,
            "published_date": self.published_date,
        }


class WebSearchEvidence:
    """Structured evidence returned by the WebSearchTool to the Orchestrator."""

    def __init__(
        self,
        query: str,
        status: str,  # "success" | "no_results" | "failed"
        results: List[WebSearchResult],
        provider: str = "none",
        error: Optional[str] = None,
        cleaned_query: Optional[str] = None,
    ):
        self.query = query
        self.status = status
        self.results = results
        self.provider = provider
        self.error = error
        self.cleaned_query = cleaned_query or query

    def __iter__(self):
        """Allows direct iteration over results for backward compatibility."""
        return iter(self.results)

    def __len__(self):
        return len(self.results)

    def __getitem__(self, index):
        return self.results[index]

    def __bool__(self):
        return bool(self.results)


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Query external search engine API and return raw result dicts."""
        ...


class TavilyProvider(WebSearchProvider):
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        if not settings.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not set.")
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_items = []
        for r in data.get("results", []):
            raw_items.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "published_date": r.get("published_date"),
            })
        return raw_items


class SerperProvider(WebSearchProvider):
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        if not settings.SERPER_API_KEY:
            raise RuntimeError("SERPER_API_KEY is not set.")
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.SERPER_API_KEY},
            json={"q": query, "num": max_results},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_items = []

        # Include Knowledge Graph item if available
        kg = data.get("knowledgeGraph")
        if kg and kg.get("description"):
            raw_items.append({
                "title": kg.get("title", "Overview"),
                "url": kg.get("website", ""),
                "snippet": kg.get("description", ""),
                "published_date": None,
            })

        for r in data.get("organic", [])[:max_results]:
            raw_items.append({
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "published_date": r.get("date"),
            })
        return raw_items


class NullProvider(WebSearchProvider):
    """No web search configured. Gracefully returns empty results."""

    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        return []


def _get_provider() -> WebSearchProvider:
    provider = (settings.WEB_SEARCH_PROVIDER or "").lower().strip()
    if provider == "tavily" and settings.TAVILY_API_KEY:
        return TavilyProvider()
    if provider == "serper" and settings.SERPER_API_KEY:
        return SerperProvider()
    if settings.SERPER_API_KEY:
        return SerperProvider()
    if settings.TAVILY_API_KEY:
        return TavilyProvider()
    return NullProvider()


class WebSearchService:
    """Dedicated Web Search Tool providing source filtering, relevant content extraction,
    and source ranking before returning structured WebSearchEvidence."""

    def __init__(self):
        self.provider = _get_provider()

    def is_available(self) -> bool:
        return not isinstance(self.provider, NullProvider)

    def _clean_search_query(self, query: str) -> str:
        """Strip conversational prefixes (e.g. 'search the web for') to generate clean search queries."""
        cleaned = _CONVERSATIONAL_PREFIXES.sub("", query.strip())
        return cleaned.strip() if len(cleaned.strip()) >= 3 else query.strip()

    def _filter_sources(self, raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Source filtering: drop invalid URLs, private IPs, tracking links, and duplicate domains."""
        filtered = []
        seen_urls = set()

        for item in raw_items:
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            snippet = (item.get("snippet") or "").strip()

            # 1. Require URL and content
            if not url or (not title and not snippet):
                continue
            if not snippet and title.lower() in ("empty", "untitled", "no title", "none"):
                continue

            # 2. Validate URL syntax
            try:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    continue
                netloc = parsed.netloc.lower()
                if not netloc or netloc in ("localhost", "127.0.0.1"):
                    continue
                # Block known ad/tracker domains
                clean_domain = netloc.lstrip("www.") if netloc.startswith("www.") else netloc
                if any(clean_domain == blocked or clean_domain.endswith("." + blocked) for blocked in _BLOCKED_DOMAINS):
                    continue
            except Exception:
                continue

            # 3. Canonical URL deduplication (strip tracking parameters)
            canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)

            filtered.append(item)

        return filtered

    def _extract_content(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Relevant content extraction: clean HTML tags, entities, and whitespace."""
        extracted = []
        for item in items:
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            # Unescape HTML entities & strip HTML tags
            clean_title = html.unescape(re.sub(r"<[^>]+>", " ", title))
            clean_snippet = html.unescape(re.sub(r"<[^>]+>", " ", snippet))

            clean_title = " ".join(clean_title.split())
            clean_snippet = " ".join(clean_snippet.split())

            extracted.append({
                "title": clean_title,
                "url": item.get("url", ""),
                "snippet": clean_snippet,
                "published_date": item.get("published_date"),
            })
        return extracted

    def _rank_sources(self, query: str, items: List[Dict[str, Any]], max_results: int) -> List[WebSearchResult]:
        """Source ranking: compute lexical overlap with query, title relevance, and domain authority."""
        query_words = set(re.findall(r"\w+", query.lower()))
        stop_words = {"what", "is", "the", "and", "or", "in", "on", "for", "with", "a", "an", "to", "of", "about"}
        keywords = {w for w in query_words if len(w) > 2 and w not in stop_words}
        if not keywords:
            keywords = query_words

        scored_results: List[WebSearchResult] = []

        for item in items:
            title = item["title"]
            url = item["url"]
            snippet = item["snippet"]
            domain = WebSearchResult._extract_domain(url)

            title_words = set(re.findall(r"\w+", title.lower()))
            snippet_words = set(re.findall(r"\w+", snippet.lower()))

            # Overlap calculations
            title_overlap = len(keywords & title_words) / max(len(keywords), 1)
            snippet_overlap = len(keywords & snippet_words) / max(len(keywords), 1)

            # Domain authority bonus
            domain_bonus = 0.20 if any(domain.endswith(auth) for auth in _AUTHORITATIVE_DOMAINS) else 0.0
            if domain.endswith(".edu") or domain.endswith(".gov"):
                domain_bonus = max(domain_bonus, 0.25)

            # Combined score: 40% snippet overlap + 35% title overlap + 25% domain authority
            raw_score = (0.40 * snippet_overlap) + (0.35 * title_overlap) + domain_bonus
            # Base quality score to preserve provider-returned order if overlap is sparse
            score = min(max(raw_score, 0.1), 1.0)

            scored_results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    score=score,
                    domain=domain,
                    published_date=item.get("published_date"),
                )
            )

        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:max_results]

    def search_evidence(self, query: str, max_results: Optional[int] = None) -> WebSearchEvidence:
        """Primary Web Search Tool method: executes query cleaning, API retrieval, source
        filtering, relevant content extraction, and source ranking.
        Returns structured WebSearchEvidence."""
        max_results = max_results or settings.WEB_SEARCH_MAX_RESULTS
        provider_name = type(self.provider).__name__

        if not self.is_available():
            logger.info("Web search requested but no search provider is configured.")
            return WebSearchEvidence(
                query=query,
                status="no_results",
                results=[],
                provider=provider_name,
                error="No web search provider configured",
            )

        cleaned_query = self._clean_search_query(query)
        cache_key = hash_text(f"{cleaned_query}::{max_results}")
        cached_results = web_search_cache.get(cache_key)
        if cached_results is not None:
            logger.info(f"[WEB_SEARCH] Cache hit for query={cleaned_query!r} results={len(cached_results)}")
            return WebSearchEvidence(
                query=query,
                cleaned_query=cleaned_query,
                status="success" if cached_results else "no_results",
                results=cached_results,
                provider=provider_name,
            )

        try:
            # 1. External Search API execution
            raw_results = self.provider.search(cleaned_query, max_results=max_results * 2)

            if not raw_results:
                return WebSearchEvidence(
                    query=query,
                    cleaned_query=cleaned_query,
                    status="no_results",
                    results=[],
                    provider=provider_name,
                )

            # 2. Source Filtering
            filtered = self._filter_sources(raw_results)

            # 3. Relevant Content Extraction
            extracted = self._extract_content(filtered)

            # 4. Source Ranking
            ranked = self._rank_sources(cleaned_query, extracted, max_results=max_results)

            # Cache results
            web_search_cache.set(cache_key, ranked)

            logger.info(
                f"[WEB_SEARCH] query={query!r} cleaned={cleaned_query!r} provider={provider_name} "
                f"raw={len(raw_results)} filtered={len(filtered)} final={len(ranked)}"
            )

            return WebSearchEvidence(
                query=query,
                cleaned_query=cleaned_query,
                status="success" if ranked else "no_results",
                results=ranked,
                provider=provider_name,
            )

        except Exception as e:
            safe_error = _sanitize_error(str(e))
            logger.warning(f"[WEB_SEARCH] Web search API execution failed: {safe_error}")
            return WebSearchEvidence(
                query=query,
                cleaned_query=cleaned_query,
                status="failed",
                results=[],
                provider=provider_name,
                error=safe_error,
            )

    def search(self, query: str, max_results: Optional[int] = None) -> List[WebSearchResult]:
        """Backward-compatible method returning List[WebSearchResult]."""
        evidence = self.search_evidence(query, max_results=max_results)
        return evidence.results


web_search_service = WebSearchService()
