from __future__ import annotations

import errno
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from loguru import logger

from autoshelf.apply_state import CopyStage, RunPlanEntry, update_run_entry
from autoshelf.filesystem import Filesystem, LocalFilesystem


class RunEntryUpdater(Protocol):
    def __call__(
        self,
        plan_path: Path,
        source_path: str,
        *,
        status: str | None = None,
        target_path: str | None = None,
        copy_stage: CopyStage | None = None,
        staged_path: str | None = None,
    ) -> RunPlanEntry | None: ...


@dataclass(slots=True)
class FileMover:
    root: Path
    plan_path: Path
    staging_dir: Path
    filesystem: Filesystem = field(default_factory=LocalFilesystem)
    run_entry_updater: RunEntryUpdater = update_run_entry
    stage_name_factory: Callable[[Path], str] = field(
        default_factory=lambda: lambda target: f"{uuid.uuid4().hex}{target.suffix}.part"
    )

    def move(self, entry_path: str, source: Path, target: Path) -> Path:
        try:
            self.filesystem.replace(source, target)
            return target
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
        staged_target = self._stage_copy(source, target)
        self._record_copy_stage(entry_path, copy_stage="staged", staged_target=staged_target)
        self.filesystem.replace(staged_target, target)
        self._record_copy_stage(entry_path, copy_stage="target-written")
        self.filesystem.unlink(source)
        return target

    def recover(self, entry: RunPlanEntry, target: Path) -> Path | None:
        source = self.root / entry.path
        staged_target = self.root / entry.staged_path if entry.staged_path else None
        if self._can_finalize_duplicate_source(source, target, entry.source_hash):
            logger.info("resuming duplicated source cleanup for {}", entry.path)
            self.filesystem.unlink(source)
            self._clear_staged_artifact(staged_target)
            self.run_entry_updater(
                self.plan_path,
                entry.path,
                target_path=str(target.relative_to(self.root)),
                copy_stage="pending",
                staged_path="",
            )
            return target
        if staged_target is not None and self.filesystem.exists(staged_target):
            recovered = self._recover_staged_target(entry, source, target, staged_target)
            if recovered is not None:
                return recovered
        if self.filesystem.exists(source) or not self.filesystem.exists(target):
            return None
        if entry.source_hash and self.filesystem.hash_file(target) != entry.source_hash:
            return None
        logger.info("resuming completed move for {}", entry.path)
        self.run_entry_updater(
            self.plan_path,
            entry.path,
            target_path=str(target.relative_to(self.root)),
            copy_stage="pending",
            staged_path="",
        )
        return target

    def verify(
        self,
        source: Path,
        target: Path,
        source_hash: str,
        *,
        reconciled: bool = False,
    ) -> None:
        if self.filesystem.exists(source) and not reconciled:
            raise ValueError(f"source still exists after move: {source}")
        if not self.filesystem.exists(target):
            raise ValueError(f"target missing after move: {target}")
        if source_hash and self.filesystem.hash_file(target) != source_hash:
            raise ValueError("target hash mismatch after move")

    def cleanup(self) -> None:
        if self.filesystem.exists(self.staging_dir):
            self.filesystem.rmtree(self.staging_dir)

    def _stage_copy(self, source: Path, target: Path) -> Path:
        self.filesystem.mkdir(self.staging_dir, parents=True, exist_ok=True)
        staged_target = self.staging_dir / self.stage_name_factory(target)
        self.filesystem.copy2(source, staged_target)
        if self.filesystem.hash_file(source) != self.filesystem.hash_file(staged_target):
            raise ValueError("copy verification failed")
        return staged_target

    def _record_copy_stage(
        self,
        entry_path: str,
        *,
        copy_stage: CopyStage,
        staged_target: Path | None = None,
    ) -> None:
        staged_path = ""
        if staged_target is not None:
            staged_path = str(staged_target.relative_to(self.root))
        self.run_entry_updater(
            self.plan_path,
            entry_path,
            copy_stage=copy_stage,
            staged_path=staged_path,
        )

    def _can_finalize_duplicate_source(
        self,
        source: Path,
        target: Path,
        source_hash: str,
    ) -> bool:
        if not (self.filesystem.exists(source) and self.filesystem.exists(target)):
            return False
        if source_hash:
            return self.filesystem.hash_file(target) == source_hash
        return self.filesystem.hash_file(source) == self.filesystem.hash_file(target)

    def _recover_staged_target(
        self,
        entry: RunPlanEntry,
        source: Path,
        target: Path,
        staged_target: Path,
    ) -> Path | None:
        if entry.source_hash and self.filesystem.hash_file(staged_target) != entry.source_hash:
            return None
        logger.info("recovering staged copy for {}", entry.path)
        if not self.filesystem.exists(target):
            self.filesystem.replace(staged_target, target)
            self.run_entry_updater(
                self.plan_path,
                entry.path,
                target_path=str(target.relative_to(self.root)),
                copy_stage="target-written",
                staged_path=str(staged_target.relative_to(self.root)),
            )
        if self.filesystem.exists(source):
            self.filesystem.unlink(source)
        self._clear_staged_artifact(staged_target)
        self.run_entry_updater(
            self.plan_path,
            entry.path,
            target_path=str(target.relative_to(self.root)),
            copy_stage="pending",
            staged_path="",
        )
        return target

    def _clear_staged_artifact(self, staged_target: Path | None) -> None:
        if staged_target is None or not self.filesystem.exists(staged_target):
            return
        self.filesystem.unlink(staged_target)
