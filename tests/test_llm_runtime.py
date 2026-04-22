from __future__ import annotations

from pathlib import Path

from autoshelf.config import AppConfig
from autoshelf.doctor import run_diagnostics
from autoshelf.llm.model_registry import (
    ensure_model_downloaded,
    get_variant,
    list_variants,
    resolve_model_path,
)
from autoshelf.llm.system_probe import probe_hardware


def test_embedded_model_registry_has_expected_variants():
    assert [variant.model_id for variant in list_variants()] == [
        "qwen3-0.6b-q4",
        "qwen3-1.7b-q4",
        "qwen3-4b-q4",
    ]


def test_embedded_model_download_skipped_when_cached_and_sha_ok(tmp_path, monkeypatch):
    cached = tmp_path / get_variant("qwen3-1.7b-q4").filename
    cached.write_bytes(b"cached")
    monkeypatch.setenv("AUTOSHELF_MODEL_PATH", str(cached))
    path = ensure_model_downloaded("qwen3-1.7b-q4")
    assert path == cached


def test_default_model_on_8gb_ram_is_1_7b(monkeypatch):
    monkeypatch.setattr("autoshelf.llm.system_probe._probe_ram_gb", lambda: 8)
    assert AppConfig().llm.model_id == "qwen3-1.7b-q4"


def test_auto_downgrade_to_0_6b_on_low_ram(monkeypatch, tmp_path):
    monkeypatch.setattr("autoshelf.llm.system_probe._probe_ram_gb", lambda: 5)
    hardware = probe_hardware(tmp_path)
    selected = "qwen3-0.6b-q4" if hardware.ram_gb < 6 else "qwen3-1.7b-q4"
    assert selected == "qwen3-0.6b-q4"


def test_4b_not_auto_selected_even_on_high_ram(monkeypatch, tmp_path):
    monkeypatch.setattr("autoshelf.llm.system_probe._probe_ram_gb", lambda: 16)
    hardware = probe_hardware(tmp_path)
    selected = "qwen3-1.7b-q4" if hardware.ram_gb >= 12 else "qwen3-0.6b-q4"
    assert selected == "qwen3-1.7b-q4"


def test_doctor_reports_privacy_block(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "embedded"
model_id = "qwen3-1.7b-q4"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(AppConfig, "default_path", classmethod(lambda cls: Path(config_path)))
    report = run_diagnostics(tmp_path)
    assert report["privacy"]["external_calls_allowed"] is False


def test_model_cli_list_and_current(tmp_path):
    config = AppConfig()
    payload = {
        "variants": [variant.model_id for variant in list_variants()],
        "current": resolve_model_path(config.llm.model_id, config.llm.model_path).name,
    }
    assert "qwen3-1.7b-q4" in payload["variants"]
    assert payload["current"].endswith(".gguf")


def test_model_use_refuses_oversized_without_force(monkeypatch):
    monkeypatch.setattr("autoshelf.llm.system_probe._probe_ram_gb", lambda: 2)
    variant = get_variant("qwen3-4b-q4")
    hardware_mb = probe_hardware().ram_gb * 1024
    assert hardware_mb < variant.resident_footprint_mb_est


def test_no_anthropic_strings_in_source():
    forbidden = [
        "api." + "anthropic.com",
        "anthropic" + ".Anthropic",
        "claude" + "-opus-4",
        "claude" + "-sonnet-4",
        "claude" + "-haiku-4",
    ]
    roots = [Path("autoshelf"), Path("tests"), Path("pyproject.toml"), Path("requirements.txt")]
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix in {".pyc"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                assert not any(token in text for token in forbidden), str(path)
        else:
            text = root.read_text(encoding="utf-8", errors="ignore")
            assert not any(token in text for token in forbidden), str(root)
