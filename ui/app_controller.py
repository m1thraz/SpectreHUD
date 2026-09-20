"""
Central Application Orchestrator for SpectreHUD.

Orchestrates UI panels, domain managers, and specialized coordinators.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtCore import QObject, Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QPushButton

from core.config import ConfigManager
from core.snippets import SnippetManager
from core.loot import LootManager
from core.clipboard_history import ClipboardHistory
from core.project import ProjectManager
from core.screenshots import ScreenshotManager, ScreenshotTransactionService
from core.project import ProjectSessionService
from core.i18n import get_i18n, get_locale, t
from core.logger import get_logger
from core.event_bus import ActivePhaseChangedPayload, EventBus, EventType
from core.phase_context import PhaseContext
from core.storage import PersistenceError

from ui.phase_toast_hud import PhaseToastHUD
from ui.message_boxes import show_error_dialog
from ui.variable_bar import VariableBar
from ui.clipboard_monitor import ClipboardMonitor
from ui.panels.header_panel import HeaderPanel
from ui.panels.search_panel import SearchPanel
from ui.panels.content_panel import ContentPanel
from ui.panels.footer_panel import FooterPanel
from ui.settings_dialog import SettingsDialog
from ui.content_renderer import CallbackContentRenderer, ContentRenderer, RenderResult
from ui.controllers import (
    CheatsheetController,
    LootController,
    HistoryController,
    QuickNoteController,
    ReportController,
    ProjectController,
)
from ui.coordinators import (
    WorkspaceCoordinator,
    NavigationCoordinator,
    ClipboardCoordinator,
    ExportCoordinator,
    SettingsCoordinator,
)

logger = get_logger(__name__)


class AppController(QObject):
    """
    Lean central orchestrator coordinating UI panels and workflow coordinators.
    """

    mode_changed = pyqtSignal(str)
    content_refreshed = pyqtSignal()
    restart_requested = pyqtSignal()

    def __init__(
        self,
        window: QWidget,
        header_panel: HeaderPanel,
        search_panel: SearchPanel,
        var_bar: VariableBar,
        content_panel: ContentPanel,
        footer_panel: FooterPanel,
        config_manager: ConfigManager,
        snippet_manager: SnippetManager,
        loot_manager: LootManager,
        clipboard_history: ClipboardHistory,
        clipboard_monitor: ClipboardMonitor,
        project_manager: ProjectManager,
        screenshot_manager: ScreenshotManager,
        event_bus: EventBus,
        quick_note_manager: Optional[Any] = None,
        phase_context: Optional[PhaseContext] = None,
    ):
        super().__init__(window)
        self.window = window
        self.header = header_panel
        self.search = search_panel
        self.var_bar = var_bar
        self.content = content_panel
        self.footer = footer_panel

        self.config = config_manager
        self.snippet_manager = snippet_manager
        self.project_manager = project_manager
        self.loot_manager = loot_manager
        self.clipboard_history = clipboard_history
        self.clipboard_monitor = clipboard_monitor
        self.quick_note_manager = quick_note_manager
        self.screenshot_manager = screenshot_manager
        self.event_bus = event_bus
        self._i18n = get_i18n()
        self._unsubscribe_active_phase = None
        self._disposed = False

        self.phase_context = (
            phase_context if phase_context is not None else PhaseContext(event_bus=self.event_bus)
        )
        self.phase_hud = PhaseToastHUD()

        self.session_service = ProjectSessionService(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            clipboard_history=self.clipboard_history,
            quick_note_manager=self.quick_note_manager,
            phase_context=self.phase_context,
        )
        self.cards: List[QWidget] = []
        self._rendered_mode: Optional[str] = None
        self._quick_ip_popup: Optional[Any] = None
        self._quick_find_popup: Optional[Any] = None
        self._current_phase_id: Optional[str] = self.phase_context.active_phase_id
        self._recorded_in_session: int = 0

        # Specialized Coordinators & Providers
        self._target_provider = lambda: (
            self.var_bar.txt_target.text().strip() if hasattr(self.var_bar, "txt_target") else ""
        )
        self._phase_provider = lambda: self.phase_context.active_phase_id

        # Domain Controllers
        self.cheatsheet_ctrl = CheatsheetController(
            self.snippet_manager, event_bus=self.event_bus, parent=self
        )
        self.loot_ctrl = LootController(
            self.loot_manager,
            self.project_manager,
            phase_provider=self._phase_provider,
            event_bus=self.event_bus,
            parent=self,
        )
        self.report_ctrl = ReportController(
            self.project_manager,
            self.loot_manager,
            self.clipboard_history,
            parent_widget=self.window,
            config_manager=self.config,
        )
        self.quick_note_ctrl = QuickNoteController(
            quick_note_manager=self.quick_note_manager,
            loot_controller=self.loot_ctrl,
            report_controller=self.report_ctrl,
            target_provider=self._target_provider,
            phase_provider=self._phase_provider,
            event_bus=self.event_bus,
            parent=self,
        )
        self.clipboard_monitor.set_phase_provider(self._phase_provider)
        self.history_ctrl = HistoryController(
            clipboard_history=self.clipboard_history,
            clipboard_monitor=self.clipboard_monitor,
            loot_manager=self.loot_manager,
            project_manager=self.project_manager,
            event_bus=self.event_bus,
            parent=self,
        )
        self.project_ctrl = ProjectController(
            self.project_manager,
            event_bus=self.event_bus,
            parent=self,
            config_manager=self.config,
        )

        self.navigation_coord = NavigationCoordinator(
            header=self.header,
            search=self.search,
            var_bar=self.var_bar,
            content=self.content,
            report_ctrl=self.report_ctrl,
            event_bus=self.event_bus,
            on_mode_switched=self._on_mode_switched,
            parent=self,
        )
        self.workspace_coord = WorkspaceCoordinator(
            project_manager=self.project_manager,
            session_service=self.session_service,
            project_ctrl=self.project_ctrl,
            report_ctrl=self.report_ctrl,
            event_bus=self.event_bus,
            parent=self,
        )
        self.clipboard_coord = ClipboardCoordinator(
            clipboard_monitor=self.clipboard_monitor,
            history_ctrl=self.history_ctrl,
            loot_ctrl=self.loot_ctrl,
            target_provider=self._target_provider,
            quick_note_ctrl=self.quick_note_ctrl,
            phase_provider=self._phase_provider,
            parent=self,
        )
        self.export_coord = ExportCoordinator(
            project_manager=self.project_manager,
            loot_manager=self.loot_manager,
            history_ctrl=self.history_ctrl,
            target_provider=self._target_provider,
            config_manager=self.config,
            parent=self,
        )
        self.report_ctrl.set_export_coordinator(self.export_coord)
        self.screenshot_transaction = ScreenshotTransactionService(
            loot_manager=self.loot_manager,
            persist_project_state=self.save_current_project_state,
        )
        self.settings_coord = SettingsCoordinator(
            config=self.config,
            event_bus=self.event_bus,
            workspace_coord=self.workspace_coord,
            report_ctrl=self.report_ctrl,
            footer=self.footer,
            window=self.window,
            loot_manager=self.loot_manager,
            clipboard_history=self.clipboard_history,
            # Resolve callbacks at invocation time so tests and runtime
            # extensions can replace the controller boundary deliberately.
            update_footer_status=lambda: self._update_footer_status(),
            load_active_project_state=lambda: self.load_active_project_state(),
            refresh_filter_pills=lambda: self.refresh_filter_pills(),
            refresh_content=lambda: self.refresh_content(),
            retranslate_ui=lambda locale: self.retranslate_ui(locale),
        )

        self._renderers: Dict[str, ContentRenderer] = {
            "cheatsheet": CallbackContentRenderer(
                self._build_cheatsheet_pills, self._render_cheatsheet
            ),
            "loot": CallbackContentRenderer(self._build_loot_pills, self._render_loot),
            "history": CallbackContentRenderer(self._build_history_pills, self._render_history),
            "notes": CallbackContentRenderer(self._build_notes_pills, self._render_notes),
            "report": CallbackContentRenderer(lambda: None, self._render_report),
        }

        self._shortcuts_dialog = None
        self._wire_signals()

        # Synchronize initial language
        initial_lang = self.config.get("language", "en")
        self._i18n.set_locale(initial_lang)
        self.snippet_manager.set_language(initial_lang)

    @property
    def shortcuts_dialog(self):
        return self._shortcuts_dialog

    @property
    def active_mode(self) -> str:
        return self.navigation_coord.active_mode

    @active_mode.setter
    def active_mode(self, mode: str) -> None:
        self.navigation_coord.active_mode = mode

    def dispose(self) -> None:
        """Detach process-lifetime subscriptions before deferred Qt deletion."""
        if self._disposed:
            return
        self._disposed = True
        self._discard_cheatsheet_cache()

        if self._unsubscribe_active_phase is not None:
            self._unsubscribe_active_phase()
            self._unsubscribe_active_phase = None
        try:
            self._i18n.locale_changed.disconnect(self.retranslate_ui)
        except (TypeError, RuntimeError):
            pass

    def _wire_signals(self) -> None:
        # Header & Navigation
        self.header.mode_changed.connect(self.switch_mode)
        self.navigation_coord.mode_changed.connect(self.mode_changed.emit)
        self.header.project_menu_requested.connect(self._show_project_menu)
        self.header.screenshot_requested.connect(self.trigger_screenshot)
        self.header.quick_note_requested.connect(self.trigger_quick_note)
        self.header.toggle_rec_requested.connect(self.clipboard_coord.toggle_pause)
        self.header.settings_requested.connect(self.open_settings_dialog)
        self.header.minimize_requested.connect(self.window.hide)
        # request_quit(quit_app=True) must not receive QPushButton.clicked's bool
        self.header.close_requested.connect(lambda: self.window.request_quit())

        # Panels & Inputs
        self.search.search_changed.connect(lambda _: self.refresh_content())
        self.search.pills_width_changed.connect(self._on_pills_width_changed)
        self.var_bar.variables_changed.connect(self._on_variables_changed)
        self.var_bar.add_snippet_clicked.connect(self._on_add_button_clicked)
        self.var_bar.import_snippets_clicked.connect(self.on_import_snippets_clicked)
        self.footer.always_on_top_toggled.connect(self._on_always_on_top_toggled)
        self.footer.shortcuts_requested.connect(self.open_shortcuts_dialog)

        # Data & Controller Events
        self.cheatsheet_ctrl.snippets_updated.connect(self._on_data_updated)
        self.loot_ctrl.loot_updated.connect(self._on_loot_data_updated)
        self.history_ctrl.history_updated.connect(self._on_history_data_updated)
        self.quick_note_ctrl.notes_updated.connect(self._on_notes_updated)
        self.clipboard_coord.history_mutated.connect(self._on_history_data_updated)
        self.clipboard_coord.loot_mutated.connect(self._on_loot_data_updated)
        self.clipboard_coord.notes_mutated.connect(self._on_notes_updated)

        self.screenshot_manager.screenshot_saved.connect(self._on_screenshot_saved)
        # Clipboard callbacks may originate outside the GUI thread.  Always
        # cross the Qt boundary before the coordinator touches UI state.
        self.clipboard_monitor.entry_added.connect(
            self._on_clipboard_entry_added,
            Qt.ConnectionType.QueuedConnection,  # type: ignore[call-arg]
        )
        if self.quick_note_manager and hasattr(self.quick_note_manager, "entry_added"):
            self.quick_note_manager.entry_added.connect(
                lambda _: self._on_notes_updated(), Qt.ConnectionType.QueuedConnection
            )
        self.clipboard_monitor.logging_state_changed.connect(self._on_logging_state_changed)
        self._last_doc_activity_time = time.time()
        self._nudge_timer = QTimer(self)
        self._nudge_timer.setInterval(30000)
        self._nudge_timer.timeout.connect(self._check_rec_nudge)
        self._nudge_timer.start()

        self.footer.phase_menu_requested.connect(self._show_phase_menu)
        self.content.scroll_area.verticalScrollBar().valueChanged.connect(
            self._maybe_load_more_cheatsheet
        )
        if hasattr(self.header, "phase_menu_requested"):
            self.header.phase_menu_requested.connect(self._show_phase_menu)
        self._unsubscribe_active_phase = self.event_bus.subscribe(
            EventType.ACTIVE_PHASE_CHANGED, self._on_active_phase_changed
        )
        self._i18n.locale_changed.connect(self.retranslate_ui)

    def activate_phase(self, phase_id: Optional[str], source: str = "ui") -> None:
        """Activates a pentest phase, updating the active project context."""
        self.phase_context.set_active_phase(phase_id, source=source)

    def activate_phase_by_order(self, order: int, source: str = "hotkey") -> None:
        """Activates a pentest phase by 1-based order index (1..6)."""
        from core.phases import PHASES

        for phase in PHASES:
            if phase.order == order:
                changed = self.phase_context.set_active_phase(phase.key, source=source)
                if not changed and source == "hotkey":
                    self.phase_hud.show_phase(phase.key)
                return

    def _on_active_phase_changed(self, payload: ActivePhaseChangedPayload) -> None:
        """Handles phase change event from event bus."""
        phase_id = payload.phase_id
        source = payload.source
        old_phase = getattr(self, "_current_phase_id", None)
        self._current_phase_id = phase_id

        self.footer.set_phase(phase_id)
        if hasattr(self.header, "set_phase"):
            self.header.set_phase(phase_id)
        if source == "hotkey":
            self.phase_hud.show_phase(phase_id)

        if old_phase and old_phase != phase_id:
            self._check_phase_switch_nudge(old_phase, phase_id)

    def _show_phase_menu(self, button: QPushButton) -> None:
        """Opens the phase selection popup menu over the footer phase button."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        from core.phases import PHASES

        menu = QMenu(self.window)
        menu.setProperty("class", "SecondaryMenu")

        active_id = self.phase_context.active_phase_id

        for phase in PHASES:
            label = f"{phase.order}. {phase.long} ({phase.short})"
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(active_id == phase.key)
            act.triggered.connect(
                lambda checked, k=phase.key: self.activate_phase(k, source="phase_menu")
            )

        menu.addSeparator()
        act_none = menu.addAction(t("phases.unassigned", "Unassigned"))
        act_none.setCheckable(True)
        act_none.setChecked(active_id is None)
        act_none.triggered.connect(lambda: self.activate_phase(None, source="phase_menu"))

        size = menu.sizeHint()
        pos = button.mapToGlobal(QPoint(0, -size.height() - 4))
        menu.exec(pos)

    def open_shortcuts_dialog(self) -> None:
        """Opens or focuses the central shortcut overview dialog."""
        if (
            hasattr(self, "_shortcuts_dialog")
            and self._shortcuts_dialog is not None
            and self._shortcuts_dialog.isVisible()
        ):
            self._shortcuts_dialog.raise_()
            self._shortcuts_dialog.activateWindow()
            return

        from ui.shortcuts_dialog import ShortcutHelpDialog

        self._shortcuts_dialog = ShortcutHelpDialog(config_manager=self.config, parent=self.window)
        self._shortcuts_dialog.show()

    def trigger_quick_note(self) -> None:
        """Opens the lightweight quick note capture popup."""
        if hasattr(self, "quick_note_ctrl") and self.quick_note_ctrl:
            self.quick_note_ctrl.show_popup()

    def trigger_quick_ip(self) -> None:
        """Opens the lightweight quick IP popup."""
        self._open_quick_ip_popup()

    def trigger_quick_loot(self) -> None:
        """Opens the Add-Loot dialog non-modally as a floating remote control."""
        target_ip = self._target_provider()
        default_cat = self.phase_context.active_phase_id or "misc"
        self.loot_ctrl.open_add_dialog(
            parent_widget=None,
            target_ip=target_ip,
            default_category=default_cat,
            modal=False,
            on_accepted=lambda _data: self._on_loot_data_updated(),
        )

    def trigger_quick_find(self) -> None:
        """Opens the lightweight quick-find snippet HUD popup."""
        self._open_quick_find_popup()

    def _get_quick_find_variables(self) -> Dict[str, Any]:
        vars_dict = (
            self.var_bar.get_variables()
            if self.var_bar and hasattr(self.var_bar, "get_variables")
            else {}
        )
        if hasattr(self, "config") and self.config and hasattr(self.config, "session_param_cache"):
            merged = dict(self.config.session_param_cache)
            merged.update(vars_dict)
            return merged
        return vars_dict

    def _open_quick_find_popup(self) -> None:
        if not hasattr(self, "cheatsheet_ctrl") or not self.cheatsheet_ctrl:
            return
        from ui.quick_find_popup import QuickFindPopup

        if not hasattr(self, "_quick_find_popup") or self._quick_find_popup is None:
            self._quick_find_popup = QuickFindPopup(
                cheatsheet_controller=self.cheatsheet_ctrl,
                variable_provider=self._get_quick_find_variables,
                config_manager=self.config if hasattr(self, "config") else None,
                parent=None,
            )
        self._quick_find_popup.show_at_cursor()

    def _open_quick_ip_popup(self) -> None:
        if not self.var_bar:
            return
        from ui.quick_ip_popup import QuickIpPopup

        if not hasattr(self, "_quick_ip_popup") or self._quick_ip_popup is None:
            self._quick_ip_popup = QuickIpPopup(parent=None)
            self._quick_ip_popup.target_changed.connect(self._on_quick_ip_target_changed)
            self._quick_ip_popup.attacker_changed.connect(self._on_quick_ip_attacker_changed)

        vars_dict = self.var_bar.get_variables() if hasattr(self.var_bar, "get_variables") else {}
        target_ip = vars_dict.get("target_ip", "")
        attacker_ip = vars_dict.get("attacker_ip", "")

        self._quick_ip_popup.show_at_cursor(target_ip, attacker_ip)

    def _on_quick_ip_target_changed(self, text: str) -> None:
        if self.var_bar and hasattr(self.var_bar, "txt_target"):
            if self.var_bar.txt_target.text() != text:
                self.var_bar.txt_target.setText(text)

    def _on_quick_ip_attacker_changed(self, text: str) -> None:
        if self.var_bar and hasattr(self.var_bar, "txt_attacker"):
            if self.var_bar.txt_attacker.text() != text:
                self.var_bar.txt_attacker.setText(text)

    def _on_notes_updated(self) -> None:
        self._reset_rec_nudge()
        self._update_notes_badge()
        if self.active_mode == "notes":
            self.refresh_filter_pills()
            self.refresh_content()

    def _update_notes_badge(self) -> None:
        count = (
            sum(
                1
                for note in self.quick_note_manager.get_all_entries()
                if note.get("status", "inbox") != "resolved"
            )
            if self.quick_note_manager
            else 0
        )
        self.header.update_notes_badge(count)

    def _update_loot_badge(self) -> None:
        if not self.loot_manager:
            self.header.update_loot_badge(0)
            return
        cfg = getattr(self, "config", None)
        threshold = int(cfg.get("badge_warning_threshold", 5)) if cfg and hasattr(cfg, "get") else 5
        entries = self.loot_manager.get_all_entries()
        markdown = ""
        if hasattr(self, "report_ctrl") and self.report_ctrl:
            report_markdown = self.report_ctrl.markdown_for_analysis()
            if report_markdown is None:
                return
            markdown = report_markdown
        from core.reporting import classify_loot_report_state

        state = classify_loot_report_state(markdown, entries)
        unsynced_count = len(state.missing) + len(state.stale) + len(state.orphaned_ids)
        self.header.update_loot_badge(unsynced_count, threshold=threshold)

    def get_session_recap_info(self) -> Dict[str, Any]:
        """Collects state for the session recap banner."""
        phase_name = None
        if self.phase_context.active_phase_id:
            from core.phases import get_phase

            phase = get_phase(self.phase_context.active_phase_id)
            phase_name = phase.short if phase else self.phase_context.active_phase_id

        open_notes = (
            sum(
                1
                for note in self.quick_note_manager.get_all_entries()
                if note.get("status", "inbox") != "resolved"
            )
            if self.quick_note_manager
            else 0
        )

        unsynced_loot = 0
        if self.loot_manager:
            entries = self.loot_manager.get_all_entries()
            report_markdown: Optional[str] = ""
            if hasattr(self, "report_ctrl") and self.report_ctrl:
                report_markdown = self.report_ctrl.markdown_for_analysis()
            if report_markdown is not None:
                from core.reporting import classify_loot_report_state

                state = classify_loot_report_state(report_markdown, entries)
                unsynced_loot = len(state.missing) + len(state.stale) + len(state.orphaned_ids)

        target = self._target_provider()
        last_action, resume_context = self._get_last_action_summary_and_context()
        attention = self.get_next_attention_item()
        display_action = f"Next: {attention['text']}" if attention else last_action
        if attention:
            resume_context = attention.get("context") or resume_context

        return {
            "phase_name": phase_name,
            "target": target,
            "open_notes": open_notes,
            "unsynced_loot": unsynced_loot,
            "last_action": display_action,
            "attention_item": attention,
            "resume_context": resume_context,
        }

    def get_next_attention_item(self) -> Optional[Dict[str, Any]]:
        """Determines the single most urgent pending task in deterministic priority:
        1. Explicit follow-up note (status == 'followup')
        2. Unreviewed inbox note (status == 'inbox')
        3. Unsynced loot/finding
        Returns None if there is no actionable pending item.
        """
        if self.quick_note_manager:
            all_notes = self.quick_note_manager.get_all_entries()
            # 1. Follow-up notes
            for note in all_notes:
                if note.get("status") == "followup":
                    text = (note.get("text") or "").strip()
                    snippet = text[:30] + ("..." if len(text) > 30 else "")
                    return {
                        "type": "followup",
                        "text": f'Follow-up note "{snippet}"',
                        "context": {"mode": "notes", "id": note.get("id")},
                    }
            # 2. Inbox notes
            for note in all_notes:
                if note.get("status", "inbox") == "inbox":
                    text = (note.get("text") or "").strip()
                    snippet = text[:30] + ("..." if len(text) > 30 else "")
                    return {
                        "type": "inbox",
                        "text": f'Review note "{snippet}"',
                        "context": {"mode": "notes", "id": note.get("id")},
                    }

        # 3. Unsynced loot/findings
        if self.loot_manager:
            entries = self.loot_manager.get_all_entries()
            markdown = ""
            if hasattr(self, "report_ctrl") and self.report_ctrl:
                report_markdown = self.report_ctrl.markdown_for_analysis()
                if report_markdown is None:
                    return None
                markdown = report_markdown
            from core.reporting import classify_loot_report_state

            state = classify_loot_report_state(markdown, entries)
            if state.missing:
                missing_id = state.missing[0]
                missing_entry = next((e for e in entries if e.get("id") == missing_id), None)
                title = (missing_entry.get("title") if missing_entry else "") or "unlinked loot"
                snippet = title[:30] + ("..." if len(title) > 30 else "")
                return {
                    "type": "unsynced_loot",
                    "text": f'Sync finding "{snippet}"',
                    "context": {"mode": "report"},
                }

        return None

    def _get_last_action_summary_and_context(self) -> Tuple[Optional[str], Dict[str, Any]]:
        """Finds the most recent Note or Loot action snippet and computes resume context."""
        candidates = []
        if self.quick_note_manager:
            for note in self.quick_note_manager.get_all_entries():
                ts = note.get("timestamp", "")
                text = (note.get("text") or "").strip()
                if text:
                    candidates.append((ts, "Note", text, {"mode": "notes", "id": note.get("id")}))
        if self.loot_manager:
            for loot in self.loot_manager.get_all_entries():
                ts = loot.get("timestamp", "")
                title = (loot.get("title") or "").strip()
                if title:
                    candidates.append((ts, "Loot", title, {"mode": "loot", "id": loot.get("id")}))

        if not candidates:
            return None, {"mode": self.active_mode or "cheatsheet"}

        candidates.sort(key=lambda x: str(x[0]), reverse=True)
        latest_ts, kind, text, ctx = candidates[0]
        snippet = text[:35] + ("..." if len(text) > 35 else "")
        time_part = (
            latest_ts.split()[-1][:5]
            if " " in latest_ts
            else (latest_ts[-8:-3] if len(latest_ts) >= 8 else "")
        )
        if time_part:
            summary = f"Letzte {kind} ({time_part}): \"{snippet}\""
        else:
            summary = f"Letzte {kind}: \"{snippet}\""
        return summary, ctx

    def _get_last_action_summary(self) -> Optional[str]:
        """Finds the most recent Note or Loot action snippet."""
        summary, _ = self._get_last_action_summary_and_context()
        return summary

    def handle_resume(self, context: Optional[Dict[str, Any]] = None) -> None:
        """Navigates to the most relevant resume context after an interruption."""
        ctx = context or {}
        target_mode = ctx.get("mode") or self.active_mode or "cheatsheet"
        self.switch_mode(target_mode)
        if target_mode == "notes":
            phase = ctx.get("phase")
            if phase and hasattr(self.quick_note_ctrl, "select_filter"):
                self.quick_note_ctrl.select_filter(phase)
            if ctx.get("review_mode") and hasattr(self.quick_note_ctrl, "set_review_mode"):
                self.quick_note_ctrl.set_review_mode(True)

    def _on_logging_state_changed(self, is_active: bool) -> None:
        """Handles REC indicator updates and resets nudge countdown."""
        self.header.update_rec_indicator(is_active)
        self._reset_rec_nudge()
        if is_active:
            self._recorded_in_session = 0
        else:
            rec_count = getattr(self, "_recorded_in_session", 0)
            if rec_count > 0:
                self._check_recorder_stopped_nudge(rec_count)
                self._recorded_in_session = 0

    def _check_phase_switch_nudge(self, old_phase: str, new_phase: Optional[str]) -> None:
        """Shows a subtle, non-modal review nudge if leaving a phase with open items."""
        if not self.config.get("review_nudges_enabled", True):
            return
        if not hasattr(self.window, "isVisible") or not self.window.isVisible():
            return

        open_notes = [
            n for n in self.quick_note_manager.get_all_entries()
            if n.get("status") != "resolved" and n.get("category") == old_phase
        ]
        captures = [
            h for h in self.clipboard_history.get_all_history()
            if h.get("phase_id") == old_phase
        ]

        if not open_notes and not captures:
            return

        from core.phases import PHASES
        phase_obj = next((p for p in PHASES if p.key == old_phase), None)
        phase_name = phase_obj.short if phase_obj else old_phase.upper()

        if open_notes and captures:
            message = t(
                "nudge.phase_switch",
                "{phase}: {notes} und {captures}",
                phase=phase_name,
                notes=t("nudge.open_notes", "{count} offene Notes", count=len(open_notes)),
                captures=t("nudge.captures", "{count} Captures", count=len(captures)),
            )
        elif open_notes:
            message = t(
                "nudge.phase_notes_only",
                "{phase}: {count} offene Notes",
                phase=phase_name,
                count=len(open_notes),
            )
        else:
            message = t(
                "nudge.phase_captures_only",
                "{phase}: {count} Captures",
                phase=phase_name,
                count=len(captures),
            )

        resume_ctx = {
            "mode": "notes" if open_notes else "history",
            "phase": old_phase,
            "review_mode": bool(open_notes),
        }

        recap_banner = getattr(self.window, "recap_banner", None)
        if recap_banner and hasattr(recap_banner, "show_nudge"):
            recap_banner.show_nudge({
                "tag": t("nudge.tag", "REVIEW //"),
                "message": message,
                "action_label": t("nudge.action_review", "Review"),
                "resume_context": resume_ctx,
            })

    def _check_recorder_stopped_nudge(self, count: int) -> None:
        """Shows a subtle, non-modal review nudge after clipboard recording stops."""
        if not self.config.get("review_nudges_enabled", True):
            return
        if not hasattr(self.window, "isVisible") or not self.window.isVisible():
            return

        message = t(
            "nudge.rec_stopped",
            "Clipboard-Aufzeichnung beendet · {count} Einträge erfasst",
            count=count,
        )
        recap_banner = getattr(self.window, "recap_banner", None)
        if recap_banner and hasattr(recap_banner, "show_nudge"):
            recap_banner.show_nudge({
                "tag": t("nudge.tag", "REVIEW //"),
                "message": message,
                "action_label": t("nudge.action_review", "Review"),
                "resume_context": {"mode": "history"},
            })

    def _check_rec_nudge(self) -> None:
        """Checks whether active clipboard REC has run without documentation captures."""
        if not self.config.get("nudge_enabled", True):
            self.header.set_rec_nudged(False)
            return
        if not getattr(self.clipboard_monitor, "is_recording", False):
            self.header.set_rec_nudged(False)
            return
        threshold_sec = int(self.config.get("nudge_interval_minutes", 25)) * 60
        elapsed = time.time() - getattr(self, "_last_doc_activity_time", time.time())
        self.header.set_rec_nudged(elapsed >= threshold_sec)

    def _reset_rec_nudge(self) -> None:
        """Resets the documentation activity timer and clears any active nudge."""
        self._last_doc_activity_time = time.time()
        self.header.set_rec_nudged(False)


    def switch_mode(self, mode: str) -> None:
        self.navigation_coord.switch_mode(mode)

    def toggle_mode(self) -> None:
        self.navigation_coord.toggle_mode()

    def _toggle_pause_history(self, *, show_shortcut_feedback: bool = False) -> None:
        is_active = self.clipboard_coord.toggle_pause()
        if show_shortcut_feedback:
            self.phase_hud.show_recording(is_active)

    def _on_pills_width_changed(self, width: int) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_pills_width(
                width, self._select_category, self.search.get_pills_layout()
            )

    def _on_mode_switched(self, mode: str) -> None:

        self.var_bar.set_add_visible(
            mode in ("cheatsheet", "loot"), is_cheatsheet=(mode == "cheatsheet")
        )

        self.refresh_filter_pills()

        self.refresh_content()

    def refresh_filter_pills(self) -> None:

        self.search.clear_pills()

        self._renderer_for_mode().build_pills()

    def _renderer_for_mode(self) -> ContentRenderer:
        """Return the registered renderer, preserving History as legacy fallback."""
        return self._renderers.get(self.active_mode, self._renderers["history"])

    def _build_cheatsheet_pills(self) -> None:
        pills_layout = self.search.get_pills_layout()
        self.cheatsheet_ctrl.build_filter_pills(
            pills_layout,
            self._select_category,
            available_width=self.search.get_pills_available_width(),
        )

    def _build_loot_pills(self) -> None:
        export_tooltip = t(
            "report.export_copy_tip",
            "Creates a new copy based on current session loot",
        )
        self.loot_ctrl.build_filter_pills(
            self.search.get_pills_layout(),
            self._select_loot_type,
            lambda: self.export_coord.export_loot(self.window),
            self._clear_loot,
            export_tooltip,
            lambda: self.export_coord.export_loot_to_obsidian(self.window),
            self._toggle_loot_view,
            self.config.get("loot_view_mode", "list"),
            self._toggle_loot_density,
            self.config.get("loot_density", "comfortable"),
        )

    def _build_history_pills(self) -> None:
        export_tooltip = t(
            "history.generate_draft_tip",
            "Generate a new Markdown draft from current Loot and Clipboard History; this does not export the Report Editor document.",
        )
        self.history_ctrl.build_filter_pills(
            self.search.get_pills_layout(),
            self._select_history_filter,
            lambda: self.export_coord.export_report(self.window),
            lambda: self.clipboard_coord.clear_history(self.window),
            export_tooltip,
        )

    def _build_notes_pills(self) -> None:
        self.quick_note_ctrl.build_filter_pills(
            self.search.get_pills_layout(),
            self._select_notes_filter,
            self._clear_notes,
        )

    def refresh_content(self) -> None:
        if self._rendered_mode == "cheatsheet" and self.active_mode != "cheatsheet":
            self._stash_cheatsheet_view()
        result = self._renderer_for_mode().render()
        self.cards = result.cards
        self.footer.set_count(result.footer_text)
        if result.refresh_geometry:
            self.content.refresh_content_geometry()
            self.content.schedule_content_geometry_refresh()
        self._rendered_mode = self.active_mode
        self.content_refreshed.emit()

    @staticmethod
    def _format_entry_count(count: int) -> str:
        if count == 1:
            return t("footer.entry_count_single", "1 entry")
        return t("footer.entries_count", "{count} entries", count=count)

    def _prepare_card_content(self):
        content_layout = self.content.get_layout()
        self.report_ctrl.detach_tab_if_needed(content_layout)
        self.content.clear_cards()
        self.cards.clear()
        return content_layout

    def _render_report(self) -> RenderResult:
        cards = self.report_ctrl.render_content(self.content.get_layout())
        return RenderResult(cards, "Report Editor", refresh_geometry=False)

    def _render_cheatsheet(self) -> RenderResult:
        signature = self._current_cheatsheet_signature()
        if self.cheatsheet_ctrl.can_restore_cache(signature):
            cached_widgets, cached_cards, cached_scroll = self.cheatsheet_ctrl.pop_cached_view()
            self._prepare_card_content()
            self.content.restore_cards(cached_widgets)
            self.content.restore_scroll_value(cached_scroll)
            self.cheatsheet_ctrl.update_variables(cached_cards, self.var_bar.get_variables())
            self.cheatsheet_ctrl.set_render_signature(signature)
            return RenderResult(
                cached_cards,
                self._format_entry_count(self.cheatsheet_ctrl.total_result_count),
            )

        self._discard_cheatsheet_cache()
        cards = self.cheatsheet_ctrl.render_content(
            self._prepare_card_content(),
            self.search.get_query(),
            self.var_bar.get_variables() if self.var_bar else {},
            self._on_snippet_deleted,
            self.window,
            self.content.show_empty_state,
            self._on_content_copied,
            self._on_cheatsheet_batch_loaded,
        )
        self.cheatsheet_ctrl.set_render_signature(signature)
        count = (
            self.cheatsheet_ctrl.total_result_count
            if self.cheatsheet_ctrl.has_active_batch
            else len(cards)
        )
        return RenderResult(cards, self._format_entry_count(count))

    def _current_cheatsheet_signature(self) -> tuple[str, str, str]:
        return (
            self.search.get_query(),
            self.cheatsheet_ctrl.current_category_id,
            self.snippet_manager.language,
        )

    def _stash_cheatsheet_view(self) -> None:
        self.cheatsheet_ctrl.stash_view(
            cards=self.cards,
            detached_widgets=self.content.detach_cards(),
            scroll_val=self.content.scroll_value(),
            discard_fn=self.content.discard_detached_cards,
        )
        self.cards = []

    def _discard_cheatsheet_cache(self) -> None:
        self.cheatsheet_ctrl.discard_cache(self.content.discard_detached_cards)

    def _on_cheatsheet_batch_loaded(self) -> None:
        self.footer.set_count(self._format_entry_count(self.cheatsheet_ctrl.total_result_count))
        self.content.refresh_content_geometry()
        self.content.schedule_content_geometry_refresh()
        self.content_refreshed.emit()

    def _maybe_load_more_cheatsheet(self, value: int) -> None:
        if self.active_mode != "cheatsheet":
            return
        scrollbar = self.content.scroll_area.verticalScrollBar()
        self.cheatsheet_ctrl.check_scroll_load_more(value, scrollbar)

    def _export_single_loot_to_obsidian(self, entry_id: str) -> None:
        self.export_coord.export_single_loot_to_obsidian(self.window, entry_id)

    def _render_loot(self) -> RenderResult:
        content_layout = self._prepare_card_content()
        query = self.search.get_query()
        project_dir = self.project_manager.get_project_dir(
            self.project_manager.get_active_project()
        )
        density = self.config.get("loot_density", "comfortable")
        if self.config.get("loot_view_mode", "list") == "board":
            cards = self.loot_ctrl.render_board_content(
                content_layout,
                query,
                project_dir,
                self._on_loot_deleted,
                self._on_edit_loot_requested,
                self._on_export_loot_entry,
                self._on_move_loot_category,
                self.window,
                on_export_obsidian=self._export_single_loot_to_obsidian,
                on_copied=self._on_content_copied,
                density=density,
            )
        else:
            cards = self.loot_ctrl.render_content(
                content_layout,
                query,
                project_dir,
                self._on_loot_deleted,
                self._on_edit_loot_requested,
                self._on_export_loot_entry,
                self.window,
                self.content.show_empty_state,
                on_export_obsidian=self._export_single_loot_to_obsidian,
                on_copied=self._on_content_copied,
                density=density,
            )
        return RenderResult(cards, self._format_entry_count(len(cards)))

    def _render_notes(self) -> RenderResult:
        cards = self.quick_note_ctrl.render_content(
            self._prepare_card_content(),
            self.search.get_query(),
            self._on_content_copied,
            self.window,
            self.content.show_empty_state,
            self._on_edit_note_requested,
        )
        return RenderResult(cards, self._format_entry_count(len(cards)))

    def _render_history(self) -> RenderResult:
        variables = self.var_bar.get_variables() if self.var_bar else {}
        cards = self.history_ctrl.render_content(
            self._prepare_card_content(),
            self.search.get_query(),
            variables.get("target_ip"),
            lambda item: self.clipboard_coord.add_history_to_loot(self.window, item),
            self.clipboard_coord.delete_history_entry,
            self.window,
            self.content.show_empty_state,
            self._on_content_copied,
            on_add_to_note=lambda item: self.clipboard_coord.add_history_to_note(self.window, item),
            on_edit_history=self._on_edit_history_requested,
        )
        return RenderResult(cards, self._format_entry_count(len(cards)))

    def _on_content_copied(self, _text: str) -> None:
        """Minimize the overlay after an intentional card copy when configured."""
        if self.config.get("auto_hide_on_copy", False):
            self.window.showMinimized()

    def _select_category(self, cat_id: str) -> None:
        self.cheatsheet_ctrl.select_category(cat_id)
        self.refresh_content()

    def _select_loot_type(self, type_id: str) -> None:
        self.loot_ctrl.select_loot_type(type_id)
        self.refresh_content()

    def _toggle_loot_view(self) -> None:
        """Persist and immediately apply the alternate Loot presentation."""
        current_mode = self.config.get("loot_view_mode", "list")
        next_mode = "list" if current_mode == "board" else "board"
        try:
            self.config.set("loot_view_mode", next_mode)
        except PersistenceError as exc:
            logger.error(f"Could not persist Loot view mode: {exc}")
            show_error_dialog(
                self.window,
                t("loot.view_switch_failed_title", "View switch failed"),
                t(
                    "loot.view_switch_failed",
                    "The Loot view could not be changed:\n{error}",
                    error=str(exc),
                ),
            )
            return
        self.refresh_filter_pills()
        self.refresh_content()

    def _toggle_loot_density(self) -> None:
        """Persist and immediately apply the alternate card density."""
        current_density = self.config.get("loot_density", "comfortable")
        next_density = "comfortable" if current_density == "compact" else "compact"
        try:
            self.config.set("loot_density", next_density)
        except PersistenceError as exc:
            logger.error(f"Could not persist Loot density: {exc}")
            show_error_dialog(
                self.window,
                t("loot.density_switch_failed_title", "Density switch failed"),
                t(
                    "loot.density_switch_failed",
                    "The card density could not be changed:\n{error}",
                    error=str(exc),
                ),
            )
            return
        self.refresh_filter_pills()
        self.refresh_content()

    def _select_notes_filter(self, filter_id: str) -> None:
        self.quick_note_ctrl.select_filter(filter_id)
        self.refresh_content()

    def _clear_notes(self) -> None:
        if self.quick_note_ctrl.clear_all_notes(self.window):
            self._on_notes_updated()

    def _select_history_filter(self, filter_id: str) -> None:
        self.history_ctrl.select_history_filter(filter_id)
        self.refresh_content()

    def _on_variables_changed(self, vars_dict: Dict[str, str]) -> None:
        if self.active_mode == "cheatsheet":
            self.cheatsheet_ctrl.update_variables(self.cards, vars_dict)

    def on_add_button_clicked(self) -> None:
        target_ip = self._target_provider()
        if self.active_mode == "cheatsheet":
            if self.cheatsheet_ctrl.open_add_dialog(self.window):
                self._on_data_updated()
        elif self.active_mode == "loot":
            if self.loot_ctrl.open_add_dialog(self.window, target_ip=target_ip):
                self._on_loot_data_updated()
        elif self.active_mode in ("notes", "history"):
            self.quick_note_ctrl.show_popup()

    _on_add_button_clicked = on_add_button_clicked

    def on_import_snippets_clicked(self) -> None:
        if self.cheatsheet_ctrl.import_snippets_dialog(self.window):
            self._on_data_updated()

    _on_import_snippets_clicked = on_import_snippets_clicked

    def _on_edit_loot_requested(self, entry: Dict[str, Any]) -> None:
        def export_obsidian(entry_id: str) -> None:
            self.export_coord.export_single_loot_to_obsidian(self.window, entry_id)

        if self.loot_ctrl.open_edit_dialog(
            self.window,
            entry,
            on_export_file=self._on_export_loot_entry,
            on_export_obsidian=export_obsidian,
        ):
            self._on_loot_data_updated()

    def _on_edit_history_requested(self, entry: Dict[str, Any]) -> None:
        if self.history_ctrl.open_edit_dialog(self.window, entry):
            self._on_history_data_updated()

    def _on_edit_note_requested(self, entry: Dict[str, Any]) -> None:
        if self.quick_note_ctrl.open_edit_dialog(self.window, entry):
            self._on_notes_updated()

    def _on_export_loot_entry(self, entry_id: str) -> None:
        self.loot_ctrl.export_entry_to_file_with_feedback(entry_id, self.window)

    def _on_move_loot_category(self, entry_id: str, category: str, target_index: int) -> bool:
        return self.loot_ctrl.move_entry_to_category(entry_id, category, target_index, self.window)

    def _on_snippet_deleted(self, snippet_id: str) -> None:
        self.cheatsheet_ctrl.delete_snippet(snippet_id)
        self._on_data_updated()

    def _on_loot_deleted(self, loot_id: str) -> None:
        self.loot_ctrl.delete_loot(loot_id)
        self._on_loot_data_updated()

    def _on_clipboard_entry_added(self, entry: Dict[str, Any]) -> None:
        self._recorded_in_session = getattr(self, "_recorded_in_session", 0) + 1
        self.clipboard_coord.on_clipboard_entry_added(entry)

    def _clear_loot(self) -> None:
        if self.loot_ctrl.clear_loot(self.window):
            self._on_loot_data_updated()

    def _on_data_updated(self) -> None:
        self._discard_cheatsheet_cache()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_loot_data_updated(self) -> None:
        self.save_current_project_state()
        self.report_ctrl.refresh_loot_sync_state()
        self._reset_rec_nudge()
        self._update_loot_badge()
        self.refresh_filter_pills()
        self.refresh_content()

    def _on_history_data_updated(self) -> None:
        self.save_current_project_state()
        if self.active_mode == "history":
            self.refresh_filter_pills()
            self.refresh_content()

    # Workspaces
    def _show_project_menu(self, btn_anchor: QPushButton) -> None:
        self.workspace_coord.show_project_menu(
            btn_anchor, self.window, self.switch_to_project, self._open_new_project_dialog
        )

    def _open_new_project_dialog(self) -> None:
        self.workspace_coord.open_new_project_dialog(
            self.window,
            self._target_provider(),
            self.var_bar.txt_attacker.text().strip()
            if hasattr(self.var_bar, "txt_attacker")
            else "",
            self.var_bar.txt_port.text().strip() if hasattr(self.var_bar, "txt_port") else "4444",
            self.switch_to_project,
        )

    def load_active_project_state(self) -> None:
        active_proj = self.project_manager.get_active_project()
        self.header.set_project_title(active_proj)
        state = self.workspace_coord.load_active_project_session(self.window)
        if state is not None and self.var_bar:
            self.var_bar.set_variables(state.to_dict())
        self._update_notes_badge()
        self._update_loot_badge()

    def save_current_project_state(self) -> bool:
        vars_dict = self.var_bar.get_variables() if self.var_bar else {}
        return self.workspace_coord.save_current_project_session(vars_dict)

    def switch_to_project(self, project_name: str) -> None:
        def on_switched(pname: str):
            self.load_active_project_state()
            self.refresh_filter_pills()
            self.refresh_content()

        self.workspace_coord.switch_to_project(
            project_name=project_name,
            window=self.window,
            variables_provider=lambda: self.var_bar.get_variables() if self.var_bar else {},
            on_success_callback=on_switched,
        )

    # Screenshots & Settings
    def trigger_screenshot(self) -> None:
        if not self.screenshot_manager.is_capture_available():
            if self.screenshot_manager.capabilities.wayland:
                msg = t(
                    "header.snip_wayland_unavailable",
                    "Bereichs-Screenshot ist unter Wayland derzeit nicht verfügbar.",
                )
            else:
                msg = t(
                    "header.snip_unavailable",
                    "Bereichs-Screenshot ist auf dieser Plattform nicht verfügbar.",
                )
            logger.warning(msg)
            if (
                hasattr(self, "header")
                and hasattr(self.header, "btn_screenshot")
                and self.header.btn_screenshot
            ):
                from PyQt6.QtWidgets import QToolTip

                btn = self.header.btn_screenshot
                QToolTip.showText(btn.mapToGlobal(btn.rect().bottomLeft()), msg, btn)
            return

        self.screenshot_manager.start_capture(
            self.window,
            self.project_manager,
            self.loot_manager,
            target_ip=self._target_provider(),
            phase_id=self.phase_context.active_phase_id,
        )

    def _on_screenshot_saved(self, loot_entry: Dict[str, Any]) -> None:
        result = self.screenshot_transaction.commit(loot_entry)
        if not result.ok:
            return
        self.event_bus.publish(EventType.SCREENSHOT_SAVED, {"entry": loot_entry})
        phase = loot_entry.get("category", "")
        target = loot_entry.get("target_ip", "")
        if hasattr(self, "phase_hud") and self.phase_hud is not None:
            self.phase_hud.show_screenshot(
                phase_name=phase.upper() if phase else "", target=target
            )

    def open_settings_dialog(self) -> None:
        previous_theme = self.config.get("theme", "cyber_dark")
        applied_settings: Dict[str, Any] = {}
        dlg = SettingsDialog(self.config, parent=self.window)

        def apply_settings(settings: Dict[str, Any]) -> None:
            applied_settings.update(settings)
            self._on_settings_applied(settings)

        dlg.settings_applied.connect(apply_settings)
        accepted = bool(dlg.exec())
        if accepted and applied_settings.get("theme", previous_theme) != previous_theme:
            self.restart_requested.emit()

    def _on_settings_applied(self, new_settings: Dict[str, Any]) -> None:
        self.settings_coord.apply(new_settings)

    def _on_always_on_top_toggled(self, checked: bool) -> None:
        self.config.set("always_on_top", checked)
        flags = self.window.windowFlags()
        flags = (
            (flags | Qt.WindowType.WindowStaysOnTopHint)
            if checked
            else (flags & ~Qt.WindowType.WindowStaysOnTopHint)
        )
        was_visible = self.window.isVisible()
        self.window.setWindowFlags(flags)
        if was_visible:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def retranslate_ui(self, locale_code: str = "") -> None:
        active_lang = locale_code or get_locale()
        self._discard_cheatsheet_cache()
        if hasattr(self, "snippet_manager") and self.snippet_manager:
            self.snippet_manager.set_language(active_lang)
        self.header.retranslate()
        self._update_notes_badge()
        self._update_loot_badge()
        if self.var_bar:
            self.var_bar.retranslate()
        self._update_footer_status()
        self.search.update_placeholder(self.active_mode)
        self.refresh_filter_pills()
        self.refresh_content()
        self.event_bus.publish(EventType.LANGUAGE_CHANGED, {"locale": active_lang})

    def _update_footer_status(self) -> None:
        hotkey_raw = self.config.get("hotkey", "<ctrl>+<alt>+h")
        quit_hotkey_raw = self.config.get("quit_hotkey", "<ctrl>+<alt>+q")
        quick_note_hotkey_raw = self.config.get("quick_note_hotkey", "<ctrl>+<alt>+n")
        quick_ip_hotkey_raw = self.config.get("quick_ip_hotkey", "<ctrl>+<alt>+i")
        quick_loot_hotkey_raw = self.config.get("quick_loot_hotkey", "<ctrl>+<alt>+l")
        self.footer.update_hotkey_display(
            hotkey_raw,
            quit_hotkey_raw,
            quick_note_hotkey_raw=quick_note_hotkey_raw,
            quick_ip_hotkey_raw=quick_ip_hotkey_raw,
            quick_loot_hotkey_raw=quick_loot_hotkey_raw,
        )
