from __future__ import annotations

import os
from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def remote_llm_allowed() -> bool:
    return os.environ.get("AUTOSHELF_ALLOW_REMOTE_LLM", "").strip() == "1"


def assert_loopback_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in LOOPBACK_HOSTS or remote_llm_allowed():
        return url
    raise ValueError(
        "External LLM hosts are blocked. Set AUTOSHELF_ALLOW_REMOTE_LLM=1 to override."
    )


def external_calls_allowed(url: str | None = None) -> bool:
    if url is None or not url.strip():
        return False
    try:
        assert_loopback_url(url)
    except ValueError:
        return False
    parsed = urlparse(url)
    return (parsed.hostname or "").lower() not in LOOPBACK_HOSTS
