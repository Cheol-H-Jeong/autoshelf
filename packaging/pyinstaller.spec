# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

try:
    from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
    from PyInstaller.utils.hooks import collect_submodules
except Exception:
    Analysis = COLLECT = EXE = PYZ = None

    def collect_submodules(name):
        return [name]


project_root = Path.cwd()
hidden_imports = (
    collect_submodules("llama_cpp")
    + collect_submodules("PySide6.QtCore")
    + collect_submodules("PySide6.QtGui")
    + collect_submodules("PySide6.QtWidgets")
    + collect_submodules("PySide6.QtSvg")
    + collect_submodules("huggingface_hub")
    + ["psutil", "autoshelf.parsers.registry"]
)
hiddenimports = hidden_imports

datas = [
    ("autoshelf/i18n/*.json", "autoshelf/i18n"),
    ("resources", "resources"),
    ("docs/USER_GUIDE.md", "docs"),
    ("LICENSE", "."),
]

block_cipher = None

if Analysis is not None:
    gui_analysis = Analysis(
        ["autoshelf/__main__.py"],
        pathex=[str(project_root)],
        binaries=[],
        datas=datas,
        hiddenimports=hidden_imports,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=["anthropic"],
        win_no_prefer_redirects=False,
        win_private_assemblies=False,
        cipher=block_cipher,
        noarchive=False,
    )
    pyz = PYZ(gui_analysis.pure, gui_analysis.zipped_data, cipher=block_cipher)
    gui_exe = EXE(
        pyz,
        gui_analysis.scripts,
        [],
        exclude_binaries=True,
        name="autoshelf",
        icon="resources/icons/autoshelf.ico",
        console=False,
        uac_admin=False,
    )
    cli_exe = EXE(
        pyz,
        gui_analysis.scripts,
        [],
        exclude_binaries=True,
        name="autoshelf-cli",
        icon="resources/icons/autoshelf.ico",
        console=True,
        uac_admin=False,
    )
    coll = COLLECT(
        gui_exe,
        cli_exe,
        gui_analysis.binaries,
        gui_analysis.zipfiles,
        gui_analysis.datas,
        name="autoshelf",
    )
