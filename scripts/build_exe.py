#!/usr/bin/env python3
"""
SpectreHUD Standalone Executable Builder
Uses PyInstaller to compile a single-file portable Windows executable.
"""

import sys
import subprocess
import shutil
from pathlib import Path

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

    if not spec_file.exists():
        print(f"[-] Error: Spec file not found at {spec_file}")
        return False

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
        str(spec_file)
    ]

    print(f"[*] Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        exe_path = dist_dir / "SpectreHUD.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print(f"[+] BUILD SUCCESSFUL!")
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
