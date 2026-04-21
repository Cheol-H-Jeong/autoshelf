from __future__ import annotations

import re

from autoshelf.planner.chunking import FileBrief
from autoshelf.planner.naming import normalize_folder_name

GENERIC_PARENT_NAMES = {
    "archive",
    "archives",
    "camera",
    "camera_uploads",
    "desktop",
    "docs",
    "documents",
    "downloads",
    "files",
    "images",
    "img",
    "inbox",
    "media",
    "misc",
    "photos",
    "pictures",
    "scans",
    "sorted",
    "temp",
    "tmp",
    "uploads",
    "기타",
    "다운로드",
    "문서",
    "바탕화면",
    "사진",
    "업로드",
    "이미지",
    "임시",
    "정리",
    "파일",
}

CONTEXT_TOP_LEVELS = {
    "finance": {"en": "Finance", "ko": "재무"},
    "learning": {"en": "Learning", "ko": "학습"},
}

DOCUMENT_CONTEXT_EXTENSIONS = {"doc", "docx", "hwp", "md", "pdf", "ppt", "pptx", "txt"}

CONTEXT_SUBFOLDERS = {
    "invoice": {"en": "Invoices", "ko": "청구서"},
    "receipt": {"en": "Receipts", "ko": "영수증"},
    "tax": {"en": "Taxes", "ko": "세금"},
    "budget": {"en": "Budgets", "ko": "예산"},
    "course_notes": {"en": "Course Notes", "ko": "강의자료"},
    "screenshots": {"en": "Screenshots", "ko": "스크린샷"},
}

CONTEXT_KEYWORDS = {
    "finance": {
        "invoice",
        "invoices",
        "receipt",
        "receipts",
        "expense",
        "expenses",
        "billing",
        "payment",
        "payments",
        "reimbursement",
        "tax",
        "taxes",
        "vat",
        "세금",
        "영수증",
        "청구",
        "청구서",
        "결제",
    },
    "learning": {
        "class",
        "course",
        "curriculum",
        "lecture",
        "lectures",
        "lesson",
        "lessons",
        "notes",
        "study",
        "syllabus",
        "강의",
        "강의자료",
        "노트",
        "복습",
        "수업",
        "스터디",
        "학습",
    },
    "invoice": {"invoice", "invoices", "billing", "bill", "청구", "청구서"},
    "receipt": {"receipt", "receipts", "expense", "expenses", "reimbursement", "영수증", "지출"},
    "tax": {"tax", "taxes", "vat", "w2", "1099", "세금", "부가세", "연말정산"},
    "budget": {"budget", "budgets", "forecast", "forecasts", "예산", "추정"},
    "course_notes": {
        "class",
        "course",
        "curriculum",
        "lecture",
        "lectures",
        "lesson",
        "lessons",
        "notes",
        "study",
        "syllabus",
        "강의",
        "강의자료",
        "노트",
        "복습",
        "수업",
        "스터디",
        "학습",
    },
    "screenshots": {"screen", "screenshot", "screenshots", "capture", "캡처", "스크린샷"},
}


def contextual_primary_dir(
    brief: FileBrief,
    *,
    default_top_level: str,
    corpus_english: bool,
) -> list[str]:
    context_key = _context_key(brief)
    top_level = (
        _label(CONTEXT_TOP_LEVELS[context_key], corpus_english)
        if context_key
        else default_top_level
    )
    parts = [top_level]
    specific = _specific_context_folder(brief, corpus_english)
    if specific is not None:
        parts.append(specific)
        return parts
    meaningful_parent = meaningful_parent_folder(brief, fallback=top_level)
    if meaningful_parent is not None and meaningful_parent.casefold() != top_level.casefold():
        parts.append(meaningful_parent)
    return parts


def meaningful_parent_folder(brief: FileBrief, *, fallback: str) -> str | None:
    for segment in reversed(_parent_segments(brief)):
        normalized = normalize_folder_name(segment, fallback)
        if normalized == fallback:
            continue
        if _is_generic_parent(segment):
            continue
        return normalized
    return None


def _context_key(brief: FileBrief) -> str | None:
    if brief.extension.lower() not in DOCUMENT_CONTEXT_EXTENSIONS:
        return None
    signal = _signal_text(brief)
    for key in ("finance", "learning"):
        if _contains_keyword(signal, key):
            return key
    return None


def _specific_context_folder(brief: FileBrief, corpus_english: bool) -> str | None:
    signal = _signal_text(brief)
    extension = brief.extension.lower()
    if extension in {"png", "jpg", "jpeg"} and _contains_keyword(signal, "screenshots"):
        return _label(CONTEXT_SUBFOLDERS["screenshots"], corpus_english)
    for key in ("invoice", "receipt", "tax", "budget", "course_notes"):
        if _contains_keyword(signal, key):
            return _label(CONTEXT_SUBFOLDERS[key], corpus_english)
    return None


def _label(labels: dict[str, str], corpus_english: bool) -> str:
    return labels["en"] if corpus_english else labels["ko"]


def _signal_text(brief: FileBrief) -> str:
    return " ".join(
        part.strip().lower()
        for part in (
            brief.path,
            brief.parent_name,
            brief.parent_path,
            brief.filename,
            brief.title,
            brief.head_text,
        )
        if part.strip()
    )


def _contains_keyword(signal: str, key: str) -> bool:
    return any(keyword in signal for keyword in CONTEXT_KEYWORDS[key])


def _parent_segments(brief: FileBrief) -> list[str]:
    if brief.parent_path:
        segments = [
            segment for segment in brief.parent_path.split("/") if segment and segment != "."
        ]
        if segments:
            return segments
    if brief.parent_name:
        return [brief.parent_name]
    return []


def _is_generic_parent(name: str) -> bool:
    lowered = name.strip().casefold()
    if lowered in GENERIC_PARENT_NAMES:
        return True
    return re.fullmatch(r"\d{4}([-/]\d{1,2})?", lowered) is not None
