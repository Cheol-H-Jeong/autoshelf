# Changelog

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
