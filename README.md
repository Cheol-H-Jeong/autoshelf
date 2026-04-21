# autoshelf

`autoshelf` scans a folder, extracts lightweight content context, drafts a reversible organization plan, applies moves plus shortcuts, and leaves behind `FOLDER_GUIDE.md`, `FILE_INDEX.md`, and a tamper-evident `manifest.jsonl`.

## Features

- Real Anthropic planner path with tool-use JSON, jittered retries, a cooldown circuit breaker, prompt caching fields, and per-chunk FakeLLM fallback.
- Offline deterministic planning for CI and first-run use.
- Parser coverage for text, pdf, office, hwp, image, code, archive, and media files.
- Two-phase apply with resumable run plans, interrupt-aware run state, staged cross-device moves, hash verification, and undo history.
- PySide6 desktop GUI with saved light/dark theme support, runtime language/theme updates, rationale-rich review previews, and dedicated Home, Review, Apply, History, and Settings tabs.
- Korean and English UI catalogs.

Operator documentation lives in [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

## Install

### Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
```

With `pipx`:

```bash
pipx install '.[all]'
autoshelf version
```

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[all]
```

## CLI

```bash
python -m autoshelf --help
python -m autoshelf scan /path/to/root
python -m autoshelf plan /path/to/root --resume
python -m autoshelf preview /path/to/root
python -m autoshelf apply /path/to/root --policy append-counter
python -m autoshelf --progress json plan /path/to/root
python -m autoshelf verify /path/to/root
python -m autoshelf export /path/to/root --output /tmp/autoshelf-bundles
python -m autoshelf import /tmp/autoshelf-bundles/root.tar.gz /path/to/audit-root
python -m autoshelf undo /path/to/root --dry-run
python -m autoshelf history /path/to/root
python -m autoshelf stats
python -m autoshelf doctor
python -m autoshelf version
python -m autoshelf gui
```

Offline planning is used automatically when `ANTHROPIC_API_KEY` is unset or `llm.provider = "fake"`.

When Anthropic planning is enabled, autoshelf sends each file brief with its immediate parent folder name so uploads from meaningful staging folders like `receipts/`, `client-a/`, or `강의자료/` keep that signal during classification. The Anthropic prompt prefix also includes stable few-shot examples in a cacheable system block so repeated runs on the same machine spend fewer prompt tokens on shared planner instructions.

After an apply, run `python -m autoshelf verify /path/to/root` to confirm the on-disk tree still matches the manifest hash chain.
If an apply is interrupted, rerun `python -m autoshelf apply /path/to/root --resume <run-id>` to finish the recorded run safely. `verify` now reports incomplete runs and leftover staged recovery artifacts under `.autoshelf/` so operators can audit the tree before trusting it.

Before an apply, run `python -m autoshelf preview /path/to/root` to build a browsable `.autoshelf/preview/` tree made from symlinks only. Autoshelf reuses the saved plan draft when it already has assignments, or replans automatically when you pass `--refresh` or there is no complete draft yet. The preview path mirrors final collision handling, so duplicate names render as `file (2).ext` there before you commit to a live move.

Use `python -m autoshelf export /path/to/root` to package the current `manifest.jsonl`, `FOLDER_GUIDE.md`, `FILE_INDEX.md`, plan draft, rules file, and resumable run plans into a portable `.tar.gz` bundle. Each bundle now carries a signed-style inventory in `bundle/metadata.json` with per-file SHA-256 checksums plus an operator-facing `bundle/IMPORT_GUIDE.md`. Import that archive into another root with `python -m autoshelf import ...` to unpack it under `.autoshelf/imports/` for offline review, debugging, or support handoff without touching live files. Import rejects path traversal, duplicate members, unsupported tar entries, and checksum mismatches before the bundle is committed into place.

For machine consumers, add `--progress json` before the subcommand to emit JSONL progress events on stdout and finish with a single `result` line. That keeps long-running `plan`, `apply`, `export`, `import`, `verify`, and `doctor` runs pipe-friendly for wrappers and automation.

Autoshelf now saves a numbered `schema_version` in `config.toml` and migrates older unversioned configs on load, so desktop settings can evolve without breaking existing installations.

If you run Anthropic planning against unstable connectivity, tune the new reliability knobs in `config.toml`:

```toml
[llm]
max_retries = 4
retry_base_delay_ms = 500
retry_max_delay_ms = 8000
retry_jitter_ms = 250
circuit_breaker_threshold = 3
circuit_breaker_cooldown_seconds = 30
```

## Rules File

Install `autoshelf` with `.[rules]` if you want YAML rule files without the full optional stack:

```bash
pip install -e .[rules]
```

Place `.autoshelfrc.yaml` at the root you plan or apply. Autoshelf reads it before planning, keeps pinned folders in the proposed tree, and forces matching files into the configured targets.

```yaml
version: 1
pinned_dirs:
  - Finance/Taxes
  - Documents/Receipts
exclude_globs:
  - Inbox/**
  - "*.tmp"
mappings:
  - glob: "*.invoice.pdf"
    priority: 10
    target: Finance/Invoices
    also_relevant:
      - Documents
  - glob: "Screenshots/*.png"
    target: Images/Screenshots
```

`exclude_globs` removes matching files from scan, plan, preview, and apply. When multiple mapping rules overlap, the highest `priority` wins. Run `python -m autoshelf doctor /path/to/root` to confirm the rules file parses cleanly and to see the parsed rule counts.

## GUI

- Home: folder selection, recent folders, scan status, offline banner.
- Review: current/proposed tree panes, colored move previews, assignment table, and folder rationale hints.
- Apply: progress bar, token counter, log, cancel button.
- History: run table with undo/open/show-manifest actions.
- Settings: persisted model pickers, chunk slider, locale/theme controls, and saved configuration feedback that applies immediately to the live window.

Keyboard shortcuts:

- `F5`: switch to Home and rerun the scan preview.
- `Ctrl+Enter`: switch to Apply and start the apply workflow.
- `Ctrl+Z`: switch to History and queue an undo review action.

## Packaging

- `python packaging/build.py` creates a Linux release tarball under `dist/` with a wheel, installer script, desktop entry, and bundled docs.
- `python packaging/bump_version.py patch|minor|major` updates `pyproject.toml`, `autoshelf/__init__.py`, and adds the next changelog heading.
- `packaging/pyinstaller.spec` remains available for a future standalone desktop bundle.
- `packaging/windows/autoshelf.iss` builds the Inno Setup installer.
- `packaging/linux/autoshelf.desktop` is the Linux desktop entry.
- `packaging/build.py` is the host-aware build driver.

## Screenshots

- `docs/screenshots/home.png`
- `docs/screenshots/review.png`
- `docs/screenshots/apply.png`
- `docs/screenshots/history.png`
- `docs/screenshots/settings.png`

## License

MIT. See [LICENSE](LICENSE).
