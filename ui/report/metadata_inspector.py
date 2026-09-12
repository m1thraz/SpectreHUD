"""
SpectreHUD Report Metadata Inspector.

Provides a structured form editor for report header metadata (client, scope,
tester, classification, version) with real-time model synchronization.
"""

from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import ReportMetadata
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon

CLASSIFICATIONS = [
    "Vertraulich – Nur für internen Gebrauch",
    "Confidential – Internal Use Only",
    "TLP:CLEAR",
    "TLP:GREEN",
    "TLP:AMBER",
    "TLP:RED",
    "Öffentlich / Public",
]


class ReportMetadataInspector(QWidget):
    """Contextual form editor for report metadata."""

    metadata_changed = pyqtSignal(ReportMetadata)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportMetadataInspector")
        self._metadata = ReportMetadata()
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header card
        header_card = GlassPanel(self)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.clipboard-list", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        lbl_title = QLabel(t("report.inspector_metadata_title", "Report Metadata & Parameters"))
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()

        main_layout.addWidget(header_card)

        # Form Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            """
        )

        content_widget = QWidget()
        form_layout = QFormLayout(content_widget)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Inputs
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("e.g. Security Assessment Report: TargetCorp")
        self.txt_title.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_title", "Report Title:")), self.txt_title)

        self.txt_client = QLineEdit()
        self.txt_client.setPlaceholderText("e.g. TargetCorp AG")
        self.txt_client.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_client", "Client / Organization:")), self.txt_client)

        self.txt_tester = QLineEdit()
        self.txt_tester.setPlaceholderText("e.g. SecLab Lead Auditor")
        self.txt_tester.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_tester", "Lead Tester / Analyst:")), self.txt_tester)

        self.txt_scope = QLineEdit()
        self.txt_scope.setPlaceholderText("e.g. 10.10.10.0/24 or *.example.com")
        self.txt_scope.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_scope", "Target / Scope:")), self.txt_scope)

        self.txt_timeframe = QLineEdit()
        self.txt_timeframe.setPlaceholderText("e.g. 01.09.2026 – 05.09.2026")
        self.txt_timeframe.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_timeframe", "Assessment Period:")), self.txt_timeframe)

        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("YYYY-MM-DD")
        self.txt_date.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_date", "Report Date:")), self.txt_date)

        self.cmb_classification = QComboBox()
        self.cmb_classification.setEditable(True)
        self.cmb_classification.addItems(CLASSIFICATIONS)
        self.cmb_classification.currentTextChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_classification", "Classification:")), self.cmb_classification)

        self.txt_version = QLineEdit()
        self.txt_version.setPlaceholderText("v1.0")
        self.txt_version.textChanged.connect(self._on_field_changed)
        form_layout.addRow(self._make_label(t("report.meta_version", "Report Version:")), self.txt_version)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 500; color: #c9d1d9; font-size: 12px;")
        return lbl

    def load_metadata(self, metadata: ReportMetadata) -> None:
        self._loading = True
        try:
            self._metadata = metadata
            self.txt_title.setText(metadata.title)
            self.txt_client.setText(metadata.client)
            self.txt_tester.setText(metadata.tester)
            self.txt_scope.setText(metadata.target_scope)
            self.txt_timeframe.setText(metadata.timeframe)
            self.txt_date.setText(metadata.date)

            idx = self.cmb_classification.findText(metadata.classification)
            if idx >= 0:
                self.cmb_classification.setCurrentIndex(idx)
            else:
                self.cmb_classification.setCurrentText(metadata.classification)

            self.txt_version.setText(metadata.version or "v1.0")
        finally:
            self._loading = False

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        updated = ReportMetadata(
            title=self.txt_title.text().strip(),
            client=self.txt_client.text().strip(),
            tester=self.txt_tester.text().strip(),
            target_scope=self.txt_scope.text().strip(),
            timeframe=self.txt_timeframe.text().strip(),
            date=self.txt_date.text().strip(),
            classification=self.cmb_classification.currentText().strip(),
            version=self.txt_version.text().strip() or "v1.0",
            custom_fields=dict(self._metadata.custom_fields),
        )
        self._metadata = updated
        self.metadata_changed.emit(updated)
