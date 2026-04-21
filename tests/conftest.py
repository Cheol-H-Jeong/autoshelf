from __future__ import annotations

import sys
import types
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def sample_corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    samples = {
        "budget.xlsx": "quarterly budget",
        "meeting.txt": "meeting notes",
        "report.md": "# Report\nsummary",
        "photo.jpg": "binary",
        "archive.zip": "PK\x03\x04",
    }
    for name, content in samples.items():
        path = root / name
        if name.endswith((".jpg", ".zip")):
            path.write_bytes(content.encode("utf-8"))
        else:
            path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def mock_anthropic(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, object]] = []
    queued_responses: deque[object] = deque()

    class RateLimitError(Exception):
        pass

    class InternalServerError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class MockMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            response = queued_responses.popleft()
            if isinstance(response, Exception):
                raise response
            return response

        def count_tokens(self, **kwargs):
            content = kwargs["messages"][0]["content"]
            if isinstance(content, list):
                text = " ".join(str(item.get("text", "")) for item in content)
            else:
                text = str(content)
            return SimpleNamespace(input_tokens=max(1, len(text) // 4))

    class MockAnthropicClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.messages = MockMessages()

        def count_tokens(self, text: str):
            return max(1, len(text) // 4)

    module = types.SimpleNamespace(
        Anthropic=MockAnthropicClient,
        RateLimitError=RateLimitError,
        InternalServerError=InternalServerError,
        APIConnectionError=APIConnectionError,
    )
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return SimpleNamespace(
        module=module,
        calls=calls,
        responses=queued_responses,
        make_response=_make_anthropic_response,
    )


def _make_anthropic_response(
    tree: dict[str, object],
    assignments: list[dict[str, object]],
    unsure_paths: list[str] | None = None,
    usage: dict[str, int] | None = None,
):
    usage_data = {
        "input_tokens": 120,
        "output_tokens": 40,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 20,
    }
    if usage is not None:
        usage_data.update(usage)
    tool_input = {
        "tree": tree,
        "assignments": assignments,
        "unsure_paths": unsure_paths or [],
    }
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="emit_plan", input=tool_input)],
        usage=SimpleNamespace(**usage_data),
    )
