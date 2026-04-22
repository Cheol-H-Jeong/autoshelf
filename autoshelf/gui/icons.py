from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "icons" / "lucide"
if not ICON_DIR.exists():
    ICON_DIR = Path(__file__).resolve().parents[3] / "resources" / "icons" / "lucide"


def icon(name: str) -> QIcon:
    path = icon_path(name)
    return QIcon(str(path)) if path.exists() else QIcon()


def icon_path(name: str) -> Path:
    return ICON_DIR / f"{name}.svg"


def available_icons() -> set[str]:
    return {path.stem for path in ICON_DIR.glob("*.svg")}
