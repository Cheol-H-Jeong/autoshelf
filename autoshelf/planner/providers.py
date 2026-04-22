from __future__ import annotations

from autoshelf.config import AppConfig
from autoshelf.planner.llm import (
    EmbeddedPlannerLLM,
    FakeLLM,
    LocalHTTPPlannerLLM,
    select_auto_provider,
)
from autoshelf.rules import PlanningRules


def load_llm_provider(config: AppConfig, rules: PlanningRules | None = None):
    provider = config.llm.provider.lower()
    if provider == "auto":
        selected, base_url = select_auto_provider(config)
        if selected == "local_http" and base_url:
            return LocalHTTPPlannerLLM(config, base_url, rules)
        try:
            return EmbeddedPlannerLLM(config, rules)
        except Exception:
            return FakeLLM()
    if provider == "embedded":
        return EmbeddedPlannerLLM(config, rules)
    if provider == "local_http":
        if config.llm.local_http_url:
            return LocalHTTPPlannerLLM(config, config.llm.local_http_url, rules)
        return FakeLLM()
    return FakeLLM()


def fake_provider(_config: AppConfig, _rules: PlanningRules | None = None):
    return FakeLLM()
