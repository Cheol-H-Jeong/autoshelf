# Changelog

## v1.0.8

- Added schema-backed Anthropic reliability controls in `config.toml`, including retry delay bounds, jitter, and circuit-breaker thresholds, with config migration coverage for existing installs.
- Added jittered retry backoff plus a cooldown circuit breaker around Anthropic planner requests so repeated API outages degrade quickly to the offline planner instead of hammering the remote path.
- Documented the new planner reliability controls in the README and added regression coverage for retry timing, breaker-open fallback, and cooldown recovery.

## v1.0.7

- Added a numbered config migration framework so legacy unversioned `config.toml` files are normalized and upgraded on load instead of failing strict validation.
- Added `--progress json` to stream JSONL progress events and a final JSON result line on stdout for CLI automation around planning, apply, export, import, verify, and diagnostics.
- Documented the new machine-readable progress mode and schema-versioned config behavior in the README, with regression coverage for both features.

## v1.0.6

- Improved planner briefs by including each file's immediate parent folder name in the classification payload and summary text, preserving signals from staging folders like receipts, clients, or lecture materials.
- Added stable few-shot planner examples to the Anthropic system prompt in a cacheable block so repeated planning runs reuse shared instruction tokens more effectively.
- Added regression coverage for the richer brief payload and updated the README to document how autoshelf now uses parent-folder context during online classification.

## v1.0.5

- Added `autoshelf export <root>` to package the current manifest, human guide, file index, resumable run plans, and recent run history into a portable support bundle.
- Added `autoshelf import <archive> <root>` to unpack those bundles under `.autoshelf/imports/` for offline audit and cross-machine troubleshooting without mutating a live organized tree.
- Added regression coverage for bundle export/import and documented the operator workflow in the README.

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
