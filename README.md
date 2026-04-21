# autoshelf v1.0.1

`autoshelf` scans a folder, extracts lightweight content context, drafts a reversible organization plan, applies moves plus shortcuts, and leaves behind `FOLDER_GUIDE.md`, `FILE_INDEX.md`, and a tamper-evident `manifest.jsonl`.

## Features

- Real Anthropic planner path with tool-use JSON, retries, rate limiting, prompt caching fields, and per-chunk FakeLLM fallback.
- Offline deterministic planning for CI and first-run use.
- Parser coverage for text, pdf, office, hwp, image, code, archive, and media files.
- Two-phase apply with resumable run plans, hash verification, and undo history.
- PySide6 desktop GUI with Home, Review, Apply, History, and Settings tabs.
- Korean and English UI catalogs.

## Install

### Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
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
python -m autoshelf verify /path/to/root
python -m autoshelf undo /path/to/root --dry-run
python -m autoshelf history /path/to/root
python -m autoshelf stats
python -m autoshelf doctor
python -m autoshelf version
python -m autoshelf gui
```

Offline planning is used automatically when `ANTHROPIC_API_KEY` is unset or `llm.provider = "fake"`.

After an apply, run `python -m autoshelf verify /path/to/root` to confirm the on-disk tree still matches the manifest hash chain.

## GUI

- Home: folder selection, recent folders, scan status, offline banner.
- Review: current/proposed tree panes, assignment table, planner rerun button.
- Apply: progress bar, token counter, log, cancel button.
- History: run table with undo/open/show-manifest actions.
- Settings: API key field, model pickers, chunk slider, locale/theme controls.

## Packaging

- `packaging/pyinstaller.spec` builds the desktop bundle.
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
