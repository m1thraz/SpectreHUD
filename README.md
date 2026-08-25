# 👻 SpectreHUD

> **Spotlight-Style CTF Cheatsheet & Session Loot Overlay for Pentesters & Security Researchers.**

SpectreHUD is an ultra-fast, frameless HUD overlay built with PyQt6. It provides instant access to cheatsheets, dynamic IP/port variable substitution, automated clipboard logging (opt-in), snippet bookmarking, snipping tool integration, an **in-app markdown report editor with live preview**, and a **phase-structured Pentest / CTF Markdown report generator**.

---

## 🚀 Key Features

- **⚡ Instant Spotlight Search:** Global hotkey (`Strg + Super + <` on Windows/Linux) brings up the HUD instantly over any application or VM window.
- **🎯 Dynamic Variables:** Live interpolation of `{{TARGET_IP}}`, `{{ATTACKER_IP}}`, `{{PORT}}` and `{{WORDLIST}}` into all cheat commands.
- **📁 Isolated Project Workspaces:** Create dedicated workspaces per machine or CTF challenge (`📁 Box: ...`).
- **📝 Session Loot & Pentest Categorization:**
  - Save credentials, hashes, directories, flags, and notes with explicit pentest phase classification (`Recon`, `Initial Access`, `PrivEsc`, `Post-Ex`, `Scripts`, `Misc`).
  - In-place editing and recategorization via the `✏️` edit button or card double-click.
  - Automatic migration of legacy entries lacking category to `misc`.
- **📷 Visual PoC Snipping:** Capture screen regions directly into the project's loot directory and automatically embed them into write-up reports.
- **🔴 Privacy-Safe Clipboard Watcher:** 
  - Defaults to **PAUSED (`⏸️ REC: Aus`)** on startup to prevent accidental logging of private host data or password manager clips.
  - One-click toggle (`Ctrl + P`) when starting your terminal hacking session.
- **📊 Phase-Structured Reporting & Editor Tab (`ReportBuilder` & `ReportEditorTab`):**
  - Unified Markdown report generation combining categorized loot, screenshots, and chronological terminal history.
  - In-app split editor with Qt-native debounced Markdown live preview.
  - Automatic backup (`report.md.bak`) before regeneration and dirty-state protection against accidental data loss.

---

## 📊 Category-based Reporting Workflow

SpectreHUD's reporting engine (`core/report_builder.py`) organizes all collected data into standard pentest phases:

1. **Reconnaissance & Enumeration:** Discovered ports, service banners, URLs and endpoints.
2. **Initial Access & Exploitation:** User credentials, login proofs, and initial footholds.
3. **Privilege Escalation:** SUID binaries, password hashes, and root/system flags.
4. **Post-Exploitation & Lateral Movement:** Internal subnets, pivoting notes, and secondary host creds.
5. **Custom Scripts & PoCs:** Exploits, automation scripts, and custom payloads.
6. **Sonstiges & Unkategorisiert:** General notes and miscellaneous artifacts.

At the bottom of each phase, a markdown quote placeholder (`> `) is provided for immediate handwritten analysis, followed by the chronological terminal command log and an executive summary template.

---

## 🔒 Security & Privacy Notice

> [!WARNING]
> SpectreHUD is designed as a local assessment aid for Capture The Flag (CTF) challenges and authorized security tests. 
> Session loot and clipboard history are stored in plaintext JSON within your local project directory to allow easy export and inspection. **Do not use the tool on production systems without authorization, and keep the clipboard recorder paused (`Ctrl + P`) outside of test sessions.**

---

## 🛠️ Installation & Usage

```bash
# Clone the repository
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

# Install runtime dependencies
pip install -r requirements.txt

# Or install in editable mode with development dependencies:
pip install -e ".[dev]"

# Start SpectreHUD
python main.py
```

### Running Tests

```bash
# Run the complete test suite
python -m pytest
```
