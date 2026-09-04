"""Transactional application shutdown workflow."""

from typing import Callable

from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from core.i18n import t
from core.storage import PersistenceError


class ShutdownCoordinator:
    """Coordinates dirty checks, persistence, geometry flush, and termination."""

    def __init__(
        self,
        *,
        window: QWidget,
        config,
        confirm_discard: Callable[[], bool],
        save_project_state: Callable[[], bool],
        logger,
    ) -> None:
        self._window = window
        self._config = config
        self._confirm_discard = confirm_discard
        self._save_project_state = save_project_state
        self._logger = logger

    def request_quit(self, *, quit_app: bool = True) -> bool:
        """Return whether shutdown may proceed after all safety checks."""
        if not self._confirm_discard():
            return False

        if not self._save_project_state() and not self._resolve_save_failure():
            return False

        self._persist_window_geometry()
        if quit_app:
            app = QApplication.instance()
            if app:
                app.quit()
        return True

    def _resolve_save_failure(self) -> bool:
        message = QMessageBox(self._window)
        message.setWindowTitle(t("quit.save_failed_title", "Save Failed"))
        message.setText(
            t(
                "quit.save_failed_text",
                "The current project state could not be saved to disk.\n\n"
                "What would you like to do?",
            )
        )
        message.setIcon(QMessageBox.Icon.Warning)
        retry_button = message.addButton(
            t("quit.retry", "Retry Save"), QMessageBox.ButtonRole.ActionRole
        )
        discard_button = message.addButton(
            t("quit.discard", "Quit Without Saving"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = message.addButton(
            t("quit.cancel", "Cancel"), QMessageBox.ButtonRole.RejectRole
        )
        message.setDefaultButton(cancel_button)
        message.exec()
        clicked = message.clickedButton()
        if clicked == retry_button:
            return self._save_project_state()
        return clicked == discard_button

    def _persist_window_geometry(self) -> None:
        try:
            self._config.update(
                {
                    "window_width": self._window.width(),
                    "window_height": self._window.height(),
                }
            )
        except PersistenceError as exc:
            self._logger.warning(
                "Could not persist window geometry during shutdown: %s", exc
            )
        except Exception:
            self._logger.exception(
                "Unexpected error while persisting window geometry during shutdown"
            )
