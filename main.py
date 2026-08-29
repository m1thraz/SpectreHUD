import sys
import os
import traceback
import time
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows consoles to prevent UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer

from core.single_instance import ApplicationLockError, acquire_application_lock, release_application_lock
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.hotkey_listener import HotkeyListener
from core.logger import setup_logger, get_logger
from ui.main_window import MainWindow

from ui.styles import CYBER_DARK_QSS, build_app_theme, get_app_icon

logger = get_logger("app")


def _startup_mark(started_at: float, stage: str) -> None:
    """Emits opt-in startup timing marks for real desktop profiling."""
    if os.environ.get("SPECTREHUD_STARTUP_PROFILE"):
        elapsed_ms = (time.perf_counter() - started_at) * 1_000
        print(f"[SpectreHUD startup] {stage}: {elapsed_ms:.1f} ms", flush=True)

def global_exception_hook(exctype, value, tb):
    """
    Global exception hook protecting the GUI process from sudden termination
    on unhandled slot exceptions, logging the incident with full traceback.
    """
    tb_str = "".join(traceback.format_exception(exctype, value, tb))
    logger.critical(f"Unhandled exception caught by global hook:\n{tb_str}")
    
    if issubclass(exctype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exctype, value, tb)
        return
        
    app = QApplication.instance()
    if app and not os.environ.get("SPECTREHUD_NO_GUI_CRASH_POPUP"):
        active_win = app.activeWindow()
        QMessageBox.critical(
            active_win,
            "Unerwarteter Fehler",
            f"Ein unerwarteter Fehler ist aufgetreten:\n{value}\n\n"
            f"Die Details wurden im Log protokolliert. Ihre Sitzungsdaten im RAM bleiben erhalten."
        )

sys.excepthook = global_exception_hook

def create_tray_icon_pixmap(is_recording: bool, app_icon: QIcon | None = None) -> QPixmap:
    """Returns the SpectreHUD logo, tinted red while clipboard recording is active."""
    icon = app_icon if app_icon is not None and not app_icon.isNull() else get_app_icon()
    pixmap = icon.pixmap(32, 32)
    if pixmap.isNull() or not is_recording:
        return pixmap

    # Preserve the logo's silhouette and transparency while making the active
    # recording state unmistakable in the system tray.
    recording_pixmap = QPixmap(pixmap.size())
    recording_pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(recording_pixmap)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(recording_pixmap.rect(), QColor("#f85149"))
    painter.end()
    return recording_pixmap


def _create_production_container():
    """Defers container imports until the single-instance lock is held."""
    from core.container import ServiceContainer

    return ServiceContainer.create_production()

def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print("SpectreHUD 2.0.0")
        sys.exit(0)
    if "--help" in sys.argv or "-h" in sys.argv:
        print("SpectreHUD - Sleek CTF Cheatsheet & Session Loot Overlay HUD")
        print("Usage: spectrehud [OPTIONS]")
        print("\nOptions:")
        print("  -h, --help     Show this message and exit")
        print("  -v, --version  Show version and exit")
        sys.exit(0)

    started_at = time.perf_counter()
    logger.info("Starting SpectreHUD application...")
    app = QApplication(sys.argv)
    _startup_mark(started_at, "QApplication ready")
    app.setApplicationName("SpectreHUD")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(CYBER_DARK_QSS)

    # Acquire this before creating services that access the registry, workspace,
    # clipboard or UI.  QLockFile also handles stale locks left by crashed runs.
    try:
        application_lock = acquire_application_lock()
    except ApplicationLockError as exc:
        logger.error("Could not acquire SpectreHUD application lock: %s", exc, exc_info=True)
        QMessageBox.critical(
            None,
            "SpectreHUD konnte nicht starten",
            "SpectreHUD konnte den Single-Instance-Lock nicht anlegen. "
            "Bitte prüfe, ob das Konfigurationsverzeichnis verfügbar und beschreibbar ist.",
        )
        return
    _startup_mark(started_at, "application lock acquired")
    if application_lock is None:
        QMessageBox.information(
            None,
            "SpectreHUD läuft bereits",
            "SpectreHUD läuft bereits. Bitte schließe die vorhandene Instanz, bevor du es erneut startest.",
        )
        return

    app_icon = get_app_icon()
    hotkey_listener = None
    try:
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)

        # Initialize Service Container
        container = _create_production_container()
        _startup_mark(started_at, "service container ready")
        app.setStyleSheet(build_app_theme(
            container.config_manager.get("ui_font", "segoe_ui"),
            container.config_manager.get("code_font", "consolas")
        ))
        container.clipboard_watcher.start_listening()

        # Main Window
        window = MainWindow(container=container)
        _startup_mark(started_at, "MainWindow constructed")
        if not app_icon.isNull():
            window.setWindowIcon(app_icon)
        window.show()
        _startup_mark(started_at, "MainWindow shown")

        # Global Hotkey Listener
        from core.hotkey_listener import HotkeyConfig
        from core.event_bus import EventType

        hotkey_toggle = container.config_manager.get("hotkey", "<ctrl>+<cmd>+<")
        hotkey_snip = container.config_manager.get("snip_hotkey", "<ctrl>+<cmd>+x")
        hotkey_quit = container.config_manager.get("quit_hotkey", "<ctrl>+<cmd>+q")
        hotkey_config = HotkeyConfig(toggle=hotkey_toggle, screenshot=hotkey_snip, quit=hotkey_quit)
        
        hotkey_listener = HotkeyListener(config=hotkey_config)
        hotkey_listener.toggle_requested.connect(window.toggle_visibility)
        hotkey_listener.screenshot_requested.connect(window.trigger_screenshot)
        hotkey_listener.quit_requested.connect(window.request_quit)
        hotkey_listener.start()
        _startup_mark(started_at, "hotkey listener started")

        # Register safety net shutdown hook
        app.aboutToQuit.connect(window.prepare_for_shutdown)

        # System Tray Icon (Default: Paused for privacy)
        tray_icon = QSystemTrayIcon(QIcon(create_tray_icon_pixmap(is_recording=False, app_icon=app_icon)), app)
        tray_icon.setToolTip("SpectreHUD [REC: Paused] - CTF Cheatsheet & Loot Overlay")
        tray_menu = QMenu()
        
        act_toggle = QAction("SpectreHUD anzeigen (Strg+Super+<)", tray_menu)
        act_toggle.triggered.connect(window.toggle_visibility)
        tray_menu.addAction(act_toggle)

        act_snip = QAction("Screenshot aufnehmen (Strg+Super+X)", tray_menu)
        act_snip.triggered.connect(window.trigger_screenshot)
        tray_menu.addAction(act_snip)

        act_rec_toggle = QAction("Clipboard-Logger aktivieren (Ctrl+P)", tray_menu)
        act_rec_toggle.triggered.connect(window._toggle_pause_history)
        tray_menu.addAction(act_rec_toggle)

        tray_menu.addSeparator()

        act_options = QAction("Optionen & Hotkeys... (Ctrl+,)", tray_menu)
        act_options.triggered.connect(window.open_settings_dialog)
        tray_menu.addAction(act_options)

        act_quit = QAction(f"Beenden ({hotkey_quit})", tray_menu)
        act_quit.triggered.connect(window.request_quit)
        tray_menu.addAction(act_quit)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.activated.connect(lambda reason: window.toggle_visibility() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray_icon.show()
        _startup_mark(started_at, "system tray ready")

        def update_tray_state(is_active: bool):
            tray_icon.setIcon(QIcon(create_tray_icon_pixmap(is_recording=is_active, app_icon=app_icon)))
            status = "REC: ON" if is_active else "REC: Paused"
            tray_icon.setToolTip(f"SpectreHUD [{status}] - CTF Cheatsheet & Loot Overlay")
            act_rec_toggle.setText(f"Clipboard-Logger {'pausieren' if is_active else 'fortsetzen'} (Ctrl+P)")

        container.clipboard_watcher.logging_state_changed.connect(update_tray_state)

        def on_hotkeys_changed(data: dict):
            new_toggle = data.get("hotkey", container.config_manager.get("hotkey", "<ctrl>+<cmd>+<"))
            new_snip = data.get("snip_hotkey", container.config_manager.get("snip_hotkey", "<ctrl>+<cmd>+x"))
            new_quit = data.get("quit_hotkey", container.config_manager.get("quit_hotkey", "<ctrl>+<cmd>+q"))
            new_cfg = HotkeyConfig(toggle=new_toggle, screenshot=new_snip, quit=new_quit)
            hotkey_listener.update_config(new_cfg)
            act_toggle.setText(f"SpectreHUD anzeigen ({new_toggle})")
            act_snip.setText(f"Screenshot aufnehmen ({new_snip})")
            act_quit.setText(f"Beenden ({new_quit})")

        container.event_bus.subscribe(EventType.HOTKEY_SETTINGS_CHANGED, on_hotkeys_changed)

        _startup_mark(started_at, "application ready")
        if os.environ.get("SPECTREHUD_STARTUP_PROFILE"):
            profile_exit_ms = int(os.environ.get("SPECTREHUD_PROFILE_EXIT_MS", "0"))
            if profile_exit_ms > 0:
                QTimer.singleShot(profile_exit_ms, app.quit)

        exit_code = app.exec()
        logger.info("SpectreHUD shutting down cleanly.")
    finally:
        if hotkey_listener is not None:
            hotkey_listener.stop()
        release_application_lock(application_lock)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
