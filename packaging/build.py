from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    spec = root / "packaging" / "pyinstaller.spec"
    subprocess.run(["pyinstaller", str(spec)], check=False, cwd=root)
    dist = root / "dist"
    artifact = dist / ("autoshelf" if platform.system() != "Windows" else "autoshelf.exe")
    if artifact.exists():
        sha_path = artifact.with_suffix(artifact.suffix + ".sha256")
        sha_path.write_text(_sha256(artifact), encoding="utf-8")
    return artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    print(build())
