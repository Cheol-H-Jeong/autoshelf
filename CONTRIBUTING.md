## Contributing

Autoshelf is maintained as a safety-first product. Changes are expected to preserve reversibility, operator auditability, and stable public CLI behavior.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
```

## Required Gates

Run these before opening a pull request:

```bash
./.venv/bin/pytest -q
./.venv/bin/ruff check .
./.venv/bin/pyright --outputjson
```

If you touch the desktop shell, also run the offscreen smoke coverage:

```bash
QT_QPA_PLATFORM=offscreen ./.venv/bin/pytest -q tests/test_gui_smoke.py tests/test_gui_review.py
```

## Change Rules

- Keep modules under 500 lines. Split code instead of growing a catch-all module.
- New behavior requires at least one regression test.
- Do not remove public APIs or rewrite git history.
- Prefer additive migrations and compatibility shims over breaking config changes.
- Do not introduce new network dependencies; only the existing Anthropic provider path is allowed.
- Use `pathlib`, type hints, `loguru`, and `from __future__ import annotations` in new Python modules.

## Pull Request Expectations

- Describe the operator-facing impact and any risk area.
- Call out manifest, apply, undo, preview, verify, or GUI behavior changes explicitly.
- Include screenshots or terminal transcripts for user-facing UI/CLI changes when practical.
- Update `CHANGELOG.md` for release-worthy changes.

## Release Notes

Patch releases follow the existing `v1.0.x` pattern. The release flow expects:

1. Green gates.
2. Version bumps in `pyproject.toml` and `autoshelf/__init__.py`.
3. A `CHANGELOG.md` entry.
4. A pushed git tag.
5. A GitHub Release body copied from the changelog entry.
