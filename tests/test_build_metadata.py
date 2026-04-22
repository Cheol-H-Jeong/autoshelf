import importlib.util
import json
from pathlib import Path


def _build_module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "autoshelf_packaging_build", root / "packaging/build.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_dry_run_emits_metadata(tmp_path):
    root = Path(__file__).resolve().parents[1]
    metadata = _build_module().build_windows(root=root, output_dir=tmp_path, dry_run=True)
    document = json.loads((tmp_path / "build-metadata.json").read_text(encoding="utf-8"))
    assert document["dry_run"] is True
    assert document["sha256"] == "0" * 64
    assert document["artifact"].endswith("-win-x64-setup.exe")
    assert metadata.packaged_files
