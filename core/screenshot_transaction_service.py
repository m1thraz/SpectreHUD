"""Transactional completion of screenshot persistence without UI concerns."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from core.logger import get_logger
from core.loot_manager import LootManager


logger = get_logger(__name__)


@dataclass(frozen=True)
class ScreenshotTransactionResult:
    """Outcome of committing the project state for a captured screenshot."""

    ok: bool
    error: Optional[BaseException] = None
    cleanup_errors: tuple[BaseException, ...] = ()


class ScreenshotTransactionService:
    """Persist a completed screenshot or roll back its loot and image artifacts."""

    def __init__(
        self,
        loot_manager: LootManager,
        persist_project_state: Callable[[], bool],
    ) -> None:
        self.loot_manager = loot_manager
        self.persist_project_state = persist_project_state

    def commit(self, loot_entry: Mapping[str, Any]) -> ScreenshotTransactionResult:
        """Commit project state and clean up screenshot artifacts on failure."""
        failure: BaseException
        try:
            if self.persist_project_state():
                return ScreenshotTransactionResult(ok=True)
            failure = RuntimeError("Project state save failed after screenshot capture.")
        except Exception as exc:
            failure = exc

        logger.error("Screenshot project-state commit failed: %s", failure)
        cleanup_errors = self._rollback(loot_entry)
        return ScreenshotTransactionResult(
            ok=False,
            error=failure,
            cleanup_errors=cleanup_errors,
        )

    def _rollback(self, loot_entry: Mapping[str, Any]) -> tuple[BaseException, ...]:
        cleanup_errors: list[BaseException] = []
        screenshot_id = loot_entry.get("id")
        if screenshot_id:
            entries_before_screenshot = [
                entry
                for entry in self.loot_manager.get_all_entries()
                if entry.get("id") != screenshot_id
            ]
            try:
                self.loot_manager.replace_entries_and_persist(entries_before_screenshot)
            except Exception as exc:
                cleanup_errors.append(exc)
                logger.exception(
                    "Failed to roll back loot after screenshot session-save failure."
                )

        file_path = loot_entry.get("file_path")
        if file_path:
            try:
                Path(str(file_path)).unlink(missing_ok=True)
            except OSError as exc:
                cleanup_errors.append(exc)
                logger.error(
                    "Failed to remove screenshot PNG after session rollback: %s",
                    exc,
                )

        return tuple(cleanup_errors)
