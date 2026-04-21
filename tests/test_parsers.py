from __future__ import annotations

from autoshelf.parsers import parse_file


def test_text_parser_reads_head(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Title\nBody line", encoding="utf-8")
    parsed = parse_file(path)
    assert parsed.title == "Title"
    assert "Body line" in parsed.head_text


def test_unknown_parser_falls_back(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\x01")
    parsed = parse_file(path)
    assert parsed.title == "blob"
