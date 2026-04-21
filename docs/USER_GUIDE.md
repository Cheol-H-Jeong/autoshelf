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

Apply and audit:

```bash
python -m autoshelf apply /srv/incoming --policy append-counter
python -m autoshelf verify /srv/incoming
```

If an apply is interrupted, rerun the recorded operation instead of starting over:

```bash
python -m autoshelf apply /srv/incoming --resume <run-id>
```

## Rules File

Put `.autoshelfrc.yaml` at the root you want to organize. The rules file is read for `scan`, `plan`, `preview`, `apply`, and `doctor`.

Supported controls:

- `pinned_dirs`: folders that must exist in the proposed tree even if the planner would not invent them.
- `exclude_globs`: file or path globs that autoshelf should ignore entirely.
- `mappings`: forced file placement rules.
- `priority`: precedence between overlapping mapping rules. Higher numbers win.
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

## Preview and Verification

`autoshelf preview` creates `.autoshelf/preview/` using symlinks only. It is safe to inspect, index, or open from a file browser because it does not move the live files.

`autoshelf verify` checks the manifest, expected targets, expected shortcuts, and incomplete run state. Run it after each production apply and before trusting a tree that may have been modified by other tools.

## Automation

For wrappers or schedulers, add `--progress json` before the subcommand:

```bash
python -m autoshelf --progress json plan /srv/incoming
python -m autoshelf --progress json apply /srv/incoming
```

Each run emits JSONL progress records and ends with a single `result` object on stdout.

## Screenshots

Reserved placeholders for product documentation:

- `docs/screenshots/home.png`
- `docs/screenshots/review.png`
- `docs/screenshots/apply.png`
- `docs/screenshots/history.png`
- `docs/screenshots/settings.png`
