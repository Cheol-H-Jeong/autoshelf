from __future__ import annotations

import json
from pathlib import Path

from autoshelf.parsers.base import ParsedContext


def parse_text(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            text = json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    head = text[:max_head_chars].strip()
    title = next((line.strip() for line in text.splitlines() if line.strip()), path.stem)
    return ParsedContext(title=title[:120], head_text=head, extra_meta={})
