<p align="center">
  <img src="data/icon.svg" alt="SpectreHUD Logo" width="128" height="128">
</p>

# <p align="center">SpectreHUD</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green?style=for-the-badge&logo=qt" alt="PyQt6">
  <img src="https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange?style=for-the-badge" alt="Windows & Linux">
  <img src="https://img.shields.io/badge/Focus-TryHackMe%20%7C%20HTB%20%7C%20CTFs-red?style=for-the-badge" alt="CTF Focus">
  <img src="https://img.shields.io/badge/i18n-English%20%7C%20German-purple?style=for-the-badge" alt="i18n English & German">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge" alt="MIT License">
</p>

> **Tactical Spotlight-style cheatsheet, session loot, and live report HUD for CTFs and penetration testing labs.**

SpectreHUD is an ultra-fast, frameless HUD overlay built on PyQt6 — accessible anywhere via a global hotkey over terminals, browsers, and VM windows. It unifies instant cheatsheet search with dynamic variable replacement, an opt-in clipboard logger, native screenshot snipping, phase-categorized session loot management, and a live-preview editable Markdown report generator. At the end of your session, you get an almost finished write-up without needing an external editor.

![SpectreHUD Main View](assets/spectrehud_main.png)

---

## Features

- **Instant Search via Global Hotkey** — `Ctrl + Super + <` (customizable) summons the HUD instantly over any active window (terminals, browsers, or VM consoles).
- **Dynamic Variables** — `{{TARGET_IP}}`, `{{ATTACKER_IP}}`, `{{PORT}}`, `{{WORDLIST}}` are replaced live across all cheatsheet commands. No more tedious manual copy-paste editing.
- **Multi-Location Workspaces & Project Registry** — Create isolated project workspaces anywhere on your filesystem (default directory or custom paths like `D:\CTF\BoxName`). SpectreHUD automatically indexes and remembers project locations for quick 1-click switching and imports.
- **Session Loot with Pentest Phase Categorization** — Credentials, hashes, directories, flags, and notes are classified by type and phase: *Recon, Initial Access, Privilege Escalation, Post-Exploitation, Custom Scripts, and Misc*.
- **Native Screenshot Snipping** — Region capture tool saves snippets directly into the active project's `loot/` directory and embeds them automatically into your report.
- **Privacy-Conscious, Opt-in Clipboard Logger** — Starts **paused** by default (`REC: Off`) to protect your credentials. A single shortcut (`Ctrl + P`) or click activates logging exclusively for your active hacking session.
- **Live Markdown Report Editor** — Edit the generated pentest report directly inside the app (split-view: markdown editor on the left, live HTML preview on the right), with automatic backup before regeneration and unsaved change detection.
- **Full Internationalization (i18n)** — Switch instantly between **English (US)** and **German (Standard)** without restarting the application.
- **Modular Settings & Hotkey Configuration** — Customize global toggle shortcuts, snip tool bindings, always-on-top behavior, and default variables in a cyber glassmorphism dialog (`Ctrl + ,`).

![Add Command Dialog](assets/spectrehud_add_command.png)



---

## Phase-Based Report Workflow

The automated report generator (`core/report_builder.py`) organizes session data into six standard penetration testing phases:

1. **Reconnaissance & Enumeration** — Open ports, service banners, discovered URLs, and endpoints.
2. **Initial Access & Exploitation** — Discovered credentials, login proof, and foothold vectors.
3. **Privilege Escalation** — SUID binaries, cracked hashes, root/system flags.
4. **Post-Exploitation & Lateral Movement** — Internal subnets, pivoting notes, additional host accounts.
5. **Custom Scripts & PoCs** — Custom exploits, automation scripts, and payloads.
6. **Notes & Uncategorized** — Miscellaneous observations and takeaways.

Each phase includes freeform text areas for explanations, followed by a chronological terminal output log and an Executive Summary template. Edit your report in the **Report Tab** (`Ctrl + 4`) and save with `Ctrl + S`.

![Live Markdown Report Editor](assets/spectrehud_report_editor.png)

---

## Keyboard Shortcuts

| Shortcut | Scope | Action |
|---|---|---|
| `Ctrl + Super + <` | Global | Toggle SpectreHUD overlay visibility |
| `Ctrl + Super + X` | Global | Start region screenshot snip tool |
| `Ctrl + Super + Q` | Global | Quit SpectreHUD completely |
| `Esc` | In-App | Hide HUD overlay / Close modal dialog |
| `Tab` | In-App | Cycle between Cheatsheet, Loot, and History tabs |
| `Ctrl + 1` / `2` / `3` / `4` | In-App | Switch directly to Cheatsheet / Loot / History / Report |
| `Ctrl + F` | In-App | Focus spotlight search input |
| `Ctrl + N` | In-App | Create a new command snippet |
| `Ctrl + S` | In-App | Take region screenshot (or Save Report in Report tab) |
| `Ctrl + P` | In-App | Toggle clipboard logger (REC: ON / REC: Paused) |
| `Ctrl + ,` | In-App | Open Settings & Hotkey Options |

---

## Security & Privacy Notice

> [!WARNING]
> SpectreHUD is intended as a local productivity tool for CTF challenges, training laboratories, and authorized penetration testing engagements. Session loot and clipboard logs are stored in **plaintext JSON** inside your local project folders for transparent inspection and easy export. Do not store production secrets without authorization, and keep the clipboard recorder paused outside active sessions (`Ctrl + P`).

---

## Known Limitations

- **Multi-Monitor Display Coverage:** SpectreHUD seamlessly captures and spans across all active displays in your virtual desktop (including negative x/y monitor offsets and mixed DPI configurations).
- **Wayland Screen Capture Security Model (`XDG_SESSION_TYPE=wayland`):** On modern Linux Wayland compositors (GNOME/KDE Wayland), direct screen capture without user portal prompts is restricted by the operating system's security architecture. If Qt's screen grab returns an empty canvas, SpectreHUD safely falls back and logs a diagnostic warning.
- **Wayland Global Shortcuts:** Global key hooks under pure Wayland require desktop shortcut permissions or using the system tray menu actions.

---

## Installation & Execution

### Standard Installation

```bash
# Clone the repository
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

# Install package
pip install .

# Launch via CLI entry point
spectrehud
```

### Developer Mode (Editable Install with Tests)

```bash
# Clone repository
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

# Install in editable mode
pip install -e .

# Run test suite
python -m unittest discover tests

# Build distribution wheel
pip wheel . --no-deps -w dist/
```

---

## License

SpectreHUD is open source and licensed under the [MIT License](LICENSE).
