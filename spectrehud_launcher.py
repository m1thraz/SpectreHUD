"""Lightweight console entry point that defers all GUI imports."""

from __future__ import annotations

import sys

from core.cli import exit_for_cli_argument


def main() -> None:
    exit_for_cli_argument(sys.argv)

    from main import main as run_application

    run_application()


if __name__ == "__main__":
    main()
