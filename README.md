# autoshelf v1.0.7

`autoshelf` scans a folder, extracts lightweight content context, drafts a reversible organization plan, applies moves plus shortcuts, and leaves behind `FOLDER_GUIDE.md`, `FILE_INDEX.md`, and a tamper-evident `manifest.jsonl`.

## Features

- Real Anthropic planner path with tool-use JSON, retries, rate limiting, prompt caching fields, and per-chunk FakeLLM fallback.
- Offline deterministic planning for CI and first-run use.
- Parser coverage for text, pdf, office, hwp, image, code, archive, and media files.
- Two-phase apply with resumable run plans, hash verification, and undo history.
- PySide6 desktop GUI with saved light/dark theme support, rationale-rich review previews, and dedicated Home, Review, Apply, History, and Settings tabs.
- Korean and English UI catalogs.

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

Use `python -m autoshelf export /path/to/root` to package the current `manifest.jsonl`, `FOLDER_GUIDE.md`, `FILE_INDEX.md`, and resumable run plans into a portable `.tar.gz` bundle. Import that archive into another root with `python -m autoshelf import ...` to unpack it under `.autoshelf/imports/` for offline review, debugging, or support handoff without touching live files.

For machine consumers, add `--progress json` before the subcommand to emit JSONL progress events on stdout and finish with a single `result` line. That keeps long-running `plan`, `apply`, `export`, `import`, `verify`, and `doctor` runs pipe-friendly for wrappers and automation.

Autoshelf now saves a numbered `schema_version` in `config.toml` and migrates older unversioned configs on load, so desktop settings can evolve without breaking existing installations.

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
mappings:
  - glob: "*.invoice.pdf"
    target: Finance/Invoices
    also_relevant:
      - Documents
  - glob: "Screenshots/*.png"
    target: Images/Screenshots
```

Run `python -m autoshelf doctor /path/to/root` to confirm the rules file parses cleanly.

## GUI

- Home: folder selection, recent folders, scan status, offline banner.
- Review: current/proposed tree panes, colored move previews, assignment table, and folder rationale hints.
- Apply: progress bar, token counter, log, cancel button.
- History: run table with undo/open/show-manifest actions.
- Settings: persisted model pickers, chunk slider, locale/theme controls, and saved configuration feedback.

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
