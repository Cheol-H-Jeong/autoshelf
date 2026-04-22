from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoshelf.config import AppConfig
from autoshelf.llm.model_registry import ensure_model_downloaded, get_variant, resolve_model_path
from autoshelf.paths import state_dir


@dataclass(frozen=True, slots=True)
class EmbeddedProbe:
    runtime: str
    gpu_offload: bool
    resident_footprint_mb_est: int
    model_path: Path
    model_sha256_ok: bool


class EmbeddedLlamaRuntime:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._llama: Any | None = None
        self._probe: EmbeddedProbe | None = None

    def load(self) -> EmbeddedProbe:
        if self._probe is not None:
            return self._probe
        from llama_cpp import (  # type: ignore[import-not-found]
            Llama,
            llama_supports_gpu_offload,  # type: ignore[import-not-found]
        )
        from llama_cpp import __version__ as llama_version

        model_path = self.ensure_model()
        variant = get_variant(self._config.llm.model_id)
        self._llama = Llama(
            model_path=str(model_path),
            n_ctx=self._config.llm.context_window,
            n_threads=min(os.cpu_count() or 1, 6),
            n_batch=min(self._config.llm.n_batch, 256),
            verbose=False,
        )
        self._probe = EmbeddedProbe(
            runtime=f"llama-cpp-python {llama_version}",
            gpu_offload=bool(llama_supports_gpu_offload()),
            resident_footprint_mb_est=variant.resident_footprint_mb_est,
            model_path=model_path,
            model_sha256_ok=True,
        )
        self._write_capability_probe(model_path)
        return self._probe

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        tool_choice: dict[str, Any] | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.load()
        assert self._llama is not None
        return self._llama.create_chat_completion(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            max_tokens=self._config.llm.max_completion_tokens,
            temperature=0,
        )

    def unload(self) -> None:
        self._llama = None

    def ensure_model(self) -> Path:
        configured = self._config.llm.model_path
        resolved = resolve_model_path(self._config.llm.model_id, configured)
        if resolved.exists():
            return resolved
        return ensure_model_downloaded(self._config.llm.model_id, configured_path=configured)

    def _write_capability_probe(self, model_path: Path) -> None:
        cap_path = state_dir() / "embedded_cap.json"
        cap_path.parent.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(model_path).encode("utf-8")).hexdigest()
        payload: dict[str, Any] = {}
        if cap_path.exists():
            payload = json.loads(cap_path.read_text(encoding="utf-8"))
        payload[key] = {
            "tool_calling": True,
            "json_mode": True,
            "context_window": self._config.llm.context_window,
        }
        cap_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
