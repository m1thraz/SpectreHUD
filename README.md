<p align="center">
  <img src="data/icon.svg" alt="SpectreHUD Logo" width="128" height="128">
</p>

# <p align="center">SpectreHUD 2.0</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green?style=for-the-badge&logo=qt" alt="PyQt6">
  <img src="https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange?style=for-the-badge" alt="Windows & Linux">
  <img src="https://img.shields.io/badge/Focus-TryHackMe%20%7C%20HTB%20%7C%20CTFs-red?style=for-the-badge" alt="CTF Focus">
  <img src="https://img.shields.io/badge/i18n-English%20%7C%20German-purple?style=for-the-badge" alt="i18n English & German">
  <img src="https://img.shields.io/badge/Tests-pytest%20suite-brightgreen?style=for-the-badge" alt="pytest test suite">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge" alt="MIT License">
</p>

> **Tactical Spotlight-style cheatsheet, session loot manager, structured template engine, and live Markdown report HUD for CTFs and penetration testing labs.**

SpectreHUD is a frameless PyQt6 HUD overlay for CTFs and authorized penetration-testing labs. A global hotkey brings the cheatsheet, session loot, opt-in clipboard history, screenshot snipping and report editor to the foreground over terminals, browsers and VM windows. At the end of an engagement, the active project can be exported as Markdown, self-contained HTML or a portable ZIP archive.

> One SpectreHUD instance runs at a time. This prevents competing global hotkeys, clipboard watchers and project writes.

![SpectreHUD Main View](assets/spectrehud_main.png)

<p align="center"><em>Cheatsheet with live variables, project switcher, searchable commands and privacy-first recording state.</em></p>

---

## ⚡ Key Capabilities

- **Instant Search via Global Hotkey** — `Ctrl + Super + <` (customizable) summons the HUD instantly over any active window (terminals, browsers, or VM consoles).
- **Dynamic Variables** — `{{TARGET_IP}}`, `{{ATTACKER_IP}}`, `{{PORT}}`, `{{WORDLIST}}` are replaced live across all cheatsheet commands. No more tedious manual copy-paste editing.
- **Single-Instance, Multi-Location Workspaces** — One active application coordinates global hotkeys, clipboard monitoring and project writes. Create isolated workspaces anywhere on your filesystem (for example `D:\CTF\BoxName`), import existing projects and archive them as ZIP files.
- **Severity-Aware Session Loot** — Credentials, hashes, directories, flags, and notes are classified by pentest phase (*Recon, Initial Access, Privilege Escalation, Post-Exploitation, Custom Scripts, Misc*) and **Severity Level** (*Critical, High, Medium, Low, Info*), automatically calculating risk metrics summaries and severity badges.
- **Native Screenshot Snipping** — Region capture tool saves snippets directly into the active project's `loot/` directory and embeds them automatically into your reports and live previews.
- **Privacy-Conscious, Opt-in Clipboard Logger** — Starts **paused** by default (`REC: Off`) to protect your credentials. A single shortcut (`Ctrl + P`) or click activates logging exclusively for the active project session.
- **Report Editor V2** — A compact **Change View** menu selects source editor, synchronized split view, or live preview (the `Ctrl + 1` / `2` / `3` shortcuts remain available). The Markdown toolbar supports headings, emphasis, code, lists, links and tables; find/replace, debounced preview updates and periodic autosave keep longer reports manageable.
- **Interactive Report Preview & Client-Friendly Export** — Edit text directly in the standalone HTML preview, resize embedded images, print to PDF, or save an edited HTML copy. Before export, choose **Dark — SpectreHUD** or the print-friendly **Light — Client / Print** design.
- **Structured Template Engine & Template Manager** — Choose from built-in industry templates (*Standard CTF Box, Web Application Pentest, Active Directory Assessment, Executive Summary*) or create custom user templates with JSON schema validation, dynamic placeholders, and structured sections.
- **1-Click HTML & ZIP Export**:
  - **Standalone HTML Exporter** — Generates self-contained, offline HTML reports with Cyber-Dark styling and embedded screenshots.
  - **Box Archiver** — Compresses the entire project workspace (`recon/`, `exploit/`, `loot/`, `report.md`, `project_state.json`) into a clean ZIP archive with path-traversal safeguards.
- **German & English Interface** — The interface can be switched live between **English (US)** and **German (Standard)**. Core forms, report actions and user-facing error prompts use the active locale.
- **Pentest Mode (Optional Encryption)** — Per-project encryption protects `project_state.json` (variables, loot and clipboard history) with a password-derived key that exists only for the unlocked session. See [Pentest Mode](docs/pentest_mode.md) for scope and limitations.
- **Modular Settings & Hotkey Configuration** — Customize global hotkeys, font families for app/code/report output, always-on-top behavior, workspace and default variables in the settings dialog (`Ctrl + ,`).

![Add Command Dialog](assets/spectrehud_add_command.png)

### Project and report workflow

| Create a project | Write and preview the report |
|---|---|
| ![New project dialog](assets/spectrehud_new_project.png) | ![Live Markdown report editor](assets/spectrehud_report_editor.png) |

---

## 🛡️ Report Templates & Workflow

The template subsystem (`core/reporting/`) generates structured penetration testing write-ups populated automatically with your session loot and chronological command logs:

1. **Executive Summary & Scope** — Target IP/hostname, engagement dates, scope, and auto-calculated finding metrics summary.
2. **Reconnaissance & Enumeration** — Open ports, service banners, discovered URLs, and endpoints.
3. **Initial Access & Exploitation** — Discovered credentials, login proof, and foothold vectors.
4. **Privilege Escalation** — SUID binaries, cracked hashes, root/system flags.
5. **Post-Exploitation & Lateral Movement** — Internal subnets, pivoting notes, additional host accounts.
6. **Remediation & Hardening** — Actionable defensive countermeasures prioritized by severity.

Edit your report in the **Report Tab** (`Ctrl + 4`), customize templates in the **Template Manager** (`🎨 Templates...`), and save with `Ctrl + S`. Use **Change View** for Editor, Split, or Live Preview; `Ctrl + 1` / `2` / `3` are retained as report-editor shortcuts.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Scope | Action |
|---|---|---|
| `Ctrl + Super + <` | Global | Toggle SpectreHUD overlay visibility |
| `Ctrl + Super + X` | Global | Start region screenshot snip tool |
| `Ctrl + Super + Q` | Global | Quit SpectreHUD completely |
| `Esc` | In-App | Hide HUD overlay / Close modal dialog |
| `Ctrl + 1` / `2` / `3` / `4` | In-App | Switch Mode: Cheatsheet / Loot / History / Report Editor |
| `Ctrl + 1` / `2` / `3` | Report tab | Switch view: Editor / Split / Live Preview (also available via **Change View**) |
| `Ctrl + F` | In-App | Focus spotlight command search |
| `Ctrl + N` | In-App | Add new command snippet or loot entry |
| `Ctrl + S` | In-App | Capture screenshot (or Save Report in Report tab) |
| `Ctrl + P` | In-App | Toggle clipboard recorder (REC: ON / REC: Paused) |
| `Ctrl + ,` | In-App | Open Settings & Hotkey Options |

---

## 🔒 Security & Resilience Guarantees

SpectreHUD is hardened against adversarial input, directory traversal, and data corruption:

1. **Path Traversal & Sandboxing**: All template IDs, project names, and image attachments are validated against strict regex patterns (`^[a-zA-Z0-9_-]{1,64}$`) and sandboxed within workspace boundaries using `Path.is_relative_to()`.
2. **ZIP Archiver Path Sanitization**: Archive creation normalizes internal file paths and prevents Zip-Slip vulnerabilities.
3. **Atomic Persistence & Rollback**: Writes to project states, user snippets, and Markdown reports utilize atomic file replacement (`.tmp_*` -> target rename) to protect against crashes or disk interruptions.
4. **Drag & Drop Security**: Image insertion into the report preview is strictly sandboxed to project `loot/` subdirectories with size limits (15 MB), preventing local file disclosure.
5. **Single-Instance Guard**: A Qt `QLockFile` is acquired before the service container, workspace and UI start. A second launch exits with a clear message; crashed owners and stale locks are recovered safely.
6. **Consistent Domain Events**: Loot and clipboard-history changes each publish exactly one event with a stable payload contract, avoiding duplicate UI refreshes and ambiguous state updates.
7. **Regression Coverage**: The pytest suite covers unit, integration, workflow-invariant and adversarial regression cases. The release gate is the actual CI result rather than a hard-coded test count; see the [release-readiness plan](docs/release_readiness_plan.md).

> [!WARNING]
> SpectreHUD is intended as a local productivity tool for CTF challenges, training laboratories, and authorized penetration-testing engagements. By default, session loot and clipboard logs are stored in **plaintext JSON** inside local project folders for transparent inspection and easy export. Enable Pentest Mode when `project_state.json` needs encryption; reports, notes and screenshots remain outside that encryption scope. Keep the clipboard recorder paused outside active sessions (`Ctrl + P`).

---

## 🖥️ Multi-Monitor & Platform Notes

- **Multi-Monitor Display Coverage:** SpectreHUD seamlessly captures and spans across all active displays in your virtual desktop (including negative x/y monitor offsets and mixed DPI configurations).
- **Linux Wayland Compatibility (`XDG_SESSION_TYPE=wayland`):** On modern Linux Wayland compositors (GNOME/KDE Wayland), direct screen capture without user portal prompts is restricted by the operating system's security architecture. If Qt's screen grab returns an empty canvas, SpectreHUD safely falls back and logs a diagnostic warning.

---

## 🚀 Installation & Execution

### Standalone Executable (Windows)

Download `SpectreHUD.exe` directly from the [GitHub Releases](https://github.com/m1thraz/SpectreHUD/releases) page and run it — no Python installation required!

To compile your own standalone single-file `.exe`:
```bash
python scripts/build_exe.py
# Output: dist/SpectreHUD.exe
```

### Standard Python Package Installation

```bash
# Clone the repository
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

# Install package
pip install .

# Optional: Create Windows Desktop Shortcut with App Logo
python create_desktop_shortcut.py

# Launch via CLI entry point
spectrehud
```

### Developer Mode (Editable Install & Test Suite)

```bash
# Clone repository
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Run the full test suite
python run_tests.py
# Or via pytest
pytest

# Build distribution wheel & verify
pip wheel . --no-deps --no-build-isolation -w dist/
python scripts/verify_wheel.py dist/
```

---

## 📜 License

SpectreHUD is open source and licensed under the [MIT License](LICENSE).
