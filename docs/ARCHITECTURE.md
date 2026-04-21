## Autoshelf Architecture

`autoshelf` is a reversible file-organization system with a CLI pipeline and a desktop review shell built on the same core services.

## Component Map

```text
scan/parsers -> planner -> preview/review -> apply -> manifest/undo/verify
      |            |            |                |            |
      |            |            |                |            +-> audit + drift checks
      |            |            |                +-> staged moves + shortcuts
      |            |            +-> GUI + preview symlink tree
      |            +-> rules + offline heuristics + Anthropic provider
      +-> file metadata + duplicate hashes + parsed head text
```

## Data Flow

1. `autoshelf.scanner` walks the target root, applies ignore rules, and extracts metadata plus light parser output.
2. `autoshelf.rules` injects hard policy such as pinned folders and forced mappings before any model planning.
3. `autoshelf.planner.pipeline` converts file briefs into planner assignments using either offline heuristics or the Anthropic-backed provider path, then runs a full-tree review pass that can merge weak workflow folders and rewrite operator-facing rationales before preview or apply.
4. `autoshelf.preview` materializes a browseable symlink tree under `.autoshelf/preview/` so operators can inspect the proposed structure without moving live files.
5. `autoshelf.applier` promotes files into their final destinations, records resumable state, emits `manifest.jsonl`, and creates related-location shortcuts.
6. `autoshelf.verify` re-walks the tree, validates expected targets and shortcuts, and reports interrupted-copy drift or external tampering.
7. `autoshelf.undo` consumes the manifest trail to provide a reversible operator workflow.

## Storage Layout

- `.autoshelf/plan_draft.json`: latest planner draft.
- `.autoshelf/preview/`: dry-run symlink projection of the proposed tree.
- `.autoshelf/staging/`: interrupted-copy recovery area for staged artifacts.
- `.autoshelf/imports/`: validated import bundles before promotion.
- `manifest.jsonl`: append-only audit trail for apply operations.
- `FOLDER_GUIDE.md` and `FILE_INDEX.md`: human-readable operator outputs.

## Runtime Boundaries

- The only network path is the existing Anthropic planner provider. All other production workflows stay local.
- Core file operations live outside the GUI so the CLI and desktop shell use the same planning, preview, apply, undo, and verify logic.
- Filesystem-side reliability work is isolated in `applier.py`, `apply_state.py`, `filesystem.py`, and `verify.py`; GUI code should remain presentation-only.

## Extension Points

- Add parser support under `autoshelf/parsers/` and register it through `registry.py`.
- Add config migrations under `autoshelf/config_migrations/versions/` with a new numbered module and registry entry.
- Add CLI-safe automation output by extending `autoshelf.progress`.
- Add GUI review affordances under `autoshelf/gui/` without duplicating planner or applier logic.
