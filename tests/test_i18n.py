from __future__ import annotations

import json
from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.i18n import t


def test_i18n_catalogs_have_expected_keys():
    base = Path(__file__).resolve().parents[1] / "autoshelf" / "i18n"
    en = json.loads((base / "en.json").read_text(encoding="utf-8"))
    ko = json.loads((base / "ko.json").read_text(encoding="utf-8"))
    assert set(en) == set(ko)


def test_i18n_missing_key_falls_back_to_key():
    assert t("missing.key", AppConfig(language_preference="en")) == "missing.key"


def test_i18n_returns_korean_string():
    assert t("home.title", AppConfig(language_preference="ko")) == "홈"
