from datetime import datetime
from typing import Optional, Tuple, List, Callable, Any
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt, QRect
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QGuiApplication, QPixmap, QPainter, QColor
from core.display_geometry import (
    ScreenGeometry,
    VirtualDesktopBoundingBox,
    compute_virtual_desktop_bounding_box,
    compute_screen_paint_offset,
)
from core.logger import get_logger


from core.platform import (
    PlatformCapabilities,
    ScreenCaptureStatus,
    detect_platform_capabilities,
)


class ScreenshotSaveError(RuntimeError):
    """Raised when writing the captured screenshot image file to disk fails."""

    pass


logger = get_logger("screenshot")


def _grab_window(screen: Any, window_id: int = 0) -> QPixmap:
    """Helper wrapping QScreen.grabWindow to bridge PyQt6 stub voidptr vs int."""
    return screen.grabWindow(window_id)  # type: ignore[arg-type,no-any-return]


class ScreenshotManager(QObject):
    """
    Coordinates desktop screenshots across single and multi-monitor setups,
    interactive region selection overlay, and automatic file & loot persistence.
    """

    screenshot_saved = pyqtSignal(dict)

    def __init__(
        self,
        parent: Optional[QObject] = None,
        capabilities: Optional[PlatformCapabilities] = None,
        overlay_factory: Optional[Callable[..., Any]] = None,
    ):
        super().__init__(parent)
        self._capabilities = (
            capabilities if capabilities is not None else detect_platform_capabilities()
        )
        self._overlay_factory = overlay_factory
        self._active_overlay: Optional[Any] = None

    @property
    def capabilities(self) -> PlatformCapabilities:
        return self._capabilities

    @property
    def overlay_factory(self) -> Optional[Callable[..., Any]]:
        """Returns the currently configured overlay factory."""
        return self._overlay_factory

    def set_overlay_factory(self, factory: Optional[Callable[..., Any]]) -> None:
        """Explicitly configures the UI overlay factory used for interactive screen captures."""
        self._overlay_factory = factory

    def is_capture_available(self) -> bool:
        """Return True if desktop screen grab is expected to work on the current OS session."""
        return self._capabilities.screen_capture

    def capture_status(self) -> ScreenCaptureStatus:
        """Return the explicit screen capture status (AVAILABLE, LIMITED, UNAVAILABLE)."""
        return self._capabilities.screen_capture_status

    def capture_virtual_desktop(
        self,
    ) -> Tuple[Optional[QPixmap], Optional[VirtualDesktopBoundingBox]]:
        """
        Captures screenshots of all active displays and composites them into a single QPixmap
        spanning the entire virtual desktop bounding box.

        Correctly handles:
        - Single-monitor setups (identical single grab behavior).
        - Multi-monitor setups with negative x/y offsets and mixed resolutions.
        - Mixed Device Pixel Ratios (DPR).
        - Graceful fallback to primary screen if multi-grab encounters errors or empty pixmaps.
        """
        screens = QGuiApplication.screens()
        if not screens:
            logger.warning("No display screens detected by Qt for desktop capture.")
            return None, None

        # Single-monitor fast path (zero overhead / 100% backward compatible)
        if len(screens) == 1:
            primary = screens[0]
            try:
                pix = _grab_window(primary, 0)
                if not pix.isNull():
                    geom = primary.geometry()
                    bbox = VirtualDesktopBoundingBox(
                        geom.x(), geom.y(), geom.width(), geom.height()
                    )
                    return pix, bbox
                else:
                    logger.warning(f"Primary screen {primary.name()} returned null pixmap on grab.")
                    return None, None
            except Exception as e:
                logger.error(f"Failed to grab primary screen: {e}", exc_info=True)
                return None, None

        # Multi-monitor composite path
        try:
            screen_geoms: List[ScreenGeometry] = []
            for s in screens:
                geom = s.geometry()
                dpr = s.devicePixelRatio()
                screen_geoms.append(
                    ScreenGeometry(
                        x=geom.x(),
                        y=geom.y(),
                        width=geom.width(),
                        height=geom.height(),
                        device_pixel_ratio=dpr,
                    )
                )

            bbox = compute_virtual_desktop_bounding_box(screen_geoms)
            if bbox.width <= 0 or bbox.height <= 0:
                logger.warning(f"Invalid virtual desktop bounding box computed: {bbox}")
                return None, None

            composite = QPixmap(bbox.width, bbox.height)
            composite.fill(QColor(10, 14, 20))  # dark fallback background for multi-monitor gaps

            painter = QPainter(composite)
            success_count = 0

            for s, s_geom in zip(screens, screen_geoms):
                try:
                    pix = _grab_window(s, 0)
                    if pix.isNull():
                        logger.warning(
                            f"Screen '{s.name()}' returned null pixmap on grab (e.g. Wayland restriction)."
                        )
                        continue

                    offset_x, offset_y = compute_screen_paint_offset(s_geom, bbox)
                    target_rect = QRect(offset_x, offset_y, s_geom.width, s_geom.height)

                    # Draw screen grab into logical target rect
                    painter.drawPixmap(target_rect, pix)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error grabbing screen '{s.name()}': {e}", exc_info=True)

            painter.end()

            if success_count > 0:
                logger.info(
                    f"Successfully captured {success_count}/{len(screens)} screens across virtual desktop {bbox.width}x{bbox.height} at ({bbox.min_x}, {bbox.min_y})"
                )
                return composite, bbox
            else:
                logger.warning(
                    "All multi-monitor screen grabs failed. Attempting primary screen fallback."
                )
                fallback_screen = QGuiApplication.primaryScreen()
                if fallback_screen is not None:
                    fallback_pix = _grab_window(fallback_screen, 0)
                    if not fallback_pix.isNull():
                        geom = fallback_screen.geometry()
                        return fallback_pix, VirtualDesktopBoundingBox(
                            geom.x(), geom.y(), geom.width(), geom.height()
                        )
                return None, None

        except Exception as e:
            logger.error(
                f"Unexpected error during multi-monitor virtual desktop capture: {e}", exc_info=True
            )
            # Fallback to primary screen
            fallback_screen = QGuiApplication.primaryScreen()
            if fallback_screen is not None:
                try:
                    fallback_pix = _grab_window(fallback_screen, 0)
                    if not fallback_pix.isNull():
                        geom = fallback_screen.geometry()
                        return fallback_pix, VirtualDesktopBoundingBox(
                            geom.x(), geom.y(), geom.width(), geom.height()
                        )
                except Exception:
                    pass
            return None, None

    def start_capture(
        self,
        parent_window: QWidget,
        project_manager,
        loot_manager,
        target_ip: str = "",
        overlay_factory: Optional[Callable[..., Any]] = None,
    ) -> bool:
        """
        Main entry point:
        1. Checks desktop capability availability.
        2. Hides parent window.
        3. Delays 220ms for clean desktop view.
        4. Grabs virtual desktop across all active monitors.
        5. Launches injected overlay_factory.
        """
        if not self.is_capture_available():
            if self._capabilities.wayland:
                logger.warning(
                    "Desktop screenshot capture is unavailable or restricted in this Wayland session."
                )
            else:
                logger.warning(
                    f"Desktop screenshot capture is not supported on platform '{self._capabilities.system}'."
                )
            return False

        factory = overlay_factory or self._overlay_factory
        if factory is None:
            logger.warning("No overlay factory configured for interactive screenshot capture.")
            return False

        was_visible = parent_window.isVisible()
        parent_window.hide()

        def do_grab():
            try:
                full_pixmap, bbox = self.capture_virtual_desktop()
                if not full_pixmap or full_pixmap.isNull():
                    logger.warning("No valid desktop pixmap captured for snip overlay.")
                    if was_visible:
                        parent_window.show()
                    return

                self._active_overlay = factory(full_pixmap, bbox=bbox)

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
        return True

    def _on_snip_completed(
        self,
        cropped_pixmap: QPixmap,
        parent_window: QWidget,
        project_manager,
        loot_manager,
        target_ip: str,
    ) -> None:
        """Saves cropped pixmap to project loot directory and creates Loot entry."""
        try:
            active_proj = project_manager.get_active_project()
            proj_dir = project_manager.get_project_dir(active_proj)
            loot_dir = proj_dir / "loot"
            loot_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now()
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            filepath = loot_dir / f"screenshot_{timestamp_str}.png"
            counter = 1
            while filepath.exists():
                filepath = loot_dir / f"screenshot_{timestamp_str}_{counter}.png"
                counter += 1

            filename = filepath.name

            # Save PNG to disk
            success = cropped_pixmap.save(str(filepath), "PNG")
            if not success:
                logger.error(f"Failed to save cropped screenshot PNG to {filepath}")
                raise ScreenshotSaveError(f"Failed to save cropped screenshot PNG to {filepath}")

            logger.info(f"Saved screenshot snip to {filepath}")

            # Create loot entry only AFTER successful file write
            default_title = f"Screenshot {now.strftime('%Y-%m-%d %H:%M:%S')}"
            markdown_content = f"![{default_title}](loot/{filename})"

            loot_entry = loot_manager.add_entry(
                entry_type="screenshot",
                title=default_title,
                content=markdown_content,
                target_ip=target_ip,
            )
            loot_entry["file_path"] = str(filepath)

            # AppController owns both the state commit and the single domain event.
            self.screenshot_saved.emit(loot_entry)
        except (OSError, RuntimeError) as e:
            logger.error(f"Error handling completed snip: {e}", exc_info=True)
            raise
        finally:
            self._restore_parent_window(parent_window)

    def _restore_parent_window(self, parent_window: QWidget) -> None:
        """Restore the HUD after a completed or failed screenshot lifecycle."""
        try:
            parent_window.show()
            parent_window.setWindowState(
                parent_window.windowState() & ~Qt.WindowState.WindowMinimized
                | Qt.WindowState.WindowActive
            )
            parent_window.raise_()
            parent_window.activateWindow()

        except RuntimeError as e:
            logger.error(f"Error restoring parent window after screenshot: {e}")

    def _on_snip_cancelled(self, parent_window: QWidget) -> None:
        """Restores HUD when user cancels snip."""
        self._restore_parent_window(parent_window)
