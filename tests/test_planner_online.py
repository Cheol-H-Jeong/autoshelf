from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoshelf.config import AppConfig, LLMSettings
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.llm import AnthropicPlannerLLM
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import FileInfo


def test_anthropic_payload_uses_tool_schema(monkeypatch, mock_anthropic, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    (tmp_path / ".autoshelfrc.yaml").write_text(
        """
version: 1
pinned_dirs:
  - Finance/Taxes
mappings:
  - glob: "*.invoice.pdf"
    target: Finance/Invoices
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "draft.txt").write_text("draft", encoding="utf-8")
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy" / "draft-copy.txt").write_text("draft", encoding="utf-8")
    config = AppConfig(llm=LLMSettings(provider="anthropic"))
    mock_anthropic.responses.append(
        mock_anthropic.make_response(
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
    file_info = FileInfo(
        absolute_path=tmp_path / "inbox" / "draft.txt",
        relative_path=Path("inbox/draft.txt"),
        parent_name="inbox",
        filename="draft.txt",
        stem="draft",
        extension="txt",
        size_bytes=5,
        mtime=datetime.now().timestamp(),
        ctime=datetime.now().timestamp(),
        file_hash="shared-hash",
    )
    duplicate = FileInfo(
        absolute_path=tmp_path / "copy" / "draft-copy.txt",
        relative_path=Path("copy/draft-copy.txt"),
        parent_name="copy",
        filename="draft-copy.txt",
        stem="draft-copy",
        extension="txt",
        size_bytes=5,
        mtime=datetime.now().timestamp(),
        ctime=datetime.now().timestamp(),
        file_hash="shared-hash",
    )
    contexts = {
        file_info.absolute_path: ParsedContext("Draft", "notes", {}),
        duplicate.absolute_path: ParsedContext("Copy", "notes", {}),
    }
    result = PlannerPipeline(config).plan([file_info, duplicate], contexts, root=tmp_path)
    assert result.assignments
    payload = mock_anthropic.calls[0]
    system_text = "\n".join(str(block["text"]) for block in payload["system"])
    assert payload["tool_choice"] == {"type": "tool", "name": "emit_plan"}
    assert payload["tools"][0]["name"] == "emit_plan"
    assert payload["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert "Example 1:" in payload["system"][1]["text"]
    assert "Finance/Taxes" in system_text
    assert payload["messages"][0]["content"][0]["text"].startswith("Propose or refine")
    assert "'parent_name': 'inbox'" in payload["messages"][0]["content"][0]["text"]
    assert "'parent_path': 'inbox'" in payload["messages"][0]["content"][0]["text"]
    assert "'duplicate_group_size': 2" in payload["messages"][0]["content"][0]["text"]


def test_anthropic_retry_falls_back_on_rate_limit(monkeypatch, mock_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sleeps: list[float] = []
    monkeypatch.setattr("autoshelf.planner.reliability.random.uniform", lambda _start, _end: 0.125)
    config = AppConfig(
        llm=LLMSettings(
            provider="anthropic",
            max_retries=2,
            retry_base_delay_ms=500,
            retry_max_delay_ms=4000,
            retry_jitter_ms=250,
        )
    )
    mock_anthropic.responses.extend(
        [
            mock_anthropic.module.RateLimitError("too many"),
            mock_anthropic.module.RateLimitError("still too many"),
            mock_anthropic.module.RateLimitError("give up"),
        ]
    )
    llm = AnthropicPlannerLLM(config)
    monkeypatch.setattr(
        type(llm._retry_policy),
        "sleep_for_attempt",
        lambda self, attempt: sleeps.append([0.625, 1.125][attempt]) or sleeps[-1],
    )
    assignments = llm.assign(
        {"Documents": {}},
        [
            FileBrief(
                path="draft.txt",
                parent_name="inbox",
                filename="draft.txt",
                extension="txt",
                mtime=datetime.now().timestamp(),
                title="Draft",
                head_text="notes",
            )
        ],
    )
    assert len(mock_anthropic.calls) == 3
    assert sleeps == [0.625, 1.125]
    assert assignments[0].fallback is True
    assert llm.usage.fallback_chunks == 1


def test_anthropic_circuit_breaker_skips_calls_while_open(monkeypatch, mock_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config = AppConfig(
        llm=LLMSettings(
            provider="anthropic",
            max_retries=0,
            circuit_breaker_threshold=1,
            circuit_breaker_cooldown_seconds=60,
        )
    )
    mock_anthropic.responses.append(mock_anthropic.module.RateLimitError("outage"))
    llm = AnthropicPlannerLLM(config)
    briefs = [
        FileBrief(
            path="draft.txt",
            parent_name="inbox",
            filename="draft.txt",
            extension="txt",
            mtime=datetime.now().timestamp(),
            title="Draft",
            head_text="notes",
        )
    ]

    first = llm.assign({"Documents": {}}, briefs)
    second = llm.assign({"Documents": {}}, briefs)

    assert len(mock_anthropic.calls) == 1
    assert first[0].fallback is True
    assert second[0].fallback is True
    assert llm.usage.fallback_chunks == 2


def test_anthropic_circuit_breaker_recovers_after_cooldown(monkeypatch, mock_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    now = {"value": 0.0}
    monkeypatch.setattr("autoshelf.planner.reliability.time.monotonic", lambda: now["value"])
    config = AppConfig(
        llm=LLMSettings(
            provider="anthropic",
            max_retries=0,
            circuit_breaker_threshold=1,
            circuit_breaker_cooldown_seconds=30,
        )
    )
    mock_anthropic.responses.append(mock_anthropic.module.RateLimitError("outage"))
    llm = AnthropicPlannerLLM(config)
    briefs = [
        FileBrief(
            path="draft.txt",
            parent_name="inbox",
            filename="draft.txt",
            extension="txt",
            mtime=datetime.now().timestamp(),
            title="Draft",
            head_text="notes",
        )
    ]

    first = llm.assign({"Documents": {}}, briefs)
    second = llm.assign({"Documents": {}}, briefs)
    now["value"] = 31.0
    mock_anthropic.responses.append(
        mock_anthropic.make_response(
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
    third = llm.assign({"Documents": {}}, briefs)

    assert len(mock_anthropic.calls) == 2
    assert first[0].fallback is True
    assert second[0].fallback is True
    assert third[0].fallback is False
    assert llm.usage.fallback_chunks == 2


def test_online_pipeline_parses_tool_response(monkeypatch, mock_anthropic, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config = AppConfig(llm=LLMSettings(provider="anthropic"))
    file_info = FileInfo(
        absolute_path=tmp_path / "budget.txt",
        relative_path=Path("budget.txt"),
        parent_name="",
        filename="budget.txt",
        stem="budget",
        extension="txt",
        size_bytes=3,
        mtime=datetime(2024, 5, 1).timestamp(),
        ctime=datetime(2024, 5, 1).timestamp(),
        file_hash="abc",
    )
    contexts = {file_info.absolute_path: ParsedContext("Budget", "quarterly budget", {})}
    proposal = mock_anthropic.make_response(
        tree={"Documents": {}},
        assignments=[
            {
                "path": "budget.txt",
                "primary_dir": ["Documents"],
                "also_relevant": [],
                "summary": "quarterly budget",
                "confidence": 0.8,
            }
        ],
    )
    finalize = mock_anthropic.make_response(tree={"Documents": {}}, assignments=[])
    assign = mock_anthropic.make_response(
        tree={"Documents": {}},
        assignments=[
            {
                "path": "budget.txt",
                "primary_dir": ["Documents"],
                "also_relevant": [["Archive"]],
                "summary": "quarterly budget",
                "confidence": 0.55,
            }
        ],
    )
    mock_anthropic.responses.extend([proposal, finalize, assign])
    result = PlannerPipeline(config).plan([file_info], contexts, root=tmp_path)
    assert result.tree == {"Documents": {}}
    assert result.assignments[0].also_relevant == [["Archive"]]
    assert result.usage.input_tokens > 0
