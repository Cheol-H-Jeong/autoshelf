from __future__ import annotations

from autoshelf.config import AppConfig
from autoshelf.scanner import scan_directory


def test_scan_empty_dir(tmp_path):
    files = scan_directory(tmp_path, AppConfig())
    assert files == []


def test_scan_mixed_dir(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "alpha.txt").write_text("hello", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.txt").write_text("x", encoding="utf-8")
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.4")
    files = scan_directory(tmp_path, AppConfig())
    names = {item.filename for item in files}
    assert names == {"alpha.txt", "report.pdf"}
