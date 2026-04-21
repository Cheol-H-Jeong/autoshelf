from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from autoshelf.config import AppConfig
from autoshelf.rules import is_path_excluded


@dataclass(slots=True)
class FileInfo:
    """Scanned file metadata."""

    absolute_path: Path
    relative_path: Path
    parent_name: str
    filename: str
    stem: str
    extension: str
    size_bytes: int
    mtime: float
    ctime: float
    file_hash: str


def scan_directory(
    root: Path,
    config: AppConfig | None = None,
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> list[FileInfo]:
    """Recursively inventory a directory."""

    cfg = config or AppConfig()
    files: list[FileInfo] = []
    paths = sorted(root.rglob("*"))
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        if _is_excluded(root, path, cfg.exclude, cfg.include_dotfiles):
            continue
        try:
            if path.is_dir():
                continue
            stat = path.stat()
            files.append(
                FileInfo(
                    absolute_path=path.resolve(),
                    relative_path=path.resolve().relative_to(root.resolve()),
                    parent_name=path.parent.name,
                    filename=path.name,
                    stem=path.stem,
                    extension=path.suffix.lower().lstrip("."),
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                    ctime=stat.st_ctime,
                    file_hash=_hash_file(path),
                )
            )
        except OSError as exc:
            logger.warning("scan failed for {}: {}", path, exc)
        if on_progress is not None:
            on_progress(index, total, path)
    return files


def _is_excluded(root: Path, path: Path, patterns: Iterable[str], include_dotfiles: bool) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if not include_dotfiles and any(part.startswith(".") for part in parts):
        return True
    return is_path_excluded(str(rel), list(patterns))


def _hash_file(path: Path) -> str:
    digest = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
