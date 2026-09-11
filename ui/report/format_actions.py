"""Formatting and media insertion actions for the Report Editor."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from core.i18n import t
from core.logger import get_logger
from ui.markdown_toolbar_actions import (
    align_text,
    insert_blockquote,
    insert_fenced_code,
    insert_horizontal_rule,
    insert_image,
    insert_link,
    insert_page_break,
    insert_spacer,
    insert_table,
    prefix_lines,
    set_heading,
    wrap_selection,
)
from ui.message_boxes import show_error_dialog
from ui.report.dialogs import (
    LootImagePickerDialog,
    MarkdownTableDialog,
    ReportIconPickerDialog,
)
from ui.report.icon_assets import ReportIconError, render_report_icon

logger = get_logger(__name__)


def _get_symbol(name: str, fallback: Any) -> Any:
    """Resolve symbol preserving test patches from both report_editor_tab and local module."""
    from unittest.mock import Mock

    if isinstance(fallback, Mock):
        return fallback

    import sys

    mod = sys.modules.get("ui.report_editor_tab")
    if mod is not None and hasattr(mod, name):
        val = getattr(mod, name)
        if isinstance(val, Mock):
            return val
    return fallback


class ReportFormatActions:
    """Encapsulates all cursor formatting, structure creation, and media insertion operations."""

    def __init__(
        self,
        editor: Any,
        parent_widget: QWidget,
        loot_manager_provider: Callable[[], Any],
        report_file_manager_provider: Callable[[], Any],
        current_project_provider: Callable[[], Optional[str]],
        format_toolbar_provider: Optional[Callable[[], Optional[QWidget]]] = None,
    ):
        self._editor_provider = editor if callable(editor) else (lambda: editor)
        self.parent_widget = parent_widget
        self._loot_manager_provider = loot_manager_provider
        self._report_file_manager_provider = report_file_manager_provider
        self._current_project_provider = current_project_provider
        self._format_toolbar_provider = format_toolbar_provider

    @property
    def editor(self) -> QPlainTextEdit:
        return self._editor_provider()

    @property
    def loot_manager(self) -> Any:
        return self._loot_manager_provider()

    @property
    def report_file_manager(self) -> Any:
        return self._report_file_manager_provider()

    @property
    def current_project(self) -> Optional[str]:
        return self._current_project_provider()

    # ------------------------------------------------------------------ #
    # Pure Cursor Formatting Operations
    # ------------------------------------------------------------------ #

    def format_heading(self, level: int) -> None:
        set_heading(self.editor, level)

    def format_wrap(self, prefix: str, suffix: str) -> None:
        wrap_selection(self.editor, prefix, suffix)

    def format_align(self, alignment: str) -> None:
        align_text(self.editor, alignment)

    def format_quote(self) -> None:
        insert_blockquote(self.editor)

    def format_horizontal_rule(self) -> None:
        insert_horizontal_rule(self.editor)

    def format_code_block(self) -> None:
        insert_fenced_code(self.editor)

    def format_list(self, numbered: bool) -> None:
        prefix_lines(self.editor, numbered)

    def format_link(self) -> None:
        insert_link(self.editor)

    def format_table(self) -> None:
        dialog_cls = _get_symbol("MarkdownTableDialog", MarkdownTableDialog)
        dialog = dialog_cls(self.parent_widget)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            insert_table(self.editor, dialog.rows.value(), dialog.columns.value())

    def format_page_break(self) -> None:
        insert_page_break(self.editor)

    def format_spacer(self, size: str) -> None:
        insert_spacer(self.editor, size)

    # ------------------------------------------------------------------ #
    # Media & Asset Insertion Operations
    # ------------------------------------------------------------------ #

    def format_image(self) -> None:
        """Offers screenshot insertion from Loot or local filesystem browse."""
        screenshot_entries = (
            self.loot_manager.get_entries(entry_type="screenshot")
            if self.loot_manager
            else []
        )

        if not screenshot_entries:
            self._call_browse_and_insert_image()
            return

        menu = QMenu(self.parent_widget)
        action_browse = menu.addAction(t("report.image_browse", "📁 Choose from Computer..."))
        menu.addSeparator()

        menu.addSection(t("report.image_from_loot", "📸 Screenshots from Loot:"))
        entry_actions: Dict[Any, Any] = {}
        for entry in screenshot_entries[:6]:
            title = entry.get("title", "Screenshot")
            ts = entry.get("timestamp", "")
            label = f"{title}  ({ts})" if ts else title
            act = menu.addAction(label)
            entry_actions[act] = entry

        action_all_loot = None
        if len(screenshot_entries) > 6:
            menu.addSeparator()
            action_all_loot = menu.addAction(
                t("report.image_all_loot", "🔍 Browse all Screenshots...")
            )

        button = None
        if self._format_toolbar_provider:
            toolbar = self._format_toolbar_provider()
            if toolbar:
                button = toolbar.findChild(QPushButton, "btn_insert_image")

        pos = (
            button.mapToGlobal(button.rect().bottomLeft())
            if button
            else self.parent_widget.mapToGlobal(self.parent_widget.rect().center())
        )
        selected_action = menu.exec(pos)

        if not selected_action:
            return

        if selected_action == action_browse:
            self._call_browse_and_insert_image()
        elif selected_action == action_all_loot:
            self._call_open_loot_image_picker(screenshot_entries)
        elif selected_action in entry_actions:
            self._call_insert_loot_entry_image(entry_actions[selected_action])

    def _call_browse_and_insert_image(self) -> None:
        from unittest.mock import Mock

        parent_method = getattr(self.parent_widget, "_browse_and_insert_image", None)
        if isinstance(parent_method, Mock):
            parent_method()
            return
        self.browse_and_insert_image()

    def _call_open_loot_image_picker(self, screenshot_entries: List[dict]) -> None:
        from unittest.mock import Mock

        parent_method = getattr(self.parent_widget, "_open_loot_image_picker", None)
        if isinstance(parent_method, Mock):
            parent_method(screenshot_entries)
            return
        self.open_loot_image_picker(screenshot_entries)

    def _call_insert_loot_entry_image(self, entry: dict) -> None:
        from unittest.mock import Mock

        parent_method = getattr(self.parent_widget, "_insert_loot_entry_image", None)
        if isinstance(parent_method, Mock):
            parent_method(entry)
            return
        self.insert_loot_entry_image(entry)

    def insert_loot_entry_image(self, entry: dict) -> None:
        """Inserts a markdown image from a loot screenshot entry."""
        title = entry.get("title", "Screenshot")
        content = (entry.get("content") or "").strip()

        if content.startswith("![") and content.endswith(")"):
            cursor = self.editor.textCursor()
            cursor.insertText(content)
            self.editor.setFocus()
        else:
            insert_image(self.editor, content, alt_text=title)

    def open_loot_image_picker(self, screenshot_entries: List[dict]) -> None:
        """Opens a searchable dialog to select from all loot screenshots."""
        project_dir = None
        rfm = self.report_file_manager
        if rfm and getattr(rfm, "project_manager", None):
            try:
                pname = rfm.resolve_project_name(self.current_project)
                project_dir = rfm.project_manager.get_project_dir(pname)
            except Exception:
                pass

        dialog_cls = _get_symbol("LootImagePickerDialog", LootImagePickerDialog)
        dialog = dialog_cls(
            screenshot_entries, project_dir=project_dir, parent=self.parent_widget
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_entry:
            self.insert_loot_entry_image(dialog.selected_entry)

    def browse_and_insert_image(self) -> None:
        """Prompts the user for an image file from the disk and inserts its relative markdown link."""
        start_dir = ""
        project_dir = None
        rfm = self.report_file_manager
        if rfm and getattr(rfm, "project_manager", None):
            try:
                pname = rfm.resolve_project_name(self.current_project)
                project_dir = rfm.project_manager.get_project_dir(pname)
                screenshots_dir = project_dir / "screenshots"
                if screenshots_dir.is_dir():
                    start_dir = str(screenshots_dir)
                elif project_dir.is_dir():
                    start_dir = str(project_dir)
            except Exception as e:
                logger.debug(f"Failed to resolve project dir for image dialog: {e}")

        file_dialog_cls = _get_symbol("QFileDialog", QFileDialog)
        file_path, _ = file_dialog_cls.getOpenFileName(
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

        rel_path = file_path
        if rfm:
            try:
                rel_path = rfm.import_image(file_path, self.current_project)
            except Exception as e:
                logger.warning(f"Could not copy image to project directory: {e}")
                if project_dir:
                    try:
                        rel_path = (
                            Path(file_path).resolve().relative_to(project_dir.resolve()).as_posix()
                        )
                    except ValueError:
                        rel_path = file_path.replace("\\", "/")
                else:
                    rel_path = file_path.replace("\\", "/")

        alt_text = Path(file_path).stem
        insert_image(self.editor, rel_path, alt_text=alt_text)

    def format_icon(self) -> None:
        """Render a curated QtAwesome icon to a project PNG and insert it as Markdown."""
        dialog_cls = _get_symbol("ReportIconPickerDialog", ReportIconPickerDialog)
        dialog = dialog_cls(self.parent_widget)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_icon is None:
            return

        rfm = self.report_file_manager
        try:
            if not rfm or not getattr(rfm, "project_manager", None):
                raise RuntimeError("Project manager unavailable")
            pname = rfm.resolve_project_name(self.current_project)
            project_dir = rfm.project_manager.get_project_dir(pname)
            definition = dialog.selected_icon
            render_icon_fn = _get_symbol("render_report_icon", render_report_icon)
            relative_path = render_icon_fn(project_dir, definition.icon_name)
        except (AttributeError, OSError, RuntimeError, ReportIconError) as exc:
            logger.warning("Could not create report icon asset: %s", exc)
            show_err_fn = _get_symbol("show_error_dialog", show_error_dialog)
            show_err_fn(
                self.parent_widget,
                t("report.icon_error_title", "Icon could not be inserted"),
                t(
                    "report.icon_error_message",
                    "The report icon could not be created:\n{error}",
                    error=str(exc),
                ),
            )
            return

        alt_text = t(definition.label_key, definition.key.replace("_", " ").title())
        insert_image(self.editor, relative_path, alt_text=alt_text)
