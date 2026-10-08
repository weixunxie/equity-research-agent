"""Abuse protection for the public API: a sliding-window rate limiter and a
TTL response cache. Both are in-process and dependency-free — enough for a
single-instance deployment; swap in Redis if the API is ever scaled out.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class RateLimiter:
    """Allow at most ``limit`` hits per ``window`` seconds for each key.

    ``limit <= 0`` disables the limiter. ``clock`` is injectable for tests.
    """

    def __init__(
        self, limit: int, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> float:
        """Seconds until ``key`` may hit again; 0 if it may now. Doesn't record."""
        if self.limit <= 0:
            return 0.0
        with self._lock:
            hits = self._prune(key)
            if len(hits) < self.limit:
                return 0.0
            return max(0.0, hits[0] + self.window - self._clock())

    def hit(self, key: str) -> None:
        """Record one hit for ``key``."""
        if self.limit <= 0:
            return
        with self._lock:
            self._prune(key).append(self._clock())

    def _prune(self, key: str) -> deque[float]:
        cutoff = self._clock() - self.window
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        # Drop idle keys so the table doesn't grow with every client ever seen.
        if len(self._hits) > 10_000:
            for k in [k for k, v in self._hits.items() if not v and k != key]:
                del self._hits[k]
        return hits


class TTLCache(Generic[T]):
    """A small LRU cache whose entries expire ``ttl`` seconds after being set.

    ``ttl <= 0`` disables caching. ``clock`` is injectable for tests.
    """

    def __init__(
        self, ttl: float, max_entries: int = 128, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl = ttl
        self.max_entries = max_entries
        self._clock = clock
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at >= self.ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: T) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            self._items[key] = (self._clock(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
