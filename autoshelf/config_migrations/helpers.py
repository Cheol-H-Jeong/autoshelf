from __future__ import annotations


def normalize_string_list(value: object, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    seen: set[str] = set()
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        items.append(text)
        seen.add(text)
    return items or list(default)


def normalize_choice(value: object, allowed: set[str], fallback: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in allowed:
            return normalized
    return fallback


def normalize_positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value > 0 else fallback
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    return fallback


def normalize_non_negative_int(value: object, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value if value >= 0 else fallback
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed >= 0 else fallback
    return fallback


def normalize_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return fallback
