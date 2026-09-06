"""
Small in-process TTL cache used to protect expensive vector-search and LLM
calls from repeated/rapid-fire identical queries (e.g. a judge re-clicking
"Analyze" during a live demo, or a flaky frontend retry).

For production scale this would be swapped for Redis with the same
interface; kept in-memory here to keep the MVP dependency-free.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional

from app.config import get_settings

_settings = get_settings()


class TTLCache:
    def __init__(self, max_entries: int, ttl_seconds: int):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def make_key(*parts: str) -> str:
        joined = "||".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            # LRU touch
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.monotonic() + self.ttl_seconds, value)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)


rag_cache = TTLCache(max_entries=_settings.CACHE_MAX_ENTRIES, ttl_seconds=_settings.CACHE_TTL_SECONDS)
llm_cache = TTLCache(max_entries=_settings.CACHE_MAX_ENTRIES, ttl_seconds=_settings.CACHE_TTL_SECONDS)
