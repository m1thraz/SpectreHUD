"""Build a copy-installable DOCX plugin bundle for the current platform."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PLUGIN_SLUG = "spectrehud-docx"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DEPENDENCIES = ("python-docx>=1.1,<2",)


def build_bundle(output_dir: Path, *, vendor_dependencies: bool) -> Path:
    source_root = Path(__file__).resolve().parent
    stage = output_dir / PLUGIN_SLUG
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copy2(source_root / "plugin.json", stage / "plugin.json")
    shutil.copytree(
        source_root / "spectrehud_docx",
        stage / "spectrehud_docx",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    if vendor_dependencies:
        vendor = stage / "vendor"
        constraints = source_root.parents[1] / "constraints-release.txt"
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(vendor),
        ]
        if constraints.is_file():
            command.extend(("--constraint", str(constraints)))
        command.extend(PLUGIN_DEPENDENCIES)
        subprocess.run(command, check=True)
    operating_system = platform.system().strip().lower() or sys.platform
    architecture = platform.machine().strip().lower() or "unknown"
    platform_tag = f"{operating_system}-{architecture}"
    archive_base = output_dir / f"{PLUGIN_SLUG}-{PLUGIN_VERSION}-{platform_tag}"
    archive = Path(shutil.make_archive(str(archive_base), "zip", output_dir, PLUGIN_SLUG))
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument(
        "--no-vendor",
        action="store_true",
        help="Build only the plugin code (for local validation, not release distribution).",
    )
    args = parser.parse_args()
    archive = build_bundle(args.output_dir.resolve(), vendor_dependencies=not args.no_vendor)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
