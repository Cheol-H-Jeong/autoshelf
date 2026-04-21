# Autoshelf — v1.0 Specification

> This supersedes SPEC.md (v0.1 MVP). Everything in SPEC.md that is not explicitly revised here remains in force. v1.0 is the first release intended for real end-user distribution on Windows + Linux.

Version: 1.0.0
Last updated: 2026-04-22
Primary author: autoshelf team (Cheol-H-Jeong)

---

## 1. Release goals

1. **Production-ready desktop app** — installable on Windows (.exe via PyInstaller + Inno Setup) and Linux (AppImage + .deb), double-clickable, no terminal required.
2. **Real LLM planning** — actual Anthropic API calls with prompt caching, batching, retry, structured JSON tool-use for plan + assignments. Offline `FakeLLM` remains as first-run default and CI test backbone.
3. **Full GUI** — all 5 tabs from SPEC §4.7 functional end-to-end (Home, Review, Apply, History, Settings) with a proposed-tree diff viewer, drag-and-drop folder rename, per-file reassignment, live Apply progress, Undo from History.
4. **Safety-first defaults** — dry-run first, atomic transaction log, root-escape guard, reversible Undo even across app restarts, quarantine for files the planner rejected.
5. **Trust & transparency** — every move logged; `FILE_INDEX.md` + `FOLDER_GUIDE.md` kept in sync and machine-parseable; a `manifest.jsonl` emitted alongside them.
6. **i18n** — Korean and English UI strings, auto-detected, user-overridable.
7. **Extensible** — new parsers and new LLM providers pluggable via entry points.

## 2. New / revised features vs. v0.1

### 2.1 Planner — real LLM path (blocker for v1.0)

Replace the stub `AnthropicPlannerLLM` with a fully-wired client:

- Uses `anthropic` SDK `client.messages.create(...)` with:
  - `system`: cached (`cache_control={"type":"ephemeral"}`) block containing the folder-rules system prompt + any existing `FOLDER_GUIDE.md` content for idempotent re-runs.
  - `messages`: rolling tree + new chunk of briefs, emitted as structured JSON.
  - `tools`: one tool `emit_plan` with a JSON schema (tree: dict, assignments: list of {path, primary_dir: list[str], also_relevant: list[list[str]], summary: str, confidence: 0–1}, unsure: list[str]). The model is forced to use `tool_choice={"type":"tool","name":"emit_plan"}`.
- Three model roles, each configurable in `Settings`:
  - `classification_model` default `claude-haiku-4-5`
  - `planning_model` default `claude-sonnet-4-6`
  - `review_model` default `claude-sonnet-4-6` (used only in Round 2 finalize)
- Rate limiting: token-bucket wrapper (`RateLimiter`), defaults 2 RPS + concurrency 3.
- Retries: exponential backoff (0.5s → 8s, 4 retries) on 429 / 5xx / connection errors; permanent error surfaces to GUI.
- Cost estimator: tokens in/out per call tallied; displayed in Apply tab.
- Fallback: any call failure downgrades the *single chunk* to `FakeLLM`, never the whole run; `FILE_INDEX.md` marks the affected files with `⚠ fallback`.
- Prompt-caching is real: first call primes the cache, subsequent chunks reuse it; log `cache_read_input_tokens` vs `cache_creation_input_tokens`.

### 2.2 Planner — chunking & incremental tree

- Chunk size by token budget, not file count. Helper: `count_tokens(briefs)` using `anthropic.Anthropic.count_tokens` (network-free heuristic fallback: 3.5 chars/token for mixed Korean/English).
- Streaming per-chunk: as each chunk returns, the incremental draft tree is written to `.autoshelf/plan_draft.json` so a crash mid-plan is resumable (`autoshelf plan --resume`).
- After all chunks, Round 2 finalize sends the full tree + naming-rules to `review_model`; it may rename, merge, or split folders. A deterministic post-validator then enforces SPEC §4.4 hard rules (no "misc", no language mixing inside one folder name, no ambiguous sibling pairs, depth ≤ 3 unless `deep_ok: true` is set by the LLM with a justification).
- Round 3 assignment uses the final tree. For any file the LLM's `confidence < 0.6`, its `also_relevant` top candidate is also honored (shortcut created). Files with `confidence < 0.3` go to a `.autoshelf/quarantine/` bucket and are listed in the manifest as "needs human review".

### 2.3 Parsers

- `pdf.py`: pypdf primary, falls back to `pdfminer.six` if pypdf returns empty string; extracts OCR hint when the PDF has no text at all (logs "scanned PDF — no OCR").
- `office.py`: pptx titles (first text frame per slide, first 3 slides), docx first 2 paragraphs + title style, xlsx first sheet name + first 10 rows as pseudo-text.
- `hwp.py`: pyhwp primary; if unavailable, `olefile` + `hwp5txt` CLI fallback. Timeout 8s per file.
- `text.py`: handles `.txt`, `.md`, `.csv`, `.json`, `.log`, `.rtf`, `.epub`(via `ebooklib` if installed). Encoding detection with `charset-normalizer`.
- `image.py` (new): reads EXIF date/camera, IPTC title/keywords. File still classified primarily by extension, but EXIF contributes to the brief.
- `code.py` (new): for source files (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.cs`, `.cpp`, `.c`, `.sql`, `.sh`) — extracts module docstring / header comment / first N lines.
- `archive.py` (new): for `.zip`/`.tar`/`.7z` — lists top-level entries as the brief (does NOT extract).
- `media.py` (new): for `.mp3`/`.mp4`/`.mov`/`.mkv`/`.wav` — pulls `mutagen` / `ffprobe` metadata (title, artist, duration).
- Every parser returns the same `ParsedContext(title, head_text, extra_meta)` and registers via an entry point `autoshelf.parsers` so 3rd parties can plug in.
- Safety: each parser is called under a subprocess-bounded or signal-bounded 10s cap; errors are captured and the file still receives a filename-only context.

### 2.4 Applier

- Two-phase commit: first write a JSONL plan file at `.autoshelf/runs/<run_id>.plan.jsonl`, then execute row by row. If interrupted, `autoshelf apply --resume <run_id>` continues.
- Atomicity per file: move (same device) → `os.rename`; cross-device → copy-then-delete with post-copy hash verification.
- Collision handling: conflict policy per run — `append-counter` (default), `overwrite`, `skip`, `prompt` (GUI only).
- Permission-denied / locked files: logged, file left in place, manifest notes the skip.
- Shortcut creation:
  - Linux: symlink first, `.desktop` file second if target dir is on a non-POSIX filesystem.
  - Windows: `.lnk` via `pylnk3`; if unavailable, falls back to a copy of the file suffixed ` (사본)` / ` (copy)`.
- Post-apply verification: every planned move is asserted (source gone, target present, size + hash match).
- Manifest emission: `FOLDER_GUIDE.md`, `FILE_INDEX.md`, and `manifest.jsonl` (one JSON line per moved file) are overwritten atomically via tempfile + rename.

### 2.5 Undo & History

- `Database.TransactionRecord` gains `run_id`, `sequence`, `status` (`planned`/`applied`/`reverted`).
- `undo` command accepts:
  - no args → reverts the single most recent `applied` run LIFO.
  - `--run-id <id>` → reverts a specific run.
  - `--dry-run` → prints what would happen.
- GUI History tab: list of past runs (root, timestamp, moved count, status), Undo + "Open folder" + "Show manifest" per row.
- Revert is idempotent: if a file was subsequently moved by a later run, revert only moves it if the current location matches the recorded target; otherwise the entry is flagged `conflict` and user is asked.

### 2.6 GUI (PySide6)

All 5 screens real:

- **Home**
  - Folder picker (drag-and-drop target), recent-folders list (max 8).
  - Scan stats (files counted, size, extension histogram) shown live during scan.
  - Big "Plan →" button; disabled until scan finishes.
  - Offline-mode banner when `ANTHROPIC_API_KEY` is missing.
- **Review**
  - Left pane: current tree (read-only).
  - Right pane: proposed tree. Rename by double-click, rearrange by drag, delete by Del.
  - Per-file list below: path, confidence bar, primary-dir chip, "also-relevant" chips, reassign via right-click.
  - "Re-run Planner" button (uses edited tree as seed; LLM may refine).
  - "Approve & Apply →" button.
- **Apply**
  - Progress bar with per-file log, token-usage counter, elapsed, ETA.
  - Cancel (graceful; already-moved files are kept, a partial manifest is written).
  - Success screen links to `FILE_INDEX.md` and "Open in File Manager".
- **History**
  - Past runs table as described in §2.5.
  - Undo button per row.
- **Settings**
  - API key (stored via `keyring` on both platforms; never written to plain config).
  - Model selection (3 dropdowns).
  - Chunk token budget slider (4k–32k).
  - Language preference (auto / ko / en).
  - Dry-run default toggle.
  - Exclude-glob list.
  - Theme (system / light / dark).
  - "Test connection" button that issues a 1-token ping.

All long-running work runs on a `QThread`; main thread never blocks. Signals carry progress.

### 2.7 Packaging & distribution

- `pyproject.toml` extras: `gui`, `parsers`, `llm`, `dev`, `all`.
- `packaging/pyinstaller.spec` — produces one-dir build; hidden imports for `anthropic`, `PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtWidgets`, parser libs.
- `packaging/windows/autoshelf.iss` — Inno Setup script producing `autoshelf-1.0.0-win-x64-setup.exe` (install to `%ProgramFiles%\autoshelf\`, add Start Menu shortcut, register `.autoshelf-plan` file association).
- `packaging/linux/autoshelf.desktop` — valid desktop entry; packaged into AppImage via `linuxdeploy` and into `.deb` via `dpkg-deb`.
- `packaging/build.py` — single-entry build driver that detects host OS and produces the correct artifact; emits SHA-256 alongside.
- `packaging/Makefile` — `make build-linux`, `make build-windows` (latter requires wine or CI runner), `make release VERSION=x.y.z`.
- GitHub Actions `.github/workflows/release.yml` — on tag `v*.*.*`: build Linux artifact on Ubuntu runner, Windows artifact on windows runner, attach to a GitHub Release.
- GitHub Actions `.github/workflows/ci.yml` — on push/PR: lint + test on Linux and Windows, Python 3.11 and 3.12.

### 2.8 Observability

- `loguru` sinks: stderr + rotating file at `~/.local/state/autoshelf/logs/autoshelf.log` (Linux) / `%LOCALAPPDATA%\autoshelf\logs\` (Windows), 10 MB × 5.
- Telemetry: local-only counters in SQLite (`events` table): scans, plans, applies, undos, per-extension counts, LLM tokens, LLM cache-hit rate, parser error rate. NEVER uploaded. A `autoshelf stats` CLI subcommand dumps them as a table.
- Crash handler: uncaught exceptions in GUI write a `crash-<timestamp>.log` next to the main log and show a dialog with "Copy to clipboard".

### 2.9 i18n

- All user-facing strings routed through `autoshelf.i18n.t("key", **kwargs)`.
- Catalogs: `autoshelf/i18n/ko.json`, `autoshelf/i18n/en.json`. English is canonical; Korean is the other v1.0 language.
- Auto-detect from `locale.getdefaultlocale()`; Settings override.
- Folder-name generator respects the chosen UI language AND the corpus majority language separately — if the user selects Korean UI but the corpus is 95% English, folder names still go English (following SPEC §4.4 corpus-majority rule). This is documented.

### 2.10 Plugins & extension points

- Entry points under these groups:
  - `autoshelf.parsers` → callables returning `ParsedContext`, registered by extension glob.
  - `autoshelf.llm_providers` → factories producing objects that implement the `PlannerLLM` Protocol.
  - `autoshelf.naming_rules` → validators called during Round 2 finalize.
- Discovery via `importlib.metadata.entry_points(group=...)`.
- Built-in providers (`anthropic`, `fake`) registered via `pyproject.toml` entry points.

### 2.11 CLI — v1.0 surface

```
autoshelf scan <root> [--exclude GLOB] [--json]
autoshelf plan <root> [--resume] [--model MODEL] [--chunk-tokens N] [--dry-run]
autoshelf apply <root> [--resume RUN_ID] [--dry-run] [--policy POLICY] [--yes]
autoshelf undo <root> [--run-id RUN_ID] [--dry-run]
autoshelf history <root> [--limit N] [--json]
autoshelf stats [--json]
autoshelf gui
autoshelf doctor       # diagnostics: python ver, deps, API key, disk, parsers available
autoshelf version
```

All subcommands accept `--log-level {debug,info,warning,error}` and `--config PATH`.

### 2.12 Doctor

`autoshelf doctor` performs:
- Python version check (>=3.11).
- Required deps importable (anthropic, PySide6, pypdf, openpyxl, python-pptx, python-docx, pyhwp).
- `ANTHROPIC_API_KEY` set; test ping to the API (1 token).
- Disk space in `~/.local/share/autoshelf` / `%LOCALAPPDATA%\autoshelf`.
- Writability of selected root (if passed).
- `pylnk3` on Windows, symlink capability on Linux.

Emits a table + exit-code 0/1.

## 3. Non-goals (still, for v1.0)

- No OCR.
- No cloud sync.
- No multi-user collaboration.
- No real-time filesystem watcher.
- No mobile build.

## 4. Acceptance criteria (blocker list)

- [ ] `pip install -e .[all]` succeeds on Python 3.11 Linux.
- [ ] `python -m autoshelf --help` lists all 9 subcommands from §2.11.
- [ ] `pytest -q` — at least **25** tests, all passing. Coverage by module:
  - scanner (empty, mixed, excluded, permission-error)
  - parsers (one per supported extension, happy + malformed file)
  - planner offline (FakeLLM single-language corpus, mixed corpus, empty corpus, resume-from-draft)
  - planner online mocked (Anthropic client mocked, tool-use JSON parsed, retry on 429)
  - applier (dry-run, apply, cross-device, collision, resume, verify-hash)
  - undo (single run, specific run, conflict detection)
  - manifest (idempotent regen)
  - shortcuts (symlink Linux; .lnk path exercised via mock)
  - i18n (ko + en keys present, missing-key fallback)
  - doctor (pure function, mocked environment)
- [ ] `ruff check .` clean.
- [ ] `pyright --outputjson` returns zero errors (relaxed mode).
- [ ] GUI smoke test (offscreen via `QT_QPA_PLATFORM=offscreen`) instantiates all 5 screens without raising.
- [ ] End-to-end test: fixture directory with 30 mixed files → scan → plan (FakeLLM) → apply → verify `FILE_INDEX.md` lists all 30 with valid new paths → undo → verify original layout restored.
- [ ] `autoshelf doctor` passes on the dev machine.
- [ ] `README.md` updated with v1.0 features, install instructions for Windows + Linux, screenshots-placeholder, CLI reference auto-generated.
- [ ] `CHANGELOG.md` created with `v1.0.0` entry.
- [ ] GitHub Actions workflow files exist and are syntactically valid (`yamllint` clean).
- [ ] Git tag `v1.0.0` created on the final commit.

## 5. Code hygiene

- Every module under 500 lines; split with clear names if needed.
- `from __future__ import annotations` mandatory.
- Public API docstring'd; internals bare.
- No `print()` in library code; `logger.bind(component=...)` everywhere.
- `pydantic` v2 for all config + LLM response schemas.
- All filesystem ops through `pathlib.Path`; no `os.path.join`.
- Tests isolated: no network, no user home touch, all state in `tmp_path`.
- `conftest.py` provides fixtures: `sample_corpus` (generates a realistic mixed dir), `mock_anthropic` (pytest fixture that stubs `anthropic.Anthropic`).

## 6. Delivery

On completion, tag `v1.0.0` and push to `origin main` + tags. Create a GitHub Release body from CHANGELOG.md entry.
