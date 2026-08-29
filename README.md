<p align="center">
  <img src="data/icon.svg" alt="SpectreHUD Logo" width="128" height="128">
</p>

<h1 align="center">SpectreHUD</h1>

<p align="center">
  <strong>A focused workspace for CTFs, Hack The Box, TryHackMe and authorized security labs.</strong>
</p>

<p align="center">
  Capture the engagement in SpectreHUD. Keep the knowledge where you want it.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green?style=for-the-badge&logo=qt" alt="PyQt6">
  <img src="https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange?style=for-the-badge" alt="Windows & Linux">
  <img src="https://img.shields.io/badge/Focus-HTB%20%7C%20THM%20%7C%20CTFs-red?style=for-the-badge" alt="CTF Focus">
  <img src="https://img.shields.io/badge/i18n-English%20%7C%20German-purple?style=for-the-badge" alt="English & German">
  <img src="https://img.shields.io/badge/Tests-300%2B-brightgreen?style=for-the-badge" alt="300+ Tests">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge" alt="MIT License">
</p>

---

## Work the box, not the workspace

SpectreHUD is a lightweight desktop workspace built around the active CTF or lab session.

Instead of spreading commands, target information, screenshots, clipboard findings, loot and report notes across several applications and browser tabs, SpectreHUD keeps the operational context of the current box in one place.

Bring it up with a global hotkey, find or reuse a command, substitute the current target variables, capture relevant output, take a screenshot, record loot and continue working.

When the engagement is finished, turn that session into a structured Markdown or HTML report without first reconstructing what happened across multiple tools.

![SpectreHUD Main View](assets/spectrehud_main.png)

<p align="center"><em>Searchable commands, live target variables and the active project context in one focused workspace.</em></p>

---

## Why SpectreHUD?

Tools such as Obsidian and CherryTree are excellent for building long-term knowledge bases.

SpectreHUD solves a different problem.

It focuses on the period while you are actively working a box.

```text
Terminal / Browser / VM
          ↓
      SpectreHUD
          ↓
 Commands · Target Context · Loot
 Screenshots · Clipboard · Report
          ↓
  Long-term knowledge base
```

The goal is not to replace your notes application.

The goal is to remove the repetitive workflow around it.

With SpectreHUD, you do not need to turn a general-purpose knowledge base into a dedicated CTF environment with additional capture workflows, templates, engagement variables and session-specific organization.

Use SpectreHUD for the engagement.

Use Obsidian, CherryTree or your preferred knowledge system for the material worth keeping afterwards.

> **Work fast in SpectreHUD. Keep your knowledge base clean.**

---

## Core Workflow

A typical engagement looks like this:

```text
Create / open project
        ↓
Set TARGET, LHOST, PORT and other variables
        ↓
Search and reuse commands
        ↓
Capture clipboard findings and screenshots
        ↓
Organize useful results as loot
        ↓
Build the report while you work
        ↓
Export the finished engagement
```

SpectreHUD is deliberately optimized for this loop instead of trying to become a general-purpose note-taking platform.

---

## Spotlight Command Search

Bring SpectreHUD to the foreground instantly and search your command library without leaving the current workflow.

* Fast global HUD access
* Searchable command snippets
* Categories and filters
* Custom commands
* Copy-to-clipboard workflow
* Variable substitution before execution

Example command:

```bash
nmap -sC -sV {{TARGET_IP}} -p {{PORT}}
```

With:

```text
TARGET_IP = 10.10.11.42
PORT      = 8080
```

SpectreHUD gives you:

```bash
nmap -sC -sV 10.10.11.42 -p 8080
```

No repeated search-and-replace across notes and terminals.

---

## Project Context and Live Variables

Every project carries its own engagement context.

Common variables include:

```text
{{TARGET_IP}}
{{ATTACKER_IP}}
{{PORT}}
{{WORDLIST}}
```

Change the target once and reuse it across the command library.

Projects keep their own session state so switching between boxes does not require rebuilding the context manually.

SpectreHUD can also import existing project workspaces and archive completed ones as portable ZIP files.

---

## Session Loot

Capture useful findings while they are still in context.

Loot can include:

* Credentials
* Hashes
* Flags
* URLs and directories
* Enumeration results
* Commands
* Findings
* Notes
* Screenshots
* Custom entries

Entries can be organized by penetration-testing phase:

* Reconnaissance
* Initial Access
* Privilege Escalation
* Post-Exploitation
* Custom Scripts
* Miscellaneous

Severity levels provide additional prioritization:

```text
Critical · High · Medium · Low · Info
```

The goal is simple:

> When something important appears during the engagement, recording it should take seconds rather than interrupting the workflow.

![Add Command Dialog](assets/spectrehud_add_command.png)

---

## Screenshot Snipping

Capture a region of the screen directly from SpectreHUD.

Screenshots are stored with the active project and can be reused immediately in loot entries and reports.

This removes the usual workflow of:

```text
screenshot tool
→ save somewhere
→ rename file
→ find notes
→ drag image
→ fix path
```

Capture it once and keep moving.

---

## Optional Clipboard History

SpectreHUD can maintain a clipboard history scoped to the active project.

This is useful for quickly recovering:

* Commands
* Paths
* URLs
* Tool output
* Credentials
* Interesting one-liners

Clipboard recording is explicitly controllable from the HUD and can remain disabled when it is not needed.

---

## Report While You Work

Documentation does not have to start after the box is finished.

SpectreHUD includes a Markdown report workspace with three views.

### Source Editor

Write and edit Markdown directly.

### Split View

Edit Markdown while seeing the rendered result beside it.

### Live Preview

Focus entirely on the rendered report.

| Create a project                                         | Write and preview the report                                        |
| -------------------------------------------------------- | ------------------------------------------------------------------- |
| ![New project dialog](assets/spectrehud_new_project.png) | ![Live Markdown report editor](assets/spectrehud_report_editor.png) |

The report can incorporate the context already collected during the session instead of forcing you to reconstruct the engagement afterwards.

---

## Structured Report Templates

SpectreHUD includes templates for common security-lab and reporting workflows.

Built-in templates include:

* Standard CTF Box
* Web Application Pentest
* Active Directory Assessment
* Executive Summary

Templates can provide sections such as:

```text
Executive Summary
Scope
Reconnaissance
Enumeration
Initial Access
Privilege Escalation
Post-Exploitation
Findings
Remediation
```

Custom templates can also be created through the Template Manager.

The template engine is intended to provide structure without forcing every engagement into the same document.

---

## Export

Completed engagements can currently be exported as:

### Markdown

Keep the report portable and editable in any Markdown-compatible tool.

### Standalone HTML

Generate a self-contained offline report with embedded styling and screenshots.

### Project Archive

Package the complete SpectreHUD workspace into a ZIP archive for backup or transfer.

```text
project/
├── recon/
├── exploit/
├── loot/
├── notes/
├── report.md
└── project_state.json
```

---

## Knowledge Base Integration

SpectreHUD is designed to complement long-term knowledge-management tools rather than replace them.

A core direction of the project is making the boundary between active engagement and long-term knowledge as frictionless as possible.

### Planned Obsidian Integration

The planned Obsidian workflow will allow users to:

* Export the current report directly into an Obsidian vault
* Transfer report screenshots and attachments
* Generate useful Obsidian properties and frontmatter
* Export selected or complete session loot
* Append new findings to an existing project note
* Open the exported note directly in Obsidian

The intended workflow is strictly one-way:

```text
SpectreHUD → Obsidian
```

SpectreHUD remains responsible for the active engagement while Obsidian remains responsible for long-term organization, linking and knowledge retention.

No dedicated Obsidian capture setup or CTF-specific plugin stack should be required.

### Planned CherryTree Export

CherryTree support is planned through portable export formats such as HTML rather than direct manipulation of CherryTree's internal database.

The same principle applies:

> Capture and structure the engagement in SpectreHUD, then move the finished material into the knowledge system you already use.

---

## English and German

SpectreHUD supports runtime switching between:

* English
* German

The interface, dialogs and report-related workflows are internationalized.

---

## Keyboard-Driven Workflow

SpectreHUD is designed to stay out of the way until it is needed.

| Shortcut           | Action                                 |
| ------------------ | -------------------------------------- |
| `Ctrl + Super + <` | Toggle SpectreHUD                      |
| `Ctrl + Super + X` | Start screenshot snipping              |
| `Ctrl + Super + Q` | Quit SpectreHUD                        |
| `Esc`              | Hide HUD / close dialog                |
| `Ctrl + 1`         | Cheatsheet                             |
| `Ctrl + 2`         | Loot                                   |
| `Ctrl + 3`         | Clipboard History                      |
| `Ctrl + 4`         | Report                                 |
| `Ctrl + F`         | Focus command search                   |
| `Ctrl + N`         | Add command / loot entry               |
| `Ctrl + S`         | Save report or context-specific action |
| `Ctrl + P`         | Toggle clipboard recording             |
| `Ctrl + ,`         | Settings                               |

Global shortcuts can be customized.

---

## Platform Notes

SpectreHUD currently targets:

* Windows
* Linux

Multi-monitor setups are supported, including virtual desktops with negative monitor coordinates.

### Linux / Wayland

Modern Wayland compositors restrict direct screen capture by design.

Depending on the desktop environment, screenshot capture may therefore behave differently than under X11 or Windows.

---

## Installation

### Windows Executable

Download the latest Windows build from the GitHub Releases page:

https://github.com/m1thraz/SpectreHUD/releases

No Python installation is required for the standalone executable.

### Install from Source

Requirements:

* Python 3.10+
* Windows or Linux

```bash
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

pip install .

spectrehud
```

### Developer Installation

```bash
git clone https://github.com/m1thraz/SpectreHUD.git
cd SpectreHUD

pip install -e ".[dev]"
```

Run the test suite:

```bash
python run_tests.py
```

or:

```bash
pytest
```

The current codebase contains more than 300 unit, integration and adversarial regression tests covering core workflows, persistence, reporting, project isolation and failure recovery.

Build and verify the Python package:

```bash
pip wheel . --no-deps --no-build-isolation -w dist/
python scripts/verify_wheel.py dist/
```

Build the standalone Windows executable:

```bash
python scripts/build_exe.py
```

---

## Project Philosophy

SpectreHUD intentionally does not try to become another general-purpose knowledge-management platform.

The project follows a few simple principles.

### Stay Focused

Features should improve the active CTF or security-lab workflow.

### Reduce Context Switching

Information that belongs to the current engagement should be accessible without repeatedly reorganizing windows, notes and tools.

### Capture Now, Organize Later

Recording something during a box should be cheap.

Long-term organization can happen afterwards in the knowledge system of your choice.

### Keep the Output Portable

Markdown, HTML, images and normal project files should remain usable outside SpectreHUD.

### Prefer Workflow Over Configuration

A useful CTF environment should work without first spending an evening constructing one.

---

## Quality

SpectreHUD has an extensive automated test suite covering both normal operation and adversarial failure scenarios.

The tests include areas such as:

* Project and session isolation
* Persistence and recovery
* Report generation
* Template handling
* Screenshot workflows
* Clipboard behavior
* Workspace transitions
* Import and export behavior
* Filesystem edge cases

Implementation and architecture details are documented separately in [`docs/architecture.md`](docs/architecture.md).

---

## Direction

SpectreHUD is currently focused on refining the core engagement workflow rather than continuously adding unrelated features.

Near-term areas of development include:

* Obsidian report export
* Obsidian loot export and append workflow
* Attachment-aware knowledge-base export
* CherryTree-compatible export
* Continued UX refinement based on real CTF usage

The goal remains the same:

> **Spend more time working the box and less time managing the tools around it.**

---

## License

SpectreHUD is open source and licensed under the [MIT License](LICENSE).

---

<p align="center">
  <strong>Work the box in SpectreHUD. Keep the knowledge where you want it.</strong>
</p>
