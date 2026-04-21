from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

from autoshelf.paths import state_dir
from autoshelf.rules import load_planning_rules, rules_path


def run_diagnostics(root: Path | None = None) -> dict[str, object]:
    deps = {}
    for name in ["anthropic", "PySide6", "pypdf", "openpyxl", "pptx", "docx", "olefile", "pyhwp"]:
        try:
            importlib.import_module(name)
            deps[name] = "ok"
        except Exception:
            deps[name] = "missing"
    target_root = root or Path.cwd()
    rules_file = rules_path(target_root)
    rules_status = "missing"
    if rules_file.exists():
        try:
            load_planning_rules(target_root)
        except Exception:
            rules_status = "invalid"
        else:
            rules_status = "ok"
    checks = {
        "python_ok": sys.version_info >= (3, 11),
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "state_dir_writable": _is_writable(state_dir()),
        "root_writable": _is_writable(target_root),
        "symlink_supported": _symlink_supported(target_root),
        "pylnk3_available": _module_available("pylnk3") if sys.platform == "win32" else True,
        "ffprobe_available": shutil.which("ffprobe") is not None,
        "rules_file_status": rules_status,
    }
    return {"checks": checks, "dependencies": deps}


def doctor_exit_code(report: dict[str, object]) -> int:
    checks = report["checks"]
    return 0 if checks["python_ok"] and checks["state_dir_writable"] else 1


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
