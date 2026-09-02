#!/usr/bin/env python3
"""
Pure Python Debian Package (.deb) Builder.

Builds a valid Debian binary package without requiring dpkg-deb, ar, or Linux binaries.
Creates standard GNU ar archive with debian-binary, control.tar.gz, and data.tar.gz.
"""

import gzip
import io
import os
import re
import sys
import tarfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_version(project_dir: Path) -> str:
    pyproject_file = project_dir / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text(encoding="utf-8")
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    return "2.0.3"


def create_ar_header(filename: str, size: int, mode: int = 0o100644, mtime: int = 0) -> bytes:
    """Creates a 60-byte GNU ar header."""
    name_field = f"{filename}/".ljust(16)
    mtime_field = str(mtime).ljust(12)
    owner_field = "0".ljust(6)
    group_field = "0".ljust(6)
    mode_field = oct(mode)[2:].rjust(6, "0").ljust(8)
    size_field = str(size).ljust(10)
    magic_field = "`\n"
    
    header = (
        name_field[:16]
        + mtime_field[:12]
        + owner_field[:6]
        + group_field[:6]
        + mode_field[:8]
        + size_field[:10]
        + magic_field
    )
    return header.encode("ascii")


def create_control_tar(version: str, arch: str = "all") -> bytes:
    """Generates control.tar.gz in memory."""
    control_text = f"""Package: spectrehud
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: SpectreHUD Contributors <maintainers@spectrehud.local>
Depends: python3 (>= 3.10), python3-pyqt6, python3-pynput, python3-pyperclip, python3-cryptography
Homepage: https://github.com/m1thraz/SpectreHUD
Description: Tactical CTF & Pentest Overlay — Cheatsheet, Loot Manager, Template-Engine, and Live Report HUD
 SpectreHUD is a heads-up display overlay designed for CTF challenges and
 penetration testing engagements, providing quick snippet access, parameter
 templating, and interactive Markdown report generation.
"""
    postinst_text = """#!/bin/sh
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
    postrm_text = """#!/bin/sh
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

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        # control file
        c_bytes = control_text.encode("utf-8")
        ti = tarfile.TarInfo(name="./control")
        ti.size = len(c_bytes)
        ti.mode = 0o644
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        ti.mtime = int(time.time())
        tar.addfile(ti, io.BytesIO(c_bytes))

        # postinst
        p_bytes = postinst_text.encode("utf-8")
        ti_p = tarfile.TarInfo(name="./postinst")
        ti_p.size = len(p_bytes)
        ti_p.mode = 0o755
        ti_p.uid = 0
        ti_p.gid = 0
        ti_p.uname = "root"
        ti_p.gname = "root"
        ti_p.mtime = int(time.time())
        tar.addfile(ti_p, io.BytesIO(p_bytes))

        # postrm
        r_bytes = postrm_text.encode("utf-8")
        ti_r = tarfile.TarInfo(name="./postrm")
        ti_r.size = len(r_bytes)
        ti_r.mode = 0o755
        ti_r.uid = 0
        ti_r.gid = 0
        ti_r.uname = "root"
        ti_r.gname = "root"
        ti_r.mtime = int(time.time())
        tar.addfile(ti_r, io.BytesIO(r_bytes))

    return tar_buffer.getvalue()


def create_data_tar(project_dir: Path) -> bytes:
    """Generates data.tar.gz in memory containing full application tree."""
    tar_buffer = io.BytesIO()
    now = int(time.time())

    def add_bytes(tar, arcname: str, data: bytes, mode: int = 0o644):
        ti = tarfile.TarInfo(name=arcname)
        ti.size = len(data)
        ti.mode = mode
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        ti.mtime = now
        tar.addfile(ti, io.BytesIO(data))

    def add_dir(tar, arcname: str, mode: int = 0o755):
        ti = tarfile.TarInfo(name=arcname)
        ti.type = tarfile.DIRTYPE
        ti.mode = mode
        ti.uid = 0
        ti.gid = 0
        ti.uname = "root"
        ti.gname = "root"
        ti.mtime = now
        tar.addfile(ti)

    def add_tree(tar, src_dir: Path, arc_prefix: str):
        for root, dirs, files in os.walk(src_dir):
            rel_root = Path(root).relative_to(src_dir)
            target_dir = f"{arc_prefix}/{rel_root.as_posix()}" if str(rel_root) != "." else arc_prefix
            if "__pycache__" in target_dir:
                continue
            add_dir(tar, target_dir)
            for f in files:
                if f.endswith(".pyc"):
                    continue
                file_path = Path(root) / f
                rel_file = f"{target_dir}/{f}"
                try:
                    f_bytes = file_path.read_bytes()
                    add_bytes(tar, rel_file, f_bytes, mode=0o644)
                except Exception as e:
                    print(f"Warning reading {file_path}: {e}")

    with tarfile.open(fileobj=tar_buffer, mode="w:gz", format=tarfile.GNU_FORMAT) as tar:
        # Base dirs
        add_dir(tar, "./usr")
        add_dir(tar, "./usr/bin")
        add_dir(tar, "./usr/share")
        add_dir(tar, "./usr/share/applications")
        add_dir(tar, "./usr/share/icons")
        add_dir(tar, "./usr/share/icons/hicolor")
        add_dir(tar, "./usr/lib")
        add_dir(tar, "./usr/lib/python3")
        add_dir(tar, "./usr/lib/python3/dist-packages")
        add_dir(tar, "./usr/lib/python3/dist-packages/spectrehud")

        # 1. Executable launcher script
        launcher_code = """#!/usr/bin/env python3
import sys
from pathlib import Path

# Add dist-packages to sys.path if not present
pkg_dir = "/usr/lib/python3/dist-packages/spectrehud"
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from spectrehud_launcher import main

if __name__ == "__main__":
    main()
"""
        add_bytes(tar, "./usr/bin/spectrehud", launcher_code.encode("utf-8"), mode=0o755)

        # 2. Python packages and code into /usr/lib/python3/dist-packages/spectrehud
        pkg_target = "./usr/lib/python3/dist-packages/spectrehud"
        for folder in ["core", "ui", "data", "resources"]:
            src_folder = project_dir / folder
            if src_folder.exists():
                add_tree(tar, src_folder, f"{pkg_target}/{folder}")

        for root_py in ["main.py", "spectrehud_launcher.py", "create_desktop_shortcut.py"]:
            py_file = project_dir / root_py
            if py_file.exists():
                add_bytes(tar, f"{pkg_target}/{root_py}", py_file.read_bytes(), mode=0o644)

        # 3. Desktop shortcut in /usr/share/applications/spectrehud.desktop
        desktop_file = project_dir / "resources" / "linux" / "spectrehud.desktop"
        if desktop_file.exists():
            add_bytes(tar, "./usr/share/applications/spectrehud.desktop", desktop_file.read_bytes(), mode=0o644)

        # 4. Hicolor icons
        icons_src = project_dir / "resources" / "linux" / "icons"
        if icons_src.exists():
            for size in ["48x48", "128x128", "256x256"]:
                png_file = icons_src / size / "spectrehud.png"
                if png_file.exists():
                    add_dir(tar, f"./usr/share/icons/hicolor/{size}")
                    add_dir(tar, f"./usr/share/icons/hicolor/{size}/apps")
                    add_bytes(tar, f"./usr/share/icons/hicolor/{size}/apps/spectrehud.png", png_file.read_bytes(), mode=0o644)

            svg_file = icons_src / "scalable" / "spectrehud.svg"
            if svg_file.exists():
                add_dir(tar, "./usr/share/icons/hicolor/scalable")
                add_dir(tar, "./usr/share/icons/hicolor/scalable/apps")
                add_bytes(tar, "./usr/share/icons/hicolor/scalable/apps/spectrehud.svg", svg_file.read_bytes(), mode=0o644)

    return tar_buffer.getvalue()


def build_deb(project_dir: Optional[Path] = None, output_path: Optional[Path] = None, arch: str = "all") -> Path:
    """Builds a complete, valid .deb package file."""
    if project_dir is None:
        project_dir = Path(__file__).resolve().parent.parent

    version = get_version(project_dir)
    dist_dir = project_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = dist_dir / f"spectrehud_{version}_{arch}.deb"

    print(f"[*] Building Debian package for SpectreHUD v{version} ({arch})...")

    # 1. debian-binary content
    debian_binary = b"2.0\n"

    # 2. control.tar.gz content
    print("[*] Generating control.tar.gz...")
    control_tar = create_control_tar(version=version, arch=arch)

    # 3. data.tar.gz content
    print("[*] Generating data.tar.gz...")
    data_tar = create_data_tar(project_dir=project_dir)

    # 4. Construct ar archive
    print(f"[*] Assembling AR archive at {output_path}...")
    with open(output_path, "wb") as deb:
        # AR magic
        deb.write(b"!<arch>\n")

        # 1. debian-binary
        deb.write(create_ar_header("debian-binary", len(debian_binary), mode=0o100644))
        deb.write(debian_binary)
        if len(debian_binary) % 2 != 0:
            deb.write(b"\n")

        # 2. control.tar.gz
        deb.write(create_ar_header("control.tar.gz", len(control_tar), mode=0o100644))
        deb.write(control_tar)
        if len(control_tar) % 2 != 0:
            deb.write(b"\n")

        # 3. data.tar.gz
        deb.write(create_ar_header("data.tar.gz", len(data_tar), mode=0o100644))
        deb.write(data_tar)
        if len(data_tar) % 2 != 0:
            deb.write(b"\n")

    size_bytes = output_path.stat().st_size
    print(f"[+] Successfully generated Debian package: {output_path} ({size_bytes:,} bytes)")
    return output_path


if __name__ == "__main__":
    target_all = build_deb(arch="all")
    target_amd64 = build_deb(arch="amd64")
    print(f"Built packages:\n  - {target_all}\n  - {target_amd64}")
