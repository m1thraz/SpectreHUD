import os
import time
from typing import Dict, Any, List

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QPoint, QEvent, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication, QMouseEvent

from core.logger import get_logger

from ui.variable_bar import VariableBar
from ui.panels import HeaderPanel, SearchPanel, ContentPanel, FooterPanel
from ui.app_controller import AppController
from ui.controllers.window_frame_manager import WindowFrameManager
from ui.coordinators.shutdown_coordinator import ShutdownCoordinator
from ui.styles import get_app_icon

from ui.snipping_overlay import SnippingOverlay
from core.container import ServiceContainer

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """
    Sleek, frameless, resizable Spotlight-style HUD Overlay window.
    Acts as the primary UI shell and layout assembler, delegating domain coordination to AppController.
    """

    def __init__(self, container: ServiceContainer):
        started_at = time.perf_counter()
        super().__init__()

        # Dependencies are composed outside the widget. Keeping this assignment
        # explicit makes the UI's requirements visible without duplicating DI.
        self.container = container
        self.event_bus = container.event_bus
        self.config = container.config_manager
        self.snippet_manager = container.snippet_manager
        self.project_manager = container.project_manager
        self.loot_manager = container.loot_manager
        self.clipboard_watcher = container.clipboard_watcher
        self.quick_note_manager = container.quick_note_manager
        self.screenshot_manager = container.screenshot_manager

        if getattr(self.screenshot_manager, "overlay_factory", None) is None:
            if hasattr(self.screenshot_manager, "set_overlay_factory"):
                self.screenshot_manager.set_overlay_factory(SnippingOverlay)

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
            quick_note_manager=self.quick_note_manager,
        )
        self.shutdown_coordinator = ShutdownCoordinator(
            window=self,
            config=self.config,
            confirm_discard=lambda: self.app.report_ctrl.confirm_discard_if_dirty(),
            save_project_state=lambda: self.app.save_current_project_state(),
            logger=logger,
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

    def _detect_compositor(self) -> bool:
        if self.config:
            cfg = self.config.get("compositor", None)
            if cfg is not None:
                return bool(cfg)
        from core.platform import detect_platform_capabilities
        return detect_platform_capabilities().compositor

    # -------------------------------------------------------------
    # Window Frame, Geometry, & Layout Assembly
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

        self.has_compositor = self._detect_compositor()
        self.setWindowFlags(flags)
        if self.has_compositor:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

    def _build_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout(central_widget)
        if self.has_compositor:
            outer_layout.setContentsMargins(10, 10, 10, 10)
        else:
            outer_layout.setContentsMargins(0, 0, 0, 0)
            central_widget.setStyleSheet("background-color: #0d1117;")
        outer_layout.setSpacing(0)

        # Main HUD Glass Frame
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("HudFrame")
        if not self.has_compositor:
            self.hud_frame.setStyleSheet(
                "QFrame#HudFrame { border-radius: 0px; background-color: #0d1117; }"
            )
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
            "wordlist": self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt"),
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
        self.frame_manager.install_on(
            [
                self.hud_frame,
                self.header_panel,
                self.search_panel.pills_frame,
                self.footer_panel,
                self.var_bar,
                self.content_panel.content_container,
                self.content_panel.scroll_area,
                central_widget,
            ]
        )

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Esc"), self, activated=self.hide)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_panel.set_focus)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.app._on_add_button_clicked())
        QShortcut(QKeySequence("Ctrl+Alt+S"), self, activated=lambda: self.app.trigger_screenshot())
        QShortcut(
            QKeySequence("Ctrl+Shift+X"), self, activated=lambda: self.app.trigger_screenshot()
        )
        QShortcut(QKeySequence("Ctrl+P"), self, activated=lambda: self.app._toggle_pause_history())
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.request_quit)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.app.open_settings_dialog())
        QShortcut(QKeySequence("Tab"), self, activated=lambda: self.app.toggle_mode())
        QShortcut(
            QKeySequence("Ctrl+1"), self, activated=lambda: self.app.switch_mode("cheatsheet")
        )
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.app.switch_mode("history"))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self.app.switch_mode("notes"))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self.app.switch_mode("loot"))
        QShortcut(QKeySequence("Ctrl+5"), self, activated=lambda: self.app.switch_mode("report"))
        self.shortcut_fullscreen = QShortcut(
            QKeySequence("Ctrl+Space"), self, activated=self.toggle_fullscreen
        )
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
    def filter_buttons(self) -> Dict[str, Any]:
        if self.app.active_mode == "cheatsheet":
            return self.app.cheatsheet_ctrl.filter_buttons
        elif self.app.active_mode == "loot":
            return self.app.loot_ctrl.filter_buttons
        elif self.app.active_mode == "history":
            return self.app.history_ctrl.filter_buttons
        return {}

    @property
    def report_editor_tab(self):
        return self.app.report_ctrl.get_tab_widget()

    def _show_empty_state(self, message: str) -> None:
        self.content_panel.show_empty_state(message)

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show()
            self.setWindowState(
                self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
            )
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
        """Delegate the transactional shutdown workflow."""
        return self.shutdown_coordinator.request_quit(quit_app=quit_app)

    def prepare_for_shutdown(self) -> None:
        """Safety cleanup hook connected to QApplication.aboutToQuit."""
        try:
            if hasattr(self, "project_manager"):
                self.project_manager.clear_project_key()
        except Exception:
            logger.exception("Failed to clear Pentest-Mode session key during shutdown")
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
