from __future__ import annotations

import re

FORBIDDEN_NAMES = {"misc", "etc", "other", "others", "기타"}
AMBIGUOUS_PAIRS = {("계약서", "계약문서")}


def validate_folder_name(name: str) -> None:
    """Raise ValueError when the name violates folder naming rules."""

    cleaned = " ".join(name.strip().split())
    if not cleaned:
        raise ValueError("folder name cannot be empty")
    lowered = cleaned.lower()
    if lowered in FORBIDDEN_NAMES:
        raise ValueError(f"folder name '{name}' is too vague")
    if re.fullmatch(r"\d{4}([-/]\d{1,2})?", cleaned):
        raise ValueError(f"folder name '{name}' cannot be date-only")
    words = cleaned.split()
    if _contains_hangul(cleaned):
        if len(cleaned) > 20:
            raise ValueError("korean folder names must be 20 characters or fewer")
    elif len(words) > 4:
        raise ValueError("english folder names must be 4 words or fewer")
    if len(cleaned) == 1:
        raise ValueError("single-letter folder names are not allowed")
    if _mixed_language(cleaned):
        raise ValueError("folder names cannot mix Korean and English")


def normalize_folder_name(name: str, fallback: str) -> str:
    cleaned = " ".join(name.strip().split())
    candidate = cleaned or fallback
    try:
        validate_folder_name(candidate)
        return candidate
    except ValueError:
        return fallback


def validate_sibling_names(names: list[str]) -> None:
    lowered = [name.casefold() for name in names]
    if len(set(lowered)) != len(lowered):
        raise ValueError("duplicate sibling folder names are not allowed")
    for left, right in AMBIGUOUS_PAIRS:
        if left in names and right in names:
            raise ValueError(f"ambiguous sibling pair detected: {left}, {right}")


def _contains_hangul(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in text)


def _mixed_language(text: str) -> bool:
    has_hangul = _contains_hangul(text)
    has_ascii_letters = any(char.isascii() and char.isalpha() for char in text)
    return has_hangul and has_ascii_letters
