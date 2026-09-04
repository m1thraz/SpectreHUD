#!/usr/bin/env python3
"""
SpectreHUD Standalone Executable Builder
Uses PyInstaller to compile a single-file portable Windows executable.
"""

import sys
import subprocess
from pathlib import Path


def ensure_spec_file(spec_file: Path, project_dir: Path) -> None:
    """Generates SpectreHUD.spec automatically if it does not already exist."""
    if not spec_file.exists():
        print(f"[*] Spec file not found at {spec_file}. Generating fresh spec file...")
        spec_content = """# -*- mode: python ; coding: utf-8 -*-
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
"""
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(spec_content)
        print(f"[+] Successfully created {spec_file}")


def build_standalone_exe() -> bool:
    project_dir = Path(__file__).resolve().parent.parent
    spec_file = project_dir / "SpectreHUD.spec"
    dist_dir = project_dir / "dist"
    build_dir = project_dir / "build" / "pyinstaller"

    print("=" * 60)
    print("  [+] SpectreHUD Standalone Executable Builder")
    print("=" * 60)
    print(f"[*] Project root: {project_dir}")
    print(f"[*] Spec file:    {spec_file}")

    ensure_spec_file(spec_file, project_dir)

    # Check if pyinstaller is available
    try:
        import PyInstaller

        print(f"[+] PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("[*] PyInstaller not found. Installing pyinstaller...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0.0"])
        if res.returncode != 0:
            print("[-] Failed to install PyInstaller.")
            return False

    # Run PyInstaller build
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--workpath={build_dir}",
        f"--distpath={dist_dir}",
        str(spec_file),
    ]

    print(f"[*] Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        exe_path = dist_dir / "SpectreHUD.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print("[+] BUILD SUCCESSFUL!")
            print(f"[+] Standalone Executable: {exe_path}")
            print(f"[+] Size: {size_mb:.2f} MB")
            print("=" * 60)
            return True
        else:
            print("[-] Build succeeded but SpectreHUD.exe was not found in dist/")
            return False
    else:
        print(f"[-] PyInstaller build failed with return code {result.returncode}")
        return False


if __name__ == "__main__":
    success = build_standalone_exe()
    sys.exit(0 if success else 1)
