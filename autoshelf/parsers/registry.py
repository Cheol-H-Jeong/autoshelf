from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from importlib.metadata import entry_points
from pathlib import Path

from loguru import logger

from autoshelf.parsers.base import ParsedContext, ParserSpec

_TIMEOUT_SECONDS = 10


def load_parser_specs() -> list[ParserSpec]:
    from autoshelf.parsers.archive import PARSER_SPEC as ARCHIVE
    from autoshelf.parsers.code import PARSER_SPEC as CODE
    from autoshelf.parsers.hwp import PARSER_SPEC as HWP
    from autoshelf.parsers.image import PARSER_SPEC as IMAGE
    from autoshelf.parsers.media import PARSER_SPEC as MEDIA
    from autoshelf.parsers.office import PARSER_SPECS as OFFICE
    from autoshelf.parsers.pdf import PARSER_SPEC as PDF
    from autoshelf.parsers.text import PARSER_SPEC as TEXT

    specs: list[ParserSpec] = [TEXT, PDF, HWP, IMAGE, CODE, ARCHIVE, MEDIA, *OFFICE]
    try:
        discovered = entry_points(group="autoshelf.parsers")
    except TypeError:
        discovered = entry_points().get("autoshelf.parsers", [])
    for entry_point in discovered:
        loaded = entry_point.load()
        spec = loaded() if callable(loaded) else loaded
        if isinstance(spec, ParserSpec):
            specs.append(spec)
    return specs


def parse_with_registry(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    suffix = path.suffix.lower()
    for spec in load_parser_specs():
        if suffix in spec.suffixes:
            return _run_with_timeout(spec, path, max_head_chars)
    return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "fallback"})


def _run_with_timeout(spec: ParserSpec, path: Path, max_head_chars: int) -> ParsedContext:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(spec.parse, path, max_head_chars)
        try:
            return future.result(timeout=_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.bind(component="parser").warning("parser timeout {} for {}", spec.name, path)
            return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "timeout"})
        except Exception as exc:
            logger.bind(component="parser").warning(
                "parser failure {} for {}: {}", spec.name, path, exc
            )
            return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
