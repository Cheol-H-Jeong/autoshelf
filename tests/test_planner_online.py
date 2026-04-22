from __future__ import annotations

from datetime import datetime

from autoshelf.config import AppConfig, LLMSettings
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.llm import (
    EmbeddedPlannerLLM,
    LocalHTTPPlannerLLM,
    estimate_resident_footprint_mb,
    get_planner_llm,
    select_auto_provider,
)


def test_auto_provider_prefers_self_hosted_when_up(monkeypatch, mock_local_openai):
    monkeypatch.setenv("AUTOSHELF_LLM_URL", "http://127.0.0.1:9999/v1")
    selected, base_url = select_auto_provider(AppConfig())
    assert selected == "local_http"
    assert base_url == "http://127.0.0.1:9999/v1"


def test_auto_provider_falls_back_to_embedded_when_http_unreachable(monkeypatch):
    monkeypatch.setattr(
        "autoshelf.planner.llm.probe_openai_compatible",
        lambda url, timeout=0.0: type("Probe", (), {"ok": False, "base_url": url, "probe_ms": 1})(),
    )
    monkeypatch.setattr("autoshelf.planner.llm.ollama_is_up", lambda url, timeout=0.0: False)
    selected, base_url = select_auto_provider(AppConfig())
    assert selected == "embedded"
    assert base_url is None


def test_auto_provider_falls_back_to_fake_when_no_model_available(monkeypatch):
    monkeypatch.setattr("autoshelf.planner.llm.ollama_is_up", lambda url, timeout=0.0: False)
    monkeypatch.setattr(
        "autoshelf.planner.llm.probe_openai_compatible",
        lambda url, timeout=0.0: type("Probe", (), {"ok": False, "base_url": url, "probe_ms": 1})(),
    )
    monkeypatch.setattr(
        "autoshelf.planner.llm.EmbeddedPlannerLLM",
        lambda cfg, rules=None: (_ for _ in ()).throw(RuntimeError("missing model")),
    )
    llm = get_planner_llm(AppConfig())
    assert llm.__class__.__name__ == "FakeLLM"


def test_loopback_guard_rejects_remote_url(monkeypatch):
    monkeypatch.delenv("AUTOSHELF_ALLOW_REMOTE_LLM", raising=False)
    try:
        AppConfig(llm=LLMSettings(local_http_url="http://10.0.0.2:8080/v1"))
    except ValueError as exc:
        assert "AUTOSHELF_ALLOW_REMOTE_LLM=1" in str(exc)
    else:
        raise AssertionError("Expected remote URL to be rejected")


def test_local_http_payload_uses_tool_schema(mock_local_openai, tmp_path):
    config = AppConfig(llm=LLMSettings(provider="local_http", local_http_url="http://127.0.0.1:8081/v1"))
    llm = LocalHTTPPlannerLLM(config, "http://127.0.0.1:8081/v1")
    mock_local_openai.responses.append(
        mock_local_openai.make_response(
            tree={"Documents": {}},
            assignments=[
                {
                    "path": "draft.txt",
                    "primary_dir": ["Documents"],
                    "also_relevant": [],
                    "summary": "draft",
                    "confidence": 0.8,
                }
            ],
        )
    )
    brief = FileBrief(
        path="draft.txt",
        parent_name="inbox",
        parent_path="inbox",
        meaningful_parent_hint="inbox",
        filename="draft.txt",
        extension="txt",
        mtime=datetime.now().timestamp(),
        title="Draft",
        head_text="notes",
    )
    llm.assign({"Documents": {}}, [brief])
    payload = mock_local_openai.calls[0]
    assert payload["tool_choice"]["function"]["name"] == "emit_plan"
    assert payload["response_format"] == {"type": "json_object"}


def test_embedded_llama_records_chat_completion(mock_embedded_llama, tmp_path):
    model = tmp_path / "Qwen3-1.7B-Instruct-2507-Q4_K_M.gguf"
    model.write_bytes(b"stub")
    config = AppConfig(llm=LLMSettings(provider="embedded", model_path=str(model)))
    llm = EmbeddedPlannerLLM(config)
    brief = FileBrief(
        path="draft.txt",
        parent_name="inbox",
        filename="draft.txt",
        extension="txt",
        mtime=datetime.now().timestamp(),
        title="Draft",
        head_text="notes",
    )
    llm.assign({"Documents": {}}, [brief])
    assert mock_embedded_llama.calls


def test_resident_footprint_under_3gb_for_default():
    config = AppConfig()
    assert estimate_resident_footprint_mb(config) < 3000
