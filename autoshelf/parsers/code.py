from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec

_CODE_SUFFIXES = (".py", ".js", ".ts", ".go", ".rs", ".java", ".cs", ".cpp", ".c", ".sql", ".sh")


def parse_code(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
    lines = text.splitlines()
    title = path.stem
    for line in lines[:20]:
        stripped = line.strip().strip("#/\"'* ")
        if stripped:
            title = stripped[:120]
            break
    head = "\n".join(lines[:40])[:max_head_chars]
    return ParsedContext(
        title=title, head_text=head, extra_meta={"language": path.suffix.lower().lstrip(".")}
    )


PARSER_SPEC = ParserSpec(name="code", suffixes=_CODE_SUFFIXES, parse=parse_code)
