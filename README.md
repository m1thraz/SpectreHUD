<p align="center">
  <img src="data/icon.svg" alt="SpectreHUD logo" width="128" height="128">
</p>

# SpectreHUD

[![CI](https://github.com/m1thraz/SpectreHUD/actions/workflows/ci.yml/badge.svg)](https://github.com/m1thraz/SpectreHUD/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Windows and Linux](https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange)

SpectreHUD is a local desktop workspace for CTFs, Hack The Box, TryHackMe, and
other authorized security labs. It keeps the active engagement context—target
variables, reusable commands, clipboard findings, screenshots, loot, and a
Markdown report—in one focused project.

> **Portfolio context:** Brought from initial concept to first public release in six days using iterative AI-assisted development, testing, and adversarial review. Development continues with a focus on maintenance, usability refinements, and real-world workflow feedback.



![SpectreHUD main view](assets/spectrehud_main.png)

## What it does

- Per-project target variables and reusable command snippets
- Loot, optional clipboard history, and region screenshots tied to the active project
- Markdown report editor with source, split, and live-preview views
- Structured report templates, editable standalone HTML, Markdown, Obsidian, and CherryTree exports
- Global hotkeys, tray integration, English/German UI, and optional encrypted Pentest-Mode project state

```text
Terminal / Browser / VM
          ↓
      SpectreHUD
          ↓
 Commands · Loot · Screenshots · Report
          ↓
 Obsidian / CherryTree / Portable export
```

## Engineering focus

SpectreHUD is intentionally a **single-user desktop application**. Its quality
work focuses on data integrity and normal desktop failure modes: atomic writes,
rollback during failed project changes, recovery from corrupted local state,
and a single application instance. It is not a network service or a hostile
local-file processor. Customer-facing exports are treated separately because
captured target content may be opened later in a recipient's browser.

For the implementation details, see:

- [Architecture guide](docs/architecture.md)
- [Desktop threat model and test scope](docs/threat_model.md)
- [v2.0.0 release notes](docs/release_notes_v2.0.0.md)
- [Pentest Mode](docs/pentest_mode.md)

## Installation

### Windows executable

Download the current Windows build from the [GitHub Releases page](https://github.com/m1thraz/SpectreHUD/releases). No Python installation is required.

### From source

Requirements: Python 3.10+ on Windows or Linux.

```bash
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD
pip install .
spectrehud
```

For development:

```bash
pip install -e ".[dev]"
python run_tests.py
```

Build the distributable artifacts with:

```bash
pip wheel . --no-deps --no-build-isolation -w dist/
python scripts/verify_wheel.py dist/
python scripts/build_exe.py
```

## Platform notes

SpectreHUD targets Windows and Linux. On modern Wayland desktops, screen
capture can be restricted by the compositor and may behave differently from
Windows or X11.

## License

Released under the [MIT License](LICENSE).
