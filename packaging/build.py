from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as importlib_metadata
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import tomllib
from pathlib import Path

from loguru import logger
from packaging.requirements import Requirement
from pydantic import BaseModel, ConfigDict, Field


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    runtime_dependencies: tuple[str, ...] = ()


class BundleMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    platform: str
    machine: str
    python: str
    wheel: str
    launcher: str
    install_script: str
    runtime_distributions: tuple[str, ...] = Field(default_factory=tuple)
    install_verified: bool = False


class BuildResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact: Path
    sha256_path: Path
    wheel_path: Path
    metadata_path: Path


def build(
    root: Path | None = None,
    output_dir: Path | None = None,
    verify_install: bool = False,
) -> BuildResult:
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    metadata = _load_project_metadata(project_root)
    artifact_basename = (
        f"{metadata.name}-{metadata.version}-linux-{_normalize_machine()}-bundle"
    )
    dist_dir = (output_dir or project_root / "dist").resolve()
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
        if verify_install:
            _verify_install(bundle_root, metadata)
            metadata_path = _update_install_verification(metadata_path, install_verified=True)
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
    runtime_dir = bundle_root / "runtime" / "site-packages"
    bootstrap_path = bundle_root / "runtime" / "bootstrap.py"
    bin_dir = bundle_root / "bin"
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    bundled_wheel = wheelhouse_dir / wheel_path.name
    shutil.copy2(wheel_path, bundled_wheel)
    runtime_distributions = _stage_runtime(runtime_dir, metadata, bundled_wheel)
    _write_bootstrap(bootstrap_path, metadata)
    _write_launcher(bin_dir / metadata.name, metadata)
    _write_install_script(bundle_root, metadata)
    _write_bundle_readme(bundle_root, metadata, bundled_wheel.name, runtime_distributions)
    _copy_if_present(project_root / "README.md", docs_dir / "README.md")
    _copy_if_present(project_root / "LICENSE", docs_dir / "LICENSE")
    _copy_if_present(
        project_root / "packaging" / "linux" / "autoshelf.desktop",
        bundle_root / "autoshelf.desktop",
    )
    metadata_path = bundle_root / "build-metadata.json"
    bundle_metadata = BundleMetadata(
        name=metadata.name,
        version=metadata.version,
        platform="linux",
        machine=_normalize_machine(),
        python=f"{sys.version_info.major}.{sys.version_info.minor}",
        wheel=bundled_wheel.name,
        launcher=f"bin/{metadata.name}",
        install_script="install.sh",
        runtime_distributions=runtime_distributions,
    )
    metadata_path.write_text(
        bundle_metadata.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def _stage_runtime(
    runtime_dir: Path,
    metadata: ProjectMetadata,
    bundled_wheel: Path,
) -> tuple[str, ...]:
    _install_wheel_into_runtime(runtime_dir, bundled_wheel)
    runtime_distributions = _resolve_runtime_distributions(metadata.runtime_dependencies)
    for distribution_name in runtime_distributions:
        _copy_distribution(distribution_name, runtime_dir)
    return runtime_distributions


def _install_wheel_into_runtime(runtime_dir: Path, bundled_wheel: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--target",
        str(runtime_dir),
        str(bundled_wheel),
    ]
    logger.info("Installing bundled wheel into runtime overlay")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    if completed.stdout.strip():
        logger.debug(completed.stdout.strip())
    if completed.stderr.strip():
        logger.debug(completed.stderr.strip())


def _resolve_runtime_distributions(requirements: tuple[str, ...]) -> tuple[str, ...]:
    pending = list(requirements)
    resolved: dict[str, str] = {}
    while pending:
        requirement_name = pending.pop()
        distribution = importlib_metadata.distribution(requirement_name)
        canonical_name = _canonicalize(distribution.metadata["Name"])
        if canonical_name in resolved:
            continue
        resolved[canonical_name] = distribution.metadata["Name"]
        for dependency in distribution.requires or []:
            parsed = Requirement(dependency)
            if parsed.marker is not None and not parsed.marker.evaluate():
                continue
            pending.append(parsed.name)
    return tuple(sorted(resolved.values(), key=str.lower))


def _copy_distribution(distribution_name: str, runtime_dir: Path) -> None:
    distribution = importlib_metadata.distribution(distribution_name)
    files = distribution.files
    if files is None:
        raise RuntimeError(f"Installed distribution metadata is incomplete for {distribution_name}")
    copied = 0
    for file in files:
        source = Path(distribution.locate_file(file))
        if not source.exists() or source.is_dir():
            continue
        destination = runtime_dir / Path(file)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    if copied == 0:
        raise RuntimeError(f"No installable files found for {distribution_name}")


def _write_bundle_readme(
    bundle_root: Path,
    metadata: ProjectMetadata,
    wheel_name: str,
    runtime_distributions: tuple[str, ...],
) -> None:
    distribution_summary = ", ".join(runtime_distributions) if runtime_distributions else "none"
    readme_path = bundle_root / "README.txt"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    readme_path.write_text(
        textwrap.dedent(
            f"""\
            {metadata.name} {metadata.version} Linux bundle

            Contents
            - wheelhouse/{wheel_name}: original wheel artifact for auditing or pipx workflows
            - runtime/site-packages/: vendored runtime dependencies copied from
              the build environment
            - bin/{metadata.name}: portable launcher that runs the vendored runtime
              with Python {python_version}
            - install.sh: installer that copies this version into
              ~/.local/share/autoshelf/releases/
            - autoshelf.desktop: desktop entry template for Linux shells that support it
            - docs/: copied project README and LICENSE when present

            Install
            1. Extract this tarball.
            2. Run ./install.sh
            3. Launch ~/.local/bin/{metadata.name}

            Notes
            - Installation does not download Python packages; the bundle already
              contains the runtime
              dependencies detected in the build environment.
            - This Linux bundle requires Python {python_version} on the target
              machine because compiled
              extension wheels are copied from the release builder.
            - Vendored runtime distributions: {distribution_summary}
            """
        ),
        encoding="utf-8",
    )


def _write_launcher(path: Path, metadata: ProjectMetadata) -> None:
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    python_detect_command = (
        "import sys; "
        'print(f"{sys.version_info.major}.{sys.version_info.minor}")'
    )
    path.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            RUNTIME_DIR="$SCRIPT_DIR/../runtime/site-packages"
            PYTHON_BIN="${{PYTHON_BIN:-python{python_version}}}"

            if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
                PYTHON_BIN="${{PYTHON_FALLBACK:-python3}}"
            fi

            DETECTED_PYTHON="$(
                "$PYTHON_BIN" -c '{python_detect_command}'
            )"
            if [[ "$DETECTED_PYTHON" != "{python_version}" ]]; then
                echo "{metadata.name} Linux bundle requires Python {python_version}," \
                    "found $DETECTED_PYTHON" >&2
                exit 1
            fi

            export PYTHONPATH="$RUNTIME_DIR${{PYTHONPATH:+:$PYTHONPATH}}"
            exec "$PYTHON_BIN" "$SCRIPT_DIR/../runtime/bootstrap.py" "$@"
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_bootstrap(path: Path, metadata: ProjectMetadata) -> None:
    path.write_text(
        textwrap.dedent(
            f"""\
            from __future__ import annotations

            import runpy
            import sys
            from pathlib import Path

            runtime_dir = Path(__file__).resolve().parent / "site-packages"
            sanitized_path = [str(runtime_dir)]
            sanitized_path.extend(entry for entry in sys.path[1:] if entry)
            sys.path[:] = sanitized_path
            runpy.run_module("{metadata.name}", run_name="__main__", alter_sys=True)
            """
        ),
        encoding="utf-8",
    )


def _write_install_script(bundle_root: Path, metadata: ProjectMetadata) -> None:
    install_script = bundle_root / "install.sh"
    install_script.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            set -euo pipefail

            SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
            INSTALL_ROOT="${{1:-$HOME/.local/share/{metadata.name}}}"
            BIN_DIR="${{2:-$HOME/.local/bin}}"
            RELEASES_DIR="$INSTALL_ROOT/releases"
            RELEASE_DIR="$RELEASES_DIR/{metadata.version}"
            mkdir -p "$RELEASES_DIR" "$BIN_DIR"
            rm -rf "$RELEASE_DIR"
            mkdir -p "$RELEASE_DIR"
            cp -a "$SCRIPT_DIR/." "$RELEASE_DIR/"
            cat > "$BIN_DIR/{metadata.name}" <<EOF
            #!/usr/bin/env bash
            set -euo pipefail
            exec "$RELEASE_DIR/bin/{metadata.name}" "\\$@"
            EOF
            chmod +x "$BIN_DIR/{metadata.name}"
            "$BIN_DIR/{metadata.name}" version >/dev/null
            echo "{metadata.name} installed to $RELEASE_DIR"
            """
        ),
        encoding="utf-8",
    )
    install_script.chmod(0o755)


def _verify_install(bundle_root: Path, metadata: ProjectMetadata) -> None:
    with tempfile.TemporaryDirectory(prefix="autoshelf-install-verify-") as temp_dir:
        temp_root = Path(temp_dir)
        install_root = temp_root / "install-root"
        bin_dir = temp_root / "bin"
        install_completed = subprocess.run(
            [str(bundle_root / "install.sh"), str(install_root), str(bin_dir)],
            capture_output=True,
            text=True,
        )
        if install_completed.returncode != 0:
            raise RuntimeError(
                "Install verification failed while running install.sh:\n"
                f"stdout:\n{install_completed.stdout}\n"
                f"stderr:\n{install_completed.stderr}"
            )
        completed = subprocess.run(
            [str(bin_dir / metadata.name), "version"],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Install verification failed while running the installed launcher:\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        if completed.stdout.strip() != metadata.version:
            raise RuntimeError(
                "Installed bundle did not report the expected version: "
                f"{completed.stdout.strip()} != {metadata.version}"
            )
        if install_completed.stdout.strip():
            logger.debug(install_completed.stdout.strip())


def _update_install_verification(metadata_path: Path, install_verified: bool) -> Path:
    metadata = BundleMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    metadata_path.write_text(
        metadata.model_copy(update={"install_verified": install_verified}).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    return metadata_path


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
    runtime_dependencies = tuple(
        Requirement(requirement).name for requirement in project.get("dependencies", [])
    )
    return ProjectMetadata(
        name=project["name"],
        version=project["version"],
        runtime_dependencies=runtime_dependencies,
    )


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


def _canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="packaging/build.py")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--verify-install", action="store_true", default=False)
    return parser


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    args = _build_parser().parse_args()
    result = build(root=args.root, output_dir=args.output_dir, verify_install=args.verify_install)
    print(result.artifact)


if __name__ == "__main__":
    main()
