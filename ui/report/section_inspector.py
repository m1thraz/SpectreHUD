"""
SpectreHUD Report Section Inspector.

Provides a focused markdown editor for isolated narrative report sections
(Executive Summary, Scope & Methodik, Attack Path narrative) without clutter.
"""

from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from ui.glass_panel import GlassPanel
from ui.markdown_highlighter import MarkdownHighlighter
from ui.report.source_editor import ReportSourceEditor
from ui.styles.icons import icon


class ReportSectionInspector(QWidget):
    """Contextual focused editor for an individual narrative section."""

    section_changed = pyqtSignal(str, str)  # identity, content

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportSectionInspector")
        self._identity: str = ""
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(250)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header card
        self.header_card = GlassPanel(self)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(8)

        self.lbl_icon = QLabel()
        h_layout.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_section_title", "Abschnitts-Editor"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        self.lbl_hint = QLabel(t("report.inspector_section_hint", "Fokussierte Bearbeitung"))
        self.lbl_hint.setStyleSheet("font-size: 11px; color: #8b949e;")
        h_layout.addWidget(self.lbl_hint)

        main_layout.addWidget(self.header_card)

        # Editor
        self.editor = ReportSourceEditor(self)
        self.editor.setProperty("class", "ReportSourceEditor")
        self._highlighter = MarkdownHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._on_text_changed)

        main_layout.addWidget(self.editor, stretch=1)

    def load_section(
        self,
        identity: str,
        title: str,
        content: str,
        icon_name: str = "fa5s.edit",
    ) -> None:
        self._loading = True
        try:
            self._identity = identity
            self.lbl_title.setText(title or identity)
            self.lbl_icon.setPixmap(icon(icon_name, color="#00e5ff").pixmap(20, 20))
            self.editor.setPlainText(content)
        finally:
            self._loading = False

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        if self._identity:
            self.section_changed.emit(self._identity, self.editor.toPlainText())
