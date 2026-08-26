#!/usr/bin/env python3
"""
Release Artifact Inspector for SpectreHUD Wheels.
Verifies all necessary files, package data, controllers, and entry points exist inside the built Wheel.
"""

import sys
import zipfile
from pathlib import Path

REQUIRED_FILES = [
    "main.py",
    "create_desktop_shortcut.py",
    "data/__init__.py",
    "data/default_snippets.json",
    "core/config.py",
    "core/snippet_manager.py",
    "core/loot_manager.py",
    "core/clipboard_watcher.py",
    "core/project_manager.py",
    "core/screenshot_manager.py",
    "core/project_session_service.py",
    "core/validators.py",
    "core/atomic_write.py",
    "core/report_builder.py",
    "core/report_file_manager.py",
    "core/i18n.py",
    "ui/main_window.py",
    "ui/controllers/__init__.py",
    "ui/controllers/cheatsheet_controller.py",
    "ui/controllers/loot_controller.py",
    "ui/controllers/history_controller.py",
    "ui/controllers/report_controller.py",
    "ui/controllers/project_controller.py",
    "ui/controllers/window_frame_manager.py",
    "ui/base_dialog.py",
    "ui/settings_dialog.py",
]

def verify_wheel(wheel_path: Path) -> bool:
    print(f"[*] Inspecting Wheel: {wheel_path.name}")
    if not wheel_path.exists():
        print(f"[-] Error: Wheel file does not exist: {wheel_path}")
        return False

    with zipfile.ZipFile(wheel_path, "r") as zf:
        names = set(zf.namelist())
        print(f"[+] Total files in wheel: {len(names)}")

        missing = []
        for req in REQUIRED_FILES:
            if req not in names:
                missing.append(req)

        if missing:
            print("[-] Missing required files in wheel archive:")
            for m in missing:
                print(f"    - {m}")
            return False

        # Verify entry point
        entry_point_files = [n for n in names if n.endswith("entry_points.txt")]
        if not entry_point_files:
            print("[-] Error: entry_points.txt missing in wheel .dist-info")
            return False

        ep_content = zf.read(entry_point_files[0]).decode("utf-8")
        if "spectrehud = main:main" not in ep_content:
            print("[-] Error: 'spectrehud = main:main' entry point not found in entry_points.txt")
            return False

    print("[+] All required modules, package data, controllers, and entry points verified successfully!")
    return True

def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    if target.is_dir():
        wheels = list(target.glob("*.whl"))
        if not wheels:
            print(f"[-] No .whl files found in directory: {target}")
            sys.exit(1)
        wheel_path = wheels[0]
    else:
        wheel_path = target

    if not verify_wheel(wheel_path):
        sys.exit(1)

if __name__ == "__main__":
    main()
