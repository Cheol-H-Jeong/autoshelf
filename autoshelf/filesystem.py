from __future__ import annotations

import hashlib
import shutil
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from autoshelf.scanner import _hash_file


class Filesystem(Protocol):
    def exists(self, path: Path) -> bool: ...

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None: ...

    def replace(self, source: Path, target: Path) -> None: ...

    def unlink(self, path: Path) -> None: ...

    def copy2(self, source: Path, target: Path) -> None: ...

    def rmtree(self, path: Path) -> None: ...

    def hash_file(self, path: Path) -> str: ...


@dataclass(slots=True)
class LocalFilesystem:
    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def replace(self, source: Path, target: Path) -> None:
        source.replace(target)

    def unlink(self, path: Path) -> None:
        path.unlink()

    def copy2(self, source: Path, target: Path) -> None:
        shutil.copy2(source, target)

    def rmtree(self, path: Path) -> None:
        shutil.rmtree(path)

    def hash_file(self, path: Path) -> str:
        return _hash_file(path) if path.exists() else ""


@dataclass(slots=True)
class FakeFilesystem:
    files: dict[Path, bytes] = field(default_factory=dict)
    directories: set[Path] = field(default_factory=set)
    _failures: dict[tuple[str, Path], list[BaseException]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def __post_init__(self) -> None:
        normalized_files = {self._normalize(path): content for path, content in self.files.items()}
        normalized_dirs = {self._normalize(path) for path in self.directories}
        self.files = normalized_files
        self.directories = normalized_dirs
        for path in tuple(self.files):
            self._ensure_parents(path.parent)

    def exists(self, path: Path) -> bool:
        normalized = self._normalize(path)
        return normalized in self.files or normalized in self.directories

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        normalized = self._normalize(path)
        if self.exists(normalized):
            if not exist_ok:
                raise FileExistsError(str(normalized))
            return
        parent = normalized.parent
        if parent != normalized and not parents and parent not in self.directories:
            raise FileNotFoundError(str(parent))
        self._ensure_parents(normalized)
        self.directories.add(normalized)

    def replace(self, source: Path, target: Path) -> None:
        normalized_source = self._normalize(source)
        normalized_target = self._normalize(target)
        self._raise_if_queued("replace", normalized_source)
        if normalized_source not in self.files:
            raise FileNotFoundError(str(normalized_source))
        self._ensure_parents(normalized_target.parent)
        self.files[normalized_target] = self.files.pop(normalized_source)

    def unlink(self, path: Path) -> None:
        normalized = self._normalize(path)
        self._raise_if_queued("unlink", normalized)
        if normalized not in self.files:
            raise FileNotFoundError(str(normalized))
        del self.files[normalized]

    def copy2(self, source: Path, target: Path) -> None:
        normalized_source = self._normalize(source)
        normalized_target = self._normalize(target)
        self._raise_if_queued("copy2", normalized_source)
        if normalized_source not in self.files:
            raise FileNotFoundError(str(normalized_source))
        self._ensure_parents(normalized_target.parent)
        self.files[normalized_target] = self.files[normalized_source]

    def rmtree(self, path: Path) -> None:
        normalized = self._normalize(path)
        self._raise_if_queued("rmtree", normalized)
        self.files = {
            file_path: content
            for file_path, content in self.files.items()
            if not self._is_relative_to(file_path, normalized)
        }
        self.directories = {
            directory
            for directory in self.directories
            if not self._is_relative_to(directory, normalized)
        }

    def hash_file(self, path: Path) -> str:
        normalized = self._normalize(path)
        if normalized not in self.files:
            return ""
        return hashlib.blake2b(self.files[normalized], digest_size=16).hexdigest()

    def write_text(self, path: Path, content: str) -> None:
        self.write_bytes(path, content.encode("utf-8"))

    def write_bytes(self, path: Path, content: bytes) -> None:
        normalized = self._normalize(path)
        self._ensure_parents(normalized.parent)
        self.files[normalized] = content

    def read_text(self, path: Path) -> str:
        normalized = self._normalize(path)
        return self.files[normalized].decode("utf-8")

    def queue_failure(self, operation: str, path: Path, exc: BaseException) -> None:
        normalized = self._normalize(path)
        self._failures[(operation, normalized)].append(exc)

    def list_files(self) -> Iterable[Path]:
        return sorted(self.files)

    def _raise_if_queued(self, operation: str, path: Path) -> None:
        key = (operation, path)
        queued = self._failures.get(key)
        if not queued:
            return
        exc = queued.pop(0)
        if not queued:
            del self._failures[key]
        raise exc

    def _ensure_parents(self, path: Path) -> None:
        current = self._normalize(path)
        lineage: list[Path] = []
        while current != current.parent and current not in self.directories:
            lineage.append(current)
            current = current.parent
        for entry in reversed(lineage):
            self.directories.add(entry)

    def _normalize(self, path: Path) -> Path:
        return Path(path)

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        if path == parent:
            return True
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True
