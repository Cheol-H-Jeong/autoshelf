from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict

VERSION_PATTERN = re.compile(r'(?m)^(version\s*=\s*")(?P<value>\d+\.\d+\.\d+)(")$')
INIT_PATTERN = re.compile(r'(?m)^(__version__\s*=\s*")(?P<value>\d+\.\d+\.\d+)(")$')


class VersionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> VersionInfo:
        parts = value.split(".")
        if len(parts) != 3:
            raise ValueError(f"Unsupported version format: {value}")
        return cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))

    def bump(self, part: str) -> VersionInfo:
        if part == "major":
            return VersionInfo(major=self.major + 1, minor=0, patch=0)
        if part == "minor":
            return VersionInfo(major=self.major, minor=self.minor + 1, patch=0)
        return VersionInfo(major=self.major, minor=self.minor, patch=self.patch + 1)

    def render(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def bump_version(part: str, root: Path | None = None) -> str:
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    current = _read_current_version(project_root)
    next_version = current.bump(part).render()
    logger.info("Bumping version from {} to {}", current.render(), next_version)
    _rewrite_file(project_root / "pyproject.toml", VERSION_PATTERN, next_version)
    _rewrite_file(project_root / "autoshelf" / "__init__.py", INIT_PATTERN, next_version)
    _prepend_changelog_heading(project_root / "CHANGELOG.md", next_version)
    return next_version


def _read_current_version(project_root: Path) -> VersionInfo:
    document = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = document["project"]
    return VersionInfo.parse(project["version"])


def _rewrite_file(path: Path, pattern: re.Pattern[str], next_version: str) -> None:
    original = path.read_text(encoding="utf-8")
    updated, count = pattern.subn(rf"\g<1>{next_version}\g<3>", original, count=1)
    if count != 1:
        raise RuntimeError(f"Could not update version in {path}")
    path.write_text(updated, encoding="utf-8")


def _prepend_changelog_heading(path: Path, next_version: str) -> None:
    heading = f"## v{next_version}"
    original = path.read_text(encoding="utf-8")
    if heading in original:
        return
    insertion = f"# Changelog\n\n{heading}\n\n- \n\n"
    if original.startswith("# Changelog"):
        rest = original[len("# Changelog") :].lstrip("\n")
        path.write_text(f"{insertion}{rest}", encoding="utf-8")
        return
    path.write_text(f"{insertion}{original}", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="packaging/bump_version.py")
    parser.add_argument("part", choices=["patch", "minor", "major"])
    parser.add_argument("--root", type=Path, default=None)
    return parser


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    args = _build_parser().parse_args()
    print(bump_version(args.part, root=args.root))


if __name__ == "__main__":
    main()
