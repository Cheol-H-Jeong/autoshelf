from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class FileBrief:
    path: str
    filename: str
    extension: str
    mtime: float
    title: str
    head_text: str

    @property
    def summary(self) -> str:
        return (
            f"{self.filename} | ext={self.extension} | mtime={int(self.mtime)} | "
            f"title={self.title} | excerpt={self.head_text[:180]}"
        )[:300]


def chunk_briefs(briefs: Iterable[FileBrief], max_tokens: int) -> list[list[FileBrief]]:
    chunks: list[list[FileBrief]] = []
    current: list[FileBrief] = []
    current_tokens = 0
    for brief in briefs:
        estimate = max(1, len(brief.summary) // 4)
        if current and current_tokens + estimate > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(brief)
        current_tokens += estimate
    if current:
        chunks.append(current)
    return chunks
