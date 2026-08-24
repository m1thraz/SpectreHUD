# SpectreHUD — Tactical CTF & CLI Cheatsheet Overlay

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green?style=for-the-badge&logo=qt" alt="PyQt6">
  <img src="https://img.shields.io/badge/OS-Windows%20%7C%20Linux-orange?style=for-the-badge" alt="Windows & Linux">
  <img src="https://img.shields.io/badge/CI-Passing-brightgreen?style=for-the-badge&logo=githubactions&logoColor=white" alt="CI Status">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Focus-TryHackMe%20%7C%20HTB%20%7C%20CTFs-red?style=for-the-badge" alt="CTF Focus">
</p>

<p align="center">
  <img src="assets/spectrehud_main.png" alt="SpectreHUD Overlay" width="800" style="border-radius: 8px;">
</p>

**Ein lokales Operations-HUD für CTFs:** Dokumentieren, organisieren und arbeiten, ohne ständig zwischen fünf verschiedenen Anwendungen (VM, Browser, Notizen, Snipping-Tool, Terminal) zu wechseln. 

**SpectreHUD** ist ein minimalistisches, rahmenloses Desktop-HUD (Heads-Up-Display im Spotlight / Raycast-Stil), das speziell für TryHackMe-, HackTheBox- und CTF-Challenges entwickelt wurde. Im Gegensatz zu schweren Wissensmanagement-Systemen ist SpectreHUD als **einsatzzentrierter Workspace** konzipiert: Es schwebt nahtlos über deinen Terminals und VMs und bündelt interaktive Befehlsvorlagen, ein Session-Loot-Notizbuch, Workspace-Projektmanagement, ein integriertes **Screenshot-Snipping-Tool** und einen automatischen Clipboard-Logger mit 1-Klick-Write-Up-Export.

> [!NOTE]
> **Sicherheitshinweis für den Praxiseinsatz:** SpectreHUD ist für CTF-Challenges, Pentest-Labs (z. B. TryHackMe, HackTheBox, Proving Grounds) und Trainingsumgebungen konzipiert. Alle erfassten Daten (Credentials, Hashes, Tokens, Befehle) werden lokal im Klartext (`JSON` & `Markdown`) in deinem Workspace abgelegt. Speichere darin keine realen Produktiv-Passwörter oder vertraulichen Produktiv-Schlüssel.

---

## Key Features

### 1. Frameless Cyber-HUD (Always-on-Top)
- **Glassmorphism-Optik:** Milchig-transluzenter Dark-Look (`rgba`), abgerundete Ecken und feiner Cyan-Glow.
- **Kein Taskleisten-Ballast:** Verhält sich wie ein echtes System-Overlay (`Qt.Tool`) und lässt sich frei per Maus auf dem Bildschirm verschieben.
- **Globaler Hotkey:** Mit **`Strg + Super + <`** (bzw. `Ctrl + Win + <`) blitzschnell von überall aufrufen und schließen.
- **Schnelles Beenden:** Beende die Anwendung komplett mit **`Strg + Super + Q`** (global) oder **`Ctrl + Q`** (im HUD).

### 2. Integrierte Screenshot- & Region-Snip-Engine
- **Nativ ohne Zusatz-Bibliotheken:** Nutzt hochperformant PyQt6 `QScreen` und `QPainter`.
- **Goldstandard Snipping-Overlay:** Bei Auslösung blendet sich das HUD kurz aus, friert den Desktop ein und öffnet ein abgedunkeltes Vollbild mit Fadenkreuz und ziehbarem Rahmen (`#00e5ff`) inkl. Live-Pixelanzeige.
- **Automatische Projekt-Ablage:** Sichert den Bereich als PNG unter `~/spectre_projects/[BoxName]/loot/screenshot_YYYYMMDD_HHMMSS.png`.
- **Loot & Report Integration:** Erzeugt sofort einen Markdown-fähigen `[📷 Screenshot]`-Eintrag `![Titel](loot/screenshot_....png)` im Session-Loot inkl. Thumbnail-Vorschau und `🖼️ Öffnen`-Button!
- **Hotkeys:** Global via **`Strg + Super + X`** (bzw. `Ctrl + Win + X`), im HUD via **`Ctrl + S`** oder Klick auf **`📷 Snip`**.

### 3. Projekt- & Workspace-Management (~/spectre_projects/)
- **Isolierte Ordnerstruktur pro Box:**
  - `📁 [BoxName]/recon/` (Nmap-Scans, Gobuster-Logs)
  - `📁 [BoxName]/exploit/` (Exploits, Payloads, Reverse-Shells)
  - `📁 [BoxName]/loot/` (Screenshots, Flags, Keys, Hashes)
  - `📝 [BoxName]/notes.md` (Formatierte Notizen & Write-Up Vorlage)
  - `⚙️ [BoxName]/project_state.json` (Target-IP, LHOST, Loot-Einträge, Verlauf)
- **Schneller Box-Wechsler im Header:** Mit einem Klick auf `📁 Box: [Lame ▾]` zu einer anderen Box springen oder per `➕ Neues Projekt...` eine neue Box mit Target-IP anlegen.

### 4. Echtzeit-Variablen & Auto-Detect
- Globale Statusleiste für **`Target IP`**, **`LHOST`** und **`Port`**.
- **Live-Interpolation:** Alle Befehlsvorschauen im Cheatsheet passen sich synchron in Echtzeit deinen IPs/Ports an.
- **`🔄 Auto` Button:** Erkennt automatisch deine aktive OpenVPN / TryHackMe / WireGuard `10.x.x.x`- oder `tun0`-IP.

### 5. Modus 1: Interaktives Cheatsheet (Ctrl + 1)
- **Spotlight-Suche:** Sofortiger Cursor-Fokus beim Öffnen — tippe z. B. `curl`, `nmap`, `sql`, `suid` oder `lfi`.
- **Horizontale Filter-Chips:** Kategorien wie 🌐 *Web & HTTP*, 🐧 *Linux Shell*, 🪟 *Windows & PS*, 📡 *Network & Scans*, 🗄️ *SQL*, 🔐 *Crypto & Encoding* und ⭐ *Custom*.
- **Interaktive Inline-Parameter:** Befehle mit Platzhaltern wie `{{WORDLIST}}`, `{{PARAM}}` oder `{{PATH}}` öffnen beim Kopieren einen fokussierten Mini-Prompt mit **Live-Befehlsvorschau**, **Smart-Presets** und **Session-Memory**.

### 6. Modus 2: Session-Loot & Notizbuch (Ctrl + 2)
- Schnelle Erfassung von Beute direkt im HUD:
  - 📷 **Screenshots & PoCs**
  - 🔑 **Credentials / Logins** (`admin:Password123`)
  - 🔐 **Hashes** (NTLM, sha512crypt)
  - 📂 **Directories & URLs** (`/hidden_admin/`)
  - 🚩 **Flags** (`THM{...}`, `user.txt`)
  - 📝 **Notizen & Beobachtungen**
- **1-Click Kopieren:** Werte direkt ohne Markieren ins Clipboard kopieren.
- **`💾 Exportieren`**: Sichert alle Notizen der Box direkt in `[BoxName]/loot/loot.txt`.

### 7. Modus 3: Clipboard-Logger & Report-Generator (Ctrl + 3)
- **Automatischer Background-Watcher:** Protokolliert alle im Terminal oder Browser kopierten Befehle und Ausgaben mit Zeitstempel und Target-Zuordnung.
- **Duplicate-Filter:** Filtert aufeinanderfolgende Duplikate und leere/zu große Blöcke heraus.
- **`➕ Zu Loot`**: Übernimmt historische Clipboard-Snippets mit 1 Klick ins Session-Loot.
- **`💾 Report (.md)`**: Generiert auf Knopfdruck ein vollständiges, strukturiertes **CTF Write-Up / Report-Dokument** (`.md`) mit Header, Loot-Zusammenfassung, Screenshots und chronologischem Bash-Befehlsverlauf direkt in `[BoxName]/notes.md`.

---

## Tastenkombinationen

| Shortcut | Aktion |
|---|---|
| `Strg + Super + <` | SpectreHUD global ein- / ausblenden |
| `Strg + Super + Q` | **SpectreHUD komplett beenden (Global)** |
| `Ctrl + Q` (im HUD) | **SpectreHUD komplett beenden** |
| `Strg + Super + X` | Screenshot & Region-Snip global auslösen |
| `Ctrl + S` (im HUD) | Screenshot & Region-Snip starten |
| `Tab` | Durch die 3 Modi zirkulieren (`Cheatsheet` ➔ `Loot` ➔ `History`) |
| `Ctrl + 1` | Direkt zu **Cheatsheet** |
| `Ctrl + 2` | Direkt zu **Session-Loot** |
| `Ctrl + 3` | Direkt zu **Clipboard-Historie & Report** |
| `Ctrl + F` | Spotlight-Suche fokussieren & Text markieren |
| `Ctrl + N` | Neuen Befehl oder neuen Loot anlegen |
| `Enter` (im Prompt) | Parameter übernehmen & Befehl kopieren |
| `Esc` | Snip abbrechen, Dialog schließen oder HUD verstecken |

---

## Installation & Start

### 1. Repository klonen & Abhängigkeiten installieren
```bash
git clone https://github.com/DEIN_USERNAME/SpectreHUD.git
cd SpectreHUD
pip install -r requirements.txt
```

### 2. Starten
```bash
python main.py
```

### 3. Desktop-Verknüpfung erstellen (Windows)
```bash
python create_desktop_shortcut.py
```

---

## Tech-Stack

- **Core:** Python 3.10+
- **GUI Framework:** PyQt6 (Translucent Glassmorphism QSS Styling)
- **Global Hotkey:** `pynput` (Optimiert für Multi-Layout & VK_OEM_102)
- **Clipboard Management:** `QClipboard` & `pyperclip`
- **Workspaces & Storage:** Lokale Projektstrukturen unter `~/spectre_projects/`

---

## Lizenz
Open Source unter der [MIT License](LICENSE).
