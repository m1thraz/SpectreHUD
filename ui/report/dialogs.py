"""Dialog widgets owned by the report editor workflow."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting.template_engine import ReportTemplate
from core.reporting.template_repository import TemplateRepository
from core.theme_palette import (
    ACCENT_NAV_ACTIVE,
    BG_SURFACE,
    BORDER_DEFAULT,
    CYBER_CYAN,
    TEXT_PRIMARY,
)
from ui.template_manager_dialog import TemplateManagerDialog


class MarkdownTableDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(t("report.table_title", "Insert Table"))
        layout = QVBoxLayout(self)
        self.rows = QSpinBox()
        self.rows.setRange(1, 10)
        self.rows.setValue(2)
        self.columns = QSpinBox()
        self.columns.setRange(1, 10)
        self.columns.setValue(3)
        layout.addWidget(QLabel(t("report.table_rows", "Rows:")))
        layout.addWidget(self.rows)
        layout.addWidget(QLabel(t("report.table_columns", "Columns:")))
        layout.addWidget(self.columns)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        insert = QPushButton(t("report.table_insert", "Insert Table"))
        insert.setProperty("class", "PrimaryBtn")
        insert.clicked.connect(self.accept)
        buttons.addWidget(insert)
        layout.addLayout(buttons)


class ReportGenerationDialog(QDialog):
    """Choose a report template immediately before generating from loot."""

    def __init__(
        self,
        template_repo: TemplateRepository,
        selected_template: Optional[ReportTemplate] = None,
        has_existing_report: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.template_repo = template_repo
        self.selected_template: Optional[ReportTemplate] = selected_template
        self.setWindowTitle(t("report.generate_title", "Generate Report from Loot"))
        self.setMinimumWidth(460)
        self._build_ui(has_existing_report)
        self._populate_templates()

    def _build_ui(self, has_existing_report: bool) -> None:
        self.setObjectName("ReportGenerationDialog")
        self.setStyleSheet(
            f"QDialog#ReportGenerationDialog {{ background-color: {BG_SURFACE}; color: {TEXT_PRIMARY}; }}"
        )
        layout = QVBoxLayout(self)
        description = QLabel(
            t(
                "report.generate_description",
                "Creates a structured report from current loot and clipboard history.",
            )
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(description)
        if has_existing_report:
            warning = QLabel(
                t(
                    "report.generate_warning",
                    "The existing report will be replaced. It is backed up as <b>report.md.bak</b> first.",
                )
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #f0b429; margin-top: 6px;")
            layout.addWidget(warning)
        form = QFormLayout()
        self.combo_templates = QComboBox()
        self.combo_templates.setView(QListView())
        self.combo_templates.setStyleSheet(
            f"QComboBox {{ background-color: {BG_SURFACE}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_DEFAULT}; border-radius: 6px; padding: 6px 10px; font-size: 13px; min-height: 26px; }}"
            f"QComboBox:focus {{ border: 1px solid {CYBER_CYAN}; }}"
            f"QComboBox QAbstractItemView, QComboBox QListView {{ background-color: {BG_SURFACE}; color: {TEXT_PRIMARY}; border: 1px solid {CYBER_CYAN}; border-radius: 6px; selection-background-color: {ACCENT_NAV_ACTIVE}; selection-color: {CYBER_CYAN}; padding: 4px; outline: none; }}"
            f"QComboBox QAbstractItemView::item, QComboBox QListView::item {{ background-color: {BG_SURFACE}; color: {TEXT_PRIMARY}; padding: 6px 10px; min-height: 24px; font-size: 13px; }}"
            f"QComboBox QAbstractItemView::item:hover, QComboBox QListView::item:hover, QComboBox QAbstractItemView::item:selected, QComboBox QListView::item:selected {{ background-color: {ACCENT_NAV_ACTIVE}; color: {CYBER_CYAN}; }}"
        )
        self.combo_templates.setToolTip(
            t("report.template_tip", "Select a template for the newly generated report")
        )
        form.addRow(t("report.template_label", "Report Template:"), self.combo_templates)
        layout.addLayout(form)
        self.btn_manage_templates = QPushButton(t("report.manage_templates", "🎨 Templates..."))
        self.btn_manage_templates.setProperty("class", "SecondaryBtn")
        self.btn_manage_templates.clicked.connect(self._open_template_manager)
        layout.addWidget(self.btn_manage_templates, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        generate = QPushButton(t("report.generate", "Generate Report"))
        generate.setProperty("class", "PrimaryBtn")
        generate.clicked.connect(self._accept_selection)
        buttons.addWidget(generate)
        layout.addLayout(buttons)

    def _populate_templates(self) -> None:
        selected_id = self.selected_template.id if self.selected_template else None
        templates = self.template_repo.get_all_templates()
        self.combo_templates.blockSignals(True)
        self.combo_templates.clear()
        for template in templates:
            self.combo_templates.addItem(
                f"{template.name} [{template.language.upper()}]", template.id
            )
        index = self.combo_templates.findData(selected_id) if selected_id else -1
        self.combo_templates.setCurrentIndex(index if index >= 0 else (0 if templates else -1))
        self.combo_templates.blockSignals(False)

    def _open_template_manager(self) -> None:
        dialog = TemplateManagerDialog(repository=self.template_repo, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_template:
            self.selected_template = dialog.selected_template
        self._populate_templates()

    def _accept_selection(self) -> None:
        template_id = self.combo_templates.currentData()
        template = self.template_repo.get_template(template_id) if template_id else None
        if template is None:
            QMessageBox.warning(
                self,
                t("report.no_template_title", "No Template"),
                t("report.no_template_message", "Please select a report template."),
            )
            return
        self.selected_template = template
        self.accept()
