from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def create_shortcut(target: Path, shortcut_path: Path) -> Path:
    """Create a platform-appropriate shortcut and return its path."""

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        return _create_windows_shortcut(target, shortcut_path)
    if shortcut_path.exists():
        shortcut_path.unlink()
    try:
        os.symlink(target, shortcut_path)
        return shortcut_path
    except OSError:
        desktop_path = shortcut_path.with_suffix(".desktop")
        desktop_path.write_text(
            f"[Desktop Entry]\nType=Link\nName=autoshelf shortcut\nURL=file://{target}\n",
            encoding="utf-8",
        )
        return desktop_path


def _create_windows_shortcut(target: Path, shortcut_path: Path) -> Path:
    try:
        import pylnk3  # type: ignore[import-not-found]
    except ImportError:
        link_path = shortcut_path
        if shortcut_path.suffix.lower() != ".lnk":
            link_path = shortcut_path.with_suffix(shortcut_path.suffix + ".lnk")
        try:
            os.symlink(target, link_path)
            return link_path
        except OSError:
            return link_path
    link_path = (
        shortcut_path
        if shortcut_path.suffix.lower() == ".lnk"
        else shortcut_path.with_suffix(".lnk")
    )
    pylnk3.create(str(target), str(link_path))
    return link_path


def copy_fallback(target: Path, shortcut_path: Path) -> Path:
    copy_name = (
        shortcut_path.with_name(f"{shortcut_path.stem} (copy){shortcut_path.suffix}")
        if shortcut_path.suffix
        else shortcut_path.with_name(f"{shortcut_path.name} (copy)")
    )
    shutil.copy2(target, copy_name)
    return copy_name
