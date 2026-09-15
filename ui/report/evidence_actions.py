"""Evidence attachment workflows for report findings."""

from pathlib import Path
import re
from typing import Any, Callable, Optional
import uuid

from PyQt6.QtWidgets import QDialog, QFileDialog, QWidget

from core.i18n import t
from core.logger import get_logger
from core.reporting import ReportEvidenceItem, supporting_evidence_from_loot_entry
from ui.message_boxes import show_warning_dialog
from ui.report.dialogs import (
    ClipboardHistoryPickerDialog,
    LootEntryPickerDialog,
    LootImagePickerDialog,
)

logger = get_logger(__name__)


class ReportEvidenceActions:
    """Collect evidence from project sources and attach normalized items."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        loot_manager_provider: Callable[[], Any],
        clipboard_history_provider: Callable[[], Any],
        report_file_manager_provider: Callable[[], Any],
        current_project_provider: Callable[[], Optional[str]],
        attach_evidence: Callable[[ReportEvidenceItem], None],
    ):
        self.parent_widget = parent_widget
        self._loot_manager_provider = loot_manager_provider
        self._clipboard_history_provider = clipboard_history_provider
        self._report_file_manager_provider = report_file_manager_provider
        self._current_project_provider = current_project_provider
        self._attach_evidence = attach_evidence

    @property
    def loot_manager(self) -> Any:
        return self._loot_manager_provider()

    @property
    def clipboard_history(self) -> Any:
        return self._clipboard_history_provider()

    @property
    def report_file_manager(self) -> Any:
        return self._report_file_manager_provider()

    @property
    def current_project(self) -> Optional[str]:
        return self._current_project_provider()

    def attach_loot_screenshot(self) -> None:
        loot_manager = self.loot_manager
        if not loot_manager:
            return
        screenshot_entries = [
            entry
            for entry in loot_manager.get_all_entries()
            if entry.get("type") in ("screenshot", "image")
            or "![image]" in (entry.get("content") or "")
        ]
        if not screenshot_entries:
            show_warning_dialog(
                self.parent_widget,
                t("report.no_screenshots_title", "Keine Screenshots gefunden"),
                t(
                    "report.no_screenshots_msg",
                    "Im aktiven Projekt wurden noch keine Screenshots in Loot erfasst.",
                ),
            )
            return

        project_dir = self._resolve_project_dir()
        dialog = LootImagePickerDialog(
            screenshot_entries,
            project_dir=project_dir,
            parent=self.parent_widget,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_entry:
            return

        entry = dialog.selected_entry
        content = (entry.get("content") or "").strip()
        markdown_target = re.search(r"\((.*?)\)", content)
        self._attach_evidence(
            ReportEvidenceItem(
                id=self._new_id(),
                type="screenshot",
                caption=entry.get("title", "Screenshot"),
                content=markdown_target.group(1) if markdown_target else content,
                source_loot_id=entry.get("id"),
            )
        )

    def attach_image_file(self) -> None:
        report_file_manager = self.report_file_manager
        project_dir = self._resolve_project_dir()
        start_dir = ""
        if project_dir is not None:
            screenshots_dir = project_dir / "screenshots"
            if screenshots_dir.is_dir():
                start_dir = str(screenshots_dir)
            elif project_dir.is_dir():
                start_dir = str(project_dir)

        file_path, _ = QFileDialog.getOpenFileName(
            self.parent_widget,
            t("report.select_image_title", "Select Image"),
            start_dir,
            t(
                "report.select_image_filter",
                "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All Files (*.*)",
            ),
        )
        if not file_path:
            return

        relative_path = file_path
        if report_file_manager:
            try:
                relative_path = report_file_manager.import_image(file_path, self.current_project)
            except Exception as error:
                logger.warning("Could not copy image to project directory: %s", error)
                relative_path = self._portable_image_path(file_path, project_dir)

        self._attach_evidence(
            ReportEvidenceItem(
                id=self._new_id(),
                type="screenshot",
                caption=Path(file_path).stem,
                content=relative_path,
            )
        )

    def attach_clipboard_history(self) -> None:
        clipboard_history = self.clipboard_history
        if not clipboard_history:
            return
        history = clipboard_history.get_all_history()
        if not history:
            show_warning_dialog(
                self.parent_widget,
                t("report.no_clipboard_title", "Keine Clipboard-Einträge"),
                t(
                    "report.no_clipboard_msg",
                    "In der Clipboard-Historie wurden noch keine Einträge erfasst.",
                ),
            )
            return

        dialog = ClipboardHistoryPickerDialog(history, parent=self.parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_entry:
            return

        text = dialog.selected_entry.get("text", "").strip()
        first_line = text.splitlines()[0] if text else "Terminal Output"
        if len(first_line) > 40:
            first_line = first_line[:37] + "..."
        self._attach_evidence(
            ReportEvidenceItem(
                id=self._new_id(),
                type="terminal",
                caption=first_line,
                content=text,
                source_loot_id=dialog.selected_entry.get("id"),
            )
        )

    def attach_loot_entry(self) -> None:
        loot_manager = self.loot_manager
        if not loot_manager:
            return
        entries = loot_manager.get_all_entries()
        if not entries:
            show_warning_dialog(
                self.parent_widget,
                t("report.no_loot_title", "Keine Loot-Einträge"),
                t(
                    "report.no_loot_msg",
                    "Im aktiven Projekt wurden noch keine Einträge in Loot gespeichert.",
                ),
            )
            return

        dialog = LootEntryPickerDialog(entries, parent=self.parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_entry:
            return

        entry = dialog.selected_entry
        evidence = supporting_evidence_from_loot_entry(entry)
        if evidence is not None:
            self._attach_evidence(evidence)

    def _resolve_project_dir(self) -> Optional[Path]:
        report_file_manager = self.report_file_manager
        if not report_file_manager or not getattr(report_file_manager, "project_manager", None):
            return None
        try:
            project_name = report_file_manager.resolve_project_name(self.current_project)
            return report_file_manager.project_manager.get_project_dir(project_name)
        except Exception as error:
            logger.debug("Failed to resolve report project directory: %s", error)
            return None

    @staticmethod
    def _portable_image_path(file_path: str, project_dir: Optional[Path]) -> str:
        if project_dir is not None:
            try:
                return Path(file_path).resolve().relative_to(project_dir.resolve()).as_posix()
            except ValueError:
                pass
        return file_path.replace("\\", "/")

    @staticmethod
    def _new_id() -> str:
        return f"ev-{uuid.uuid4().hex[:6]}"
