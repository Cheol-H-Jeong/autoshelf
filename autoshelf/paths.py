from __future__ import annotations

import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "autoshelf"
    return Path.home() / ".config" / "autoshelf"


def state_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "autoshelf"
    return Path.home() / ".local" / "state" / "autoshelf"


def log_dir() -> Path:
    return state_dir() / "logs"


def global_db_path() -> Path:
    return state_dir() / "autoshelf.sqlite"
