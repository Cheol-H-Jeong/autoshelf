from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.parsers.base import ParsedContext
from autoshelf.planner.chunking import FileBrief, chunk_briefs
from autoshelf.planner.draft import load_draft, save_draft
from autoshelf.planner.llm import get_planner_llm
from autoshelf.planner.models import PlanDraft, PlannerAssignment, PlannerUsage
from autoshelf.planner.validation import validate_and_normalize_tree
from autoshelf.rules import apply_assignment_rules, load_planning_rules, merge_rule_paths
from autoshelf.scanner import FileInfo


@dataclass(slots=True)
class PlanResult:
    tree: dict[str, object]
    assignments: list[PlannerAssignment]
    unsure_paths: list[str]
    usage: PlannerUsage


class PlannerPipeline:
    """Chunked planning pipeline."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self.llm = get_planner_llm(self.config)

    def plan(
        self,
        files: list[FileInfo],
        contexts: dict[Path, ParsedContext],
        root: Path | None = None,
        resume: bool = False,
    ) -> PlanResult:
        rules = load_planning_rules(root)
        self.llm = get_planner_llm(self.config, rules)
        briefs = [self._brief(file_info, contexts) for file_info in files]
        chunks = self._chunk_briefs(briefs)
        tree: dict[str, object] = merge_rule_paths({}, rules)
        draft = load_draft(root) if resume and root is not None else None
        start_index = 0
        if draft is not None:
            tree = merge_rule_paths(draft.tree, rules)
            start_index = draft.processed_chunks
        unsure_paths: list[str] = list(draft.unsure_paths) if draft is not None else []
        for index, chunk in enumerate(chunks[start_index:], start=start_index):
            response = self.llm.propose(tree, chunk)
            tree = response.tree
            unsure_paths.extend(response.unsure_paths)
            if root is not None:
                save_draft(
                    root,
                    PlanDraft(
                        processed_chunks=index + 1,
                        tree=tree,
                        assignments=[],
                        unsure_paths=sorted(set(unsure_paths)),
                    ),
                )
        final_tree = validate_and_normalize_tree(
            merge_rule_paths(self.llm.finalize(tree, briefs), rules)
        )
        assignments: list[PlannerAssignment] = []
        for chunk in chunks:
            assignments.extend(self.llm.assign(final_tree, chunk))
        adjusted = [
            self._apply_confidence_rules(assignment)
            for assignment in apply_assignment_rules(assignments, rules)
        ]
        result = PlanResult(
            tree=final_tree,
            assignments=adjusted,
            unsure_paths=sorted(set(unsure_paths)),
            usage=self.llm.usage,
        )
        if root is not None:
            save_draft(
                root,
                PlanDraft(
                    processed_chunks=len(chunks),
                    tree=final_tree,
                    assignments=adjusted,
                    unsure_paths=result.unsure_paths,
                ),
            )
        return result

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

    def _chunk_briefs(self, briefs: list[FileBrief]) -> list[list[FileBrief]]:
        chunks: list[list[FileBrief]] = []
        current: list[FileBrief] = []
        current_tokens = 0
        for brief in briefs:
            brief_tokens = self.llm.count_tokens([brief])
            if current and current_tokens + brief_tokens > self.config.max_chunk_tokens:
                chunks.append(current)
                current = []
                current_tokens = 0
            current.append(brief)
            current_tokens += brief_tokens
        if current:
            chunks.append(current)
        return chunks or chunk_briefs(briefs, self.config.max_chunk_tokens)

    def _apply_confidence_rules(self, assignment: PlannerAssignment) -> PlannerAssignment:
        if assignment.confidence < 0.3:
            assignment.primary_dir = [".autoshelf", "quarantine"]
        if assignment.confidence < 0.6 and assignment.also_relevant:
            assignment.also_relevant = assignment.also_relevant[:1]
        return assignment
