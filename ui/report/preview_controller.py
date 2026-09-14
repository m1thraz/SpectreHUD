"""Rendering and interaction controller for the Report Workspace preview."""

from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextFormat
from PyQt6.QtWidgets import QScrollBar, QTextEdit

from ui.report.preview import ReportDocument, ReportPreviewEdit
from ui.report.preview_transforms import (
    PREVIEW_PAGEBREAK_LABEL,
    PREVIEW_PAGEBREAK_TOKEN,
    PREVIEW_SPACER_LABELS,
    PREVIEW_SPACER_TOKENS,
    prepare_preview_markdown,
)
from ui.report.report_light_palette import REPORT_LIGHT_PALETTE
from ui.report.source_editor import ReportSourceEditor
from ui.styles.icons import get_theme_color

PreviewTarget = tuple[str, str]


class ReportPreviewController:
    """Own preview rendering, semantic landmarks, focus, and scroll coupling."""

    def __init__(
        self,
        *,
        editor: ReportSourceEditor,
        preview: ReportPreviewEdit,
        document: ReportDocument,
        light_mode_provider: Callable[[], bool],
        split_mode_provider: Callable[[], bool],
    ):
        self.editor = editor
        self.preview = preview
        self.document = document
        self._light_mode_provider = light_mode_provider
        self._split_mode_provider = split_mode_provider
        self.landmarks: dict[PreviewTarget, int] = {}
        self.active_target: Optional[PreviewTarget] = None
        self.syncing_scroll = False

    def configure_typography(self, report_font: str) -> None:
        primary_font = report_font.split(",", 1)[0].strip().strip("'\"")
        preview_font = QFont(primary_font, 10)
        preview_font.setStyleHint(QFont.StyleHint.SansSerif)
        self.document.setDefaultFont(preview_font)
        palette = self._preview_palette()
        css = """
            body { font-family: __REPORT_FONT_STACK__; font-size: 13px; color: __TEXT__; line-height: 1.6; }
            h1, h2, h3, h4, h5, h6 { color: __HEADING__; font-family: __REPORT_FONT_STACK__; font-weight: 600; margin-top: 14px; margin-bottom: 6px; }
            h1 { font-size: 18px; border-bottom: 1px solid __BORDER__; padding-bottom: 4px; }
            h2 { font-size: 15px; border-bottom: 1px solid __BORDER__; padding-bottom: 3px; color: __HEADING_2__; }
            h3 { font-size: 14px; color: __HEADING_3__; }
            code { font-family: 'Cascadia Code', 'Consolas', 'Fira Code', monospace; background-color: __CODE_BG__; color: __CODE__; padding: 2px 4px; border-radius: 4px; font-size: 12px; }
            pre { background-color: __CODE_BG__; border: 1px solid __BORDER__; border-radius: 6px; padding: 8px; }
            blockquote { border-left: 3px solid __LINK__; margin: 8px 0; padding-left: 10px; color: __QUOTE__; }
            hr { border: 0; border-top: 1px solid __BORDER__; margin: 14px 0; }
            a { color: __LINK__; text-decoration: none; }
            img { max-width: 100%; border-radius: 6px; border: 1px solid __BORDER__; margin: 8px 0; }
            ul, ol { padding-left: 20px; margin: 6px 0; }
            li { margin: 3px 0; }
            p { margin: 6px 0; }
        """
        replacements = {
            "__REPORT_FONT_STACK__": report_font,
            "__TEXT__": palette["text"],
            "__HEADING__": palette["heading"],
            "__HEADING_2__": palette["heading_2"],
            "__HEADING_3__": palette["heading_3"],
            "__BORDER__": palette["border"],
            "__CODE_BG__": palette["code_bg"],
            "__CODE__": palette["code"],
            "__QUOTE__": palette["quote"],
            "__LINK__": palette["link"],
        }
        for marker, value in replacements.items():
            css = css.replace(marker, value)
        self.document.setDefaultStyleSheet(css)

    def render(self, markdown: str, project_dir: Optional[Path] = None) -> None:
        if project_dir is not None:
            self.document.set_project_dir(project_dir)
        prepared = prepare_preview_markdown(markdown)
        self.preview.setMarkdown(prepared.markdown)
        self._decorate_layout_markers()
        self._index_landmarks(prepared.landmarks)
        if self.active_target is not None:
            self.focus(*self.active_target, remember=False)
        self.sync_editor_to_preview()

    def focus(self, kind: str, identity: str, *, remember: bool = True) -> None:
        target = (kind, identity)
        if remember:
            self.active_target = target
        position = self.landmarks.get(target)
        if position is None:
            self.preview.setExtraSelections([])
            return

        cursor = QTextCursor(self.document)
        cursor.setPosition(position)
        self.preview.setTextCursor(cursor)
        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(cursor)
        selection.cursor.clearSelection()
        highlight = QColor(
            REPORT_LIGHT_PALETTE["focus_highlight"]
            if self._light_mode_provider()
            else get_theme_color("ACCENT_BRAND")
        )
        highlight.setAlpha(34 if self._light_mode_provider() else 28)
        selection.format.setBackground(highlight)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self.preview.setExtraSelections([selection])
        self.preview.ensureCursorVisible()

    def clear_focus(self) -> None:
        self.active_target = None
        self.preview.setExtraSelections([])

    def on_editor_scroll(self, value: int) -> None:
        if self.syncing_scroll or not self._split_mode_provider():
            return
        self._sync_scrollbars(
            value,
            self.editor.verticalScrollBar().maximum(),
            self.preview.verticalScrollBar(),
        )

    def on_preview_scroll(self, value: int) -> None:
        if self.syncing_scroll or not self._split_mode_provider():
            return
        self._sync_scrollbars(
            value,
            self.preview.verticalScrollBar().maximum(),
            self.editor.verticalScrollBar(),
        )

    def sync_editor_to_preview(self) -> None:
        if not self._split_mode_provider():
            return
        editor_bar = self.editor.verticalScrollBar()
        self._sync_scrollbars(
            editor_bar.value(),
            editor_bar.maximum(),
            self.preview.verticalScrollBar(),
        )

    def _sync_scrollbars(
        self, value: int, source_max: int, target_bar: QScrollBar
    ) -> None:
        target_max = target_bar.maximum()
        if source_max <= 0 or target_max <= 0:
            return
        self.syncing_scroll = True
        try:
            target_bar.setValue(int((value / source_max) * target_max))
        finally:
            self.syncing_scroll = False

    def _index_landmarks(
        self, landmarks: tuple[tuple[str, str, str], ...]
    ) -> None:
        self.landmarks.clear()
        for token, kind, identity in landmarks:
            cursor = self.document.find(token)
            if cursor.isNull():
                continue
            target_block = cursor.block()
            selection_start = cursor.selectionStart()
            selection_end = cursor.selectionEnd()
            removal_start = selection_start
            if selection_start > target_block.position():
                separator = QTextCursor(self.document)
                separator.setPosition(selection_start - 1)
                separator.setPosition(
                    selection_start, QTextCursor.MoveMode.KeepAnchor
                )
                if separator.selectedText() == " ":
                    removal_start -= 1
            cursor.setPosition(removal_start)
            cursor.setPosition(selection_end, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
            if target_block.isValid():
                self.landmarks[(kind, identity)] = target_block.position()

    def _decorate_layout_markers(self) -> None:
        cursor = self.document.find(PREVIEW_PAGEBREAK_TOKEN)
        while not cursor.isNull():
            char_format = QTextCharFormat()
            char_format.setForeground(
                QColor(
                    REPORT_LIGHT_PALETTE["pagebreak_marker"]
                    if self._light_mode_provider()
                    else get_theme_color("TEXT_MUTED")
                )
            )
            char_format.setFontWeight(QFont.Weight.DemiBold)
            cursor.insertText(PREVIEW_PAGEBREAK_LABEL, char_format)
            block_format = cursor.blockFormat()
            block_format.setAlignment(Qt.AlignmentFlag.AlignCenter)
            block_format.setTopMargin(3)
            block_format.setBottomMargin(3)
            cursor.setBlockFormat(block_format)
            cursor = self.document.find(PREVIEW_PAGEBREAK_TOKEN, cursor)
        for size, token in PREVIEW_SPACER_TOKENS.items():
            cursor = self.document.find(token)
            while not cursor.isNull():
                char_format = QTextCharFormat()
                char_format.setForeground(
                    QColor(
                        REPORT_LIGHT_PALETTE["spacer_marker"]
                        if self._light_mode_provider()
                        else get_theme_color("TEXT_DIMMED")
                    )
                )
                cursor.insertText(PREVIEW_SPACER_LABELS[size], char_format)
                block_format = cursor.blockFormat()
                block_format.setAlignment(Qt.AlignmentFlag.AlignCenter)
                margin = {"small": 3, "medium": 7, "large": 14}[size]
                block_format.setTopMargin(margin)
                block_format.setBottomMargin(margin)
                cursor.setBlockFormat(block_format)
                cursor = self.document.find(token, cursor)

    def _preview_palette(self) -> dict[str, str]:
        if self._light_mode_provider():
            return {
                "text": REPORT_LIGHT_PALETTE["text"],
                "heading": REPORT_LIGHT_PALETTE["heading"],
                "heading_2": REPORT_LIGHT_PALETTE["heading_2"],
                "heading_3": REPORT_LIGHT_PALETTE["heading_3"],
                "border": REPORT_LIGHT_PALETTE["border"],
                "code_bg": REPORT_LIGHT_PALETTE["code_bg"],
                "code": REPORT_LIGHT_PALETTE["code"],
                "quote": REPORT_LIGHT_PALETTE["quote"],
                "link": REPORT_LIGHT_PALETTE["link"],
            }
        return {
            "text": get_theme_color("TEXT_PRIMARY"),
            "heading": get_theme_color("ACCENT_PRIMARY"),
            "heading_2": get_theme_color("ACCENT_BRAND"),
            "heading_3": get_theme_color("CYBER_BLUE_LIGHT"),
            "border": get_theme_color("BORDER_DEFAULT"),
            "code_bg": get_theme_color("BG_CODE"),
            "code": get_theme_color("TEXT_CODE"),
            "quote": get_theme_color("TEXT_MUTED"),
            "link": get_theme_color("ACCENT_BRAND"),
        }
