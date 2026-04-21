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
    llm = AnthropicPlannerLLM(config)
    llm.propose(
        {},
        [
            FileBrief(
                path="draft.txt",
                filename="draft.txt",
                extension="txt",
                mtime=datetime.now().timestamp(),
                title="Draft",
                head_text="notes",
            )
        ],
    )
    payload = mock_anthropic.calls[0]
    assert payload["tool_choice"] == {"type": "tool", "name": "emit_plan"}
    assert payload["tools"][0]["name"] == "emit_plan"
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert payload["messages"][0]["content"][0]["text"].startswith("Propose or refine")


def test_anthropic_retry_falls_back_on_rate_limit(monkeypatch, mock_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("autoshelf.planner.llm.time.sleep", lambda _: None)
    config = AppConfig(llm=LLMSettings(provider="anthropic", max_retries=2))
    mock_anthropic.responses.extend(
        [
            mock_anthropic.module.RateLimitError("too many"),
            mock_anthropic.module.RateLimitError("still too many"),
            mock_anthropic.module.RateLimitError("give up"),
        ]
    )
    llm = AnthropicPlannerLLM(config)
    assignments = llm.assign(
        {"Documents": {}},
        [
            FileBrief(
                path="draft.txt",
                filename="draft.txt",
                extension="txt",
                mtime=datetime.now().timestamp(),
                title="Draft",
                head_text="notes",
            )
        ],
    )
    assert len(mock_anthropic.calls) == 3
    assert assignments[0].fallback is True
    assert llm.usage.fallback_chunks == 1


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
