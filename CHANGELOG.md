# Changelog

## v1.0.25

- Added a quarantine review workflow to the desktop Review tab so low-confidence assignments are called out explicitly instead of being buried under `.autoshelf/quarantine`.
- Added operator actions to re-plan quarantined files from source-path context or clear quarantine by keeping them in their current folder, reducing manual cleanup before a paid deployment trusts the draft.
- Expanded GUI and model regression coverage around quarantine state rendering, review actions, and localized review summaries.

## v1.0.24

- Hardened `autoshelf apply --resume` to fail closed when a source file is gone but the recorded target path contains mismatched content, preventing a corrupted recovery state from being silently rehashed into a fresh manifest.
- Expanded `autoshelf verify` to detect orphaned run plans, state files that lost their matching plan, and completed runs that still leave staged recovery residue behind under `.autoshelf/`.
- Documented the stronger recovery and verification workflow and added regression coverage for ambiguous resume states plus orphaned run metadata drift.

## v1.0.23

- Added a per-file `bundle-manifest.json` audit inventory to Linux release tarballs and surfaced `bundle_file_count` in `build-metadata.json`, so customers can independently verify exactly what was shipped.
- Extended `packaging/build.py` with a wheel-runtime smoke test that installs the wheel into an isolated runtime overlay, runs `autoshelf version`, and records `wheel_verified` alongside the existing bundle install verification.
- Updated the packaging docs and release Makefile so the documented and scripted release path now uses `--verify-install --verify-wheel`, and clarified the supported `pipx` workflows for editable checkouts versus built wheels.

## v1.0.22

- Added a full-plan review stage after initial classification so autoshelf can revisit the proposed tree with the whole corpus in view, collapse weak workflow buckets, and keep stronger repeated business parents.
- Rewrote planner summaries into concise folder rationales that now flow into the review UI and manifest, giving operators an auditable explanation for why each file landed where it did.
- Expanded planner regression coverage and docs around the new review-stage refinement path, including Anthropic payload checks for the full-assignment review call.

## v1.0.21

- Fixed the demo Apply tab and tray integration so GUI apply completion now lands on a deterministic finished signal instead of racing on a 100% progress update, keeping the offscreen smoke gate stable.
- Expanded export/import bundles into a stronger support artifact by adding `VERIFY_REPORT.json`, recent run history, and run state snapshots alongside run plans.
- Hardened `autoshelf import` to validate manifest counts, verify issue counts, and history payload consistency against bundle metadata before committing the imported audit tree.

## v1.0.20

- Added a real system tray workflow for the desktop app, including quick actions to show or hide the main window, scan `~/Downloads`, and quit cleanly without losing operator context.
- Surfaced last-run scan, apply, and undo status directly in the tray tooltip and notifications so desktop users can trust what autoshelf most recently did without reopening the full window.
- Hardened the GUI regression suite around tray actions and teardown so offscreen smoke coverage still passes cleanly in the full release gate.

## v1.0.19

- Upgraded the Review tab into a clearer diff surface with action labels, per-file before/after summaries, localized counts, and stronger confidence/rationale overlays so operators can trust proposed moves faster.
- Preserved live GUI language switching for the Review tab by rebuilding loaded preview content when runtime locale changes are saved from Settings.
- Added commercial-grade operator and developer documentation with a dedicated architecture guide, contribution guide, issue templates, PR checklist, and regression coverage that keeps those assets present.

## v1.0.18

- Split config migrations into numbered upgrade modules so schema evolution is explicit, reviewable, and easier to extend without growing a single registry file.
- Added `autoshelf config show` and `autoshelf config migrate --write` so operators can inspect pending config upgrades, rewrite `config.toml` atomically, and keep a sibling backup before the new schema is committed.
- Documented the config migration workflow and added regression coverage for migration inspection, CLI execution, atomic rewrite, and backup creation.

## v1.0.17

- Extracted staged move and recovery logic behind a filesystem backend so apply behavior can be exercised against a fake filesystem without touching the host tree.
- Wired run-plan hashing and manifest content hashing through the same backend, keeping resumable apply metadata accurate even when tests or future integrations do not use the local filesystem directly.
- Added regression coverage for fake-filesystem apply runs, cross-device staging, staged-copy recovery, and duplicate-source cleanup after interrupted promotion.

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
