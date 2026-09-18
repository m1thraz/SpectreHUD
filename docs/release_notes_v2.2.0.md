# SpectreHUD v2.2.0 – Release Notes

SpectreHUD v2.2.0 delivers major focus-workflow optimizations designed to minimize
attention and cognitive context-switching costs during active pentests and CTFs,
along with critical window compositor fixes for zero-transparency modes.

---

## Highlights

### Capture and Continue (Screenshots)

- **Non-Disruptive Capture:** Global screenshot capture (`Ctrl+Alt+S`) no longer steals
  OS focus from external terminals or IDEs, and no longer forces the UI mode to switch
  to "Loot".
- **Focus Preservation:** Window restoration cleanly distinguishes between visible/active
  states (`was_visible`, `was_active`), ensuring that an active terminal keeps desktop focus.
- **HUD Toast Confirmation:** Quick visual confirmation is rendered unobtrusively via
  `PhaseToastHUD` without grabbing focus.

### Context Provenance in Capture Pipeline

- **Strict Provenance Prioritization:** Promoting clipboard history entries to Loot or
  Quick Notes strictly respects the context captured at the moment of copying:
  `captured phase_id` > `active phase` > neutral fallback (`"misc"`), and
  `captured target_ip` > `active target` > empty.
- **Elimination of Heuristic Overwrites:** Removed legacy heuristics that previously
  forced unknown commands into "recon".

### Session Recap & Resume Checkpoint

- **Mental Context Preservation:** The Session Recap banner now summarizes current Phase,
  Target, last relevant action, and open Notes / unsynced Loot count.
- **One-Click Resume:** Includes an explicit `[Resume]` button to instantly route the user
  back into the work context where they were interrupted.
- **Relaxed Auto-Dismiss:** Increased banner duration to a stress-free 25s with an explicit
  close button, eliminating premature dismissal on casual mouse movements or clicks.

### Focus Review Decisions

- **Unambiguous Triage Actions:** Quick Note triage features four clear primary actions:
  `Loot` (convert to evidence), `Report` (append to findings/report), `Done` (resolve),
  and `Later` (mark as follow-up).
- **Inbox Prioritization:** Unreviewed inbox notes are presented ahead of postponed follow-up
  notes.

### Deterministic Next Attention Item

- **Single Next Task:** Determines exactly one next actionable recommendation based on
  persisted state:
  1. Follow-up notes (`status == "followup"`)
  2. Unreviewed inbox notes (`status == "inbox"`)
  3. Unsynchronized findings/loot
  4. None (no artificial noise or distractions)
- Displayed directly within the Session Recap banner and wired to `[Resume]`.

### Fault-Tolerant Quick Loot

- **Draft Caching:** `AddLootDialog` caches uncommitted text and titles upon accidental
  cancel, focus loss, or dialog close.
- **Recovery Banner:** Restores drafts on subsequent dialog open with an explicit
  `[Discard Draft]` option.
- **Frictionless Capture:** Automatically derives the title from the first line of content
  if the title field is left blank, avoiding blocking error popups.

### Compositor & Rounded Corners on Zero Transparency

- **Compositor Retention:** Fixed an issue where setting background transparency or
  simulated glass intensity to 0 disabled `WA_TranslucentBackground` on composited desktops,
  causing frameless window corners to render with square or black artifacts.
- **Clean Antialiasing:** Preserves antialiased 14px rounded corners and border drawing
  even when glass effects and transparency are set to minimum.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13
- Windows, macOS, and Linux (X11 & Wayland)
- Fully backward compatible with existing SpectreHUD v2.1.x project databases, templates, and configurations.
