from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.scanner import FileInfo

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z\u00C0-\u024F\u3131-\u318E\uAC00-\uD7A3]+")


class NearDuplicateInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = ""
    group_size: int = Field(default=1, ge=1)
    strongest_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    peers: tuple[str, ...] = ()


def detect_near_duplicates(
    files: list[FileInfo],
    contexts: dict[Path, ParsedContext],
    config: AppConfig,
) -> dict[str, NearDuplicateInfo]:
    if not config.near_duplicate_detection:
        return {}
    token_sets: dict[str, set[str]] = {}
    for file_info in files:
        tokens = _tokens_for_file(file_info, contexts, config)
        if tokens is None:
            continue
        token_sets[str(file_info.relative_path)] = tokens
    if len(token_sets) < 2:
        return {}
    edges = _pairwise_edges(token_sets, files, config.near_duplicate_threshold)
    if not edges:
        return {}
    return _build_group_info(edges)


def _tokens_for_file(
    file_info: FileInfo,
    contexts: dict[Path, ParsedContext],
    config: AppConfig,
) -> set[str] | None:
    context = contexts.get(file_info.absolute_path)
    if context is None:
        return None
    signal = " ".join(
        part.strip()
        for part in (context.title, context.head_text)
        if isinstance(part, str) and part.strip()
    )
    tokens = TOKEN_PATTERN.findall(signal.casefold())
    if len(tokens) < config.near_duplicate_min_token_count:
        return None
    return _shingles(tokens, config.near_duplicate_shingle_size)


def _pairwise_edges(
    token_sets: dict[str, set[str]],
    files: list[FileInfo],
    threshold: float,
) -> dict[str, dict[str, float]]:
    file_index = {str(file_info.relative_path): file_info for file_info in files}
    by_extension: dict[str, list[str]] = defaultdict(list)
    for path in token_sets:
        extension = file_index[path].extension.lower()
        by_extension[extension].append(path)
    edges: dict[str, dict[str, float]] = defaultdict(dict)
    for paths in by_extension.values():
        for left_path, right_path in combinations(sorted(paths), 2):
            similarity = _jaccard(token_sets[left_path], token_sets[right_path])
            if similarity < threshold:
                continue
            edges[left_path][right_path] = similarity
            edges[right_path][left_path] = similarity
    return edges


def _build_group_info(edges: dict[str, dict[str, float]]) -> dict[str, NearDuplicateInfo]:
    visited: set[str] = set()
    groups: dict[str, NearDuplicateInfo] = {}
    for start in sorted(edges):
        if start in visited:
            continue
        stack = [start]
        component: list[str] = []
        while stack:
            path = stack.pop()
            if path in visited:
                continue
            visited.add(path)
            component.append(path)
            stack.extend(
                neighbor
                for neighbor in sorted(edges[path], reverse=True)
                if neighbor not in visited
            )
        members = tuple(sorted(component))
        group_id = hashlib.blake2b("|".join(members).encode("utf-8"), digest_size=8).hexdigest()
        for member in members:
            peers = tuple(path for path in members if path != member)
            strongest = max((edges[member].get(peer, 0.0) for peer in peers), default=0.0)
            groups[member] = NearDuplicateInfo(
                group_id=group_id,
                group_size=len(members),
                strongest_similarity=round(strongest, 4),
                peers=peers,
            )
    return groups


def _shingles(tokens: list[str], shingle_size: int) -> set[str]:
    if len(tokens) <= shingle_size:
        return {" ".join(tokens)}
    return {
        " ".join(tokens[index : index + shingle_size])
        for index in range(len(tokens) - shingle_size + 1)
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)
