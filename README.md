# autoshelf

`autoshelf` scans a folder, extracts lightweight context from files, plans a human-readable directory tree, applies moves plus shortcuts, generates Markdown manifests, and can undo the last apply run.

## Installation

### Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

GUI support:

```bash
pip install -e .[gui]
```

Optional parsers and Anthropic integration:

```bash
pip install -e .[parsers,llm]
```

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
pip install -e .[gui]
```

## Usage

CLI help:

```bash
python -m autoshelf --help
autoshelf scan /path/to/root
autoshelf plan /path/to/root
autoshelf apply /path/to/root
autoshelf undo /path/to/root
autoshelf gui
```

Offline planning is automatic when `ANTHROPIC_API_KEY` is unset or config sets `llm.provider = "fake"`.

## GUI

The GUI is a minimal PySide6 desktop shell with the Home screen implemented and placeholder tabs for Review, Apply, History, and Settings.

## Screenshots

Placeholder:

- `docs/screenshots/home.png`
- `docs/screenshots/review.png`

## License

MIT. See [LICENSE](LICENSE).
