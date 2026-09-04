"""
Template Manager Dialog for SpectreHUD.

Allows browsing, selecting, creating, duplicating, modifying, and resetting report templates.
"""

from typing import Optional, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QHeaderView,
    QWidget,
    QInputDialog,
)

from core.reporting.template_engine import ReportTemplate
from core.reporting.template_repository import TemplateRepository
from ui.template_editor_dialog import TemplateEditorDialog
from core.i18n import t


class TemplateManagerDialog(QDialog):
    """Management dialog for viewing, customizing, and selecting Report Templates."""

    def __init__(
        self, repository: Optional[TemplateRepository] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setObjectName("TemplateManagerDialog")
        self.setWindowTitle(t("template_manager.title", "Report-Templates verwalten"))
        self.resize(750, 420)

        self.repo = repository or TemplateRepository()
        self.selected_template: Optional[ReportTemplate] = None
        self._templates: List[ReportTemplate] = []

        self._build_ui()
        self._load_templates()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        lbl = QLabel(t("template_manager.available_templates", "Verfügbare Report-Templates:"))
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setObjectName("TemplateTable")
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                t("template_manager.th_name", "Name"),
                t("template_manager.th_id", "ID"),
                t("template_manager.th_language", "Sprache"),
                t("template_manager.th_category", "Kategorie"),
                t("template_manager.th_complexity", "Komplexität"),
                t("template_manager.th_type", "Typ"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.table.itemSelectionChanged.connect(self._update_button_states)
        layout.addWidget(self.table)

        # Action Buttons Row
        btn_row = QHBoxLayout()

        self.btn_new = QPushButton(t("template_manager.btn_new", "＋ Neu..."))
        self.btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(self.btn_new)

        self.btn_duplicate = QPushButton(t("template_manager.btn_duplicate", "⎘ Duplizieren"))
        self.btn_duplicate.clicked.connect(self._on_duplicate)
        btn_row.addWidget(self.btn_duplicate)

        self.btn_edit = QPushButton(t("template_manager.btn_edit", "✎ Bearbeiten"))
        self.btn_edit.clicked.connect(self._on_edit)
        btn_row.addWidget(self.btn_edit)

        self.btn_delete = QPushButton(t("template_manager.btn_delete", "✕ Löschen / Reset"))
        self.btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch()

        self.btn_select = QPushButton(t("template_manager.btn_apply", "Template anwenden"))
        self.btn_select.setProperty("class", "PrimaryBtn")
        self.btn_select.clicked.connect(self._on_select)
        btn_row.addWidget(self.btn_select)

        self.btn_close = QPushButton(t("dialog.close", "Schließen"))
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        layout.addLayout(btn_row)

    def _load_templates(self) -> None:
        self._templates = self.repo.get_all_templates()
        self.table.setRowCount(len(self._templates))

        for row, tmpl in enumerate(self._templates):
            item_name = QTableWidgetItem(tmpl.name)
            item_id = QTableWidgetItem(tmpl.id)
            item_lang = QTableWidgetItem(tmpl.language.upper())
            item_cat = QTableWidgetItem(tmpl.category.upper())
            item_comp = QTableWidgetItem(tmpl.complexity.capitalize())
            type_str = (
                t("template_manager.type_builtin", "Werkseinstellung")
                if tmpl.is_builtin
                else t("template_manager.type_custom", "Benutzerdefiniert")
            )
            item_type = QTableWidgetItem(type_str)

            for it in (item_name, item_id, item_lang, item_cat, item_comp, item_type):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_id)
            self.table.setItem(row, 2, item_lang)
            self.table.setItem(row, 3, item_cat)
            self.table.setItem(row, 4, item_comp)
            self.table.setItem(row, 5, item_type)

        if self._templates:
            self.table.selectRow(0)
        self._update_button_states()

    def _get_selected_template(self) -> Optional[ReportTemplate]:
        row = self.table.currentRow()
        if 0 <= row < len(self._templates):
            return self._templates[row]
        return None

    def _update_button_states(self) -> None:
        tmpl = self._get_selected_template()
        has_sel = tmpl is not None
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel and not tmpl.is_builtin)
        self.btn_select.setEnabled(has_sel)

    def _on_new(self) -> None:
        dlg = TemplateEditorDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_template:
            self.repo.save_user_template(dlg.result_template)
            self._load_templates()

    def _on_duplicate(self) -> None:
        tmpl = self._get_selected_template()
        if not tmpl:
            return

        new_id, ok = QInputDialog.getText(
            self,
            t("template_manager.duplicate_title", "Template duplizieren"),
            t("template_manager.duplicate_prompt", "Neue ID für Kopie von '{name}':", name=tmpl.name),
            text=f"{tmpl.id}_copy",
        )
        if not ok or not new_id.strip():
            return

        copy_suffix = t("template_manager.copy_suffix", " (Kopie)")
        dup = ReportTemplate(
            id=new_id.strip(),
            name=f"{tmpl.name}{copy_suffix}",
            language=tmpl.language,
            category=tmpl.category,
            complexity=tmpl.complexity,
            sections=list(tmpl.sections),
            is_builtin=False,
        )
        dlg = TemplateEditorDialog(template=dup, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_template:
            self.repo.save_user_template(dlg.result_template)
            self._load_templates()

    def _on_edit(self) -> None:
        tmpl = self._get_selected_template()
        if not tmpl:
            return
        dlg = TemplateEditorDialog(template=tmpl, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_template:
            self.repo.save_user_template(dlg.result_template)
            self._load_templates()

    def _on_delete(self) -> None:
        tmpl = self._get_selected_template()
        if not tmpl or tmpl.is_builtin:
            return

        reply = QMessageBox.question(
            self,
            t("template_manager.delete_title", "Template löschen"),
            t(
                "template_manager.delete_confirm",
                "Möchtest du das Template '{name}' wirklich löschen?",
                name=tmpl.name,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.repo.delete_user_template(tmpl.id)
            self._load_templates()

    def _on_select(self) -> None:
        self.selected_template = self._get_selected_template()
        if self.selected_template:
            self.accept()

    def _on_table_double_clicked(self) -> None:
        self._on_select()
