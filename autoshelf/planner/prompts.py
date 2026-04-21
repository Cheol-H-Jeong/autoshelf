from __future__ import annotations

SYSTEM_PROMPT = """
You organize files into human-memorable folders.
Keep depth at 3 or less unless there is a strong reason.
Prefer Korean folder names when the material is mostly Korean, otherwise English.
Never use vague names like misc, etc, or 기타 unless absolutely necessary.
""".strip()

FEW_SHOT_PROMPT = """
Example 1:
- file: receipts/2024-03-tax.invoice.pdf
- signal: parent folder says receipts and filename says tax invoice
- good primary_dir: ["Finance", "Invoices"]
- good also_relevant: [["Documents"]]
- why: parent folder context is meaningful, so preserve that business
  intent instead of defaulting to a generic PDF bucket

Example 2:
- file: 강의자료/week-02-transformer-notes.md
- signal: parent folder says lecture materials and the content is study notes
- good primary_dir: ["학습", "강의자료"]
- good also_relevant: [["문서"]]
- why: create a memorable subject folder when the surrounding folder already carries a clear theme

Example 3:
- file: camera_uploads/IMG_1204.JPG
- signal: parent folder is generic camera_uploads and the filename is not descriptive
- good primary_dir: ["Images"]
- good also_relevant: []
- why: do not overfit weak parent names; keep generic ingestion folders
  from polluting the final taxonomy

Review heuristics:
- if a second-level folder is just a workflow bucket like drafts or proposals,
  prefer a stable business parent such as a client, team, or project when the
  full tree shows repeated evidence for it
- rewrite summaries as concise folder rationale, because they are shown in the
  review UI and written into the manifest for auditability
""".strip()
