"""
Lightweight, dependency-free caching.

* DocumentRegistry: a small JSON file tracking every ingested document by
  content hash, so re-uploading the same file is detected instead of
  re-embedding it, and so /documents can list what's available.
* TTLCache: generic in-memory cache with expiry, used for web search
  results and other short-lived, expensive calls.
"""
import json
import os
import threading
import time
from typing import Any, Optional

from backend.config import settings


class DocumentRegistry:
    def __init__(self, path: str = None):
        self.path = path or settings.DOC_HASH_STORE_PATH
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)

    def get_by_hash(self, content_hash: str) -> Optional[dict]:
        return self._data.get(content_hash)

    def get(self, document_id: str) -> Optional[dict]:
        for entry in self._data.values():
            if entry.get("document_id") == document_id:
                return entry
        return None

    def upsert(self, content_hash: str, record: dict):
        with self._lock:
            self._data[content_hash] = record
            self._save()

    def update_status(self, content_hash: str, status: str, **extra):
        with self._lock:
            if content_hash in self._data:
                self._data[content_hash]["status"] = status
                self._data[content_hash].update(extra)
                self._save()

    def list_all(self) -> list:
        return list(self._data.values())

    def delete(self, content_hash: str):
        with self._lock:
            if content_hash in self._data:
                del self._data[content_hash]
                self._save()


class TTLCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any):
        with self._lock:
            self._store[key] = (time.time() + self.ttl, value)


document_registry = DocumentRegistry()
web_search_cache = TTLCache(ttl_seconds=900)
embedding_cache = TTLCache(ttl_seconds=3600)
