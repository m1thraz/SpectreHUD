<p align="center">
  <img src="data/icon.svg" alt="SpectreHUD logo" width="128" height="128">
</p>

# SpectreHUD

[![CI](https://github.com/m1thraz/SpectreHUD/actions/workflows/ci.yml/badge.svg)](https://github.com/m1thraz/SpectreHUD/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Windows and Linux](https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange)

**A local companion that stays open through an entire CTF or pentest engagement, from the first recon command to the finished report.**

SpectreHUD is built to make **live pentest documentation as frictionless as possible**. Instead of reconstructing a report afterward from terminals, notes, screenshots, and browser tabs, the documentation grows alongside the engagement.

![SpectreHUD main view](assets/spectrehud_main.png)

## Workflow

```text
Terminal / Browser / VM
          ↓
Clipboard History
          ↓
Quick Notes
          ↓
Loot / Findings
          ↓
Report
          ↓
Classic Web / Professional HTML / PDF
```

Not everything has to move through every stage. Capture quickly, promote only what matters, and refine it when needed.

## What it does

- **Interactive cheatsheet** with reusable commands and live project variables
- **Quick-IP popup** to copy or change the active target without returning to the main window
- **Clipboard History** for capturing useful terminal and browser output
- **Quick Notes** with phase tagging and 1-click promotion into Loot
- **Quick Loot** for structured findings, targets, severity, recommendations, and captured evidence
- **Project-scoped screenshots** tied directly to the active engagement
- **Markdown report editor** with source, split, and editable live-preview modes
- **Add Missing Loot** to append newly captured findings without overwriting manual report edits
- **Classic Web export** for full manual control over the final HTML
- **Professional export** that restructures the report into a cleaner print-oriented format while remaining editable before PDF creation
- **Obsidian, CherryTree, Markdown, and portable exports**
- **Global hotkeys** (`Ctrl+Alt+H/X/N/I/Q`)
- **Tray integration**
- **English/German UI**
- **Built-in themes**, including Dracula, Catppuccin Mocha, Gruvbox, and Tokyo Night
- **Optional encrypted Pentest Mode** project state

## Why SpectreHUD

The core idea is not just to keep notes in one place, but to reduce interruptions between testing and documentation:

- **Capture without stopping the workflow**
- **Keep targets and commands one shortcut away**
- **Promote raw observations into structured findings**
- **Build the report during the engagement instead of afterward**
- **Keep manual edits intact instead of regenerating everything**
- **Finish in editable HTML before creating the final PDF**

## Engineering focus

SpectreHUD is intentionally a **single-user desktop application**.

Reliability work focuses on realistic desktop failure modes:

- atomic writes
- backup and recovery
- rollback during failed project changes
- corrupted-state recovery
- single-instance operation

It is not designed as a network service or as a hostile local-file processing environment. Customer-facing HTML exports are treated separately because captured target content may later be opened in a recipient's browser.

More details:

- [Architecture guide](docs/architecture.md)
- [Desktop threat model and test scope](docs/threat_model.md)
- [Pentest Mode](docs/pentest_mode.md)
- [Contributor development guide](docs/development.md)
- [Changelog](CHANGELOG.md)

## Platform Support & Verification Status

| Feature / Area | Windows | Linux (X11) | Linux (Wayland) |
|---|:---:|:---:|:---:|
| **Platform Verification Tier** | 🛡️ **Tier 1 (Production)** | 🧪 **Implemented & CI-Validated** | 🧪 **Implemented & CI-Validated** |
| **HUD Overlay & Cheatsheets** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Loot Manager & Findings** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Quick Notes & Phase Tagging** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Quick-IP Popup & Net Detection** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Report Editor & Loot Append** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Global System Hotkeys** | ✅ Yes | ✅ Yes | ⚠️ In-App Qt Shortcuts |
| **Integrated Snip Screenshot Tool** | ✅ Yes | ✅ Yes | ⚠️ Restricted by compositor |
| **VPN / Local IP Discovery (`ip -j`)** | ✅ Yes | ✅ Yes (`ip -j`) | ✅ Yes (`ip -j`) |
| **XDG Base Directory Compliance** | N/A | ✅ Yes | ✅ Yes |
| **Desktop Integration** | N/A | ✅ Yes | ✅ Yes |

## Installation

### Windows executable

Download the current Windows build from the [GitHub Releases page](https://github.com/m1thraz/SpectreHUD/releases).

No Python installation is required.

### Linux

Requirements: Python 3.10+ and standard Qt6/XCB desktop runtime dependencies.

**Ubuntu / Debian / Kali Linux**

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0 libdbus-1-3
```

**Fedora / RHEL**

```bash
sudo dnf install -y mesa-libEGL mesa-libGL libxkbcommon-x11 dbus-libs
```

**Arch Linux**

```bash
sudo pacman -S libxkbcommon-x11 xcb-util-cursor dbus
```

**Install and run**

```bash
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD
pip install .
spectrehud
```

Once published to PyPI, direct `pip install spectrehud` will also be available.

### From source / development

Requirements: Python 3.10+ on Windows or Linux.

```bash
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD
pip install -e ".[dev]"
python scripts/run_tests.py fast
```

The cross-platform test runner also provides `full`, `release`, `all`, and `targeted` modes. Calling it without a mode runs the complete unfiltered suite.

Build distributable artifacts with:

```bash
pip wheel . --no-deps --no-build-isolation -w dist/
python scripts/verify_wheel.py dist/
python scripts/build_exe.py
```

## Platform notes

Windows is the primary production-verified platform.

Linux support is implemented and CI-validated; real-desktop X11/Wayland acceptance is still being expanded across physical and virtualized desktop environments.

On modern Wayland compositors, global background key logging and arbitrary display grabbing are restricted by the compositor security model. SpectreHUD gracefully degrades to in-app keyboard shortcuts and provides clear UI guidance without blocking the application.

## Contributing and security

Focused contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Report suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md), and never place credentials or engagement data in a public issue.

## License

Released under the [MIT License](LICENSE).
