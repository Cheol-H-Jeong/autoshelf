# Changelog

## v1.0.4

- Applied saved GUI light and dark themes at startup instead of leaving the theme selector disconnected from the actual desktop palette.
- Wired the Settings screen to real config persistence with save feedback so theme, language, chunk budget, and exclude globs survive restarts.
- Rebuilt the Review tab as a real move preview with colored status indicators, target overlays, and folder-level rationale hints pulled from planner assignment summaries.

## v1.0.3

- Added a working Linux release bundle flow that emits a versioned `tar.gz` with the project wheel, installer script, desktop entry, copied docs, and SHA-256 checksum.
- Added `packaging/bump_version.py` plus `Makefile` targets so patch, minor, and major release bumps update the package version files and changelog heading consistently.
- Added regression coverage for the packaging scripts and documented the Linux bundle and `pipx` install workflow in the README.

## v1.0.2

- Added `.autoshelfrc.yaml` planning rules with pinned folders and glob-based folder overrides applied before and after planning.
- Surfaced rules constraints in Anthropic planner prompts so online planning follows the same policy as offline runs.
- Added doctor coverage for rules file validity and documented the rules workflow in the README.

## v1.0.1

- Added a tamper-evident hash-chain manifest schema with per-file content hashes.
- Added `autoshelf verify <root>` to audit applied trees for hash drift, missing targets, broken shortcuts, and unexpected files.
- Documented the verification workflow in the README CLI examples.

## v1.0.0

- Added real Anthropic planner integration with structured tool-use payloads and retry/fallback handling.
- Expanded parser support and plugin discovery entry points.
- Added resumable apply plans, richer undo history, atomic manifests, and local stats/doctor commands.
- Rebuilt the PySide6 tabs for Home, Review, Apply, History, and Settings.
- Added packaging stubs for PyInstaller, Inno Setup, Linux desktop entry, and GitHub Actions workflows.
