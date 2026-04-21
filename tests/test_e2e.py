from __future__ import annotations

from autoshelf.applier import apply_plan
from autoshelf.config import AppConfig, LLMSettings
from autoshelf.parsers import parse_file
from autoshelf.planner.pipeline import PlannerPipeline
from autoshelf.scanner import scan_directory
from autoshelf.undo import undo_last_apply


def test_end_to_end_fake_llm_pipeline_restores_absolute_paths(tmp_path):
    originals = []
    for index in range(30):
        suffix = [".txt", ".md", ".json", ".csv", ".py"][index % 5]
        path = tmp_path / f"file-{index:02d}{suffix}"
        if suffix == ".json":
            path.write_text(f'{{"index": {index}}}', encoding="utf-8")
        else:
            path.write_text(f"title {index}\nbody {index}", encoding="utf-8")
        originals.append(path.resolve())
    config = AppConfig(llm=LLMSettings(provider="fake"))
    files = scan_directory(tmp_path, config)
    contexts = {file_info.absolute_path: parse_file(file_info.absolute_path) for file_info in files}
    result = PlannerPipeline(config).plan(files, contexts, root=tmp_path)
    outcome = apply_plan(tmp_path, result.assignments, result.tree, dry_run=False)
    index_text = (tmp_path / "FILE_INDEX.md").read_text(encoding="utf-8")
    for index in range(30):
        assert f"file-{index:02d}" in index_text
    assert len(outcome.moved) == 30
    undone = undo_last_apply(tmp_path)
    assert undone.undone >= 30
    restored = sorted(path.resolve() for path in tmp_path.glob("file-*"))
    assert restored == sorted(originals)
