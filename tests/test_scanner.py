from __future__ import annotations

from pathlib import Path

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


def test_scan_respects_excluded_directory(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "bundle.js").write_text("x", encoding="utf-8")
    files = scan_directory(tmp_path, AppConfig())
    assert files == []


def test_scan_permission_error_is_nonfatal(tmp_path, monkeypatch):
    path = tmp_path / "secret.txt"
    path.write_text("hidden", encoding="utf-8")
    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):
        if self == path:
            raise OSError("denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    files = scan_directory(tmp_path, AppConfig(include_dotfiles=True))
    assert files == []
