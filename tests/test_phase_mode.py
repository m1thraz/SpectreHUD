"""
Comprehensive test suite for Pentest Phase Mode in SpectreHUD.

Covers:
- PhaseContext state management, aliases, normalization, event bus
- Hotkey configuration and phase triggers (1..6)
- Quick Loot default phase inheritance
- Quick Notes default phase preselection & submission
- Clipboard History active phase tagging & persistence
- ProjectSessionService load/save active_phase in project_state.json
- PhaseToastHUD non-activating flags & display lifecycle
"""

import json
from pathlib import Path
from PyQt6.QtCore import Qt

from core.phase_context import PhaseContext
from core.event_bus import EventBus, EventType
from core.hotkey_listener import HotkeyConfig, HotkeyListener
from core.clipboard_history import ClipboardHistory
from core.validators import validate_project_state
from core.project.session_service import ProjectSessionService
from ui.phase_toast_hud import PhaseToastHUD
from ui.history_card import HistoryCard
from ui.clipboard_monitor import ClipboardMonitor


def test_phase_context_set_and_clear():
    bus = EventBus()
    events = []
    bus.subscribe(EventType.ACTIVE_PHASE_CHANGED, events.append)

    ctx = PhaseContext(event_bus=bus)
    assert ctx.active_phase_id is None

    # Set phase 1 (recon)
    assert ctx.set_active_phase("recon", source="hotkey") is True
    assert ctx.active_phase_id == "recon"
    assert len(events) == 1
    assert events[-1] == {"phase_id": "recon", "source": "hotkey"}

    # Setting same phase again is no-op
    assert ctx.set_active_phase("recon") is False
    assert len(events) == 1

    # Aliases
    assert ctx.set_active_phase("privilege_escalation") is True
    assert ctx.active_phase_id == "privesc"

    # Numeric order strings
    assert ctx.set_active_phase("2") is True
    assert ctx.active_phase_id == "access"

    # Invalid phase string rejected
    assert ctx.set_active_phase("nonexistent_phase_foo") is False
    assert ctx.active_phase_id == "access"

    # Clear active phase
    assert ctx.clear_active_phase(source="menu") is True
    assert ctx.active_phase_id is None
    assert events[-1] == {"phase_id": None, "source": "menu"}


def test_hotkey_phase_switching_and_signals(qapp):
    cfg = HotkeyConfig()
    assert cfg.phase_1 == "<ctrl>+<alt>+1"
    assert cfg.phase_2 == "<ctrl>+<alt>+2"
    assert cfg.phase_3 == "<ctrl>+<alt>+3"
    assert cfg.phase_4 == "<ctrl>+<alt>+4"
    assert cfg.phase_5 == "<ctrl>+<alt>+5"
    assert cfg.phase_6 == "<ctrl>+<alt>+6"

    listener = HotkeyListener(config=cfg)
    emitted = []
    listener.phase_requested.connect(emitted.append)

    for order in range(1, 7):
        listener._fire_phase_trigger(order)

    assert emitted == [1, 2, 3, 4, 5, 6]


def test_clipboard_monitor_and_history_phase_tagging(qapp, tmp_path):
    storage_file = tmp_path / "clipboard_history.json"
    history = ClipboardHistory(storage_file=storage_file)

    ctx = PhaseContext()
    ctx.set_active_phase("privesc")

    monitor = ClipboardMonitor(history=history)
    monitor.set_phase_provider(lambda: ctx.active_phase_id)
    monitor._is_paused = False

    # Emulate capture with active phase
    entry = history.add_entry("whoami /priv", phase_id=ctx.active_phase_id, persist=True)
    assert entry is not None
    assert entry.get("phase_id") == "privesc"

    # Reload from disk and ensure validator preserves phase_id
    reloaded_history = ClipboardHistory(storage_file=storage_file)
    reloaded_entries = reloaded_history.get_all_history()
    assert len(reloaded_entries) == 1
    assert reloaded_entries[0].get("phase_id") == "privesc"

    # Verify HistoryCard retains the phase in its compact metadata line.
    card = HistoryCard(entry=reloaded_entries[0])
    assert "PRIVESC" in card.lbl_meta.text()


def test_project_session_service_active_phase_persistence(tmp_path):
    from unittest.mock import MagicMock
    from core.project import ProjectManager

    proj_mgr = ProjectManager(base_dir=tmp_path / "projects", config_dir=tmp_path / "config")
    proj_mgr.create_project("test_box")
    proj_mgr.active_project = "test_box"

    bus = EventBus()
    events = []
    bus.subscribe(EventType.ACTIVE_PHASE_CHANGED, events.append)

    ctx = PhaseContext(event_bus=bus)
    ctx.set_active_phase("postex")

    dummy_loot = MagicMock()
    dummy_loot.get_all_entries.return_value = []
    dummy_clipboard = MagicMock()
    dummy_clipboard.get_all_entries.return_value = []
    dummy_notes = MagicMock()
    dummy_notes.get_all_entries.return_value = []

    session_service = ProjectSessionService(
        project_manager=proj_mgr,
        loot_manager=dummy_loot,
        clipboard_history=dummy_clipboard,
        quick_note_manager=dummy_notes,
        phase_context=ctx,
    )

    # Save session
    saved = session_service.save_project_session({"target_ip": "10.10.10.50"})
    assert saved.success

    # Check project_state.json contains active_phase
    proj_dir = Path(proj_mgr.get_project_dir("test_box"))
    state_file = proj_dir / "project_state.json"
    assert state_file.exists()
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("active_phase") == "postex"
    validated = validate_project_state(data)
    assert validated.get("active_phase") == "postex"

    # Clear context and load session
    ctx.clear_active_phase(notify=False)
    assert ctx.active_phase_id is None

    session_service.load_project_session("test_box")
    assert ctx.active_phase_id == "postex"
    # Event should have source="project_load"
    assert events[-1] == {"phase_id": "postex", "source": "project_load"}


def test_phase_toast_hud_properties(qapp):
    hud = PhaseToastHUD()
    flags = hud.windowFlags()

    assert bool(flags & Qt.WindowType.FramelessWindowHint) is True
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint) is True
    assert bool(flags & Qt.WindowType.Tool) is True
    assert bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus) is True

    # Test show_phase updates UI and badge
    hud.show_phase("access")
    assert hud.badge.text() == "ACCESS"
    assert "2." in hud.lbl_phase_name.text()

    # Rapid change to recon resets text
    hud.show_phase("recon")
    assert hud.badge.text() == "RECON"
    assert "1." in hud.lbl_phase_name.text()

    # Clear to unassigned
    hud.show_phase(None)
    assert hud.badge.text() == "NONE"

    hud.show_recording(True)
    assert hud.badge.text() == "REC"
    assert "Recording" in hud.lbl_phase_name.text()

    hud.show_phase("access")
    assert "PHASE" in hud.lbl_category.text()

    hud.close()


def test_quick_note_controller_phase_inheritance(qapp, tmp_path):
    from core.quick_note_manager import QuickNoteManager
    from ui.controllers.quick_note_controller import QuickNoteController

    manager = QuickNoteManager(storage_file=tmp_path / "notes.json")
    ctx = PhaseContext()
    ctx.set_active_phase("privesc")

    ctrl = QuickNoteController(
        quick_note_manager=manager,
        phase_provider=lambda: ctx.active_phase_id,
    )

    # Adding entry with category=None uses active phase
    entry1 = ctrl.add_entry(text="Test note 1")
    assert entry1["category"] == "privesc"

    # Explicit category overrides active phase
    entry2 = ctrl.add_entry(text="Test note 2", category="recon")
    assert entry2["category"] == "recon"

    # When active phase is cleared, fallback is last_category ('recon')
    ctx.clear_active_phase()
    entry3 = ctrl.add_entry(text="Test note 3")
    assert entry3["category"] == "recon"


def test_loot_controller_phase_inheritance(qapp, tmp_path):
    from unittest.mock import MagicMock, patch
    from core.loot.manager import LootManager
    from core.project import ProjectManager
    from ui.controllers.loot_controller import LootController

    loot_mgr = LootManager(storage_file=tmp_path / "loot.json")
    proj_mgr = ProjectManager(base_dir=tmp_path / "projects", config_dir=tmp_path / "config")
    ctx = PhaseContext()
    ctx.set_active_phase("access")

    ctrl = LootController(
        loot_manager=loot_mgr,
        project_manager=proj_mgr,
        phase_provider=lambda: ctx.active_phase_id,
    )

    with patch("ui.controllers.loot_controller.AddLootDialog") as MockDialog:
        mock_instance = MagicMock()
        mock_instance.isVisible.return_value = False
        mock_instance.width.return_value = 400
        mock_instance.height.return_value = 300
        MockDialog.return_value = mock_instance

        # Default category 'misc' is overridden by active phase 'access'
        ctrl.open_add_dialog(modal=False)
        _, kwargs = MockDialog.call_args
        assert kwargs.get("default_category") == "access"

        # Explicit non-misc category is preserved
        ctrl.open_add_dialog(default_category="postex", modal=False)
        _, kwargs = MockDialog.call_args
        assert kwargs.get("default_category") == "postex"
