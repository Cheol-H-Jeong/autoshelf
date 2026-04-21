# Autoshelf — Specification

> Cross-platform desktop app (Windows + Linux) that reads a messy folder, understands each file by peeking at its contents, and automatically reorganizes everything into a human-memorable directory tree — with a Markdown map left behind so agents (and humans) can navigate quickly.

Version: 0.1.0
Last updated: 2026-04-22

---

## 1. Goals

1. Point the app at any folder; it recursively inventories every file and subfolder.
2. For document-like files (hwp, pdf, ppt/pptx, xls/xlsx, doc/docx, txt, md), extract title + head content (~first page / first ~2000 chars) for classification context.
3. Use an LLM to **plan** a human-memorable directory structure based on all contexts, chunking when context is too long, iteratively adding/refining directories until all files are accounted for.
4. **Apply** the plan: move files into their assigned directories. If a file is strongly relevant to multiple directories, move to the most relevant one and leave a shortcut (symlink on Linux, `.lnk` on Windows) in the others.
5. Write `FOLDER_GUIDE.md` (rules) and `FILE_INDEX.md` (final placement map) at the root so that any agent can find anything by reading only these two files.
6. Everything is **reversible** via a transaction log.

## 2. Non-goals

- No cloud sync / remote storage integrations in v0.1.
- No OCR for scanned PDFs (optional post-v0.1).
- No real-time watching; classification runs on demand.

## 3. Tech stack

- **Language**: Python 3.11+
- **GUI**: PySide6 (Qt 6, LGPL, cross-platform)
- **Packaging**: PyInstaller → `.exe` (Windows, one-dir), AppImage + `.deb` (Linux)
- **Parsers**:
  - `pypdf` → PDF (falls back to `pdfminer.six` for difficult PDFs)
  - `python-pptx` → pptx
  - `openpyxl` → xlsx, `xlrd` → xls
  - `python-docx` → docx
  - `olefile` + `pyhwp` (or `hwp5txt` CLI) → hwp
  - built-in → txt, md, csv, json
- **LLM**: Anthropic Claude API (`anthropic` SDK). Model defaults:
  - Classification/chunking: `claude-haiku-4-5`
  - Structure planning & review: `claude-sonnet-4-6`
  - User configurable in settings.
  - Prompt caching enabled for the fixed system prompt + folder-rules context.
- **Storage**: SQLite via `sqlalchemy` for the metadata/context index and transaction log.
- **Logging**: `loguru`.
- **Config**: `pydantic` models; persisted at `~/.config/autoshelf/config.toml` (Linux) or `%APPDATA%\autoshelf\config.toml` (Windows).

## 4. Core features

### 4.1 Inventory (scan)
- Recursive walk with configurable `exclude` globs (defaults: `.git`, `node_modules`, `__pycache__`, `.venv`, dotfiles opt-in).
- Per-file metadata: absolute path, parent folder name, filename, stem, extension, size bytes, mtime, ctime, file hash (blake2b truncated 16 bytes, for dedupe).
- Stored in SQLite table `files`.

### 4.2 Context extraction
- Parser dispatch by extension. Each parser returns `{title, head_text, extra_meta}`.
- `head_text` capped at 2000 chars (configurable). Long documents truncated after first N pages (PDF/PPTX) or first N rows (XLSX).
- Parsing errors are logged but never fatal; file is still classified using filename+metadata only.
- Parsed contexts stored in `contexts` table keyed by file id.

### 4.3 Directory planning (chunked LLM loop)
- Build a "brief" per file: ~300 chars — filename, mtime, extension, title, head_text excerpt.
- Estimate token size; fill a chunk up to `MAX_CHUNK_TOKENS` (default 20_000, leaves headroom).
- **Round 1 (propose)**: for each chunk in order, call the Planner LLM with:
  - Running draft tree (JSON, starts empty).
  - New file briefs.
  - Output: updated tree (add new dirs, merge or rename if better), per-file tentative assignment, flags for files it is unsure about.
- **Round 2 (finalize)**: after all chunks processed, one more Planner call receives the full draft tree and **revises** for human memorability (dedupe near-duplicate folders, enforce naming rules, keep depth ≤ 3 unless justified).
- **Round 3 (assign)**: per-chunk classifier pass: given the final tree, place every file. Output primary dir + up to 2 "also-relevant" dirs (for shortcuts).

### 4.4 Folder naming rules (enforced by system prompt + post-validator)
- Korean primary if the majority of filenames/content are Korean, English otherwise; never mix languages within a single folder name.
- Max 4 words, or max 20 characters for Korean.
- Use concrete nouns a human would naturally search for (topic / project / document-type / year when helpful).
- Avoid: dates-only names (`2024-03`), cryptic abbreviations, single-letter, "misc" / "기타" / "etc" except as a last resort.
- No duplicate sibling names; no ambiguous pairs (e.g. "계약서" + "계약문서").

### 4.5 Apply (move + shortcut)
- Dry-run by default. GUI "Apply" button commits.
- For each file:
  - Move to primary directory. On name collision: append ` (2)`, ` (3)`, etc.
  - For each "also-relevant" dir: create shortcut.
    - Linux: symlink (`os.symlink`).
    - Windows: `.lnk` via `pylnk3`. Falls back to symlink if Developer Mode / admin.
- All moves/shortcuts recorded in `transactions` table with before/after paths → enables **Undo** (reverse in LIFO order).

### 4.6 Markdown manifests
- `FOLDER_GUIDE.md` at root: explains the naming rules, rationale for top-level folders, and a one-liner per folder ("여기에는 X 관련 파일이 들어갑니다").
- `FILE_INDEX.md` at root: flat list of every organized file with its new path + one-line summary (from head_text) + shortcuts (if any). Agents can `cat` this file alone to know where anything lives.
- Both files are regenerated idempotently on every apply.

### 4.7 GUI (PySide6)
Windows:
1. **Home**: pick folder, see scan stats, Start button.
2. **Review**: shows proposed tree side-by-side with current tree; expandable to see per-file assignments; edit folder names inline; reject per-file placements.
3. **Apply**: progress bar + live log.
4. **History**: past runs with Undo button.
5. **Settings**: API key, model selection, chunk size, include/exclude globs, language preference.

### 4.8 Additional core features (derived from the user's ask)
- **Dry-run toggle** (default ON).
- **Undo** (transactional).
- **Idempotent re-run**: if `FOLDER_GUIDE.md` exists, incorporate existing rules; don't reshuffle already-correctly-placed files.
- **Conflict resolution**: name collisions, read-only files, locked files.
- **Safe mode**: never move into a directory outside the originally-selected root.
- **Excluded paths**: user-supplied glob list.
- **Progress + cancellation**: every long task cancelable from GUI.
- **Telemetry**: local only, stored in SQLite; never uploaded.
- **Internationalization**: Korean + English UI strings.
- **Accessibility**: keyboard navigation, high-contrast option.

## 5. Project layout

```
autoshelf/
├── README.md
├── SPEC.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── autoshelf/
│   ├── __init__.py
│   ├── __main__.py          # entry point
│   ├── config.py            # pydantic settings
│   ├── db.py                # SQLAlchemy models
│   ├── scanner.py           # inventory walk
│   ├── parsers/
│   │   ├── __init__.py      # dispatch
│   │   ├── base.py
│   │   ├── pdf.py
│   │   ├── office.py        # pptx, xlsx, docx
│   │   ├── hwp.py
│   │   └── text.py
│   ├── planner/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── prompts.py       # system prompts (Korean-aware)
│   │   ├── llm.py           # Anthropic client + caching
│   │   └── pipeline.py      # round 1/2/3
│   ├── applier.py           # moves, shortcuts, transactions
│   ├── manifest.py          # FOLDER_GUIDE.md, FILE_INDEX.md
│   ├── shortcuts.py         # cross-platform shortcut creation
│   ├── undo.py
│   └── gui/
│       ├── __init__.py
│       ├── app.py
│       ├── home.py
│       ├── review.py
│       ├── apply.py
│       ├── history.py
│       └── settings.py
├── tests/
│   ├── test_scanner.py
│   ├── test_parsers.py
│   ├── test_planner_offline.py  # uses fake LLM
│   └── test_applier.py
├── resources/
│   └── icons/
└── packaging/
    ├── pyinstaller.spec
    ├── linux/autoshelf.desktop
    └── windows/autoshelf.iss  # Inno Setup
```

## 6. Acceptance criteria (v0.1)

- [ ] `python -m autoshelf` opens the GUI on both Windows and Linux.
- [ ] Scanning a sample folder with 50+ mixed-type files completes in under 30s (excluding LLM time).
- [ ] Parsers produce a non-empty `head_text` for at least 90% of supported-extension files in the sample set.
- [ ] With a fake/offline LLM (deterministic stub), the Planner produces a tree and assigns 100% of files.
- [ ] Dry-run shows the planned tree; Apply moves files; Undo restores original paths exactly.
- [ ] `FOLDER_GUIDE.md` and `FILE_INDEX.md` are generated and self-consistent with the filesystem.
- [ ] All unit tests pass. Linter (`ruff`) clean. Type-checked (`pyright` relaxed mode).

## 7. Licensing

MIT.
