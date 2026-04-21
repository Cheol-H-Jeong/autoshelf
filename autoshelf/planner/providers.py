from __future__ import annotations

from importlib.metadata import entry_points

from autoshelf.config import AppConfig


def load_llm_provider(config: AppConfig):
    provider = config.llm.provider.lower()
    factories = {"fake": fake_provider, "anthropic": anthropic_provider}
    try:
        discovered = entry_points(group="autoshelf.llm_providers")
    except TypeError:
        discovered = entry_points().get("autoshelf.llm_providers", [])
    for entry_point in discovered:
        factories[entry_point.name] = entry_point.load()
    if provider in {"auto", "anthropic"}:
        try:
            return factories["anthropic"](config)
        except Exception:
            return factories["fake"](config)
    return factories.get(provider, factories["fake"])(config)


def fake_provider(_config: AppConfig):
    from autoshelf.planner.llm import FakeLLM

    return FakeLLM()


def anthropic_provider(config: AppConfig):
    from autoshelf.planner.llm import AnthropicPlannerLLM

    return AnthropicPlannerLLM(config)
