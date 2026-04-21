from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger


@dataclass(slots=True)
class RetryPolicy:
    """Exponential backoff with bounded jitter."""

    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float
    jitter_seconds: float
    random_source: Callable[[float, float], float] = field(
        default_factory=lambda: random.uniform
    )

    def delay_for_attempt(self, attempt: int) -> float:
        capped = min(self.max_delay_seconds, self.base_delay_seconds * (2**attempt))
        if self.jitter_seconds <= 0:
            return capped
        jitter = max(0.0, self.random_source(0.0, self.jitter_seconds))
        return min(self.max_delay_seconds, capped + jitter)

    def sleep_for_attempt(self, attempt: int) -> float:
        delay = self.delay_for_attempt(attempt)
        time.sleep(delay)
        return delay


@dataclass(slots=True)
class CircuitBreaker:
    """Track consecutive request failures and short-circuit repeated outages."""

    failure_threshold: int
    cooldown_seconds: float
    time_source: Callable[[], float] = field(default_factory=lambda: time.monotonic)
    _state: str = field(default="closed", init=False)
    _failure_count: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    @property
    def state(self) -> str:
        return self._state

    def allow_request(self) -> bool:
        if self._state != "open":
            return True
        now = self.time_source()
        if self._opened_at is not None and now - self._opened_at >= self.cooldown_seconds:
            self._state = "half-open"
            logger.bind(component="planner").info(
                "planner circuit breaker entering half-open after {}s cooldown",
                self.cooldown_seconds,
            )
            return True
        return False

    def record_success(self) -> None:
        if self._state != "closed" or self._failure_count:
            logger.bind(component="planner").info("planner circuit breaker closed after recovery")
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        now = self.time_source()
        if self._state == "half-open":
            self._trip(now)
            return
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._trip(now)

    def _trip(self, opened_at: float) -> None:
        self._state = "open"
        self._failure_count = 0
        self._opened_at = opened_at
        logger.bind(component="planner").warning(
            "planner circuit breaker opened for {}s",
            self.cooldown_seconds,
        )
