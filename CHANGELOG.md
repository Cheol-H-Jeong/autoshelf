# Changelog

## v1.0.16

- Persisted staged-copy progress in resumable run plans so cross-device applies can recover after an interruption instead of replaying from an ambiguous filesystem state.
- Taught `autoshelf apply --resume` to promote verified staged artifacts, prune duplicate source files left behind after target promotion, and complete interrupted cross-device moves without creating extra collisions.
- Expanded `autoshelf verify` and the operator docs to report interrupted copy drift explicitly, including duplicate sources after promotion and missing staged artifacts that need review.

## v1.0.15

- Upgraded the Linux release bundle to vendor the runtime dependencies already installed on the release builder, add an isolated bootstrap launcher, and verify the packaged install path before publishing the tarball.
- Hardened the packaging build driver around real-world distribution needs with build metadata for launcher/runtime contents, a portable `install.sh`, and regression coverage for end-to-end installer verification.
- Updated the release workflow, packaging Makefile targets, and README so tagged builds now run the verified Linux bundle path consistently and document when to use the tarball versus `pipx install '.[all]'`.

## v1.0.14

- Enriched planner briefs with each file's relative parent path and duplicate-group size so both Anthropic planning and offline planning see stronger ancestry context than a bare filename and immediate parent alone.
- Upgraded the offline FakeLLM classifier to keep meaningful customer and project parent folders, recognize invoice and receipt-heavy finance documents, and split screenshot imports into a dedicated image bucket without requiring network access.
- Documented the new ancestry-aware planner behavior in the README and user guide, and added regression coverage for the richer brief payload plus the new offline classification heuristics.

## v1.0.13

- Added live desktop theme and language updates so Settings changes immediately refresh the main window, tab labels, and localized control text without a restart.
- Added global GUI shortcuts for core operator actions: `F5` to rerun scan preview, `Ctrl+Enter` to jump into Apply, and `Ctrl+Z` to stage undo review from History.
- Hardened the demo GUI worker lifecycle so repeated scan/apply actions clean up their threads correctly, and documented the desktop workflow in the README and user guide.

## v1.0.12

- Added checksum-backed export bundle inventories plus `IMPORT_GUIDE.md`, and now bundle plan drafts and `.autoshelfrc.yaml` alongside manifests, guides, and resumable run plans for richer support handoff.
- Hardened `autoshelf import` with staged extraction, archive member validation, duplicate/path traversal rejection, and post-extract SHA-256 verification before imported bundles are committed into `.autoshelf/imports/`.
- Surfaced bundle version, file counts, and guide paths in CLI results, documented the audited export/import workflow, and added regression coverage for tampered and unsafe archives.

## v1.0.11

- Extended `.autoshelfrc.yaml` with `exclude_globs` and mapping `priority`, turning the rules file into a stronger per-root control surface for deterministic organization.
- Enforced rule-based exclusions across scan, plan, preview, and apply flows so ignored intake paths stay out of drafts and live runs even when a saved plan is reused.
- Added rule-count diagnostics in `autoshelf doctor`, documented production operator workflows in `docs/USER_GUIDE.md`, and expanded regression coverage for exclusion matching and mapping precedence.

## v1.0.10

- Added a safe `autoshelf preview <root>` command that materializes `.autoshelf/preview/` as a browsable symlink tree, letting operators inspect the proposed layout before moving live files.
- Reused the same target-resolution logic for preview and apply so collision handling stays consistent, including numbered `file (2).ext` destinations when names would clash.
- Documented the preview workflow in the README and added regression coverage for preview tree creation, duplicate-name rendering, and CLI draft reuse.

## v1.0.9

- Added interrupt-aware apply state files under `.autoshelf/runs/` so live organization runs record current progress, survive resumptions cleanly, and exit with a distinct interrupted status when SIGINT or SIGTERM lands mid-run.
- Routed cross-device file moves through a hidden staging area before the final atomic replace, preventing half-copied visible targets and allowing recovery from leftover staged artifacts after abrupt termination.
- Extended `autoshelf verify <root>` and the README workflow so operators can detect incomplete runs, unfinished plan entries, and staged recovery files before trusting an organized tree.

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
