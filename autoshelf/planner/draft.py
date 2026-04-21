from __future__ import annotations

import json
from pathlib import Path

from autoshelf.planner.models import PlanDraft


def draft_path(root: Path) -> Path:
    return root / ".autoshelf" / "plan_draft.json"


def load_draft(root: Path) -> PlanDraft | None:
    path = draft_path(root)
    if not path.exists():
        return None
    return PlanDraft.model_validate_json(path.read_text(encoding="utf-8"))


def save_draft(root: Path, draft: PlanDraft) -> Path:
    path = draft_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(draft.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path
