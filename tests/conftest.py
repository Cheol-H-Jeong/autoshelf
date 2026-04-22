from __future__ import annotations

import io
import json
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
def mock_local_openai(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, object]] = []
    queued_responses: deque[dict[str, object]] = deque()

    class MockHTTPResponse(io.BytesIO):
        def __init__(self, payload: dict[str, object], status: int = 200):
            super().__init__(json.dumps(payload).encode("utf-8"))
            self.status = status
            self.headers = {"Content-Length": str(len(self.getvalue()))}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=0, *args, **kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url.endswith("/v1/models") or url.endswith("/api/tags"):
            return MockHTTPResponse({"data": [{"id": "qwen3-1.7b-q4"}]})
        payload = {}
        if getattr(request, "data", None):
            payload = json.loads(request.data.decode("utf-8"))
            calls.append(payload)
        response = queued_responses.popleft()
        return MockHTTPResponse(response)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return SimpleNamespace(
        calls=calls,
        responses=queued_responses,
        make_response=_make_openai_response,
    )


@pytest.fixture
def mock_embedded_llama(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, object]] = []

    class MockLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, **kwargs):
            calls.append(kwargs)
            return _make_openai_response({"Documents": {}}, [])

    module = types.SimpleNamespace(
        Llama=MockLlama,
        __version__="0.3.0-test",
        llama_supports_gpu_offload=lambda: False,
    )
    monkeypatch.setitem(sys.modules, "llama_cpp", module)
    return SimpleNamespace(module=module, calls=calls)


def _make_openai_response(
    tree: dict[str, object],
    assignments: list[dict[str, object]],
    unsure_paths: list[str] | None = None,
) -> dict[str, object]:
    arguments = json.dumps(
        {
            "tree": tree,
            "assignments": assignments,
            "unsure_paths": unsure_paths or [],
        }
    )
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "emit_plan",
                                "arguments": arguments,
                            }
                        }
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 40},
    }
