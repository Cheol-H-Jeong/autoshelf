from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext, ParserSpec


def parse_image(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    if hasattr(Image, "UnidentifiedImageError") and not _looks_like_supported_image(path):
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
    try:
        with Image.open(path) as image:
            exif = image.getexif() or {}
            description = exif.get(0x010E, "")
            camera = exif.get(0x0110, "")
            taken_at = exif.get(0x9003, "")
            head = " ".join(part for part in [str(description), str(camera), str(taken_at)] if part)
            return ParsedContext(
                title=path.stem,
                head_text=head[:max_head_chars],
                extra_meta={"format": image.format, "size": list(image.size)},
            )
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


def _looks_like_supported_image(path: Path) -> bool:
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return False
    return (
        header.startswith(b"\xff\xd8\xff")
        or header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"II*\x00")
        or header.startswith(b"MM\x00*")
    )


PARSER_SPEC = ParserSpec(
    name="image",
    suffixes=(".jpg", ".jpeg", ".png", ".tif", ".tiff"),
    parse=parse_image,
)
