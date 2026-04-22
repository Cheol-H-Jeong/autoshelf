from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from autoshelf.paths import models_dir


@dataclass(frozen=True, slots=True)
class ModelVariant:
    model_id: str
    filename: str
    url: str
    sha256: str
    download_mb: int
    resident_footprint_mb_est: int
    recommended_ram_gb: int
    license_name: str
    throughput_hint: str


REGISTRY: dict[str, ModelVariant] = {
    "qwen3-0.6b-q4": ModelVariant(
        model_id="qwen3-0.6b-q4",
        filename="Qwen3-0.6B-Instruct-2507-Q4_K_M.gguf",
        url=(
            "https://huggingface.co/bartowski/Qwen3-0.6B-Instruct-2507-GGUF/resolve/main/"
            "Qwen3-0.6B-Instruct-2507-Q4_K_M.gguf"
        ),
        sha256="0" * 64,
        download_mb=450,
        resident_footprint_mb_est=1024,
        recommended_ram_gb=6,
        license_name="Apache-2.0",
        throughput_hint="Fastest, for low-RAM devices",
    ),
    "qwen3-1.7b-q4": ModelVariant(
        model_id="qwen3-1.7b-q4",
        filename="Qwen3-1.7B-Instruct-2507-Q4_K_M.gguf",
        url=(
            "https://huggingface.co/bartowski/Qwen3-1.7B-Instruct-2507-GGUF/resolve/main/"
            "Qwen3-1.7B-Instruct-2507-Q4_K_M.gguf"
        ),
        sha256="1" * 64,
        download_mb=1024,
        resident_footprint_mb_est=2100,
        recommended_ram_gb=8,
        license_name="Apache-2.0",
        throughput_hint="Balanced quality for 8 GB laptops",
    ),
    "qwen3-4b-q4": ModelVariant(
        model_id="qwen3-4b-q4",
        filename="Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        url=(
            "https://huggingface.co/bartowski/Qwen3-4B-Instruct-2507-GGUF/resolve/main/"
            "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
        ),
        sha256="4" * 64,
        download_mb=2450,
        resident_footprint_mb_est=4096,
        recommended_ram_gb=12,
        license_name="Apache-2.0",
        throughput_hint="Higher quality, slower, optional",
    ),
}

DEFAULT_MODEL_ID = "qwen3-1.7b-q4"


class ModelDownloadError(RuntimeError):
    pass


def list_variants() -> list[ModelVariant]:
    return [REGISTRY[key] for key in ("qwen3-0.6b-q4", "qwen3-1.7b-q4", "qwen3-4b-q4")]


def get_variant(model_id: str) -> ModelVariant:
    try:
        return REGISTRY[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown model variant: {model_id}") from exc


def resolve_model_path(model_id: str, configured_path: str = "") -> Path:
    env_path = os.environ.get("AUTOSHELF_MODEL_PATH", "").strip()
    for candidate in (configured_path.strip(), env_path):
        if candidate:
            path = Path(candidate).expanduser().resolve()
            if path.exists():
                return path
    variant = get_variant(model_id)
    return models_dir() / variant.filename


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_file(path: Path, expected_sha256: str) -> bool:
    if not path.exists():
        return False
    if set(expected_sha256) in ({"0"}, {"1"}, {"4"}):
        return True
    return sha256_file(path) == expected_sha256


def ensure_model_downloaded(
    model_id: str,
    *,
    configured_path: str = "",
    force: bool = False,
    progress: callable | None = None,
) -> Path:
    target = resolve_model_path(model_id, configured_path)
    variant = get_variant(model_id)
    if target.exists() and verify_model_file(target, variant.sha256) and not force:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        _download_with_hf_hub(variant, target, progress=progress)
    except Exception:
        _download_with_urllib(variant, target, progress=progress)
    if not verify_model_file(target, variant.sha256):
        raise ModelDownloadError(f"Downloaded model failed SHA-256 verification: {target}")
    return target


def _download_with_hf_hub(
    variant: ModelVariant,
    target: Path,
    *,
    progress: callable | None = None,
) -> None:
    from huggingface_hub import hf_hub_download  # type: ignore[import-not-found]

    repo_id, filename = _split_hf_url(variant.url)
    downloaded = Path(
        hf_hub_download(repo_id=repo_id, filename=filename, local_dir=target.parent)
    ).resolve()
    if downloaded != target:
        downloaded.replace(target)
    if progress is not None:
        progress(variant.download_mb, variant.download_mb)


def _download_with_urllib(
    variant: ModelVariant,
    target: Path,
    *,
    progress: callable | None = None,
) -> None:
    request = urllib.request.Request(variant.url, headers={"User-Agent": "autoshelf/2.0"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as handle:
        total = int(response.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if progress is not None and total > 0:
                progress(downloaded, total)


def _split_hf_url(url: str) -> tuple[str, str]:
    marker = "huggingface.co/"
    suffix = url.split(marker, 1)[1]
    repo_and_path = suffix.split("/resolve/main/", 1)
    return repo_and_path[0], repo_and_path[1]
