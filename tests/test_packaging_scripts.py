from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tarfile
from pathlib import Path


def test_build_script_creates_linux_bundle(tmp_path):
    _write_sample_project(tmp_path)

    completed = subprocess.run(
        [sys.executable, "packaging/build.py", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    artifact = Path(completed.stdout.strip())
    assert artifact.exists()
    assert artifact.name == "autoshelf-1.0.2-linux-x86_64-bundle.tar.gz"
    sha_path = artifact.with_suffix(artifact.suffix + ".sha256")
    assert sha_path.exists()
    with tarfile.open(artifact, "r:gz") as archive:
        names = archive.getnames()
        manifest_member = archive.extractfile(
            "autoshelf-1.0.2-linux-x86_64-bundle/bundle-manifest.json"
        )
        assert manifest_member is not None
        manifest = json.loads(manifest_member.read().decode("utf-8"))
    assert "autoshelf-1.0.2-linux-x86_64-bundle/bin/autoshelf" in names
    assert "autoshelf-1.0.2-linux-x86_64-bundle/build-metadata.json" in names
    assert "autoshelf-1.0.2-linux-x86_64-bundle/bundle-manifest.json" in names
    assert "autoshelf-1.0.2-linux-x86_64-bundle/install.sh" in names
    assert (
        "autoshelf-1.0.2-linux-x86_64-bundle/runtime/site-packages/autoshelf/__init__.py"
        in names
    )
    assert any(name.endswith(".whl") for name in names)
    manifest_paths = {entry["path"] for entry in manifest["files"]}
    assert "bin/autoshelf" in manifest_paths
    assert "build-metadata.json" in manifest_paths
    assert "install.sh" in manifest_paths


def test_build_script_can_verify_installed_bundle(tmp_path):
    _write_sample_project(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "packaging/build.py",
            "--root",
            str(tmp_path),
            "--verify-install",
            "--verify-wheel",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    artifact = Path(completed.stdout.strip())
    with tarfile.open(artifact, "r:gz") as archive:
        metadata_member = archive.extractfile(
            "autoshelf-1.0.2-linux-x86_64-bundle/build-metadata.json"
        )
        assert metadata_member is not None
        metadata_text = metadata_member.read().decode("utf-8")
    assert '"install_verified": true' in metadata_text
    assert '"wheel_verified": true' in metadata_text


def test_bump_version_script_updates_version_files(tmp_path):
    _write_sample_project(tmp_path)

    completed = subprocess.run(
        [sys.executable, "packaging/bump_version.py", "patch", "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    assert completed.stdout.strip() == "1.0.3"
    assert 'version = "1.0.3"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    init_text = (tmp_path / "autoshelf" / "__init__.py").read_text(encoding="utf-8")
    changelog_text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert '__version__ = "1.0.3"' in init_text
    assert "## v1.0.3" in changelog_text


def test_copy_distribution_skips_escaping_paths(tmp_path, monkeypatch):
    build_module = _load_build_module()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "header.h").write_text("header", encoding="utf-8")
    package_dir = source_root / "greenlet"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("runtime", encoding="utf-8")

    class FakeDistribution:
        files = ["../../../include/site/python3.12/greenlet/header.h", "greenlet/__init__.py"]

        def locate_file(self, file: object) -> Path:
            relative = Path(str(file))
            return source_root / relative.name if ".." in relative.parts else source_root / relative

    monkeypatch.setattr(
        build_module.importlib_metadata,
        "distribution",
        lambda name: FakeDistribution(),
    )

    build_module._copy_distribution("greenlet", runtime_dir)

    assert not (tmp_path / "include").exists()
    assert (runtime_dir / "greenlet" / "__init__.py").read_text(encoding="utf-8") == "runtime"


def _load_build_module():
    module_path = Path(__file__).resolve().parents[1] / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("autoshelf_packaging_build", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_sample_project(root: Path) -> None:
    (root / "autoshelf").mkdir(parents=True, exist_ok=True)
    (root / "packaging" / "linux").mkdir(parents=True, exist_ok=True)
    (root / "autoshelf" / "__init__.py").write_text(
        'from __future__ import annotations\n\n__version__ = "1.0.2"\n',
        encoding="utf-8",
    )
    (root / "autoshelf" / "__main__.py").write_text(
        "from __future__ import annotations\n\n"
        "from autoshelf import __version__\n\n"
        "def main() -> None:\n"
        "    print(__version__)\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n",
        encoding="utf-8",
    )
    (root / "packaging" / "linux" / "autoshelf.desktop").write_text(
        "[Desktop Entry]\nName=autoshelf\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# autoshelf\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## v1.0.2\n\n- Initial.\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "autoshelf"
version = "1.0.2"
description = "Test project"
readme = "README.md"
requires-python = ">=3.11"

[project.scripts]
autoshelf = "autoshelf.__main__:main"

[tool.setuptools.packages.find]
include = ["autoshelf*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
