from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from autoshelf.llm.policy import assert_loopback_url


@dataclass(frozen=True, slots=True)
class HTTPProbeResult:
    ok: bool
    base_url: str
    probe_ms: int


def probe_openai_compatible(url: str, timeout: float = 2.0) -> HTTPProbeResult:
    base_url = assert_loopback_url(url.rstrip("/"))
    started = time.perf_counter()
    model_url = base_url + ("/models" if base_url.endswith("/v1") else "/v1/models")
    try:
        with urllib.request.urlopen(model_url, timeout=timeout) as response:
            ok = response.status == 200
    except Exception:
        ok = False
    elapsed = int((time.perf_counter() - started) * 1000)
    return HTTPProbeResult(ok=ok, base_url=base_url, probe_ms=elapsed)


def chat_completion(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    max_tokens: int = 1024,
    timeout: float = 30.0,
) -> dict[str, Any]:
    base_url = assert_loopback_url(base_url.rstrip("/"))
    url = base_url + ("/chat/completions" if base_url.endswith("/v1") else "/v1/chat/completions")
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def ollama_is_up(url: str, timeout: float = 0.25) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as response:
            return response.status == 200
    except urllib.error.URLError:
        return False
