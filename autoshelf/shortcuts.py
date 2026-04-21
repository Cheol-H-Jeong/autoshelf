from __future__ import annotations

import os
import sys
from pathlib import Path


def create_shortcut(target: Path, shortcut_path: Path) -> Path:
    """Create a platform-appropriate shortcut and return its path."""

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        return _create_windows_shortcut(target, shortcut_path)
    if shortcut_path.exists():
        shortcut_path.unlink()
    os.symlink(target, shortcut_path)
    return shortcut_path


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
