from __future__ import annotations

from typing import Any

from autoshelf.config_migrations.helpers import normalize_choice, normalize_non_negative_int
from autoshelf.config_migrations.models import MigrationStep


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(data)
    llm = migrated.get("llm")
    llm_payload = dict(llm) if isinstance(llm, dict) else {}
    legacy_model = (
        str(llm_payload.get("model_id") or llm_payload.get("planning_model") or "").strip()
    )
    provider = normalize_choice(
        llm_payload.get("provider"),
        allowed={"auto", "embedded", "local_http", "fake"},
        fallback="auto",
    )
    llm_payload["provider"] = provider
    llm_payload["model_id"] = legacy_model or "qwen3-1.7b-q4"
    llm_payload["classification_model"] = llm_payload["model_id"]
    llm_payload["planning_model"] = llm_payload["model_id"]
    llm_payload["review_model"] = llm_payload["model_id"]
    llm_payload["model_path"] = str(llm_payload.get("model_path") or "").strip()
    llm_payload["local_http_url"] = str(llm_payload.get("local_http_url") or "").strip()
    context_window = normalize_non_negative_int(llm_payload.get("context_window"), fallback=4096)
    if context_window < 2048:
        context_window = 2048
    if context_window > 8192:
        context_window = 8192
    llm_payload["context_window"] = context_window
    llm_payload["n_batch"] = max(
        32,
        normalize_non_negative_int(llm_payload.get("n_batch"), fallback=256),
    )
    llm_payload["max_completion_tokens"] = max(
        128,
        normalize_non_negative_int(llm_payload.get("max_completion_tokens"), fallback=1024),
    )
    llm_payload["prompt_cache_enabled"] = False
    migrated["llm"] = llm_payload
    max_chunk_tokens = normalize_non_negative_int(migrated.get("max_chunk_tokens"), fallback=0)
    if max_chunk_tokens >= 20_000:
        max_chunk_tokens = 0
    migrated["max_chunk_tokens"] = max_chunk_tokens or llm_payload["context_window"] // 4
    return migrated


MIGRATION = (
    MigrationStep(
        version=3,
        name="switch-to-ondevice-llm-defaults",
        description="Replace cloud LLM defaults with embedded on-device runtime settings",
    ),
    migrate,
)
