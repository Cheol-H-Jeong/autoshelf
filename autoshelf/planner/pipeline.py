from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.chunking import FileBrief, chunk_briefs
from autoshelf.planner.llm import PlannerAssignment, get_planner_llm
from autoshelf.planner.naming import validate_folder_name, validate_sibling_names
from autoshelf.scanner import FileInfo


@dataclass(slots=True)
class PlanResult:
    tree: dict[str, object]
    assignments: list[PlannerAssignment]


class PlannerPipeline:
    """Chunked planning pipeline."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.llm = get_planner_llm(self.config)

    def plan(self, files: list[FileInfo], contexts: dict[Path, ParsedContext]) -> PlanResult:
        briefs = [self._brief(file_info, contexts) for file_info in files]
        chunks = chunk_briefs(briefs, self.config.max_chunk_tokens)
        tree: dict[str, object] = {}
        for chunk in chunks:
            response = self.llm.propose(tree, chunk)
            tree = response.tree
        final_tree = self.llm.finalize(tree, briefs)
        _validate_tree(final_tree)
        assignments = []
        for chunk in chunks:
            assignments.extend(self.llm.assign(final_tree, chunk))
        return PlanResult(tree=final_tree, assignments=assignments)

    def _brief(self, file_info: FileInfo, contexts: dict[Path, ParsedContext]) -> FileBrief:
        context = contexts.get(file_info.absolute_path, ParsedContext(file_info.stem, "", {}))
        return FileBrief(
            path=str(file_info.relative_path),
            filename=file_info.filename,
            extension=file_info.extension,
            mtime=file_info.mtime,
            title=context.title,
            head_text=context.head_text,
        )


def _validate_tree(tree: dict[str, object]) -> None:
    siblings = list(tree.keys())
    validate_sibling_names(siblings)
    for name, child in tree.items():
        validate_folder_name(name)
        _validate_tree(child)
