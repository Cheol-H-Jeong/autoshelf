from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    """Simple thread-safe token bucket for request pacing."""

    def __init__(self, requests_per_second: int = 2, concurrency: int = 3) -> None:
        self._rps = max(1, requests_per_second)
        self._lock = threading.Lock()
        self._timestamps: deque[float] = deque()
        self._semaphore = threading.Semaphore(max(1, concurrency))

    def __enter__(self) -> RateLimiter:
        self._semaphore.acquire()
        self.wait()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._semaphore.release()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= 1.0:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._rps:
                    self._timestamps.append(now)
                    return
                sleep_for = max(0.01, 1.0 - (now - self._timestamps[0]))
            time.sleep(sleep_for)
