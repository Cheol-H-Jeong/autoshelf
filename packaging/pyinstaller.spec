# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("llama_cpp")
    + collect_submodules("PySide6.QtCore")
    + collect_submodules("PySide6.QtGui")
    + collect_submodules("PySide6.QtWidgets")
)

datas = [("autoshelf/i18n/*.json", "autoshelf/i18n")]

block_cipher = None

a = Analysis(
    ["autoshelf/__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="autoshelf", console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="autoshelf")
