import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QGuiApplication, QPixmap
from ui.snipping_overlay import SnippingOverlay
from core.logger import get_logger

logger = get_logger("screenshot")

class ScreenshotManager(QObject):
    """
    Coordinates desktop screenshots, interactive region selection overlay,
    and automatic file & loot persistence.
    """
    screenshot_saved = pyqtSignal(dict)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_overlay: Optional[SnippingOverlay] = None

    def start_capture(self, parent_window: QWidget, project_manager, loot_manager, target_ip: str = "") -> None:
        """
        Main entry point:
        1. Hides parent window.
        2. Delays 200ms for clean desktop view.
        3. Grabs desktop.
        4. Launches SnippingOverlay.
        """
        was_visible = parent_window.isVisible()
        parent_window.hide()

        def do_grab():
            try:
                screen = QGuiApplication.primaryScreen()
                if not screen:
                    logger.warning("No primary screen detected for screenshot capture.")
                    if was_visible:
                        parent_window.show()
                    return

                full_pixmap = screen.grabWindow(0)
                self._active_overlay = SnippingOverlay(full_pixmap)
                
                self._active_overlay.snip_completed.connect(
                    lambda cropped: self._on_snip_completed(
                        cropped, parent_window, project_manager, loot_manager, target_ip
                    )
                )
                self._active_overlay.snip_cancelled.connect(
                    lambda: self._on_snip_cancelled(parent_window)
                )
            except (RuntimeError, OSError) as e:
                logger.error(f"Error during desktop grab: {e}", exc_info=True)
                if was_visible:
                    parent_window.show()

        QTimer.singleShot(220, do_grab)

    def _on_snip_completed(
        self, 
        cropped_pixmap: QPixmap, 
        parent_window: QWidget, 
        project_manager, 
        loot_manager,
        target_ip: str
    ) -> None:
        """Saves cropped pixmap to project loot directory and creates Loot entry."""
        try:
            active_proj = project_manager.get_active_project()
            proj_dir = project_manager.get_project_dir(active_proj)
            loot_dir = proj_dir / "loot"
            loot_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now()
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp_str}.png"
            filepath = loot_dir / filename

            # Save PNG to disk
            success = cropped_pixmap.save(str(filepath), "PNG")
            if not success:
                logger.error(f"Failed to save cropped screenshot PNG to {filepath}")
            else:
                logger.info(f"Saved screenshot snip to {filepath}")

            # Create loot entry
            default_title = f"Screenshot {now.strftime('%Y-%m-%d %H:%M:%S')}"
            markdown_content = f"![{default_title}](loot/{filename})"

            loot_entry = loot_manager.add_entry(
                entry_type="screenshot",
                title=default_title,
                content=markdown_content,
                target_ip=target_ip
            )
            loot_entry["file_path"] = str(filepath)
            self.screenshot_saved.emit(loot_entry)
        except (OSError, RuntimeError) as e:
            logger.error(f"Error handling completed snip: {e}", exc_info=True)

        # Restore and switch HUD to loot mode
        try:
            parent_window.show()
            parent_window.setWindowState(parent_window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            parent_window.raise_()
            parent_window.activateWindow()

            if hasattr(parent_window, "switch_mode"):
                parent_window.switch_mode("loot")
            if hasattr(parent_window, "refresh_filter_pills"):
                parent_window.refresh_filter_pills()
            if hasattr(parent_window, "refresh_content"):
                parent_window.refresh_content()
        except RuntimeError as e:
            logger.error(f"Error restoring parent window after screenshot: {e}")

    def _on_snip_cancelled(self, parent_window: QWidget) -> None:
        """Restores HUD when user cancels snip."""
        try:
            parent_window.show()
            parent_window.raise_()
            parent_window.activateWindow()
        except RuntimeError as e:
            logger.error(f"Error restoring parent window after cancel: {e}")
