from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.llm.model_registry import get_variant, resolve_model_path, verify_model_file
from autoshelf.llm.openai_local import probe_openai_compatible
from autoshelf.llm.policy import external_calls_allowed
from autoshelf.llm.system_probe import probe_hardware
from autoshelf.paths import state_dir
from autoshelf.planner.llm import estimate_resident_footprint_mb, select_auto_provider
from autoshelf.rules import load_planning_rules, rules_path


def run_diagnostics(root: Path | None = None) -> dict[str, object]:
    deps = {}
    for name in ["llama_cpp", "PySide6", "pypdf", "openpyxl", "pptx", "docx", "olefile", "pyhwp"]:
        try:
            importlib.import_module(name)
            deps[name] = "ok"
        except Exception:
            deps[name] = "missing"
    target_root = root or Path.cwd()
    config = AppConfig.load()
    hardware = probe_hardware(target_root)
    rules_file = rules_path(target_root)
    rules_status = "missing"
    rules_summary = {
        "pinned_dirs": 0,
        "exclude_globs": 0,
        "mappings": 0,
        "source_scoped_mappings": 0,
        "current_targets": 0,
    }
    if rules_file.exists():
        try:
            rules = load_planning_rules(target_root)
        except Exception:
            rules_status = "invalid"
        else:
            rules_status = "ok"
            rules_summary = {
                "pinned_dirs": len(rules.pinned_dirs),
                "exclude_globs": len(rules.exclude_globs),
                "mappings": len(rules.mappings),
                "source_scoped_mappings": sum(1 for rule in rules.mappings if rule.source_globs),
                "current_targets": sum(
                    1 for rule in rules.mappings if rule.target_mode == "current"
                ),
            }
    selected_provider, llm_host, probe_ms = _resolve_provider(config)
    variant = get_variant(config.llm.model_id)
    model_path = resolve_model_path(config.llm.model_id, config.llm.model_path)
    sample_completion_ok = (
        (selected_provider in {"local_http", "embedded"} and model_path.exists())
        or selected_provider == "local_http"
    )
    report = {
        "checks": {
            "python_ok": sys.version_info >= (3, 11),
            "state_dir_writable": _is_writable(state_dir()),
            "root_writable": _is_writable(target_root),
            "symlink_supported": _symlink_supported(target_root),
            "pylnk3_available": _module_available("pylnk3") if sys.platform == "win32" else True,
            "ffprobe_available": shutil.which("ffprobe") is not None,
            "rules_file_status": rules_status,
        },
        "dependencies": deps,
        "rules": rules_summary,
        "privacy": {
            "external_calls_allowed": external_calls_allowed(llm_host),
            "llm_host": "embedded" if selected_provider == "embedded" else llm_host,
        },
        "llm": {
            "selected_provider": selected_provider,
            "model_id": config.llm.model_id,
            "model_path": str(model_path),
            "model_sha256_ok": verify_model_file(model_path, variant.sha256),
            "model_download_mb": variant.download_mb,
            "resident_footprint_mb_est": estimate_resident_footprint_mb(config),
            "runtime": _runtime_string(selected_provider),
            "context_window": config.llm.context_window,
            "gpu_offload": False,
            "probe_ms": probe_ms,
            "sample_completion_ok": sample_completion_ok,
        },
        "hardware": {
            "ram_gb": hardware.ram_gb,
            "cpu_count": hardware.cpu_count,
            "free_disk_gb": hardware.free_disk_gb,
        },
    }
    return report


def doctor_exit_code(report: dict[str, object]) -> int:
    checks = report["checks"]
    llm = report["llm"]
    return (
        0
        if checks["python_ok"]
        and checks["state_dir_writable"]
        and llm["selected_provider"] != "none"
        else 1
    )


def _resolve_provider(config: AppConfig) -> tuple[str, str, int]:
    provider = config.llm.provider.lower()
    if provider == "local_http" and config.llm.local_http_url:
        probe = probe_openai_compatible(config.llm.local_http_url, timeout=2.0)
        return ("local_http" if probe.ok else "fake", probe.base_url, probe.probe_ms)
    if provider == "embedded":
        return ("embedded", "embedded", 0)
    if provider == "fake":
        return ("fake", "embedded", 0)
    selected, base_url = select_auto_provider(config)
    if selected == "local_http" and base_url:
        probe = probe_openai_compatible(base_url, timeout=2.0)
        return ("local_http", probe.base_url, probe.probe_ms)
    model_path = resolve_model_path(config.llm.model_id, config.llm.model_path)
    if model_path.exists():
        return ("embedded", "embedded", 0)
    return ("fake", "embedded", 0)


def _runtime_string(selected_provider: str) -> str:
    if selected_provider == "embedded":
        try:
            module = importlib.import_module("llama_cpp")
            return f"llama-cpp-python {getattr(module, '__version__', 'unknown')}"
        except Exception:
            return "llama-cpp-python missing"
    if selected_provider == "local_http":
        return "openai-compatible local HTTP"
    if selected_provider == "fake":
        return "heuristic fallback"
    return "unavailable"


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".autoshelf-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _symlink_supported(path: Path) -> bool:
    probe = path / ".autoshelf-link-source"
    link = path / ".autoshelf-link-target"
    try:
        probe.write_text("ok", encoding="utf-8")
        os.symlink(probe, link)
        link.unlink()
        probe.unlink()
        return True
    except OSError:
        if probe.exists():
            probe.unlink()
        if link.exists() or link.is_symlink():
            link.unlink()
        return False


def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False
