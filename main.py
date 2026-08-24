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
from ui.main_window import MainWindow

def create_tray_icon_pixmap() -> QPixmap:
    """Generates a clean programmatic icon if no image file exists."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Outer circle
    painter.setBrush(QColor("#00e5ff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
    
    # Symbol
    painter.setPen(QColor("#0d1117"))
    font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "⚡")
    painter.end()
    return pixmap

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SpectreHUD")
    app.setQuitOnLastWindowClosed(False)

    # Initialize Managers
    config_manager = ConfigManager()
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
    hotkey_listener.start()

    # System Tray Icon
    tray_icon = QSystemTrayIcon(QIcon(create_tray_icon_pixmap()), app)
    tray_icon.setToolTip("SpectreHUD - CTF Cheatsheet & Loot Overlay")
    tray_menu = QMenu()
    
    act_toggle = QAction("SpectreHUD anzeigen (Strg+Super+<)", tray_menu)
    act_toggle.triggered.connect(window.toggle_visibility)
    tray_menu.addAction(act_toggle)

    tray_menu.addSeparator()

    act_quit = QAction("Beenden", tray_menu)
    act_quit.triggered.connect(app.quit)
    tray_menu.addAction(act_quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(lambda reason: window.toggle_visibility() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray_icon.show()

    # Clean exit
    exit_code = app.exec()
    hotkey_listener.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
