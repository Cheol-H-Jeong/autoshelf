from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as importlib_metadata
import json
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
    bundle_manifest: str = "bundle-manifest.json"
    bundle_file_count: int = 0
    runtime_distributions: tuple[str, ...] = Field(default_factory=tuple)
    install_verified: bool = False
    wheel_verified: bool = False


class BundleFileRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    size_bytes: int
    sha256: str


class BuildResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact: Path
    sha256_path: Path
    wheel_path: Path
    metadata_path: Path


class WindowsBuildMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    target: str
    artifact: str
    sha256: str
    pyinstaller_spec: str
    inno_script: str
    packaged_files: list[str] = Field(default_factory=list)
    registry_keys: list[str] = Field(default_factory=list)
    shortcuts: list[str] = Field(default_factory=list)
    dry_run: bool = False


def build(
    root: Path | None = None,
    output_dir: Path | None = None,
    verify_install: bool = False,
    verify_wheel: bool = False,
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
            metadata_path = _update_verification_metadata(metadata_path, install_verified=True)
        if verify_wheel:
            _verify_wheel(wheel_path, metadata)
            metadata_path = _update_verification_metadata(metadata_path, wheel_verified=True)
        _write_tarball(bundle_root, artifact_path)
        sha256_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
        sha256_path.write_text(_sha256(artifact_path), encoding="utf-8")
        return BuildResult(
            artifact=artifact_path,
            sha256_path=sha256_path,
            wheel_path=wheel_path,
            metadata_path=metadata_path,
        )


def build_windows(
    root: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    cross_from_linux: bool = False,
) -> WindowsBuildMetadata:
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    metadata = _load_project_metadata(project_root)
    dist_dir = (output_dir or project_root / "dist").resolve()
    dist_dir.mkdir(parents=True, exist_ok=True)
    rendered_iss = render_inno_script(
        project_root, metadata.version, dist_dir / "autoshelf-rendered.iss"
    )
    generate_windows_icon(project_root)
    artifact = dist_dir / f"autoshelf-{metadata.version}-win-x64-setup.exe"
    spec_path = project_root / "packaging" / "pyinstaller.spec"
    packaged_files = _audit_windows_file_list(project_root)
    build_metadata = WindowsBuildMetadata(
        name=metadata.name,
        version=metadata.version,
        target="windows-dry-run" if dry_run else "windows",
        artifact=str(artifact),
        sha256="0" * 64 if dry_run or not artifact.exists() else _sha256(artifact),
        pyinstaller_spec=str(spec_path),
        inno_script=str(rendered_iss),
        packaged_files=packaged_files,
        registry_keys=[
            r"HKCU\Software\Classes\.autoshelf-plan",
            r"HKCU\Software\Classes\autoshelf.plan\shell\open\command",
        ],
        shortcuts=["autoshelf", "autoshelf CLI", "문서 열기"],
        dry_run=dry_run,
    )
    (dist_dir / "build-metadata.json").write_text(
        build_metadata.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (artifact.with_suffix(artifact.suffix + ".sha256")).write_text(
        f"{build_metadata.sha256}  {artifact.name}\n", encoding="utf-8"
    )
    if dry_run:
        logger.info("Windows dry-run audited {} package inputs", len(packaged_files))
        return build_metadata
    if cross_from_linux and sys.platform != "win32":
        iscc = shutil.which("iscc") or shutil.which("iscc.exe")
        wine = shutil.which("wine")
        if not iscc and not wine:
            raise RuntimeError("Windows cross-build requires wine and Inno Setup iscc.exe on PATH")
    _run_pyinstaller(project_root, spec_path)
    _run_inno(project_root, rendered_iss)
    if not artifact.exists():
        raise RuntimeError(f"Inno Setup did not produce expected artifact: {artifact}")
    sha = _sha256(artifact)
    artifact.with_suffix(artifact.suffix + ".sha256").write_text(
        f"{sha}  {artifact.name}\n",
        encoding="utf-8",
    )
    build_metadata = build_metadata.model_copy(update={"sha256": sha, "dry_run": False})
    (dist_dir / "build-metadata.json").write_text(
        build_metadata.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    _maybe_sign_installer(artifact)
    return build_metadata


def render_inno_script(project_root: Path, version: str, output_path: Path) -> Path:
    template = project_root / "packaging" / "windows" / "autoshelf.iss"
    text = template.read_text(encoding="utf-8")
    text = text.replace("{{VERSION}}", version)
    project_root_text = (
        str(project_root).replace("/", "\\") if sys.platform == "win32" else str(project_root)
    )
    text = text.replace("{{PROJECT_ROOT}}", project_root_text)
    if "{{VERSION}}" in text or "{{PROJECT_ROOT}}" in text:
        raise RuntimeError("Unresolved Inno Setup template variable")
    output_path.write_text(text, encoding="utf-8")
    return output_path


def generate_windows_icon(project_root: Path) -> Path:
    icon_path = project_root / "resources" / "icons" / "autoshelf.ico"
    if icon_path.exists():
        return icon_path
    try:
        from PIL import Image, ImageDraw
    except Exception:
        icon_path.write_bytes(b"\x00\x00\x01\x00")
        return icon_path
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    images = []
    for size in (16, 32, 48, 64, 128, 256):
        image = Image.new("RGBA", (size, size), (37, 99, 235, 255))
        draw = ImageDraw.Draw(image)
        margin = max(2, size // 6)
        draw.rounded_rectangle(
            (margin, margin, size - margin, size - margin),
            radius=size // 8,
            outline=(255, 255, 255, 255),
            width=max(1, size // 16),
        )
        draw.line(
            (margin * 2, size // 2, size - margin * 2, size // 2),
            fill=(255, 255, 255, 255),
            width=max(1, size // 16),
        )
        images.append(image)
    images[0].save(
        icon_path,
        sizes=[(image.width, image.height) for image in images],
        append_images=images[1:],
    )
    return icon_path


def _audit_windows_file_list(project_root: Path) -> list[str]:
    candidates = [
        project_root / "autoshelf",
        project_root / "resources",
        project_root / "docs" / "USER_GUIDE.md",
        project_root / "LICENSE",
        project_root / "packaging" / "pyinstaller.spec",
        project_root / "packaging" / "windows" / "autoshelf.iss",
    ]
    files: list[str] = []
    for candidate in candidates:
        if candidate.is_file():
            files.append(candidate.relative_to(project_root).as_posix())
        elif candidate.is_dir():
            files.extend(
                path.relative_to(project_root).as_posix()
                for path in candidate.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )
    return sorted(files)


def _run_pyinstaller(project_root: Path, spec_path: Path) -> None:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_path)]
    logger.info("Running {}", " ".join(command))
    subprocess.run(command, cwd=project_root, check=True)


def _run_inno(project_root: Path, iss_path: Path) -> None:
    iscc = shutil.which("iscc.exe") or shutil.which("iscc")
    if iscc is None:
        raise RuntimeError("iscc.exe was not found on PATH")
    subprocess.run([iscc, str(iss_path)], cwd=project_root, check=True)


def _maybe_sign_installer(artifact: Path) -> None:
    cert = __import__("os").environ.get("AUTOSHELF_SIGNING_CERT")
    password = __import__("os").environ.get("AUTOSHELF_SIGNING_PASS")
    if not cert or not password:
        logger.warning("AUTOSHELF_SIGNING_CERT/PASS not set; produced unsigned installer")
        return
    signtool = shutil.which("signtool.exe") or shutil.which("signtool")
    if signtool is None:
        logger.warning("signtool.exe not found; produced unsigned installer")
        return
    subprocess.run(
        [
            signtool,
            "sign",
            "/f",
            cert,
            "/p",
            password,
            "/tr",
            "http://timestamp.digicert.com",
            "/td",
            "sha256",
            "/fd",
            "sha256",
            str(artifact),
        ],
        check=True,
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
    _copy_if_present(project_root / "packaging" / "linux" / "autoshelf.1", docs_dir / "autoshelf.1")
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
    metadata_path.write_text(bundle_metadata.model_dump_json(indent=2) + "\n", encoding="utf-8")
    bundle_manifest_path = _write_bundle_manifest(bundle_root, bundle_metadata.bundle_manifest)
    bundle_records = _load_bundle_manifest(bundle_manifest_path)
    updated_metadata = bundle_metadata.model_copy(update={"bundle_file_count": len(bundle_records)})
    metadata_path.write_text(
        updated_metadata.model_dump_json(indent=2) + "\n",
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
        destination = _distribution_destination(runtime_dir, file)
        if destination is None:
            continue
        source = Path(distribution.locate_file(file))
        if not source.exists() or source.is_dir():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1
    if copied == 0:
        raise RuntimeError(f"No installable files found for {distribution_name}")


def _distribution_destination(runtime_dir: Path, package_file: object) -> Path | None:
    relative_path = Path(str(package_file))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    return runtime_dir / relative_path


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
            - docs/autoshelf.1: generated CLI man page when present

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


def _verify_wheel(wheel_path: Path, metadata: ProjectMetadata) -> None:
    with tempfile.TemporaryDirectory(prefix="autoshelf-wheel-verify-") as temp_dir:
        runtime_dir = Path(temp_dir) / "site-packages"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        _install_wheel_into_runtime(runtime_dir, wheel_path)
        runtime_distributions = _resolve_runtime_distributions(metadata.runtime_dependencies)
        for distribution_name in runtime_distributions:
            _copy_distribution(distribution_name, runtime_dir)
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    """\
                    from __future__ import annotations

                    import runpy
                    import sys
                    from pathlib import Path

                    runtime_dir = Path(sys.argv[1]).resolve()
                    sys.path[:] = [str(runtime_dir), *[entry for entry in sys.path if entry]]
                    import llama_cpp  # noqa: F401
                    sys.argv = ["autoshelf", "version"]
                    runpy.run_module("autoshelf", run_name="__main__", alter_sys=True)
                    """
                ),
                str(runtime_dir),
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Wheel verification failed while running autoshelf version:\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        if completed.stdout.strip() != metadata.version:
            raise RuntimeError(
                "Wheel verification reported the wrong version: "
                f"{completed.stdout.strip()} != {metadata.version}"
            )


def _update_verification_metadata(
    metadata_path: Path,
    install_verified: bool | None = None,
    wheel_verified: bool | None = None,
) -> Path:
    metadata = BundleMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    updates: dict[str, bool] = {}
    if install_verified is not None:
        updates["install_verified"] = install_verified
    if wheel_verified is not None:
        updates["wheel_verified"] = wheel_verified
    metadata_path.write_text(
        metadata.model_copy(update=updates).model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def _write_bundle_manifest(bundle_root: Path, manifest_name: str) -> Path:
    manifest_path = bundle_root / manifest_name
    bundle_files = sorted(
        _iter_bundle_files(bundle_root, manifest_path),
        key=lambda item: item.as_posix(),
    )
    records = [
        BundleFileRecord(
            path=path.relative_to(bundle_root).as_posix(),
            size_bytes=path.stat().st_size,
            sha256=_sha256(path),
        )
        for path in bundle_files
    ]
    manifest_path.write_text(
        json.dumps(
            {"files": [record.model_dump(mode="json") for record in records]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _load_bundle_manifest(path: Path) -> list[BundleFileRecord]:
    document = json.loads(path.read_text(encoding="utf-8"))
    files = document.get("files", [])
    return [BundleFileRecord.model_validate(record) for record in files]


def _iter_bundle_files(bundle_root: Path, manifest_path: Path):
    for path in bundle_root.rglob("*"):
        if not path.is_file() or path == manifest_path:
            continue
        yield path


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
    parser.add_argument(
        "--target",
        choices=["linux", "windows", "windows-dry-run"],
        default="linux",
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--verify-install", action="store_true", default=False)
    parser.add_argument("--verify-wheel", action="store_true", default=False)
    parser.add_argument("--cross-from-linux", action="store_true", default=False)
    return parser


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    args = _build_parser().parse_args()
    if args.target in {"windows", "windows-dry-run"}:
        metadata = build_windows(
            root=args.root,
            output_dir=args.output_dir,
            dry_run=args.target == "windows-dry-run",
            cross_from_linux=args.cross_from_linux,
        )
        print(metadata.artifact)
        return
    result = build(
        root=args.root,
        output_dir=args.output_dir,
        verify_install=args.verify_install,
        verify_wheel=args.verify_wheel,
    )
    print(result.artifact)


if __name__ == "__main__":
    main()
