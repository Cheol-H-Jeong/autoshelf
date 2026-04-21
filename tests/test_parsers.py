from __future__ import annotations

import io
import sys
import types
import zipfile
from pathlib import Path

from autoshelf.parsers import parse_file


def test_text_parser_reads_head(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Title\nBody line", encoding="utf-8")
    parsed = parse_file(path)
    assert parsed.title == "Title"
    assert "Body line" in parsed.head_text


def test_text_parser_handles_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")
    parsed = parse_file(path)
    assert parsed.title == "{not-json"


def test_pdf_parser_happy_path_with_mocked_pypdf(monkeypatch, tmp_path):
    class FakePage:
        def extract_text(self):
            return "PDF body"

    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [FakePage()]
            self.metadata = types.SimpleNamespace(title="PDF Title")

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=FakeReader))
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4")
    parsed = parse_file(path)
    assert parsed.title == "PDF Title"
    assert "PDF body" in parsed.head_text


def test_pdf_parser_malformed_file(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_docx_parser_happy_path(monkeypatch, tmp_path):
    paragraph = types.SimpleNamespace(text="Project Plan", style=types.SimpleNamespace(name="Title"))
    body = types.SimpleNamespace(text="Body text", style=types.SimpleNamespace(name="Heading 1"))
    document = types.SimpleNamespace(paragraphs=[paragraph, body])
    module = types.SimpleNamespace(Document=lambda _path: document)
    monkeypatch.setitem(sys.modules, "docx", module)
    path = tmp_path / "plan.docx"
    path.write_bytes(b"docx")
    parsed = parse_file(path)
    assert parsed.title == "Project Plan"
    assert "Body text" in parsed.head_text


def test_docx_parser_malformed_file(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"broken")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_pptx_parser_happy_path(monkeypatch, tmp_path):
    shape = types.SimpleNamespace(text="Deck Title\nAgenda")
    slide = types.SimpleNamespace(shapes=[shape])
    deck = types.SimpleNamespace(slides=[slide])
    module = types.SimpleNamespace(Presentation=lambda _path: deck)
    monkeypatch.setitem(sys.modules, "pptx", module)
    path = tmp_path / "slides.pptx"
    path.write_bytes(b"pptx")
    parsed = parse_file(path)
    assert parsed.title == "Deck Title"
    assert "Agenda" in parsed.head_text


def test_xlsx_parser_happy_path(monkeypatch, tmp_path):
    sheet = types.SimpleNamespace(
        title="Budget",
        iter_rows=lambda max_row, values_only: iter([("A", "B"), ("1", "2")]),
    )
    workbook = types.SimpleNamespace(worksheets=[sheet], sheetnames=["Budget"])
    module = types.SimpleNamespace(load_workbook=lambda *_args, **_kwargs: workbook)
    monkeypatch.setitem(sys.modules, "openpyxl", module)
    path = tmp_path / "budget.xlsx"
    path.write_bytes(b"xlsx")
    parsed = parse_file(path)
    assert parsed.title == "Budget"
    assert "Sheet: Budget" in parsed.head_text


def test_hwp_parser_handles_malformed_file(tmp_path):
    path = tmp_path / "broken.hwp"
    path.write_bytes(b"broken")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_archive_parser_lists_entries(tmp_path):
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("docs/readme.txt", "hello")
        archive.writestr("images/photo.jpg", "data")
    parsed = parse_file(path)
    assert "docs/readme.txt" in parsed.head_text
    assert parsed.extra_meta["entries"] == 2


def test_archive_parser_malformed_file(tmp_path):
    path = tmp_path / "broken.zip"
    path.write_bytes(b"broken")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_code_parser_reads_header_comment(tmp_path):
    path = tmp_path / "tool.py"
    path.write_text("# Tool header\nprint('ok')\n", encoding="utf-8")
    parsed = parse_file(path)
    assert parsed.title == "Tool header"
    assert "print('ok')" in parsed.head_text


def test_image_parser_happy_path(monkeypatch, tmp_path):
    class FakeImage:
        format = "JPEG"
        size = (640, 480)

        def getexif(self):
            return {0x010E: "Trip", 0x0110: "Camera", 0x9003: "2024:05:01 10:00:00"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    module = types.SimpleNamespace(Image=types.SimpleNamespace(open=lambda _path: FakeImage()))
    monkeypatch.setitem(sys.modules, "PIL", module)
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"img")
    parsed = parse_file(path)
    assert "Trip" in parsed.head_text
    assert parsed.extra_meta["format"] == "JPEG"


def test_image_parser_malformed_file(tmp_path):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"broken")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_media_parser_happy_path(monkeypatch, tmp_path):
    info = types.SimpleNamespace(length=12.5)
    media = types.SimpleNamespace(info=info, tags={"title": ["Theme"], "artist": ["Artist"]})
    module = types.SimpleNamespace(File=lambda _path: media)
    monkeypatch.setitem(sys.modules, "mutagen", module)
    path = tmp_path / "song.mp3"
    path.write_bytes(b"mp3")
    parsed = parse_file(path)
    assert parsed.title == "Theme"
    assert "Artist" in parsed.head_text


def test_media_parser_malformed_file(tmp_path):
    path = tmp_path / "broken.mp3"
    path.write_bytes(b"broken")
    parsed = parse_file(path)
    assert parsed.title == "broken"


def test_unknown_parser_falls_back(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\x01")
    parsed = parse_file(path)
    assert parsed.title == "blob"
