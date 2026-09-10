# SpectreHUD v2.0.9 – Release Notes

SpectreHUD v2.0.9 delivers seamless inline editing across all data cards, a dedicated cursor-level Quick-Loot capture dialog, a complete packaging and branding overhaul with multi-resolution Windows and Linux icon assets, modernized Report Editor controls with text alignment, and robust focus-loss dismissal for popup HUD widgets.

---

## Highlights

### Universal Double-Click Card Editing (Loot, Notes, History)

- **Double-Click Edit Interactions**:
  - **Loot Cards**: Double-clicking any loot item (title, credentials, code blocks, description) opens `AddLootDialog` in edit mode directly, allowing instant corrections without navigating through context menus.
  - **Quick Notes**: Double-clicking any note card (or clicking its edit button) launches `EditNoteDialog` to adjust text content, pentest phase category, triage status (`inbox`, `followup`, `resolved`), and target IP.
  - **Clipboard History**: Double-clicking any history card (or clicking the new `✎` action button) launches `EditHistoryDialog` to edit recorded commands, target IP associations, and multiline snippets directly.
- **Dedicated Modal HUD Dialogs**:
  - `EditNoteDialog` and `EditHistoryDialog` provide keyboard-first controls (`Ctrl+Enter` save, `Esc` cancel) styled in SpectreHUD's signature cyber theme.
  - History updates automatically recalculate line counts, character counts, and multiline badges via `ClipboardWatcher.update_entry()`.

### Quick-Loot Popup (`Ctrl + Alt + L`)

- Global hotkey `Ctrl+Alt+L` and header trigger open a lightweight, frameless glass popup at cursor position to rapidly log loot, credentials, tokens, or flags without switching active windows or taking focus away from the shell.
- Includes quick category selection, target IP auto-completion, and instant synchronization with the active project loot repository.

### Multi-Resolution Windows & Linux Packaging Icons

- **Windows Standalone Executable (`.exe`)**:
  - Overhauled `data/icon.ico` to embed all 7 standard Windows icon resolutions (`16x16`, `24x24`, `32x32`, `48x48`, `64x64`, `128x128`, and `256x256`) rendered directly from vector source `icon.svg`.
  - Resolves an issue where Windows Explorer defaulted to generic application icons on small icon views, taskbars, and Alt+Tab switchers.
- **Debian Linux Packaging (`.deb`)**:
  - Fixed packaging asset discovery in `scripts/build_deb.py` to match the standard `/hicolor/<size>/apps/` tree structure.
  - Both PNG bitmaps (48x48, 128x128, 256x256) and scalable vector SVG (`/usr/share/icons/hicolor/scalable/apps/spectrehud.svg`) are now correctly bundled and registered into desktop environments (GNOME, KDE, XFCE).

### Report Editor Modernization & Formatting Polish

- **Text Alignment Controls**: Added dedicated Left (`align-left`), Center (`align-center`), and Right (`align-right`) formatting buttons to the Report Editor formatting toolbar.
- **Full Toolbar Collapse**: Refined the toolbar collapse button to collapse both Tier 1 (document status/actions) and Tier 2 (formatting tools) into a sleek, minimal restore pill, maximizing writing screen real estate.
- **Print & PDF Styling**: Fixed code block clipping in PDF and print outputs; code blocks now wrap gracefully without inner scrollbars and avoid awkward mid-block page breaks.
- **Header Navigation Bar**: Removed redundant tab glyphs on the Notes button for a clean, typography-led header layout.

### Reliability & Window Management

- **Popup Focus & Auto-Close**: Replaced forced focus timers with clean transient window activation (`ActiveWindowFocusReason`), allowing Quick Note, Quick IP, and Quick Loot popups to reliably close when clicking outside or pressing `Esc`.
- **Internationalization (i18n)**: Enforced 100% translation key parity across English (`en.json`) and German (`de.json`), resolving untranslated labels in dialogs, find/replace bars, and password prompts.

---

## Compatibility and Upgrade

- Python 3.10 through 3.13.
- Fully backwards compatible with existing SpectreHUD project directories and reports.
- No database or configuration schema migrations required.
