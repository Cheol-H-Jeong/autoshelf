from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import tomllib
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class BuildResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact: Path
    sha256_path: Path
    wheel_path: Path
    metadata_path: Path


def build(root: Path | None = None) -> BuildResult:
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    metadata = _load_project_metadata(project_root)
    artifact_basename = (
        f"{metadata.name}-{metadata.version}-linux-{_normalize_machine()}-bundle"
    )
    dist_dir = project_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = dist_dir / f"{artifact_basename}.tar.gz"
    logger.info("Building Linux bundle at {}", artifact_path)

    with tempfile.TemporaryDirectory(prefix="autoshelf-build-") as temp_dir:
        temp_root = Path(temp_dir)
        wheel_dir = temp_root / "wheelhouse"
        wheel_dir.mkdir(parents=True, exist_ok=True)
        wheel_path = _build_wheel(project_root, wheel_dir)
        bundle_root = temp_root / artifact_basename
        metadata_path = _stage_bundle(project_root, bundle_root, metadata, wheel_path)
        _write_tarball(bundle_root, artifact_path)
        sha256_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
        sha256_path.write_text(_sha256(artifact_path), encoding="utf-8")
        return BuildResult(
            artifact=artifact_path,
            sha256_path=sha256_path,
            wheel_path=wheel_path,
            metadata_path=metadata_path,
        )


def _build_wheel(project_root: Path, wheel_dir: Path) -> Path:
    command = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        ".",
        "--no-deps",
        "--wheel-dir",
        str(wheel_dir),
    ]
    logger.info("Running {}", " ".join(command))
    completed = subprocess.run(
        command,
        check=True,
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        logger.debug(completed.stdout.strip())
    if completed.stderr.strip():
        logger.debug(completed.stderr.strip())
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("pip wheel did not produce a wheel artifact")
    return wheels[0]


def _stage_bundle(
    project_root: Path,
    bundle_root: Path,
    metadata: ProjectMetadata,
    wheel_path: Path,
) -> Path:
    wheelhouse_dir = bundle_root / "wheelhouse"
    docs_dir = bundle_root / "docs"
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    bundled_wheel = wheelhouse_dir / wheel_path.name
    shutil.copy2(wheel_path, bundled_wheel)
    _write_install_script(bundle_root, bundled_wheel.name)
    _write_bundle_readme(bundle_root, metadata, bundled_wheel.name)
    _copy_if_present(project_root / "README.md", docs_dir / "README.md")
    _copy_if_present(project_root / "LICENSE", docs_dir / "LICENSE")
    _copy_if_present(
        project_root / "packaging" / "linux" / "autoshelf.desktop",
        bundle_root / "autoshelf.desktop",
    )
    metadata_path = bundle_root / "build-metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "name": metadata.name,
                "version": metadata.version,
                "platform": "linux",
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "wheel": bundled_wheel.name,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return metadata_path


def _write_bundle_readme(bundle_root: Path, metadata: ProjectMetadata, wheel_name: str) -> None:
    readme_path = bundle_root / "README.txt"
    readme_path.write_text(
        textwrap.dedent(
            f"""\
            {metadata.name} {metadata.version} Linux bundle

            Contents
            - wheelhouse/{wheel_name}: installable Python wheel for the current release
            - install.sh: convenience installer that creates ~/.local/share/autoshelf/venv
            - autoshelf.desktop: desktop entry template for Linux shells that support it
            - docs/: copied project README and LICENSE when present

            Install
            1. Extract this tarball.
            2. Run ./install.sh
            3. Launch ~/.local/bin/autoshelf or call the venv binary directly.

            Notes
            - The installer uses the bundled wheel, but pip may still download Python dependencies
              unless they are already available in the target environment.
            - For development workflows, pipx install . or pip install -e .[all] remains supported.
            """
        ),
        encoding="utf-8",
    )


def _write_install_script(bundle_root: Path, wheel_name: str) -> None:
    install_script = bundle_root / "install.sh"
    install_script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            INSTALL_ROOT="${{1:-$HOME/.local/share/autoshelf}}"
            BIN_DIR="${{2:-$HOME/.local/bin}}"
            VENV_DIR="$INSTALL_ROOT/venv"
            mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
            python3 -m venv "$VENV_DIR"
            "$VENV_DIR/bin/pip" install "$SCRIPT_DIR/wheelhouse/{wheel_name}"
            cat > "$BIN_DIR/autoshelf" <<EOF
            #!/usr/bin/env bash
            set -euo pipefail
            exec "$VENV_DIR/bin/autoshelf" "\\$@"
            EOF
            chmod +x "$BIN_DIR/autoshelf"
            echo "autoshelf installed to $VENV_DIR"
            """
        ),
        encoding="utf-8",
    )
    install_script.chmod(0o755)


def _copy_if_present(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copy2(source, target)


def _write_tarball(bundle_root: Path, artifact_path: Path) -> None:
    if artifact_path.exists():
        artifact_path.unlink()
    with tarfile.open(artifact_path, "w:gz") as archive:
        archive.add(bundle_root, arcname=bundle_root.name)


def _load_project_metadata(project_root: Path) -> ProjectMetadata:
    pyproject_path = project_root / "pyproject.toml"
    document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = document["project"]
    return ProjectMetadata(name=project["name"], version=project["version"])


def _normalize_machine() -> str:
    machine = shutil.which("uname")
    if machine is not None:
        detected = subprocess.run(
            ["uname", "-m"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if detected:
            return detected.replace("/", "-")
    return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="packaging/build.py")
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    args = _build_parser().parse_args()
    result = build(root=args.root)
    print(result.artifact)


if __name__ == "__main__":
    main()
