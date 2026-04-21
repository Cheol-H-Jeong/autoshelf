from __future__ import annotations

from pathlib import Path

from autoshelf.parsers.base import ParsedContext


def parse_office(path: Path, max_head_chars: int = 2000) -> ParsedContext:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _parse_docx(path, max_head_chars)
    if suffix == ".pptx":
        return _parse_pptx(path, max_head_chars)
    if suffix == ".xlsx":
        return _parse_xlsx(path, max_head_chars)
    if suffix == ".xls":
        return _parse_xls(path, max_head_chars)
    return ParsedContext(title=path.stem, head_text="", extra_meta={})


def _parse_docx(path: Path, max_head_chars: int) -> ParsedContext:
    try:
        import docx  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        document = docx.Document(str(path))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)
        head = text[:max_head_chars]
        title = next((p.text.strip() for p in document.paragraphs if p.text.strip()), path.stem)
        return ParsedContext(title=title[:120], head_text=head, extra_meta={})
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


def _parse_pptx(path: Path, max_head_chars: int) -> ParsedContext:
    try:
        from pptx import Presentation  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        presentation = Presentation(str(path))
        texts: list[str] = []
        for slide in presentation.slides[:5]:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    texts.append(shape.text)
        content = "\n".join(texts)
        return ParsedContext(title=path.stem, head_text=content[:max_head_chars], extra_meta={})
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


def _parse_xlsx(path: Path, max_head_chars: int) -> ParsedContext:
    try:
        import openpyxl  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        texts: list[str] = []
        for sheet in workbook.worksheets[:2]:
            for row in sheet.iter_rows(max_row=10, values_only=True):
                texts.append(" | ".join("" if value is None else str(value) for value in row))
        head_text = "\n".join(texts)[:max_head_chars]
        return ParsedContext(title=path.stem, head_text=head_text, extra_meta={})
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})


def _parse_xls(path: Path, max_head_chars: int) -> ParsedContext:
    try:
        import xlrd  # type: ignore[import-not-found]
    except ImportError:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "unavailable"})
    try:
        workbook = xlrd.open_workbook(path)
        texts: list[str] = []
        for sheet in workbook.sheets()[:2]:
            for row_index in range(min(sheet.nrows, 10)):
                texts.append(" | ".join(str(value) for value in sheet.row_values(row_index)))
        head_text = "\n".join(texts)[:max_head_chars]
        return ParsedContext(title=path.stem, head_text=head_text, extra_meta={})
    except Exception:
        return ParsedContext(title=path.stem, head_text="", extra_meta={"parser": "failed"})
