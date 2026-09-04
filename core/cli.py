"""Dependency-free command-line handling for SpectreHUD entry points."""

from __future__ import annotations

import sys


APP_VERSION = "2.0.9"


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
