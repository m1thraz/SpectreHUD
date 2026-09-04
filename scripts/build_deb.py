#!/usr/bin/env python3
"""
SpectreHUD Debian Package (.deb) Builder.

Builds a standalone Linux binary bundle via PyInstaller and packages it into
a standard Debian .deb package adhering to Debian/Ubuntu/Kali standards with
desktop integration and icon placement.
"""

import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


def get_project_version(project_dir: Path) -> str:
    """Reads project version from pyproject.toml."""
    pyproject_file = project_dir / "pyproject.toml"
    if not pyproject_file.exists():
        return "2.0.0"

    try:
        if sys.version_info >= (3, 11):
            import tomllib

            with open(pyproject_file, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "2.0.0")
        else:
            content = pyproject_file.read_text(encoding="utf-8")
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"[!] Warning reading pyproject.toml: {e}")

    return "2.0.0"


def generate_control_file(
    version: str,
    arch: str = "amd64",
    maintainer: str = "SpectreHUD Contributors <maintainers@spectrehud.local>",
    extra_fields: Optional[Dict[str, str]] = None,
) -> str:
    """Generates the content for DEBIAN/control."""
    fields = {
        "Package": "spectrehud",
        "Version": version,
        "Section": "utils",
        "Priority": "optional",
        "Architecture": arch,
        "Maintainer": maintainer,
        "Depends": "libgl1, libegl1, libxkbcommon0, libdbus-1-3",
        "Homepage": "https://github.com/m1thraz/SpectreHUD",
        "Description": "Tactical CTF & Pentest Overlay — Cheatsheet, Loot Manager, Template-Engine, and Live Report HUD\n"
        " SpectreHUD is a heads-up display overlay designed for CTF challenges and\n"
        " penetration testing engagements, providing quick snippet access, parameter\n"
        " templating, and interactive Markdown report generation.",
    }
    if extra_fields:
        fields.update(extra_fields)

    lines = []
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    lines.append("")  # Trailing newline required by dpkg
    return "\n".join(lines)


def generate_postinst_script() -> str:
    """Generates postinst script to update desktop database and icon caches."""
    return """#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi

exit 0
"""


def generate_postrm_script() -> str:
    """Generates postrm script to update desktop database and icon caches upon removal."""
    return """#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi

exit 0
"""


def generate_launcher_wrapper() -> str:
    """Generates /usr/bin/spectrehud shell wrapper."""
    return """#!/bin/sh
exec /opt/spectrehud/spectrehud "$@"
"""


def prepare_deb_staging_tree(project_dir: Path, staging_dir: Path, version: str) -> None:
    """Prepares directory layout and files inside staging_dir."""
    debian_dir = staging_dir / "DEBIAN"
    opt_dir = staging_dir / "opt" / "spectrehud"
    bin_dir = staging_dir / "usr" / "bin"
    apps_dir = staging_dir / "usr" / "share" / "applications"
    icons_base = staging_dir / "usr" / "share" / "icons" / "hicolor"

    # Clean & recreate
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    debian_dir.mkdir(parents=True, exist_ok=True)
    opt_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    # 1. DEBIAN/control
    control_content = generate_control_file(version=version)
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    # 2. DEBIAN/postinst & postrm
    postinst_file = debian_dir / "postinst"
    postinst_file.write_text(generate_postinst_script(), encoding="utf-8")
    postinst_file.chmod(postinst_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    postrm_file = debian_dir / "postrm"
    postrm_file.write_text(generate_postrm_script(), encoding="utf-8")
    postrm_file.chmod(postrm_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # 3. Launcher wrapper: /usr/bin/spectrehud
    launcher_file = bin_dir / "spectrehud"
    launcher_file.write_text(generate_launcher_wrapper(), encoding="utf-8")
    launcher_file.chmod(launcher_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # 4. Desktop entry
    desktop_src = project_dir / "resources" / "linux" / "spectrehud.desktop"
    if desktop_src.exists():
        # Ensure Exec points to spectrehud
        content = desktop_src.read_text(encoding="utf-8")
        (apps_dir / "spectrehud.desktop").write_text(content, encoding="utf-8")

    # 5. Icons
    icon_src_dir = project_dir / "resources" / "linux" / "icons"
    if icon_src_dir.exists():
        for size in ["48x48", "128x128", "256x256"]:
            target_icon_dir = icons_base / size / "apps"
            target_icon_dir.mkdir(parents=True, exist_ok=True)
            png_icon = icon_src_dir / size / "spectrehud.png"
            if png_icon.exists():
                shutil.copy2(png_icon, target_icon_dir / "spectrehud.png")

        scalable_dir = icons_base / "scalable" / "apps"
        scalable_dir.mkdir(parents=True, exist_ok=True)
        svg_icon = icon_src_dir / "scalable" / "spectrehud.svg"
        if svg_icon.exists():
            shutil.copy2(svg_icon, scalable_dir / "spectrehud.svg")


def build_pyinstaller_bundle(project_dir: Path, output_bundle_dir: Path) -> bool:
    """Runs PyInstaller to compile the standalone onedir bundle for Linux."""
    print("[*] Running PyInstaller Linux standalone bundle build...")
    data_dir = project_dir / "data"

    datas = [
        f"{data_dir / 'default_snippets.json'}:data",
        f"{data_dir / 'default_snippets - EN.json'}:data",
        f"{data_dir / 'i18n'}:data/i18n",
        f"{data_dir / 'report_templates'}:data/report_templates",
        f"{data_dir / 'themes'}:data/themes",
        f"{data_dir / 'icon.svg'}:data",
    ]

    datas_args = []
    for d in datas:
        datas_args.extend(["--add-data", d])

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "spectrehud",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(output_bundle_dir.parent),
        "--workpath",
        str(project_dir / "build" / "pyinstaller_work"),
        *datas_args,
        "--hidden-import",
        "PyQt6.QtCore",
        "--hidden-import",
        "PyQt6.QtGui",
        "--hidden-import",
        "PyQt6.QtWidgets",
        "--hidden-import",
        "pynput",
        "--hidden-import",
        "pyperclip",
        "--hidden-import",
        "cryptography",
        str(project_dir / "main.py"),
    ]

    print(f"[*] Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_dir)
    return result.returncode == 0


def build_deb_package(project_dir: Optional[Path] = None, skip_pyinstaller: bool = False) -> Path:
    """Orchestrates building the .deb package."""
    if project_dir is None:
        project_dir = Path(__file__).resolve().parent.parent

    version = get_project_version(project_dir)
    staging_dir = project_dir / "build" / "deb_staging"
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    deb_filename = f"spectrehud_{version}_amd64.deb"
    deb_target_path = dist_dir / deb_filename

    print("=" * 60)
    print(f"  [+] SpectreHUD Debian Package Builder (v{version})")
    print("=" * 60)

    # Step 1: Prepare staging tree
    print(f"[*] Preparing staging tree in {staging_dir}...")
    prepare_deb_staging_tree(project_dir, staging_dir, version)

    # Step 2: Build or copy standalone PyInstaller bundle into /opt/spectrehud
    opt_dest = staging_dir / "opt" / "spectrehud"
    if not skip_pyinstaller:
        bundle_dist = project_dir / "build" / "pyinstaller_dist"
        if not build_pyinstaller_bundle(project_dir, bundle_dist / "spectrehud"):
            raise RuntimeError("PyInstaller build failed.")
        # Copy compiled bundle into /opt/spectrehud
        compiled_dir = bundle_dist / "spectrehud"
        if compiled_dir.exists():
            for item in compiled_dir.iterdir():
                dest_item = opt_dest / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item)
                else:
                    shutil.copy2(item, dest_item)
    else:
        # For testing / mock mode without full pyinstaller
        (opt_dest / "spectrehud").write_text("#!/bin/sh\necho SpectreHUD\n", encoding="utf-8")
        (opt_dest / "spectrehud").chmod(0o755)

    # Step 3: Run dpkg-deb to construct the .deb file
    dpkg_cmd = shutil.which("dpkg-deb")
    if not dpkg_cmd:
        print("[!] dpkg-deb not found on system PATH. Staging directory prepared successfully.")
        return deb_target_path

    print(f"[*] Building package with dpkg-deb into {deb_target_path}...")
    dpkg_args = [dpkg_cmd, "--build", "--root-owner-group", str(staging_dir), str(deb_target_path)]
    res = subprocess.run(dpkg_args, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"dpkg-deb failed: {res.stderr}")

    print(f"[+] Successfully built Debian package: {deb_target_path}")
    print(f"[+] Package size: {deb_target_path.stat().st_size:,} bytes")
    return deb_target_path


if __name__ == "__main__":
    try:
        built_deb = build_deb_package()
        print(f"[*] Done: {built_deb}")
    except Exception as err:
        print(f"[!] Error building .deb: {err}", file=sys.stderr)
        sys.exit(1)
