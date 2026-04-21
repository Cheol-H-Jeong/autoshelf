from __future__ import annotations

import json
import locale
from functools import lru_cache

from autoshelf.config import AppConfig


@lru_cache(maxsize=2)
def _catalog(language: str) -> dict[str, str]:
    path = __import__("pathlib").Path(__file__).with_name("i18n") / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def current_language(config: AppConfig | None = None) -> str:
    cfg = config or AppConfig()
    if cfg.language_preference in {"ko", "en"}:
        return cfg.language_preference
    default_locale, _ = locale.getlocale()
    if default_locale and default_locale.lower().startswith("ko"):
        return "ko"
    return "en"


def t(key: str, config: AppConfig | None = None, **kwargs) -> str:
    language = current_language(config)
    value = _catalog(language).get(key) or _catalog("en").get(key) or key
    return value.format(**kwargs)
