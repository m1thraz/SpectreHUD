# SpectreHUD v2.0.8 – Release Notes

SpectreHUD v2.0.8 is a major workflow and usability release, elevating Quick Notes from a capture inbox into a streamlined pentest workflow (**Capture → Triage → Follow-up / Loot / Report**), introducing a dedicated cursor-positioned Quick-IP popup with live IP detection, promoting Notes to a top-level HUD tab with real-time unread badges, and harmonizing global system shortcuts across operating systems.

---

## Highlights

### Quick Notes Pentest Workflow (`Capture → Triage → Follow-up / Loot / Report`)

- **Triage Status Lifecycle**: Notes now transition through structured pentest phases: `inbox`, `followup`, and `resolved`. Each card features an interactive, color-coded status pill (`📥 Inbox ▾`, `⏳ Follow-up ▾`, `✓ Resolved ▾`) with subtle text dimming for completed findings.
- **Priority Pinning & 3-Tier Sorting**: Notes can be pinned to the top of the inbox with a single click on the thumbtack icon (`fa5s.thumbtack`), glowing in signature Cyber-Cyan. The list maintains a stable 3-tier prioritized display: (1) Pinned notes, (2) Active/open notes (`inbox`, `followup`), (3) Resolved notes, while keeping newest-first order within each bucket.
- **Inline Card Editing**: Click "Edit" (or Ctrl+Enter) to modify note text directly in-place on the card, with Esc to discard changes.
- **"Send to ▾" Dual Promotion**:
  - **★ Send to Loot**: Pre-fills `AddLootDialog` with note content, category, and target IP, cleanly removing the note from the inbox upon confirmation.
  - **📝 Send to Report**: Directly appends the note as a structured Markdown block (`### Note (<PHASE>) - [<IP>] (<TIMESTAMP>)`) to the active project report and automatically marks it as `resolved`.
- **Status & Phase Filtering**: Filter bar provides triage pills (`All`, `Inbox`, `Follow-up`, `Resolved`, `📌 Pinned`) and a dedicated phase dropdown (`Phase: All ▾`).
- **Multi-Field Spotlight Search**: Search matches note content, pentest phase category, target IP, and triage status simultaneously.
- **Bulk Triage Bar**: Multi-select checkboxes on cards summon a Cyberpunk HUD bulk action bar to mark statuses, delete notes in bulk with safety confirmation, or deselect all.
- **Native Markdown-Light Rendering**: Notes display Markdown formatting (bold, code, lists, headings) cleanly in cards without external dependencies.

### Dedicated Top-Level Notes Tab & Header Bar Vector Icon System

- **First-Class Header Tab**: Promoted Quick Notes from a nested filter inside History to a dedicated top-level tab in the HUD header bar (`Notes` / `Notes (N)`) with a real-time unread badge counter.
- **Platform-Consistent Vector Icons**: Replaced platform-inconsistent Unicode emoji (`⚙`, `🚩`) with crisp vector FontAwesome icons (`fa5s.cog`, `fa5s.sticky-note`).
- **Whitespace & Padding Polish**: Eliminated redundant padding between `QFrame#HeaderBar` stylesheet rules and `HeaderPanel` layout margins, reducing unnecessary vertical whitespace and compacting mode buttons for a sleek, unified HUD aesthetic.

### Quick-IP Popup (Target + LHOST)

- Global hotkey `Ctrl+Alt+I` opens a minimal, frameless glass popup at cursor position to inspect, copy, or edit Target IP and LHOST without needing to focus the HUD.
- Features embedded 1-click circular copy buttons (`CopyableLineEdit`) and an "Auto" button that runs `NetDetector.detect_attacker_ip()` with instant live visual feedback.
- Synchronizes live on every keystroke with `VariableBar`, immediately updating cheatsheet placeholders and scheduling project autosave without requiring a manual confirm step.
- Closes cleanly via `Esc` or clicking outside (focus loss).

### Harmonized Global Shortcuts

Overhauled default system hotkeys to eliminate collisions with operating systems, desktop window managers, and browsers:
- **Toggle Overlay**: `Ctrl + Alt + H`
- **Screenshot Snip**: `Ctrl + Alt + X`
- **Quick-Note Capture**: `Ctrl + Alt + N`
- **Quick-IP Popup**: `Ctrl + Alt + I`
- **Quit Application**: `Ctrl + Alt + Q`

Automatic configuration migration upgrades legacy config files seamlessly on startup.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Fully backwards compatible with existing SpectreHUD project directories and reports.
- Legacy `project_state.json` files seamlessly load without data migrations.
