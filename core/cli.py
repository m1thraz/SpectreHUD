"""Dependency-free command-line handling for SpectreHUD entry points."""

from __future__ import annotations

import sys
from pathlib import Path


APP_VERSION = "2.2.2"


def write_cli(lines: list[str]) -> None:
    """Write CLI output when a console stream exists."""
    stream = sys.stdout
    if stream is None:
        return
    try:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
    except (AttributeError, OSError, ValueError):
        return


def exit_for_cli_argument(argv: list[str]) -> None:
    """Handle CLI-only invocations without importing the Qt application."""
    smoke_flag = "--smoke-test-export-plugin"
    if smoke_flag in argv:
        index = argv.index(smoke_flag)
        arguments = argv[index + 1 : index + 5]
        if len(arguments) != 4:
            write_cli(
                [
                    "Usage: spectrehud --smoke-test-export-plugin "
                    "PLUGIN_ROOT PLUGIN_ID OUTPUT_DIR RESULT_JSON"
                ]
            )
            raise SystemExit(2)
        from core.plugin_smoke import run_export_plugin_smoke

        raise SystemExit(
            run_export_plugin_smoke(
                plugin_root=Path(arguments[0]),
                plugin_id=arguments[1],
                output_dir=Path(arguments[2]),
                result_file=Path(arguments[3]),
            )
        )
    if "--version" in argv or "-v" in argv:
        write_cli([f"SpectreHUD {APP_VERSION}"])
        raise SystemExit(0)
    if "--help" in argv or "-h" in argv:
        write_cli(
            [
                "SpectreHUD - Sleek CTF Cheatsheet & Session Loot Overlay HUD",
                "Usage: spectrehud [OPTIONS]",
                "",
                "Options:",
                "  -h, --help     Show this message and exit",
                "  -v, --version  Show version and exit",
            ]
        )
        raise SystemExit(0)
