## Autoshelf User Guide

`autoshelf` is designed to organize a working folder without taking control away from the operator. The safest production workflow is:

1. Run `autoshelf doctor /path/to/root` before the first live run.
2. Create or update `.autoshelfrc.yaml` if you need hard policy controls.
3. Run `autoshelf plan /path/to/root`.
4. Inspect the draft with `autoshelf preview /path/to/root`.
5. Apply with `autoshelf apply /path/to/root`.
6. Verify the result with `autoshelf verify /path/to/root`.

## Install

Full local install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
```

Rules-only install for headless servers:

```bash
pip install -e .[rules]
```

## Examples

Generate the bundled demo fixture when you want to evaluate autoshelf without exposing real customer files:

```bash
python examples/fixtures/generate_demo.py /tmp/autoshelf-demo
python -m autoshelf doctor /tmp/autoshelf-demo
python -m autoshelf plan /tmp/autoshelf-demo
python -m autoshelf preview /tmp/autoshelf-demo
python -m autoshelf verify /tmp/autoshelf-demo
```

The generator creates mixed business documents, screenshots, duplicate-content files, and a sample `.autoshelfrc.yaml`. It also writes `fixture-manifest.json` so QA or support can confirm the expected corpus shape before comparing planner output between builds.

## Recommended Operator Flow

Health check:

```bash
python -m autoshelf doctor /srv/incoming
```

Plan and browse the proposed tree:

```bash
python -m autoshelf plan /srv/incoming
python -m autoshelf preview /srv/incoming
```

Planner context signals:

- Autoshelf reads the file name, parsed head text, immediate parent folder, full relative parent path, and a derived meaningful parent hint before it proposes folders.
- If two files have the same content hash, the planner brief marks them as part of the same duplicate group so the reviewer can keep related files together.
- Anthropic runs reuse one cacheable shared prompt bundle that contains the few-shot examples, live rules, and `FOLDER_GUIDE.md`, which keeps chunked planning cheaper and more consistent across a full run.
- In offline mode, those same signals are used locally to recognize stronger business buckets such as invoices, receipts, study materials, screenshots, and customer-specific parent folders.

Apply and audit:

```bash
python -m autoshelf apply /srv/incoming --policy append-counter
python -m autoshelf verify /srv/incoming
```

If multiple files have the same content hash, autoshelf now moves one canonical copy and turns the later duplicates into links at their planned destinations. That keeps the visible taxonomy intact without paying storage twice, and `undo` restores the original duplicate sources if the operator rolls the run back.

Desktop shortcuts in the GUI:

- `F5` reruns the scan preview from Home.
- `Ctrl+Enter` jumps to Apply and starts the current apply flow.
- `Ctrl+Z` jumps to History and stages an undo review request.
- Saving Settings applies theme and language changes to the live window immediately.

Quarantine review in the GUI:

- Files below the safe confidence threshold show up as `Quarantine` in Review instead of blending into the normal move list.
- `Re-plan Quarantine` derives a safer folder suggestion from the source path and file type for the selected quarantined file, or for every quarantined file if nothing is selected.
- `Clear Quarantine` keeps the selected quarantined file in its current folder and removes the quarantine target, which is useful when the operator wants to approve the rest of the plan without forcing a weak move.

Tray workflow:

- Closing the main window minimizes autoshelf to the system tray instead of terminating an active desktop session.
- The tray menu always shows the last scan/apply/undo status so operators can tell whether the last run finished cleanly.
- `Scan Downloads` sets Home to `~/Downloads` and starts a fresh scan without reopening the full CLI workflow.
- `Show window` restores the main review window; `Quit autoshelf` exits fully.

If an apply is interrupted, rerun the recorded operation instead of starting over:

```bash
python -m autoshelf apply /srv/incoming --resume <run-id>
```

`autoshelf verify` will call out three common interrupted-copy states explicitly:

- `staged_artifact`: a staged `.part` file still exists under `.autoshelf/staging/`.
- `duplicate_source`: the target file was already promoted but the source copy still exists and should be pruned by `--resume`.
- `missing_staged_artifact`: the run plan expected a staged copy that is no longer present, which warrants operator review before retrying.

It also flags run metadata drift that matters during support and recovery:

- `orphan_run_plan`: a resumable plan exists without a matching state file.
- `missing_run_plan`: a state file exists but its matching plan is gone.
- `stale_staging_artifact`: a run marked completed still left recovery files behind.

If `--resume` encounters a missing source file plus a mismatched target, autoshelf now aborts the run instead of writing a fresh manifest over that unexpected target state.

## Rules File

Put `.autoshelfrc.yaml` at the root you want to organize. The rules file is read for `scan`, `plan`, `preview`, `apply`, and `doctor`.

Supported controls:

- `pinned_dirs`: folders that must exist in the proposed tree even if the planner would not invent them.
- `exclude_globs`: file or path globs that autoshelf should ignore entirely.
- `mappings`: forced file placement rules.
- `source_globs`: optional source-folder filters for a mapping rule.
- `priority`: precedence between overlapping mapping rules. Higher numbers win.
- `target: "@current"`: keep matching files in their current source folder while still enforcing a rule.
- `also_relevant`: extra shortcut locations to create during apply.

Example:

```yaml
version: 1

pinned_dirs:
  - Finance/Taxes
  - Clients/Archive

exclude_globs:
  - ".DS_Store"
  - "Inbox/**"
  - "*.tmp"

mappings:
  - glob: "clients/acme/*.pdf"
    priority: 20
    source_globs:
      - Inbox/**
    target: Clients/Acme/Contracts
    also_relevant:
      - Finance

  - glob: "*.invoice.pdf"
    priority: 10
    target: Finance/Invoices
```

### Rule Recipes

Ignore an intake folder until it is reviewed:

```yaml
exclude_globs:
  - Inbox/**
```

Force screenshots into a fixed destination:

```yaml
mappings:
  - glob: "Screenshots/*.png"
    target: Images/Screenshots
```

Keep working notes in place, but still apply deterministic policy:

```yaml
mappings:
  - glob: "*.txt"
    source_globs:
      - Clients/**/Working
    target: "@current"
```

Prefer a customer-specific rule over a generic PDF rule:

```yaml
mappings:
  - glob: "*.pdf"
    priority: 1
    target: Documents/PDFs

  - glob: "acme/*.pdf"
    priority: 10
    target: Clients/Acme
```

Reserve empty destination folders ahead of time:

```yaml
pinned_dirs:
  - Legal/Contracts
  - Finance/Quarterly Reports
```

Inspect the parsed rules or explain a specific path before moving anything:

```bash
python -m autoshelf rules show /path/to/root
python -m autoshelf rules match /path/to/root Inbox/Notes/draft.txt Archive/draft.txt
```

## Preview and Verification

`autoshelf preview` creates `.autoshelf/preview/` using symlinks only. It is safe to inspect, index, or open from a file browser because it does not move the live files. The preview mirrors live duplicate collapsing too, so identical-content files point at one canonical preview target instead of pretending they will be copied twice.

`autoshelf verify` checks the manifest, expected targets, expected shortcuts, incomplete run state, orphaned run artifacts, and interrupted copy recovery drift. Run it after each production apply and before trusting a tree that may have been modified by other tools.

## Export and Import

Use export/import when you need a support bundle, an audit package, or a reproducible handoff to another machine:

```bash
python -m autoshelf export /srv/incoming --output /srv/bundles
python -m autoshelf import /srv/bundles/incoming.tar.gz /srv/audit
```

Exports include `manifest.jsonl`, `FOLDER_GUIDE.md`, `FILE_INDEX.md`, any saved `plan_draft.json`, `.autoshelfrc.yaml`, and resumable run plans. The bundle also includes:

- `bundle/metadata.json`: inventory, file sizes, and SHA-256 checksums for every exported payload file.
- `bundle/VERIFY_REPORT.json`: the export-time verification snapshot, including incomplete runs or unexpected files already present in the source tree.
- `bundle/history.json`: recent run history captured from the local autoshelf database for support and audit review.
- `bundle/runs/*.state.json`: run state snapshots alongside the resumable plan files.
- `bundle/IMPORT_GUIDE.md`: operator instructions for audit and replay workflows.

Imports are staged under `.autoshelf/imports/` and only moved into place after autoshelf validates the archive structure, checksum inventory, verify report, history payload, and manifest counts. If the archive contains path traversal entries, duplicate members, unsupported tar types, tampered payloads, or metadata drift, the import is rejected.

## Automation

For wrappers or schedulers, add `--progress json` before the subcommand:

```bash
python -m autoshelf --progress json plan /srv/incoming
python -m autoshelf --progress json apply /srv/incoming
```

The stdout contract is stable JSONL:

- A leading `command` record with `status: "started"` and command metadata such as `argv`, `cwd`, and resolved roots.
- Zero or more `progress` records while work is underway.
- A trailing `command` record with `status: "completed"` or `status: "failed"` plus the process exit code.
- A final `result` record when the command returns structured payload data such as a plan, verify report, or bundle summary.
- A terminal `error` record only for unexpected exceptions, so wrappers can distinguish product-reported failures from crashes.

That layout keeps stdout pipe-friendly for schedulers and support tooling while stderr remains available for human-readable logs.

## Man Page

Regenerate the Linux man page from the live CLI surface before packaging or release:

```bash
python packaging/generate_manpage.py
```

This writes `packaging/linux/autoshelf.1`, which is also copied into Linux bundle artifacts under `docs/autoshelf.1`.

## Config Upgrades

Autoshelf keeps a `schema_version` in `config.toml`. Older config files still load, but operators can inspect and apply migrations explicitly:

```bash
python -m autoshelf config show
python -m autoshelf config migrate --write
```

Use `config show` during upgrades or support calls to confirm which numbered migrations are pending. Use `config migrate --write` to rewrite the config atomically and keep a sibling backup like `config.toml.bak.v0-to-v2` for rollback or forensic review.

## Screenshots

Reserved placeholders for product documentation:

- `docs/screenshots/home.png`
- `docs/screenshots/review.png`
- `docs/screenshots/apply.png`
- `docs/screenshots/history.png`
- `docs/screenshots/settings.png`
