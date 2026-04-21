from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from autoshelf import __version__
from autoshelf.__main__ import build_parser


class OptionDoc(BaseModel):
    model_config = ConfigDict(frozen=True)

    flags: tuple[str, ...]
    metavar: str | None = None
    help_text: str = ""


class CommandDoc(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    summary: str = ""
    usage: str
    options: tuple[OptionDoc, ...] = Field(default_factory=tuple)


CommandDoc.model_rebuild()


def generate_manpage(output_path: Path) -> Path:
    parser = build_parser()
    commands = tuple(_subcommand_docs(parser))
    manpage = _render_manpage(parser, commands)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manpage, encoding="utf-8")
    logger.bind(component="packaging").info("wrote man page to {}", output_path)
    return output_path


def _subcommand_docs(parser: argparse.ArgumentParser) -> Iterable[CommandDoc]:
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        summaries = {choice.dest: choice.help or "" for choice in action._choices_actions}
        for name in sorted(action.choices):
            subparser = action.choices[name]
            yield CommandDoc(
                name=name,
                summary=summaries.get(name, "").strip(),
                usage=subparser.format_usage().replace("usage: ", "").strip(),
                options=tuple(_option_docs(subparser)),
            )


def _option_docs(parser: argparse.ArgumentParser) -> Iterable[OptionDoc]:
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        flags = tuple(action.option_strings) or (action.dest,)
        metavar = None
        if action.option_strings:
            if action.nargs != 0:
                metavar = action.metavar or action.dest.upper()
        else:
            metavar = action.metavar or action.dest.upper()
        yield OptionDoc(
            flags=flags,
            metavar=metavar,
            help_text=(action.help or "").replace("%(default)s", str(action.default)),
        )


def _render_manpage(
    parser: argparse.ArgumentParser,
    commands: tuple[CommandDoc, ...],
) -> str:
    global_options = tuple(_option_docs(parser))
    lines = [
        f'.TH AUTOSHELF 1 "2026-04-22" "autoshelf {__version__}" "User Commands"',
        ".SH NAME",
        r"autoshelf \- offline-first folder organizer with preview, audit, and recovery workflows",
        ".SH SYNOPSIS",
        ".B autoshelf",
        "[global-options] command [command-options]",
        ".SH DESCRIPTION",
        (
            "autoshelf scans a root, drafts a reversible organization plan, lets the operator "
            "preview the result, applies moves plus shortcuts, and emits manifest-driven audit "
            "artifacts for verify and undo."
        ),
        ".SH GLOBAL OPTIONS",
    ]
    lines.extend(_render_options(global_options))
    lines.append(".SH COMMANDS")
    for command in commands:
        lines.extend(
            [
                f".SS {command.name}",
                _roff_escape(command.summary or command.usage),
                ".br",
                f"Usage: {_roff_escape(command.usage)}",
            ]
        )
        if command.options:
            lines.append(".RS")
            lines.extend(_render_options(command.options))
            lines.append(".RE")
    lines.extend(
        [
            ".SH FILES",
            ".TP",
            ".I .autoshelfrc.yaml",
            "Per-root planning rules file read before scan, plan, preview, apply, and doctor.",
            ".TP",
            ".I manifest.jsonl",
            "Tamper-evident manifest written after apply and checked by verify.",
            ".TP",
            ".I .autoshelf/",
            "Working area for drafts, preview trees, run plans, run state, staging, and imports.",
            ".SH SEE ALSO",
            "docs/USER_GUIDE.md, docs/ARCHITECTURE.md, packaging/build.py",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_options(options: tuple[OptionDoc, ...]) -> list[str]:
    lines: list[str] = []
    for option in options:
        flags = ", ".join(option.flags)
        if option.metavar:
            flags = f"{flags} {option.metavar}"
        lines.append(".TP")
        lines.append(r"\fB" + _roff_escape(flags) + r"\fR")
        lines.append(_roff_escape(option.help_text) or "No additional details.")
    return lines


def _roff_escape(value: str) -> str:
    return value.replace("\\", r"\\").replace("-", r"\-")


def main() -> None:
    output_path = Path("packaging/linux/autoshelf.1")
    generate_manpage(output_path)


if __name__ == "__main__":
    main()
