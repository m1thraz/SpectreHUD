from PyQt6.QtWidgets import QApplication

from core.shortcuts import (
    VALID_CATEGORIES,
    VALID_SCOPES,
    ShortcutDefinition,
    format_hotkey_sequence,
    get_shortcuts,
)
from ui.shortcuts_dialog import ShortcutHelpDialog

app = QApplication.instance() or QApplication([])


class DummyConfigManager:
    """Mock ConfigManager for testing shortcut configuration loading."""

    def __init__(self, hotkeys=None):
        self._hotkeys = hotkeys or {}

    def get(self, key, default=None):
        return self._hotkeys.get(key, default)


def test_format_hotkey_sequence():
    assert format_hotkey_sequence("<ctrl>+<alt>+1") == "Ctrl+Alt+1"
    assert format_hotkey_sequence("<ctrl>+/") == "Ctrl+/"
    assert format_hotkey_sequence("ctrl+shift+f") == "Ctrl+Shift+F"
    assert format_hotkey_sequence("<ctrl>+c") == "Ctrl+C"
    assert format_hotkey_sequence("<esc>") == "Esc"
    assert format_hotkey_sequence("f1") == "F1"


def test_core_shortcuts_definitions():
    shortcuts = get_shortcuts()
    assert len(shortcuts) > 0

    seen_ids = set()
    for s in shortcuts:
        assert isinstance(s, ShortcutDefinition)
        assert s.id not in seen_ids, f"Duplicate shortcut id: {s.id}"
        seen_ids.add(s.id)
        assert s.sequence, f"Empty sequence for {s.id}"
        assert s.category in VALID_CATEGORIES
        assert s.scope in VALID_SCOPES
        assert s.label_key.startswith("shortcuts.")


def test_core_shortcuts_config_reflection():
    cfg = DummyConfigManager({
        "hotkey": "<ctrl>+<alt>+x",
        "quick_loot_hotkey": "<ctrl>+<alt>+l",
    })
    shortcuts = get_shortcuts(cfg)
    shortcut_map = {s.id: s for s in shortcuts}

    assert shortcut_map["global_toggle"].sequence == "Ctrl+Alt+X"
    assert shortcut_map["global_quick_loot"].sequence == "Ctrl+Alt+L"


def test_shortcuts_dialog_lifecycle():
    dialog = ShortcutHelpDialog()

    # Initial dialog state
    assert "SHORTCUT" in dialog.lbl_dialog_title.text().upper()
    assert dialog.txt_search is not None
    assert len(dialog._sections) > 0

    all_rows = [row for sec in dialog._sections for row in sec.rows]
    assert len(all_rows) > 0

    # Ensure all rows are initially visible
    for row in all_rows:
        assert not row.isHidden()

    # Search filter matching
    dialog.txt_search.setText("loot")
    visible_count = sum(1 for row in all_rows if not row.isHidden())
    assert 0 < visible_count < len(all_rows)

    # Clear search
    dialog.txt_search.clear()
    visible_count_after_clear = sum(1 for row in all_rows if not row.isHidden())
    assert visible_count_after_clear == len(all_rows)

    # Close dialog
    dialog.close()


def test_shortcuts_dialog_empty_search():
    dialog = ShortcutHelpDialog()
    all_rows = [row for sec in dialog._sections for row in sec.rows]

    dialog.txt_search.setText("nonexistent_term_xyz_123")
    visible_count = sum(1 for row in all_rows if not row.isHidden())
    assert visible_count == 0

    dialog.close()


def test_footer_panel_shortcuts_integration():
    from ui.panels.footer_panel import FooterPanel

    footer = FooterPanel()
    assert hasattr(footer, "btn_shortcuts")
    assert hasattr(footer, "shortcuts_requested")
    assert hasattr(footer, "lbl_status")

    # Verify signal emission on click
    emitted = []
    footer.shortcuts_requested.connect(lambda: emitted.append(True))
    footer.btn_shortcuts.click()
    assert len(emitted) == 1

    # Verify update_hotkey_display doesn't crash and preserves button text
    footer.update_hotkey_display("<ctrl>+<alt>+h")
    assert "Ctrl+/" in footer.btn_shortcuts.text() or "Shortcuts" in footer.btn_shortcuts.text()

