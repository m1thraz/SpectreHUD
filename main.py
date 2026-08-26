import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt

from core.config import ConfigManager
from core.snippet_manager import SnippetManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.project_manager import ProjectManager
from core.hotkey_listener import HotkeyListener
from core.logger import setup_logger, get_logger
from ui.main_window import MainWindow

from ui.styles import CYBER_DARK_QSS

logger = get_logger("app")

def create_tray_icon_pixmap(is_recording: bool = True) -> QPixmap:
    """Generates a clean programmatic icon with visual recording status."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Outer circle/box
    bg_color = QColor("#00e5ff") if is_recording else QColor("#484f58")
    painter.setBrush(bg_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
    
    # Symbol
    painter.setPen(QColor("#0d1117") if is_recording else QColor("#c9d1d9"))
    font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

    # Visual Red Recording Dot in top-right corner if recording
    if is_recording:
        painter.setBrush(QColor("#f85149"))
        painter.setPen(QColor("#ffffff"))
        painter.drawEllipse(20, 2, 10, 10)

    painter.end()
    return pixmap

def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print("SpectreHUD 1.0.0")
        return 0
    if "--help" in sys.argv or "-h" in sys.argv:
        print("SpectreHUD - Sleek CTF Cheatsheet & Session Loot Overlay HUD")
        print("Usage: spectrehud [OPTIONS]")
        print("\nOptions:")
        print("  -h, --help     Show this message and exit")
        print("  -v, --version  Show version and exit")
        return 0

    logger.info("Starting SpectreHUD application...")
    app = QApplication(sys.argv)
    app.setApplicationName("SpectreHUD")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(CYBER_DARK_QSS)

    # Initialize Managers
    config_manager = ConfigManager()
    from core.i18n import set_locale, t
    set_locale(config_manager.get("language", "de"))

    snippet_manager = SnippetManager()
    project_manager = ProjectManager()
    loot_manager = LootManager()
    clipboard_watcher = ClipboardWatcher()
    clipboard_watcher.start_listening()

    # Main Window
    window = MainWindow(config_manager, snippet_manager, loot_manager, clipboard_watcher, project_manager)
    window.show()

    # Global Hotkey Listener
    hotkey_str = config_manager.get("hotkey", "<ctrl>+<cmd>+<")
    hotkey_listener = HotkeyListener(hotkey_str=hotkey_str)
    hotkey_listener.toggle_requested.connect(window.toggle_visibility)
    hotkey_listener.screenshot_requested.connect(window.trigger_screenshot)
    hotkey_listener.quit_requested.connect(app.quit)
    hotkey_listener.start()

    # System Tray Icon (Default: Paused for privacy)
    tray_icon = QSystemTrayIcon(QIcon(create_tray_icon_pixmap(is_recording=False)), app)
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

    act_quit = QAction("Beenden (Strg+Super+Q)", tray_menu)
    act_quit.triggered.connect(app.quit)
    tray_menu.addAction(act_quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(lambda reason: window.toggle_visibility() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray_icon.show()

    def update_tray_state(is_active: bool):
        tray_icon.setIcon(QIcon(create_tray_icon_pixmap(is_recording=is_active)))
        status = "REC: ON" if is_active else "REC: Paused"
        tray_icon.setToolTip(f"SpectreHUD [{status}] - CTF Cheatsheet & Loot Overlay")
        act_rec_toggle.setText(f"Clipboard-Logger {'pausieren' if is_active else 'fortsetzen'} (Ctrl+P)")

    clipboard_watcher.logging_state_changed.connect(update_tray_state)

    # Clean exit
    exit_code = app.exec()
    logger.info("SpectreHUD shutting down cleanly.")
    hotkey_listener.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
