"""
Template Editor Dialog for SpectreHUD.

Allows users to create, modify, reorder, and configure custom report templates and sections.
"""

from typing import Optional, List
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
    QLabel,
    QMessageBox,
    QWidget,
)

from core.reporting.template_engine import ReportTemplate, TemplateSection
from core.loot_manager import CATEGORIES
from core.i18n import t


SECTION_TYPE_KEYS = {
    "header_metadata": ("template_editor.sec_header", "Header & Metadaten"),
    "executive_summary": ("template_editor.sec_summary", "Executive Summary & Findings-Matrix"),
    "scope_limitations": ("template_editor.sec_scope", "Scope & Limitations"),
    "phase_section": ("template_editor.sec_phase", "Phasen-Sektion (Loot-Kategorie)"),
    "remediation_table": ("template_editor.sec_remediation", "Remediation & Maßnahmenplan"),
    "appendix": ("template_editor.sec_appendix", "Anhang (Befehlsverlauf & Screenshots)"),
}


def get_section_type_name(sec_type: str) -> str:
    key_info = SECTION_TYPE_KEYS.get(sec_type)
    if key_info:
        return t(key_info[0], key_info[1])
    return sec_type


SECTION_TYPE_NAMES = {k: v[1] for k, v in SECTION_TYPE_KEYS.items()}


class SectionEditDialog(QDialog):
    """Dialog to configure or add a single template section."""

    def __init__(self, section: Optional[TemplateSection] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TemplateSectionEditDialog")
        self.setWindowTitle(t("template_editor.edit_section_title", "Sektion konfigurieren"))
        self.resize(420, 260)

        self._initial_section = section
        self._build_ui()
        if section:
            self._load_section(section)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.combo_type = QComboBox()
        for key in SECTION_TYPE_KEYS:
            self.combo_type.addItem(get_section_type_name(key), key)
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow(t("template_editor.lbl_type", "Typ:"), self.combo_type)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText(
            t("template_editor.ph_title", "(Optionaler individueller Titel)")
        )
        form.addRow(t("template_editor.lbl_title", "Titel:"), self.txt_title)

        self.combo_category = QComboBox()
        for cat in CATEGORIES:
            self.combo_category.addItem(cat["name"], cat["id"])
        self.row_category = form.addRow(
            t("template_editor.lbl_category", "Loot-Kategorie:"), self.combo_category
        )

        self.chk_page_break = QCheckBox(
            t("template_editor.chk_page_break", "Seitenumbruch vor dieser Sektion einfügen")
        )
        form.addRow("", self.chk_page_break)

        layout.addLayout(form)
        layout.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton(t("dialog.cancel", "Abbrechen"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton(t("dialog.ok", "OK"))
        self.btn_ok.setProperty("class", "PrimaryBtn")
        self.btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_ok)

        layout.addLayout(btn_box)
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        sec_type = self.combo_type.currentData()
        is_phase = sec_type == "phase_section"
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
        self.chk_page_break.setChecked(bool(section.page_break_before))
        self._on_type_changed()

    def get_section(self) -> TemplateSection:
        sec_type = self.combo_type.currentData()
        title = self.txt_title.text().strip() or None
        cat_id = self.combo_category.currentData() if sec_type == "phase_section" else None
        page_break = self.chk_page_break.isChecked()
        return TemplateSection(
            type=sec_type,
            title=title,
            category_id=cat_id,
            page_break_before=page_break,
        )


class TemplateEditorDialog(QDialog):
    """Dialog to create or edit a ReportTemplate."""

    result_template: Optional[ReportTemplate] = None

    def __init__(self, template: Optional[ReportTemplate] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("TemplateEditorDialog")
        title = (
            t("template_editor.title_edit", "Template-Editor")
            if template
            else t("template_editor.title_new", "Neues Report-Template erstellen")
        )
        self.setWindowTitle(title)
        self.resize(600, 520)

        self._template = template
        self.result_template: Optional[ReportTemplate] = None
        self._build_ui()
        if template:
            self._load_template(template)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.txt_id = QLineEdit()
        self.txt_id.setPlaceholderText(t("template_editor.ph_id", "z.B. custom_pentest_de"))
        form.addRow(t("template_editor.lbl_id", "Template-ID:"), self.txt_id)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText(
            t("template_editor.ph_name", "z.B. Mein Pentest Standard (DE)")
        )
        form.addRow(t("template_editor.lbl_name", "Name:"), self.txt_name)

        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Deutsch (de)", "de")
        self.combo_lang.addItem("English (en)", "en")
        form.addRow(t("template_editor.lbl_language", "Sprache:"), self.combo_lang)

        self.combo_cat = QComboBox()
        self.combo_cat.addItem(t("template_editor.cat_pentest", "Pentest (pentest)"), "pentest")
        self.combo_cat.addItem(t("template_editor.cat_ctf", "CTF Challenge (ctf)"), "ctf")
        form.addRow(t("template_editor.lbl_category", "Kategorie:"), self.combo_cat)

        self.combo_comp = QComboBox()
        self.combo_comp.addItem(t("template_editor.comp_complex", "Umfassend (complex)"), "complex")
        self.combo_comp.addItem(
            t("template_editor.comp_simple", "Kompakt / Quick (simple)"), "simple"
        )
        form.addRow(t("template_editor.lbl_complexity", "Komplexität:"), self.combo_comp)

        layout.addLayout(form)

        lbl_sec = QLabel(
            t(
                "template_editor.lbl_sections",
                "Sektionen (Reihenfolge von oben nach unten):",
            )
        )
        lbl_sec.setStyleSheet("color: #f0f6fc; font-weight: bold; margin-top: 8px;")
        layout.addWidget(lbl_sec)

        # Section List + Buttons
        sec_layout = QHBoxLayout()
        self.list_sections = QListWidget()
        self.list_sections.setObjectName("TemplateSectionList")
        sec_layout.addWidget(self.list_sections, stretch=1)

        btn_col = QVBoxLayout()
        self.btn_add_sec = QPushButton(t("template_editor.btn_add_sec", "＋ Hinzufügen"))
        self.btn_add_sec.clicked.connect(self._on_add_section)
        btn_col.addWidget(self.btn_add_sec)

        self.btn_edit_sec = QPushButton(t("template_editor.btn_edit_sec", "✎ Bearbeiten"))
        self.btn_edit_sec.clicked.connect(self._on_edit_section)
        btn_col.addWidget(self.btn_edit_sec)

        self.btn_move_up = QPushButton(t("template_editor.btn_move_up", "▲ Nach oben"))
        self.btn_move_up.clicked.connect(self._on_move_up)
        btn_col.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton(t("template_editor.btn_move_down", "▼ Nach unten"))
        self.btn_move_down.clicked.connect(self._on_move_down)
        btn_col.addWidget(self.btn_move_down)

        self.btn_remove_sec = QPushButton(t("template_editor.btn_remove_sec", "✕ Entfernen"))
        self.btn_remove_sec.clicked.connect(self._on_remove_section)
        btn_col.addWidget(self.btn_remove_sec)
        btn_col.addStretch()

        sec_layout.addLayout(btn_col)
        layout.addLayout(sec_layout)

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Abbrechen"))
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(t("dialog.save", "Speichern"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_box.addWidget(self.btn_save)

        layout.addLayout(btn_box)

    def _format_section_item(self, section: TemplateSection) -> str:
        type_str = get_section_type_name(section.type)
        details = []
        if section.category_id:
            details.append(
                t("template_editor.item_category", "Kategorie: {category}", category=section.category_id)
            )
        if section.title:
            details.append(
                t("template_editor.item_title", "Titel: '{title}'", title=section.title)
            )
        detail_str = f" ({', '.join(details)})" if details else ""
        badge = (
            f" [{t('template_editor.page_break_badge', 'Seitenumbruch')}]"
            if section.page_break_before
            else ""
        )
        return f"{type_str}{detail_str}{badge}"

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
            QMessageBox.warning(
                self,
                t("dialog.invalid_input", "Ungültige Eingabe"),
                t("template_editor.err_no_id", "Bitte eine Template-ID eingeben."),
            )
            return

        if not re.match(r"^[a-zA-Z0-9_-]+$", tid):
            QMessageBox.warning(
                self,
                t("dialog.invalid_input", "Ungültige ID"),
                t(
                    "template_editor.err_invalid_id",
                    "Die ID darf nur Buchstaben, Ziffern, '_' und '-' enthalten.",
                ),
            )
            return

        if not name:
            QMessageBox.warning(
                self,
                t("dialog.invalid_input", "Ungültige Eingabe"),
                t("template_editor.err_no_name", "Bitte einen Template-Namen eingeben."),
            )
            return

        if self.list_sections.count() == 0:
            QMessageBox.warning(
                self,
                t("dialog.warning", "Keine Sektionen"),
                t(
                    "template_editor.err_no_sections",
                    "Das Template muss mindestens eine Sektion enthalten.",
                ),
            )
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
            is_builtin=False,
        )
        self.accept()
