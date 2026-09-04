# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

repo_dir = Path.cwd()
data_dir = repo_dir / "data"

datas = [
    (str(data_dir / "default_snippets.json"), "data"),
    (str(data_dir / "default_snippets - EN.json"), "data"),
    (str(data_dir / "i18n"), "data/i18n"),
    (str(data_dir / "report_templates"), "data/report_templates"),
    (str(data_dir / "themes"), "data/themes"),
    (str(data_dir / "icon.ico"), "data"),
    (str(data_dir / "icon.svg"), "data"),
] + collect_data_files("qtawesome")

hidden_imports = [
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "pyperclip",
    "qtawesome",
]

a = Analysis(
    ["main.py"],
    pathex=[str(repo_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SpectreHUD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(data_dir / "icon.ico"),
)
