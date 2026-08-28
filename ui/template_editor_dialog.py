"""
Template Editor Dialog for SpectreHUD.

Allows users to create, modify, reorder, and configure custom report templates and sections.
"""

from typing import Optional, List
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QMessageBox, QWidget, QInputDialog
)

from core.reporting.template_engine import ReportTemplate, TemplateSection
from core.loot_manager import CATEGORIES
from ui.styles import CYBER_DARK_QSS


SECTION_TYPE_NAMES = {
    "header_metadata": "Header & Metadaten",
    "executive_summary": "Executive Summary & Findings-Matrix",
    "scope_limitations": "Scope & Limitations",
    "phase_section": "Phasen-Sektion (Loot-Kategorie)",
    "remediation_table": "Remediation & Maßnahmenplan",
    "appendix": "Anhang (Befehlsverlauf & Screenshots)"
}


# The app-wide theme does not style QListWidget instances.  Template sections
# were therefore rendered with the platform default palette (grey background
# and black text on Windows), which made the editor hard to read.
TEMPLATE_EDITOR_QSS = CYBER_DARK_QSS + """
QDialog#TemplateEditorDialog, QDialog#TemplateSectionEditDialog {
    background-color: #161b22;
    color: #f0f6fc;
}

QDialog#TemplateEditorDialog QLabel, QDialog#TemplateSectionEditDialog QLabel {
    color: #f0f6fc;
    background-color: transparent;
}

QDialog#TemplateEditorDialog QLineEdit, QDialog#TemplateSectionEditDialog QLineEdit,
QDialog#TemplateEditorDialog QComboBox, QDialog#TemplateSectionEditDialog QComboBox {
    background-color: #0d1117;
    color: #f0f6fc;
    border-color: #3d444d;
}

QDialog#TemplateEditorDialog QComboBox QAbstractItemView,
QDialog#TemplateSectionEditDialog QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #f0f6fc;
    border: 1px solid #3d444d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

QListWidget#TemplateSectionList {
    background-color: #0d1117;
    color: #f0f6fc;
    border: 1px solid #3d444d;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}

QListWidget#TemplateSectionList::item {
    color: #f0f6fc;
    background-color: transparent;
    border-radius: 4px;
    padding: 6px 8px;
}

QListWidget#TemplateSectionList::item:hover {
    background-color: #21262d;
}

QListWidget#TemplateSectionList::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}
"""


class SectionEditDialog(QDialog):
    """Dialog to configure or add a single template section."""

    def __init__(self, section: Optional[TemplateSection] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TemplateSectionEditDialog")
        self.setWindowTitle("Sektion konfigurieren")
        self.resize(420, 260)
        self.setStyleSheet(TEMPLATE_EDITOR_QSS)

        self._initial_section = section
        self._build_ui()
        if section:
            self._load_section(section)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.combo_type = QComboBox()
        for key, name in SECTION_TYPE_NAMES.items():
            self.combo_type.addItem(name, key)
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Typ:", self.combo_type)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("(Optionaler individueller Titel)")
        form.addRow("Titel:", self.txt_title)

        self.combo_category = QComboBox()
        for cat in CATEGORIES:
            self.combo_category.addItem(cat["name"], cat["id"])
        self.row_category = form.addRow("Loot-Kategorie:", self.combo_category)

        layout.addLayout(form)
        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setProperty("class", "PrimaryBtn")
        self.btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_ok)

        layout.addLayout(btn_box)
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        sec_type = self.combo_type.currentData()
        is_phase = (sec_type == "phase_section")
        self.combo_category.setVisible(is_phase)

    def _load_section(self, section: TemplateSection) -> None:
        idx = self.combo_type.findData(section.type)
        if idx >= 0:
            self.combo_type.setCurrentIndex(idx)
        if section.title:
            self.txt_title.setText(section.title)
        if section.category_id:
            cat_idx = self.combo_category.findData(section.category_id)
            if cat_idx >= 0:
                self.combo_category.setCurrentIndex(cat_idx)
        self._on_type_changed()

    def get_section(self) -> TemplateSection:
        sec_type = self.combo_type.currentData()
        title = self.txt_title.text().strip() or None
        cat_id = self.combo_category.currentData() if sec_type == "phase_section" else None
        return TemplateSection(
            type=sec_type,
            title=title,
            category_id=cat_id
        )


class TemplateEditorDialog(QDialog):
    """Dialog to create or edit a ReportTemplate."""

    result_template: Optional[ReportTemplate] = None

    def __init__(self, template: Optional[ReportTemplate] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TemplateEditorDialog")
        self.setWindowTitle("Template-Editor" if template else "Neues Report-Template erstellen")
        self.resize(600, 520)
        self.setStyleSheet(TEMPLATE_EDITOR_QSS)

        self._template = template
        self.result_template: Optional[ReportTemplate] = None
        self._build_ui()
        if template:
            self._load_template(template)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText("z.B. custom_pentest_de")
        form.addRow("Template-ID:", self.txt_id)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("z.B. Mein Pentest Standard (DE)")
        form.addRow("Name:", self.txt_name)

        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Deutsch (de)", "de")
        self.combo_lang.addItem("English (en)", "en")
        form.addRow("Sprache:", self.combo_lang)

        self.combo_cat = QComboBox()
        self.combo_cat.addItem("Pentest (pentest)", "pentest")
        self.combo_cat.addItem("CTF Challenge (ctf)", "ctf")
        form.addRow("Kategorie:", self.combo_cat)

        self.combo_comp = QComboBox()
        self.combo_comp.addItem("Umfassend (complex)", "complex")
        self.combo_comp.addItem("Kompakt / Quick (simple)", "simple")
        form.addRow("Komplexität:", self.combo_comp)

        layout.addLayout(form)

        lbl_sec = QLabel("Sektionen (Reihenfolge von oben nach unten):")
        lbl_sec.setStyleSheet("color: #f0f6fc; font-weight: bold; margin-top: 8px;")
        layout.addWidget(lbl_sec)

        # Section List + Buttons
        sec_layout = QHBoxLayout()
        self.list_sections = QListWidget()
        self.list_sections.setObjectName("TemplateSectionList")
        sec_layout.addWidget(self.list_sections, stretch=1)

        btn_col = QVBoxLayout()
        self.btn_add_sec = QPushButton("＋ Hinzufügen")
        self.btn_add_sec.clicked.connect(self._on_add_section)
        btn_col.addWidget(self.btn_add_sec)

        self.btn_edit_sec = QPushButton("✎ Bearbeiten")
        self.btn_edit_sec.clicked.connect(self._on_edit_section)
        btn_col.addWidget(self.btn_edit_sec)

        self.btn_move_up = QPushButton("▲ Nach oben")
        self.btn_move_up.clicked.connect(self._on_move_up)
        btn_col.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("▼ Nach unten")
        self.btn_move_down.clicked.connect(self._on_move_down)
        btn_col.addWidget(self.btn_move_down)

        self.btn_remove_sec = QPushButton("✕ Entfernen")
        self.btn_remove_sec.clicked.connect(self._on_remove_section)
        btn_col.addWidget(self.btn_remove_sec)
        btn_col.addStretch()

        sec_layout.addLayout(btn_col)
        layout.addLayout(sec_layout)

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Speichern")
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        layout.addLayout(btn_box)

    def _format_section_item(self, section: TemplateSection) -> str:
        type_str = SECTION_TYPE_NAMES.get(section.type, section.type)
        details = []
        if section.category_id:
            details.append(f"Kategorie: {section.category_id}")
        if section.title:
            details.append(f"Titel: '{section.title}'")
        detail_str = f" ({', '.join(details)})" if details else ""
        return f"{type_str}{detail_str}"

    def _add_section_to_list(self, section: TemplateSection) -> None:
        item = QListWidgetItem(self._format_section_item(section))
        item.setData(Qt.ItemDataRole.UserRole, section)
        self.list_sections.addItem(item)

    def _load_template(self, template: ReportTemplate) -> None:
        self.txt_id.setText(template.id)
        self.txt_id.setReadOnly(template.is_builtin)
        self.txt_name.setText(template.name)

        idx_lang = self.combo_lang.findData(template.language)
        if idx_lang >= 0:
            self.combo_lang.setCurrentIndex(idx_lang)

        idx_cat = self.combo_cat.findData(template.category)
        if idx_cat >= 0:
            self.combo_cat.setCurrentIndex(idx_cat)

        idx_comp = self.combo_comp.findData(template.complexity)
        if idx_comp >= 0:
            self.combo_comp.setCurrentIndex(idx_comp)

        self.list_sections.clear()
        for sec in template.sections:
            self._add_section_to_list(sec)

    def _on_add_section(self) -> None:
        dlg = SectionEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sec = dlg.get_section()
            self._add_section_to_list(sec)

    def _on_edit_section(self) -> None:
        row = self.list_sections.currentRow()
        if row < 0:
            return
        item = self.list_sections.item(row)
        current_sec = item.data(Qt.ItemDataRole.UserRole)
        dlg = SectionEditDialog(section=current_sec, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated_sec = dlg.get_section()
            item.setText(self._format_section_item(updated_sec))
            item.setData(Qt.ItemDataRole.UserRole, updated_sec)

    def _on_move_up(self) -> None:
        row = self.list_sections.currentRow()
        if row > 0:
            item = self.list_sections.takeItem(row)
            self.list_sections.insertItem(row - 1, item)
            self.list_sections.setCurrentRow(row - 1)

    def _on_move_down(self) -> None:
        row = self.list_sections.currentRow()
        if 0 <= row < self.list_sections.count() - 1:
            item = self.list_sections.takeItem(row)
            self.list_sections.insertItem(row + 1, item)
            self.list_sections.setCurrentRow(row + 1)

    def _on_remove_section(self) -> None:
        row = self.list_sections.currentRow()
        if row >= 0:
            self.list_sections.takeItem(row)

    def _on_save(self) -> None:
        tid = self.txt_id.text().strip()
        name = self.txt_name.text().strip()

        if not tid:
            QMessageBox.warning(self, "Ungültige Eingabe", "Bitte eine Template-ID eingeben.")
            return

        if not re.match(r'^[a-zA-Z0-9_-]+$', tid):
            QMessageBox.warning(self, "Ungültige ID", "Die ID darf nur Buchstaben, Ziffern, '_' und '-' enthalten.")
            return

        if not name:
            QMessageBox.warning(self, "Ungültige Eingabe", "Bitte einen Template-Namen eingeben.")
            return

        if self.list_sections.count() == 0:
            QMessageBox.warning(self, "Keine Sektionen", "Das Template muss mindestens eine Sektion enthalten.")
            return

        sections: List[TemplateSection] = []
        for i in range(self.list_sections.count()):
            sec = self.list_sections.item(i).data(Qt.ItemDataRole.UserRole)
            if sec:
                sections.append(sec)

        self.result_template = ReportTemplate(
            id=tid,
            name=name,
            language=self.combo_lang.currentData(),
            category=self.combo_cat.currentData(),
            complexity=self.combo_comp.currentData(),
            sections=sections,
            is_builtin=False
        )
        self.accept()
