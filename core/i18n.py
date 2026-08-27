from typing import Dict, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from core.logger import get_logger

logger = get_logger("i18n")

SUPPORTED_LOCALES: Dict[str, str] = {
    "de": "Deutsch",
    "en": "English"
}

DEFAULT_LOCALE = "en"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "de": {
        # Header & Navigation
        "header.brand": "SPECTRE // HUD",
        "header.box_label": "Box: {name}",
        "header.mode_cheatsheet": "Cheatsheet",
        "header.mode_loot": "Loot",
        "header.mode_history": "History",
        "header.mode_report": "Report",
        "header.snip": "Snip",
        "header.rec_on": "REC: ON",
        "header.rec_off": "REC: Off",
        "header.rec_paused": "REC: Paused",
        "header.opt": "⚙",
        "header.close_tip": "Overlay minimieren / verstecken (Esc)",
        "header.snip_tip": "Bereichs-Screenshot aufnehmen (Strg+Super+X oder Ctrl+S)",
        "header.rec_tip_paused": "Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+P zum Starten der Aufzeichnung.",
        "header.rec_tip_active": "Clipboard-Logger ist AKTIV (zeichnet auf).\nKlicken oder Ctrl+P zum Pausieren.",
        "header.opt_tip": "Einstellungen & Optionen öffnen (Ctrl+,)",
        "header.report_tip": "Editierbaren Markdown-Report des aktiven Projekts öffnen (Ctrl+4)",

        # Project Menu
        "project.new_project": "+ Neues Projekt / Box erstellen...",
        "project.import_folder": "Projekt-Ordner importieren / öffnen...",
        "project.import_title": "Projekt-Ordner auswählen",
        "project.open_folder": "Projektordner im Explorer öffnen",

        # Variable Bar
        "varbar.target": "Target:",
        "varbar.attacker": "LHOST:",
        "varbar.port": "Port:",
        "varbar.user": "User:",
        "varbar.pass": "Pass:",
        "varbar.pass_toggle_tip": "Passwort ein-/ausblenden",
        "varbar.auto": "Auto",
        "varbar.auto_tip": "Auto-Erkennung für tun0 / VPN / lokale IP",
        "varbar.no_ip": "Keine IP",
        "varbar.add_btn": "+ Neu",
        "varbar.add_btn_tip": "Neuen Befehl anlegen (Ctrl+N)",
        "card.tweak_tip": "Befehl anpassen vor dem Kopieren",

        # Search Bar
        "search.cheatsheet_placeholder": "Befehl, Tool oder Syntax suchen (z. B. 'curl', 'nmap', 'sql')...",
        "search.loot_placeholder": "Session Loot, Credentials, Hashes & Notizen durchsuchen...",
        "search.history_placeholder": "Clipboard-Historie, kopierte Befehle & Ausgaben durchsuchen...",

        # Filter Pills
        "filter.all_commands": "All Commands",
        "filter.favorites": "★ Favoriten",
        "filter.all_loot": "All ({count})",
        "filter.target_only": "Target IP Only",
        "filter.all_history": "All ({count})",
        "filter.commands_only": "Commands",
        "filter.outputs_only": "Outputs",

        # Privacy Warning Banner
        "privacy.warning": "Datenschutz-Hinweis: Kopierte Passwörter oder persönliche Daten werden protokolliert, solange REC aktiv ist (Pausieren mit Ctrl+P oder Klick auf REC: ON).",

        # Footer
        "footer.status": "{hotkey}: Toggle | Strg+Super+Q: Beenden | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Verstecken",
        "footer.entries_count": "{count} Einträge",
        "footer.entry_count_single": "1 Eintrag",
        "footer.always_on_top": "Im Vordergrund",
        "footer.always_on_top_tip": "Overlay immer über allen anderen Fenstern im Vordergrund halten",

        # Cards & Badges
        "card.copy": "Copy",
        "card.copied": "Copied!",
        "card.edit": "Edit",
        "card.open": "Open",
        "card.add_loot": "+ Loot",
        "card.delete_tip": "Löschen",
        "card.copy_tip": "Befehl mit aktuellen Variablen in die Zwischenablage kopieren",

        # Report Editor Tab
        "report.regenerate": "Aus Loot neu generieren",
        "report.regenerate_tip": "Aktualisiert die Struktur und fügt neue Loot-Einträge ein",
        "report.export_copy": "Kopie exportieren...",
        "report.export_copy_tip": "Erstellt eine neue Kopie basierend auf dem aktuellen Loot",
        "report.save": "Speichern",
        "report.save_tip": "Änderungen in report.md des aktiven Projekts speichern (Ctrl+S)",
        "report.saved": "Gespeichert",
        "report.unsaved": "Ungespeicherte Änderungen",
        "report.empty_title": "Kein aktives Projekt",
        "report.empty_desc": "Wähle oben eine Box aus, um den Pentest-Report zu bearbeiten.",
        "report.discard_title": "Ungespeicherte Änderungen",
        "report.discard_msg": "Du hast ungespeicherte Änderungen am aktuellen Report. Möchtest du den Tab trotzdem wechseln und die Änderungen verwerfen?",

        # Dialog Common
        "dialog.cancel": "Abbrechen",
        "dialog.save": "Speichern",
        "dialog.update": "Aktualisieren",
        "dialog.create": "Projekt erstellen",
        "dialog.browse": "Durchsuchen...",
        "dialog.error": "Fehler",

        # Add Snippet Dialog
        "snippet_dialog.title": "SPECTRE // NEUEN BEFEHL HINZUFÜGEN",
        "snippet_dialog.lbl_title": "Titel / Name des Befehls:",
        "snippet_dialog.ph_title": "z.B. Nmap UDP Scan mit Skripten",
        "snippet_dialog.lbl_category": "Kategorie:",
        "snippet_dialog.lbl_subcategory": "Unterkategorie / Gruppe:",
        "snippet_dialog.ph_subcategory": "z.B. Port Scanning oder Web Recon",
        "snippet_dialog.lbl_template": "Befehl / Template (unterstützt {{TARGET_IP}}, {{ATTACKER_IP}}, {{PORT}}, {{WORDLIST}}):",
        "snippet_dialog.ph_template": "z.B. nmap -sU -p {{PORT}} {{TARGET_IP}}",
        "snippet_dialog.lbl_desc": "Optionale Beschreibung / Notiz:",
        "snippet_dialog.ph_desc": "z.B. Scannt UDP-Port mit Versionserkennung",
        "snippet_dialog.lbl_tags": "Tags (durch Komma getrennt):",
        "snippet_dialog.ph_tags": "z.B. nmap, udp, recon",
        "snippet_dialog.err_title": "Bitte gib einen Titel für den Befehl ein.",
        "snippet_dialog.err_template": "Bitte gib den auszuführenden Befehl ein.",

        # Add Loot Dialog
        "loot_dialog.title_new": "SPECTRE // NEUEN SESSION-LOOT ERFASSEN",
        "loot_dialog.title_edit": "SPECTRE // SESSION-LOOT BEARBEITEN",
        "loot_dialog.lbl_type": "Typ des Eintrags:",
        "loot_dialog.lbl_category": "Pentest-Phase / Kategorie:",
        "loot_dialog.lbl_name": "Titel / Bezeichner:",
        "loot_dialog.ph_name": "z.B. SSH Key user 'alice', MySQL Root Password, user.txt",
        "loot_dialog.lbl_content": "Inhalt / Passwort / Hash / Flag / Notiz:",
        "loot_dialog.ph_content": "z.B. admin:SuperSecretPass! oder THM{fl4g_h3r3}",
        "loot_dialog.lbl_target": "Zugehöriges Target (optional):",
        "loot_dialog.ph_target": "10.10.10.x",
        "loot_dialog.err_title": "Bitte gib einen Titel für den Eintrag ein.",
        "loot_dialog.err_content": "Bitte gib den Inhalt / Wert ein.",

        # New Project Dialog
        "project.archive": "📦 Box archivieren (.zip)...",
        "project.archive_title": "Box als ZIP archivieren",
        "project.archive_success_title": "Archiv erstellt",
        "project.archive_error_title": "Archivierung fehlgeschlagen",
        "project_dialog.title": "SPECTRE // NEUES PROJEKT / BOX ERSTELLEN",
        "project_dialog.lbl_name": "Projekt- / Box-Name:",
        "project_dialog.ph_name": "z. B. PickleRick, Blue, Lame, InternalAudit...",
        "project_dialog.lbl_target": "Target IP:",
        "project_dialog.ph_target": "z. B. 10.10.10.80",
        "project_dialog.lbl_dir": "Basis-Verzeichnis für Projekte:",
        "project_dialog.ph_dir": "Pfad zum Workspace-Ordner...",
        "project_dialog.preview_path": "Zielpfad: {path}",
        "project_dialog.err_name": "Bitte gib einen Namen für das Projekt / die Box ein.",

        # Param Prompt Dialog
        "param_dialog.title": "SPECTRE // PARAMETER AUSFÜLLEN",
        "param_dialog.lbl_param": "Wert für {{{name}}}:",
        "param_dialog.ph_param": "Wert für {name}...",
        "param_dialog.lbl_preview": "Live-Befehlsvorschau:",
        "param_dialog.btn_copy": "Übernehmen & Kopieren",

        # Settings Dialog
        "settings.title": "SPECTRE // EINSTELLUNGEN & OPTIONEN",
        "settings.nav_hotkeys": "Hotkeys & Shortcuts",
        "settings.nav_language": "Sprache & Region",
        "settings.nav_general": "Allgemein & Verhalten",
        "settings.save_apply": "Speichern & Übernehmen",
        "settings.lbl_global_hotkeys": "Globale Tastenkombinationen (Systemweit)",
        "settings.lbl_toggle_hotkey": "SpectreHUD Ein-/Ausblenden:",
        "settings.lbl_snip_hotkey": "Screenshot Snip-Tool:",
        "settings.lbl_quit_shortcut": "SpectreHUD vollständig beenden:",
        "settings.lbl_local_shortcuts": "HUD-Interne Tastenkombinationen (Im Fenster)",
        "settings.btn_reset_defaults": "Standard-Hotkeys wiederherstellen",
        "settings.lbl_language_section": "Sprach- und Regionaleinstellungen",
        "settings.lbl_ui_language": "Oberflächensprache / UI Language:",
        "settings.lbl_date_format": "Datums- und Zeitformat:",
        "settings.lbl_behavior_section": "Overlay-Verhalten & Anzeige",
        "settings.chk_always_on_top": "Overlay immer über allen anderen Fenstern im Vordergrund halten",
        "settings.chk_auto_hide": "Overlay nach dem Kopieren eines Befehls automatisch minimieren",
        "settings.lbl_defaults_section": "Standard-Parameter",
        "settings.lbl_default_target": "Standard Target IP:",
        "settings.lbl_default_attacker": "Standard LHOST IP:",
        "settings.lbl_default_wordlist": "Standard Wordlist-Pfad:",

        # System Tray Menu
        "tray.show": "SpectreHUD anzeigen ({hotkey})",
        "tray.snip": "Screenshot aufnehmen (Strg+Super+X)",
        "tray.rec_start": "Clipboard-Logger aktivieren (Ctrl+P)",
        "tray.rec_pause": "Clipboard-Logger pausieren (Ctrl+P)",
        "tray.options": "Optionen & Hotkeys... (Ctrl+,)",
        "tray.quit": "Beenden (Strg+Super+Q)",
    },
    "en": {
        # Header & Navigation
        "header.brand": "SPECTRE // HUD",
        "header.box_label": "Box: {name}",
        "header.mode_cheatsheet": "Cheatsheet",
        "header.mode_loot": "Loot",
        "header.mode_history": "History",
        "header.mode_report": "Report",
        "header.snip": "Snip",
        "header.rec_on": "REC: ON",
        "header.rec_off": "REC: Off",
        "header.rec_paused": "REC: Paused",
        "header.opt": "⚙",
        "header.close_tip": "Minimize / hide overlay (Esc)",
        "header.snip_tip": "Capture region screenshot (Ctrl+Super+X or Ctrl+S)",
        "header.rec_tip_paused": "Clipboard logger is PAUSED (not recording).\nClick or Ctrl+P to start recording.",
        "header.rec_tip_active": "Clipboard logger is ACTIVE (recording).\nClick or Ctrl+P to pause.",
        "header.opt_tip": "Open settings & options (Ctrl+,)",
        "header.report_tip": "Open editable markdown pentest report for active box (Ctrl+4)",

        # Project Menu
        "project.new_project": "+ Create new project / box...",
        "project.import_folder": "Import / open existing project folder...",
        "project.import_title": "Select Project Folder",
        "project.open_folder": "Open project folder in file manager",

        # Variable Bar
        "varbar.target": "Target:",
        "varbar.attacker": "LHOST:",
        "varbar.port": "Port:",
        "varbar.user": "User:",
        "varbar.pass": "Pass:",
        "varbar.pass_toggle_tip": "Toggle password visibility",
        "varbar.auto": "Auto",
        "varbar.auto_tip": "Auto-detect tun0 / VPN / local IP",
        "varbar.no_ip": "No IP",
        "varbar.add_btn": "+ New",
        "varbar.add_btn_tip": "Create new command snippet (Ctrl+N)",
        "card.tweak_tip": "Tweak command before copying",

        # Search Bar
        "search.cheatsheet_placeholder": "Search commands, tools or syntax (e.g. 'curl', 'nmap', 'sql')...",
        "search.loot_placeholder": "Search session loot, credentials, hashes & notes...",
        "search.history_placeholder": "Search clipboard history, copied commands & outputs...",

        # Filter Pills
        "filter.all_commands": "All Commands",
        "filter.favorites": "★ Favorites",
        "filter.all_loot": "All ({count})",
        "filter.target_only": "Target IP Only",
        "filter.all_history": "All ({count})",
        "filter.commands_only": "Commands",
        "filter.outputs_only": "Outputs",

        # Privacy Warning Banner
        "privacy.warning": "Privacy Notice: Copied passwords or personal data are logged while REC is active (Pause with Ctrl+P or click REC: ON).",

        # Footer
        "footer.status": "{hotkey}: Toggle | Ctrl+Super+Q: Quit | Ctrl+P: REC Toggle | Ctrl+S: Snip | Esc: Hide",
        "footer.entries_count": "{count} entries",
        "footer.entry_count_single": "1 entry",
        "footer.always_on_top": "Always on Top",
        "footer.always_on_top_tip": "Keep overlay always in foreground over other windows",

        # Cards & Badges
        "card.copy": "Copy",
        "card.copied": "Copied!",
        "card.edit": "Edit",
        "card.open": "Open",
        "card.add_loot": "+ Loot",
        "card.delete_tip": "Delete",
        "card.copy_tip": "Copy command with current variables to clipboard",

        # Report Editor Tab
        "report.regenerate": "Regenerate from Loot",
        "report.regenerate_tip": "Updates report structure and appends new loot entries",
        "report.export_copy": "Export Copy...",
        "report.export_copy_tip": "Creates a new copy based on current session loot",
        "report.save": "Save",
        "report.save_tip": "Save changes to active box report.md (Ctrl+S)",
        "report.saved": "Saved",
        "report.unsaved": "Unsaved changes",
        "report.empty_title": "No active project",
        "report.empty_desc": "Select a box above to view and edit the pentest report.",
        "report.discard_title": "Unsaved Changes",
        "report.discard_msg": "You have unsaved changes in the current report. Do you want to switch tabs and discard them?",

        # Dialog Common
        "dialog.cancel": "Cancel",
        "dialog.save": "Save",
        "dialog.update": "Update",
        "dialog.create": "Create Project",
        "dialog.browse": "Browse...",
        "dialog.error": "Error",

        # Add Snippet Dialog
        "snippet_dialog.title": "SPECTRE // ADD NEW COMMAND",
        "snippet_dialog.lbl_title": "Title / Command Name:",
        "snippet_dialog.ph_title": "e.g. Nmap UDP Scan with Scripts",
        "snippet_dialog.lbl_category": "Category:",
        "snippet_dialog.lbl_subcategory": "Subcategory / Group:",
        "snippet_dialog.ph_subcategory": "e.g. Port Scanning or Web Recon",
        "snippet_dialog.lbl_template": "Command / Template (supports {{TARGET_IP}}, {{ATTACKER_IP}}, {{PORT}}, {{WORDLIST}}):",
        "snippet_dialog.ph_template": "e.g. nmap -sU -p {{PORT}} {{TARGET_IP}}",
        "snippet_dialog.lbl_desc": "Optional Description / Note:",
        "snippet_dialog.ph_desc": "e.g. Scans UDP port with version detection",
        "snippet_dialog.lbl_tags": "Tags (comma separated):",
        "snippet_dialog.ph_tags": "e.g. nmap, udp, recon",
        "snippet_dialog.err_title": "Please enter a title for the command.",
        "snippet_dialog.err_template": "Please enter the template command.",

        # Add Loot Dialog
        "loot_dialog.title_new": "SPECTRE // CAPTURE SESSION LOOT",
        "loot_dialog.title_edit": "SPECTRE // EDIT SESSION LOOT",
        "loot_dialog.lbl_type": "Entry Type:",
        "loot_dialog.lbl_category": "Pentest Phase / Category:",
        "loot_dialog.lbl_name": "Title / Identifier:",
        "loot_dialog.ph_name": "e.g. SSH Key user 'alice', MySQL Root Password, user.txt",
        "loot_dialog.lbl_content": "Content / Password / Hash / Flag / Note:",
        "loot_dialog.ph_content": "e.g. admin:SuperSecretPass! or THM{fl4g_h3r3}",
        "loot_dialog.lbl_target": "Associated Target (optional):",
        "loot_dialog.ph_target": "10.10.10.x",
        "loot_dialog.err_title": "Please enter a title for the loot entry.",
        "loot_dialog.err_content": "Please enter the content / value.",

        # New Project Dialog
        "project.archive": "📦 Archive Box (.zip)...",
        "project.archive_title": "Archive Box to ZIP",
        "project.archive_success_title": "Archive Created",
        "project.archive_error_title": "Archiving Failed",
        "project_dialog.title": "SPECTRE // CREATE NEW PROJECT / BOX",
        "project_dialog.lbl_name": "Project / Box Name:",
        "project_dialog.ph_name": "e.g. PickleRick, Blue, Lame, InternalAudit...",
        "project_dialog.lbl_target": "Target IP:",
        "project_dialog.ph_target": "e.g. 10.10.10.80",
        "project_dialog.lbl_dir": "Base Directory for Projects:",
        "project_dialog.ph_dir": "Path to workspace directory...",
        "project_dialog.preview_path": "Destination path: {path}",
        "project_dialog.err_name": "Please enter a name for the project / box.",

        # Param Prompt Dialog
        "param_dialog.title": "SPECTRE // FILL COMMAND PARAMETERS",
        "param_dialog.lbl_param": "Value for {{{name}}}:",
        "param_dialog.ph_param": "Value for {name}...",
        "param_dialog.lbl_preview": "Live Command Preview:",
        "param_dialog.btn_copy": "Apply & Copy",

        # Settings Dialog
        "settings.title": "SPECTRE // SETTINGS & OPTIONS",
        "settings.nav_hotkeys": "Hotkeys & Shortcuts",
        "settings.nav_language": "Language & Region",
        "settings.nav_general": "General & Behavior",
        "settings.save_apply": "Save & Apply",
        "settings.lbl_global_hotkeys": "Global Shortcuts (System-wide)",
        "settings.lbl_toggle_hotkey": "SpectreHUD Toggle Overlay:",
        "settings.lbl_snip_hotkey": "Screenshot Snip-Tool:",
        "settings.lbl_quit_shortcut": "Quit SpectreHUD Completely:",
        "settings.lbl_local_shortcuts": "In-App Shortcuts (Inside HUD)",
        "settings.btn_reset_defaults": "Restore Default Hotkeys",
        "settings.lbl_language_section": "Language and Regional Settings",
        "settings.lbl_ui_language": "User Interface Language:",
        "settings.lbl_date_format": "Date & Time Format:",
        "settings.lbl_behavior_section": "Overlay Behavior & Display",
        "settings.chk_always_on_top": "Keep overlay always in foreground over other windows",
        "settings.chk_auto_hide": "Automatically minimize overlay after copying command",
        "settings.lbl_defaults_section": "Default Parameters",
        "settings.lbl_default_target": "Default Target IP:",
        "settings.lbl_default_attacker": "Default LHOST IP:",
        "settings.lbl_default_wordlist": "Default Wordlist Path:",

        # System Tray Menu
        "tray.show": "Show SpectreHUD ({hotkey})",
        "tray.snip": "Capture Screenshot (Ctrl+Super+X)",
        "tray.rec_start": "Enable Clipboard Logger (Ctrl+P)",
        "tray.rec_pause": "Pause Clipboard Logger (Ctrl+P)",
        "tray.options": "Options & Hotkeys... (Ctrl+,)",
        "tray.quit": "Quit (Ctrl+Super+Q)",
    }
}


class I18nManager(QObject):
    """
    Central Internationalization (i18n) Manager for SpectreHUD.
    Provides reactive translation lookup, fallback handling, and runtime locale switching.
    """
    locale_changed = pyqtSignal(str)

    def __init__(self, default_locale: str = DEFAULT_LOCALE):
        super().__init__()
        self._current_locale = default_locale if default_locale in SUPPORTED_LOCALES else DEFAULT_LOCALE

    @property
    def current_locale(self) -> str:
        return self._current_locale

    def set_locale(self, locale_code: str) -> None:
        clean = str(locale_code).lower().strip()
        if clean in SUPPORTED_LOCALES and clean != self._current_locale:
            self._current_locale = clean
            logger.info(f"Language changed to: {SUPPORTED_LOCALES[clean]} ({clean})")
            self.locale_changed.emit(clean)

    def t(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Translates a key for the current locale with fallback to German or key itself.
        Supports parameter interpolation with kwargs.
        """
        loc_dict = TRANSLATIONS.get(self._current_locale, {})
        text = loc_dict.get(key)
        
        if text is None:
            # Fallback to German
            text = TRANSLATIONS.get("de", {}).get(key)

        if text is None:
            # Fallback to provided default or raw key
            text = default if default is not None else key

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, IndexError) as e:
                logger.warning(f"Failed to format translation string for key '{key}': {e}")
                return text

        return text


# Global singleton instance
_i18n_instance: Optional[I18nManager] = None

def get_i18n() -> I18nManager:
    """Returns the global i18n manager instance, ensuring it is always a valid live QObject."""
    global _i18n_instance
    if _i18n_instance is not None:
        try:
            # Accessing pyqtSignal touches C++ metadata and raises RuntimeError if deleted
            _ = _i18n_instance.locale_changed
        except (RuntimeError, AttributeError):
            _i18n_instance = None

    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance

def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    """Convenience global translation function."""
    return get_i18n().t(key, default=default, **kwargs)

def set_locale(locale_code: str) -> None:
    """Sets the global active locale."""
    get_i18n().set_locale(locale_code)

def get_locale() -> str:
    """Returns the current active locale code."""
    return get_i18n().current_locale