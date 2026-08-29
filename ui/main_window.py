import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QPoint, QEvent, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication, QMouseEvent

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.screenshot_manager import ScreenshotManager
from core.report_file_manager import ReportFileManager
from core.event_bus import EventBus
from core.logger import get_logger

from ui.variable_bar import VariableBar
from ui.panels import HeaderPanel, SearchPanel, ContentPanel, FooterPanel
from ui.app_controller import AppController
from ui.controllers.window_frame_manager import WindowFrameManager
from ui.styles import CYBER_DARK_QSS, get_app_icon

from core.container import ServiceContainer

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """
    Sleek, frameless, resizable Spotlight-style HUD Overlay window.
    Acts as the primary UI shell and layout assembler, delegating domain coordination to AppController.
    """

    def __init__(
        self, 
        config_manager: Optional[ConfigManager] = None, 
        snippet_manager: Optional[SnippetManager] = None, 
        loot_manager: Optional[LootManager] = None,
        clipboard_watcher: Optional[ClipboardWatcher] = None,
        project_manager: Optional[ProjectManager] = None,
        screenshot_manager: Optional[ScreenshotManager] = None,
        container: Optional[ServiceContainer] = None
    ):
        started_at = time.perf_counter()
        super().__init__()
        if container is not None:
            self.container = container
            self.event_bus = container.event_bus
            self.config = container.config_manager
            self.snippet_manager = container.snippet_manager
            self.project_manager = container.project_manager
            self.loot_manager = container.loot_manager
            self.clipboard_watcher = container.clipboard_watcher
            self.screenshot_manager = container.screenshot_manager
        else:
            self.container = None
            self.event_bus = EventBus()
            self.config = config_manager if config_manager is not None else ConfigManager()
            self.snippet_manager = snippet_manager if snippet_manager is not None else SnippetManager()
            self.project_manager = project_manager if project_manager is not None else ProjectManager(event_bus=self.event_bus)
            self.loot_manager = loot_manager if loot_manager is not None else LootManager(event_bus=self.event_bus)
            self.clipboard_watcher = clipboard_watcher if clipboard_watcher is not None else ClipboardWatcher(event_bus=self.event_bus)
            self.screenshot_manager = screenshot_manager if screenshot_manager is not None else ScreenshotManager()
        self._startup_mark(started_at, "services assigned")

        # Window Frame Manager for Frameless Resize & Dragging
        self.frame_manager = WindowFrameManager(self, self.config)
        self._startup_mark(started_at, "frame manager ready")

        # Build UI Structure & Panels
        self._init_window()
        self._startup_mark(started_at, "window configured")
        self._build_ui()
        self._startup_mark(started_at, "panels built")
        self._setup_shortcuts()
        self._startup_mark(started_at, "shortcuts registered")

        # Initialize Central App Coordinator
        self.app = AppController(
            window=self,
            header_panel=self.header_panel,
            search_panel=self.search_panel,
            var_bar=self.var_bar,
            content_panel=self.content_panel,
            footer_panel=self.footer_panel,
            config_manager=self.config,
            snippet_manager=self.snippet_manager,
            loot_manager=self.loot_manager,
            clipboard_watcher=self.clipboard_watcher,
            project_manager=self.project_manager,
            screenshot_manager=self.screenshot_manager,
            event_bus=self.event_bus,
            container=self.container
        )
        self._startup_mark(started_at, "app controller ready")

        # Load Initial Project State and Content
        self.app.load_active_project_state()
        self._startup_mark(started_at, "project state loaded")
        self.app.refresh_filter_pills()
        self._startup_mark(started_at, "filter pills built")
        # Rendering all initial Cheatsheet cards is intentionally deferred
        # until the native window is visible. This gets the HUD on screen
        # sooner while keeping the first content render on the GUI thread.
        self._startup_started_at = started_at
        self._initial_content_pending = True
        self.app.content_refreshed.connect(self._mark_initial_content_rendered)
        self._startup_mark(started_at, "initial content deferred")
        self._center_on_screen()
        self._startup_mark(started_at, "complete")

    @staticmethod
    def _startup_mark(started_at: float, stage: str) -> None:
        """Emit fine-grained startup timings only when explicitly requested."""
        if os.environ.get("SPECTREHUD_STARTUP_PROFILE"):
            elapsed_ms = (time.perf_counter() - started_at) * 1_000
            print(f"[SpectreHUD startup] MainWindow {stage}: {elapsed_ms:.1f} ms", flush=True)

    def _mark_initial_content_rendered(self) -> None:
        """Clear the deferred-render marker if another UI action rendered first."""
        self._initial_content_pending = False

    def _render_initial_content(self) -> None:
        if not self._initial_content_pending:
            return
        self.app.refresh_content()
        self._startup_mark(self._startup_started_at, "initial content rendered")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._initial_content_pending:
            QTimer.singleShot(0, self._render_initial_content)

    # -------------------------------------------------------------
    # Window & Panel Layout Construction
    # -------------------------------------------------------------
    def _init_window(self) -> None:
        self.setWindowTitle("SpectreHUD")
        w = int(self.config.get("window_width", 900))
        h = int(self.config.get("window_height", 640))
        self.resize(w, h)
        self.setMinimumSize(740, 480)
        self.setMouseTracking(True)
        
        is_always_on_top = self.config.get("always_on_top", True)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if is_always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(CYBER_DARK_QSS)

        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

    def _build_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(0)

        # Main HUD Glass Frame
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("HudFrame")
        self.hud_frame.setMouseTracking(True)
        
        hud_layout = QVBoxLayout(self.hud_frame)
        hud_layout.setContentsMargins(0, 0, 0, 0)
        hud_layout.setSpacing(0)

        # 1. Header Panel
        self.header_panel = HeaderPanel(self)
        hud_layout.addWidget(self.header_panel)

        # 2. Search & Filter Pills Panel
        self.search_panel = SearchPanel(self)
        hud_layout.addWidget(self.search_panel)

        # 3. Variable Bar
        initial_vars = {
            "target_ip": self.config.get("target_ip", "10.10.10.10"),
            "attacker_ip": self.config.get("attacker_ip", "10.10.14.5"),
            "port": self.config.get("port", "4444"),
            "wordlist": self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        }
        self.var_bar = VariableBar(initial_vars, parent=self)
        hud_layout.addWidget(self.var_bar)

        # 4. Scrollable Content Panel (Cards, History & Privacy Banner)
        self.content_panel = ContentPanel(self)
        hud_layout.addWidget(self.content_panel, stretch=1)

        # 5. Footer Panel
        self.footer_panel = FooterPanel(self)
        self.footer_panel.set_always_on_top(self.config.get("always_on_top", True))
        hud_layout.addWidget(self.footer_panel)

        outer_layout.addWidget(self.hud_frame)

        # Install event filter for universal border resizing and drag-moving
        self.frame_manager.install_on([
            self.hud_frame, self.header_panel, self.search_panel.pills_frame, 
            self.footer_panel, self.var_bar, self.content_panel.content_container, 
            self.content_panel.scroll_area, central_widget
        ])

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_panel.set_focus)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.app._on_add_button_clicked())
        QShortcut(QKeySequence("Ctrl+Alt+S"), self, activated=self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+Shift+X"), self, activated=self.trigger_screenshot)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=lambda: self.app._toggle_pause_history())
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.request_quit)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings_dialog)
        QShortcut(QKeySequence("Tab"), self, activated=self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch_mode("cheatsheet"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch_mode("loot"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.switch_mode("history"))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.switch_mode("report"))
        self.shortcut_fullscreen = QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle_fullscreen)
        self.shortcut_fullscreen.setContext(Qt.ShortcutContext.WindowShortcut)

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = max(geo.y() + 60, (geo.height() - self.height()) // 3 + geo.y())
            self.move(x, y)

    # -------------------------------------------------------------
    # App Delegation & Backward-Compatibility Properties
    # -------------------------------------------------------------
    @property
    def active_mode(self) -> str:
        return self.app.active_mode

    @active_mode.setter
    def active_mode(self, val: str) -> None:
        self.app.active_mode = val

    @property
    def cards(self) -> List[QWidget]:
        # Preserve the established programmatic contract for callers that
        # inspect cards before the window has ever been shown (notably tests).
        if getattr(self, "_initial_content_pending", False):
            self._render_initial_content()
        return self.app.cards

    @cards.setter
    def cards(self, val: List[QWidget]) -> None:
        self.app.cards = val

    @property
    def session_service(self):
        return self.app.session_service

    @property
    def cheatsheet_ctrl(self):
        return self.app.cheatsheet_ctrl

    @property
    def loot_ctrl(self):
        return self.app.loot_ctrl

    @property
    def history_ctrl(self):
        return self.app.history_ctrl

    @property
    def report_ctrl(self):
        return self.app.report_ctrl

    @property
    def project_ctrl(self):
        return self.app.project_ctrl

    @property
    def search_bar(self):
        return self.search_panel.search_bar

    @property
    def pills_frame(self):
        return self.search_panel.pills_frame

    @property
    def pills_layout(self):
        return self.search_panel.pills_layout

    @property
    def content_layout(self):
        return self.content_panel.content_layout

    @property
    def content_container(self):
        return self.content_panel.content_container

    @property
    def scroll_area(self):
        return self.content_panel.scroll_area

    @property
    def privacy_banner(self):
        return self.content_panel.privacy_banner

    @property
    def header_bar(self):
        return self.header_panel

    @property
    def btn_project(self):
        return self.header_panel.btn_project

    @property
    def btn_mode_cheatsheet(self):
        return self.header_panel.btn_mode_cheatsheet

    @property
    def btn_mode_loot(self):
        return self.header_panel.btn_mode_loot

    @property
    def btn_mode_history(self):
        return self.header_panel.btn_mode_history

    @property
    def btn_mode_report(self):
        return self.header_panel.btn_mode_report

    @property
    def btn_screenshot(self):
        return self.header_panel.btn_screenshot

    @property
    def btn_rec_indicator(self):
        return self.header_panel.btn_rec_indicator

    @property
    def btn_settings(self):
        return self.header_panel.btn_settings

    @property
    def footer_frame(self):
        return self.footer_panel

    @property
    def lbl_status(self):
        return self.footer_panel.lbl_status

    @property
    def lbl_count(self):
        return self.footer_panel.lbl_count

    @property
    def chk_always_on_top(self):
        return self.footer_panel.chk_always_on_top

    @property
    def size_grip(self):
        return self.footer_panel.size_grip

    @property
    def filter_buttons(self) -> Dict[str, Any]:
        if self.active_mode == "cheatsheet":
            return self.cheatsheet_ctrl.filter_buttons
        elif self.active_mode == "loot":
            return self.loot_ctrl.filter_buttons
        elif self.active_mode == "history":
            return self.history_ctrl.filter_buttons
        return {}

    @property
    def current_category_id(self) -> str:
        return self.cheatsheet_ctrl.current_category_id

    @current_category_id.setter
    def current_category_id(self, val: str) -> None:
        self.cheatsheet_ctrl.current_category_id = val

    @property
    def current_loot_type(self) -> str:
        return self.loot_ctrl.current_loot_type

    @current_loot_type.setter
    def current_loot_type(self, val: str) -> None:
        self.loot_ctrl.current_loot_type = val

    @property
    def current_history_filter(self) -> str:
        return self.history_ctrl.current_history_filter

    @current_history_filter.setter
    def current_history_filter(self, val: str) -> None:
        self.history_ctrl.current_history_filter = val

    @property
    def report_file_manager(self) -> ReportFileManager:
        return self.report_ctrl.report_file_manager

    @property
    def report_editor_tab(self):
        return self.report_ctrl.get_tab_widget()

    # Methods delegated to AppController
    def switch_mode(self, mode: str) -> None:
        self.app.switch_mode(mode)

    def toggle_mode(self) -> None:
        self.app.toggle_mode()

    def refresh_filter_pills(self) -> None:
        self.app.refresh_filter_pills()

    def refresh_content(self) -> None:
        self.app.refresh_content()

    def trigger_screenshot(self) -> None:
        self.app.trigger_screenshot()

    def open_settings_dialog(self) -> None:
        self.app.open_settings_dialog()

    def _select_category(self, category_id: str) -> None:
        self.app._select_category(category_id)

    def _select_loot_type(self, type_id: str) -> None:
        self.app._select_loot_type(type_id)

    def _select_history_filter(self, filter_id: str) -> None:
        self.app._select_history_filter(filter_id)

    def _switch_to_project(self, project_name: str) -> None:
        self.app.switch_to_project(project_name)

    def _save_current_project_state(self) -> bool:
        return self.app.save_current_project_state()

    def _load_active_project_state(self) -> None:
        self.app.load_active_project_state()

    def _show_empty_state(self, message: str) -> None:
        self.content_panel.show_empty_state(message)

    def _toggle_pause_history(self) -> None:
        self.app._toggle_pause_history()

    def _on_add_button_clicked(self) -> None:
        self.app._on_add_button_clicked()

    def _export_report(self) -> None:
        self.app._export_report()

    def _export_loot(self) -> None:
        self.app._export_loot()

    def _clear_loot(self) -> None:
        self.app._clear_loot()

    def _clear_history(self) -> None:
        self.app._clear_history()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.raise_()
            self.activateWindow()
            self.search_panel.set_focus()

    def toggle_fullscreen(self) -> None:
        """Toggles fullscreen without changing the user's saved normal window size."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -------------------------------------------------------------
    # Frameless Window Event Routing Delegated to WindowFrameManager
    # -------------------------------------------------------------
    def _get_resize_edge(self, pos: QPoint) -> str:
        return self.frame_manager.get_resize_edge(pos)

    def request_quit(self, quit_app: bool = True) -> bool:
        """
        Unified transactional shutdown path.
        Validates dirty reports, persists active project state, and safely terminates application.
        Returns True if shutdown proceeds, False if cancelled or aborted.
        """
        from PyQt6.QtWidgets import QMessageBox

        # 1. Dirty report confirmation
        if hasattr(self, "report_ctrl") and self.report_ctrl and not self.report_ctrl.confirm_discard_if_dirty():
            return False

        # 2. Persist project state
        saved = self._save_current_project_state()
        if not saved:
            from core.i18n import t as _t
            msg = QMessageBox(self)
            msg.setWindowTitle(_t("quit.save_failed_title", "Save Failed"))
            msg.setText(
                _t(
                    "quit.save_failed_text",
                    "The current project state could not be saved to disk.\n\n"
                    "What would you like to do?"
                )
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            retry_btn   = msg.addButton(_t("quit.retry",   "Retry Save"),            QMessageBox.ButtonRole.ActionRole)
            discard_btn = msg.addButton(_t("quit.discard", "Quit Without Saving"),    QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn  = msg.addButton(_t("quit.cancel",  "Cancel"),                 QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(cancel_btn)
            try:
                from ui.styles import CYBER_DARK_QSS
                msg.setStyleSheet(CYBER_DARK_QSS)
            except Exception:
                pass
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == retry_btn:
                # One retry attempt
                if not self._save_current_project_state():
                    return False  # Still failed — let user try again via UI
            elif clicked != discard_btn:
                return False  # Cancel or window closed

        # 3. Flush window geometry
        from core.storage import PersistenceError
        try:
            self.config.update({
                "window_width": self.width(),
                "window_height": self.height()
            })
        except PersistenceError as exc:
            logger.warning("Could not persist window geometry during shutdown: %s", exc)
        except Exception:
            logger.exception("Unexpected error while persisting window geometry during shutdown")

        # 4. Quit application
        if quit_app:
            app = QApplication.instance()
            if app:
                app.quit()
        return True

    def prepare_for_shutdown(self) -> None:
        """Safety cleanup hook connected to QApplication.aboutToQuit."""
        try:
            if hasattr(self, "hotkey_listener") and self.hotkey_listener:
                self.hotkey_listener.stop()
        except Exception:
            pass
        try:
            from core.logger import close_log_handlers
            close_log_handlers()
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self.request_quit(quit_app=False):
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Note: Window dimensions are persisted in request_quit to avoid excessive disk I/O during drag

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_press(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_move(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_release(event):
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if not self.frame_manager.handle_mouse_double_click(event):
            super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.frame_manager.handle_leave(event)
        super().leaveEvent(event)
