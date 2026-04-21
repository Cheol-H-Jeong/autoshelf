from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_media(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    metadata = _mutagen_metadata(path)
    if not metadata:
        metadata = _ffprobe_metadata(path)
    if not metadata:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "fallback"})
    head = " | ".join(f"{key}: {value}" for key, value in metadata.items())[:max_head_chars]
    return ParsedContext(
        title=str(metadata.get("title", path.stem))[:120], head_text=head, extra_meta=metadata
    )


def _mutagen_metadata(path: Path) -> dict[str, object]:
    try:
        from mutagen import File  # type: ignore[import-not-found]
    except ImportError:
        return {}
    try:
        media = File(path)
        if media is None:
            return {}
        result: dict[str, object] = {}
        if getattr(media, "info", None) is not None:
            result["duration"] = round(float(getattr(media.info, "length", 0.0)), 2)
        tags = getattr(media, "tags", None) or {}
        for key in ("title", "artist"):
            value = tags.get(key)
            if isinstance(value, list) and value:
                result[key] = str(value[0])
            elif value:
                result[key] = str(value)
        return result
    except Exception:
        return {}


def _ffprobe_metadata(path: Path) -> dict[str, object]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return {}
    try:
        completed = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        payload = json.loads(completed.stdout or "{}")
        data = payload.get("format", {})
        if not isinstance(data, dict):
            return {}
        tags = data.get("tags", {}) if isinstance(data.get("tags"), dict) else {}
        return {
            "title": str(tags.get("title", path.stem)),
            "artist": str(tags.get("artist", "")),
            "duration": float(data.get("duration", 0.0)),
        }
    except Exception:
        return {}


PARSER_SPEC = ParserSpec(
    name="media",
    suffixes=(".mp3", ".mp4", ".mov", ".mkv", ".wav"),
    parse=parse_media,
)
