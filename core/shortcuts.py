"""
Central Shortcut Definitions and Metadata for SpectreHUD.

Pure Python, Zero-Qt, headless service providing a single source of truth
for all global and in-app keyboard shortcuts across SpectreHUD.
"""

from dataclasses import dataclass
from typing import List, Optional, Any


@dataclass(frozen=True)
class ShortcutDefinition:
    """Represents a standardized keyboard shortcut definition."""

    id: str
    sequence: str
    label_key: str
    default_label: str
    scope: str  # "global" or "in_app"
    category: str  # "phases", "quick_capture", "navigation", "general", "report_editor"


VALID_SCOPES = ("global", "in_app")
VALID_CATEGORIES = ("phases", "quick_capture", "navigation", "general", "report_editor")


def format_hotkey_sequence(raw: str) -> str:
    """
    Format a raw pynput or Qt sequence string into a human-readable display string.
    Example: '<ctrl>+<alt>+h' -> 'Ctrl+Alt+H', 'ctrl+shift+v' -> 'Ctrl+Shift+V'
    """
    if not raw:
        return ""

    s = (
        raw.replace("<ctrl>", "Ctrl+")
        .replace("<cmd>", "Super+")
        .replace("<shift>", "Shift+")
        .replace("<alt>", "Alt+")
        .replace("<space>", "Space")
    )
    tokens = [t.strip("<>").strip() for t in s.split("+") if t.strip()]
    formatted = []
    for tok in tokens:
        lower = tok.lower()
        if lower in ("ctrl", "strg"):
            formatted.append("Ctrl")
        elif lower in ("alt",):
            formatted.append("Alt")
        elif lower in ("shift", "umschalt"):
            formatted.append("Shift")
        elif lower in ("super", "cmd", "win"):
            formatted.append("Super")
        elif lower == "esc":
            formatted.append("Esc")
        elif lower == "tab":
            formatted.append("Tab")
        elif lower == "space":
            formatted.append("Space")
        elif lower.startswith("f") and lower[1:].isdigit():
            formatted.append(lower.upper())
        elif len(tok) == 1:
            formatted.append(tok.upper())
        else:
            formatted.append(tok.capitalize())

    return "+".join(formatted)


def get_shortcuts(config_manager: Optional[Any] = None) -> List[ShortcutDefinition]:
    """
    Returns the complete list of SpectreHUD shortcuts.
    If a ConfigManager is provided, configurable global hotkeys dynamically reflect
    the active configuration values.
    """
    # Resolve configurable global hotkey sequences
    if config_manager is not None:
        toggle_seq = format_hotkey_sequence(config_manager.get("hotkey", "<ctrl>+<alt>+h"))
        snip_seq = format_hotkey_sequence(config_manager.get("snip_hotkey", "<ctrl>+<alt>+x"))
        note_seq = format_hotkey_sequence(
            config_manager.get("quick_note_hotkey", "<ctrl>+<alt>+n")
        )
        ip_seq = format_hotkey_sequence(config_manager.get("quick_ip_hotkey", "<ctrl>+<alt>+i"))
        loot_seq = format_hotkey_sequence(
            config_manager.get("quick_loot_hotkey", "<ctrl>+<alt>+l")
        )
        quit_seq = format_hotkey_sequence(config_manager.get("quit_hotkey", "<ctrl>+<alt>+q"))
    else:
        toggle_seq = "Ctrl+Alt+H"
        snip_seq = "Ctrl+Alt+X"
        note_seq = "Ctrl+Alt+N"
        ip_seq = "Ctrl+Alt+I"
        loot_seq = "Ctrl+Alt+L"
        quit_seq = "Ctrl+Alt+Q"

    return [
        # ==========================================
        # 1. GLOBAL SHORTCUTS: PENTEST PHASES
        # ==========================================
        ShortcutDefinition(
            id="phase_1",
            sequence="Ctrl+Alt+1",
            label_key="shortcuts.phase_1",
            default_label="Phase 1: Recon (Aufklärung)",
            scope="global",
            category="phases",
        ),
        ShortcutDefinition(
            id="phase_2",
            sequence="Ctrl+Alt+2",
            label_key="shortcuts.phase_2",
            default_label="Phase 2: Initial Access (Initialer Zugriff)",
            scope="global",
            category="phases",
        ),
        ShortcutDefinition(
            id="phase_3",
            sequence="Ctrl+Alt+3",
            label_key="shortcuts.phase_3",
            default_label="Phase 3: PrivEsc (Rechteausweitung)",
            scope="global",
            category="phases",
        ),
        ShortcutDefinition(
            id="phase_4",
            sequence="Ctrl+Alt+4",
            label_key="shortcuts.phase_4",
            default_label="Phase 4: PostEx (Post-Exploitation)",
            scope="global",
            category="phases",
        ),
        ShortcutDefinition(
            id="phase_5",
            sequence="Ctrl+Alt+5",
            label_key="shortcuts.phase_5",
            default_label="Phase 5: Scripts (Eigene Skripte / PoCs)",
            scope="global",
            category="phases",
        ),
        ShortcutDefinition(
            id="phase_6",
            sequence="Ctrl+Alt+6",
            label_key="shortcuts.phase_6",
            default_label="Phase 6: Misc (Sonstiges)",
            scope="global",
            category="phases",
        ),
        # ==========================================
        # 2. GLOBAL SHORTCUTS: QUICK CAPTURE & CONTROLS
        # ==========================================
        ShortcutDefinition(
            id="global_toggle",
            sequence=toggle_seq,
            label_key="shortcuts.global_toggle",
            default_label="SpectreHUD anzeigen / verbergen",
            scope="global",
            category="quick_capture",
        ),
        ShortcutDefinition(
            id="global_quick_ip",
            sequence=ip_seq,
            label_key="shortcuts.global_quick_ip",
            default_label="Quick-IP Popup (Target / LHOST)",
            scope="global",
            category="quick_capture",
        ),
        ShortcutDefinition(
            id="global_quick_note",
            sequence=note_seq,
            label_key="shortcuts.global_quick_note",
            default_label="Quick-Note erfassen",
            scope="global",
            category="quick_capture",
        ),
        ShortcutDefinition(
            id="global_quick_loot",
            sequence=loot_seq,
            label_key="shortcuts.global_quick_loot",
            default_label="Quick-Loot erfassen",
            scope="global",
            category="quick_capture",
        ),
        ShortcutDefinition(
            id="global_snip",
            sequence=snip_seq,
            label_key="shortcuts.global_snip",
            default_label="Bereichs-Screenshot aufnehmen",
            scope="global",
            category="quick_capture",
        ),
        ShortcutDefinition(
            id="global_quit",
            sequence=quit_seq,
            label_key="shortcuts.global_quit",
            default_label="SpectreHUD beenden (Sitzung speichern)",
            scope="global",
            category="quick_capture",
        ),
        # ==========================================
        # 3. IN-APP SHORTCUTS: NAVIGATION & MODES
        # ==========================================
        ShortcutDefinition(
            id="nav_next_tab",
            sequence="Tab",
            label_key="shortcuts.nav_next_tab",
            default_label="Nächster Tab / Modus",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_cheatsheet",
            sequence="Ctrl+1",
            label_key="shortcuts.nav_cheatsheet",
            default_label="Cheatsheet-Modus",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_history",
            sequence="Ctrl+2",
            label_key="shortcuts.nav_history",
            default_label="History-Modus (Clipboard-Historie)",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_notes",
            sequence="Ctrl+3",
            label_key="shortcuts.nav_notes",
            default_label="Notes-Modus (Notizen-Inbox)",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_loot",
            sequence="Ctrl+4",
            label_key="shortcuts.nav_loot",
            default_label="Loot-Modus (Kanban-Board)",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_report",
            sequence="Ctrl+5",
            label_key="shortcuts.nav_report",
            default_label="Report-Editor-Modus",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_fullscreen",
            sequence="Ctrl+Space",
            label_key="shortcuts.nav_fullscreen",
            default_label="Vollbild umschalten",
            scope="in_app",
            category="navigation",
        ),
        ShortcutDefinition(
            id="nav_hide",
            sequence="Esc",
            label_key="shortcuts.nav_hide",
            default_label="Overlay minimieren / verbergen",
            scope="in_app",
            category="navigation",
        ),
        # ==========================================
        # 4. IN-APP SHORTCUTS: GENERAL
        # ==========================================
        ShortcutDefinition(
            id="app_search",
            sequence="Ctrl+F",
            label_key="shortcuts.app_search",
            default_label="Suchfeld fokussieren",
            scope="in_app",
            category="general",
        ),
        ShortcutDefinition(
            id="app_new_entry",
            sequence="Ctrl+N",
            label_key="shortcuts.app_new_entry",
            default_label="Neuen Eintrag / Befehl hinzufügen",
            scope="in_app",
            category="general",
        ),
        ShortcutDefinition(
            id="app_toggle_rec",
            sequence="Ctrl+P",
            label_key="shortcuts.app_toggle_rec",
            default_label="Clipboard-Logger pausieren / fortsetzen",
            scope="in_app",
            category="general",
        ),
        ShortcutDefinition(
            id="app_settings",
            sequence="Ctrl+,",
            label_key="shortcuts.app_settings",
            default_label="Einstellungen & Optionen öffnen",
            scope="in_app",
            category="general",
        ),
        ShortcutDefinition(
            id="app_shortcuts_help",
            sequence="Ctrl+/",
            label_key="shortcuts.app_shortcuts_help",
            default_label="Tastenkürzel-Übersicht öffnen",
            scope="in_app",
            category="general",
        ),
        ShortcutDefinition(
            id="app_quit",
            sequence="Ctrl+Q",
            label_key="shortcuts.app_quit",
            default_label="SpectreHUD beenden (Sitzung speichern)",
            scope="in_app",
            category="general",
        ),
        # ==========================================
        # 5. IN-APP SHORTCUTS: REPORT EDITOR
        # ==========================================
        ShortcutDefinition(
            id="report_save",
            sequence="Ctrl+S",
            label_key="shortcuts.report_save",
            default_label="Report speichern",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_cycle_view",
            sequence="Ctrl+Shift+V",
            label_key="shortcuts.report_cycle_view",
            default_label="Ansichtsmodus wechseln (Editor / Split / Vorschau)",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_outline",
            sequence="Ctrl+Shift+O",
            label_key="shortcuts.report_outline",
            default_label="Gliederungsmenü / Outline umschalten",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_find",
            sequence="Ctrl+F",
            label_key="shortcuts.report_find",
            default_label="Im Report suchen",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_bold",
            sequence="Ctrl+B",
            label_key="shortcuts.report_bold",
            default_label="Auswahl fett formatieren (**text**)",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_italic",
            sequence="Ctrl+I",
            label_key="shortcuts.report_italic",
            default_label="Auswahl kursiv formatieren (*text*)",
            scope="in_app",
            category="report_editor",
        ),
        ShortcutDefinition(
            id="report_code",
            sequence="Ctrl+K",
            label_key="shortcuts.report_code",
            default_label="Inline-Code formatieren (`code`)",
            scope="in_app",
            category="report_editor",
        ),
    ]
