from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from ui.message_boxes import show_warning_dialog
from core.reporting import ReportTemplate
from core.reporting import TemplateRepository
from core.theme_palette import (
    ACCENT_NAV_ACTIVE,
    BG_SURFACE,
    BORDER_DEFAULT,
    CYBER_CYAN,
    TEXT_PRIMARY,
)
from ui.report.icon_assets import (
    REPORT_ICON_CATEGORIES,
    REPORT_ICON_COLORS,
    REPORT_ICONS,
    ReportIconDefinition,
)
from ui.styles.icons import icon
from ui.template_manager_dialog import TemplateManagerDialog
from ui.base_dialog import BaseHudDialog


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


class ReportIconPickerDialog(QDialog):
    """Small searchable picker for the curated report icon set."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.selected_icon: Optional[ReportIconDefinition] = None
        self._filtered_icons: list[ReportIconDefinition] = []

        self.setWindowTitle(t("report.icon_picker.title", "Insert Icon"))
        self.resize(620, 430)
        self.setMinimumSize(480, 320)

        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            t("report.icon_picker.search", "Search report icons...")
        )
        self.search_edit.setClearButtonEnabled(True)
        self.category_combo = QComboBox()
        self.category_combo.addItem(t("report.icon_picker.category.all", "All Categories"), "")
        for category in REPORT_ICON_CATEGORIES:
            self.category_combo.addItem(
                t(f"report.icon_picker.category.{category}", category.title()), category
            )
        filters.addWidget(self.search_edit, stretch=1)
        filters.addWidget(self.category_combo)
        layout.addLayout(filters)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Static)
        self.list_widget.setIconSize(QSize(32, 32))
        self.list_widget.setGridSize(QSize(135, 76))
        self.list_widget.setSpacing(4)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        self.btn_insert = QPushButton(t("report.icon_picker.insert", "Insert Icon"))
        self.btn_insert.setProperty("class", "PrimaryBtn")
        self.btn_insert.setEnabled(False)
        self.btn_insert.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.btn_insert)
        layout.addLayout(buttons)

        self.search_edit.textChanged.connect(self._populate)
        self.category_combo.currentIndexChanged.connect(self._populate)
        self._populate()

    def _populate(self, *_args) -> None:
        query = self.search_edit.text().strip().casefold()
        category = str(self.category_combo.currentData() or "")
        self.list_widget.clear()
        self._filtered_icons = []
        for definition in REPORT_ICONS:
            label = t(definition.label_key, definition.key.replace("_", " ").title())
            if category and definition.category != category:
                continue
            if query and query not in label.casefold() and query not in definition.key.casefold():
                continue
            item = QListWidgetItem(
                icon(
                    definition.icon_name,
                    color=REPORT_ICON_COLORS["default"],
                    color_active=None,
                ),
                label,
            )
            item.setData(Qt.ItemDataRole.UserRole, definition)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setToolTip(label)
            self.list_widget.addItem(item)
            self._filtered_icons.append(definition)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self.selected_icon = None
            self.btn_insert.setEnabled(False)

    def _on_selection_changed(self, current: QListWidgetItem, _previous) -> None:
        self.selected_icon = (
            current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        )
        self.btn_insert.setEnabled(self.selected_icon is not None)

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        self.selected_icon = item.data(Qt.ItemDataRole.UserRole)
        if self.selected_icon is not None:
            self.accept()


class ReportGenerationDialog(BaseHudDialog):
    """Choose a report template immediately before generating from loot."""

    def __init__(
        self,
        template_repo: TemplateRepository,
        selected_template: Optional[ReportTemplate] = None,
        has_existing_report: bool = False,
        parent: Optional[QWidget] = None,
    ):
        title = t("report.generate_title", "Generate Report from Loot")
        super().__init__(title, parent)
        self.template_repo = template_repo
        self.selected_template: Optional[ReportTemplate] = selected_template
        self.set_dialog_title(title)
        self.setMinimumWidth(460)
        self._build_ui(has_existing_report)
        self._populate_templates()

    def _build_ui(self, has_existing_report: bool) -> None:
        self.setObjectName("ReportGenerationDialog")
        layout = self.body_layout
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
        btn_label = (
            t("report.regenerate_overwrite_button", "Regenerate & Overwrite")
            if has_existing_report
            else t("report.generate", "Generate Report")
        )
        generate = QPushButton(btn_label)
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
            show_warning_dialog(
                self,
                t("report.no_template_title", "No Template"),
                t("report.no_template_message", "Please select a report template."),
            )
            return
        self.selected_template = template
        self.accept()


class ReportRegenerationConfirmDialog(BaseHudDialog):
    """Frameless confirmation for the destructive full-report regeneration path."""

    def __init__(self, parent: Optional[QWidget] = None):
        title = t("report.regenerate_confirm_title", "Overwrite Existing Report?")
        super().__init__(title, parent)
        self.setObjectName("ReportRegenerationConfirmDialog")
        self.set_dialog_title(title)
        self.setMinimumWidth(520)

        warning_row = QHBoxLayout()
        warning_icon = QLabel()
        warning_icon.setPixmap(
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            .pixmap(QSize(32, 32))
        )
        warning_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        warning_row.addWidget(warning_icon)

        message = QLabel(
            t(
                "report.regenerate_confirm_message",
                "Warning: Regenerating from scratch will completely overwrite the current "
                "report structure and all manual notes!\n\n"
                "A backup of the current state will be saved as report.md.bak, but manual "
                "edits in this report will be replaced.\n\n"
                "Tip: To keep your manual notes and only append new loot, use 'Add Missing "
                "Loot' instead.\n\nDo you really want to regenerate and overwrite?",
            )
        )
        message.setWordWrap(True)
        message.setTextFormat(Qt.TextFormat.PlainText)
        warning_row.addWidget(message, stretch=1)
        self.body_layout.addLayout(warning_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.setProperty("class", "SecondaryBtn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        overwrite = QPushButton(
            t("report.regenerate_overwrite_button", "Regenerate & Overwrite")
        )
        overwrite.setProperty("class", "DangerBtn")
        overwrite.clicked.connect(self.accept)
        buttons.addWidget(overwrite)
        self.body_layout.addLayout(buttons)


class LootImagePickerDialog(QDialog):
    """Dialog to select and preview screenshots captured in Loot for insertion into the report."""

    def __init__(
        self,
        screenshots: list[dict],
        project_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.screenshots = screenshots
        self.project_dir = project_dir
        self.selected_entry: Optional[dict] = None
        self._filtered_entries: list[dict] = []

        self.setWindowTitle(t("report.loot_images_title", "Select Screenshot from Loot"))
        self.resize(680, 430)
        self.setMinimumSize(520, 320)

        main_layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        search_label = QLabel(t("report.loot_search_label", "Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            t("report.loot_search_placeholder", "Filter by title, target IP, timestamp...")
        )
        self.search_edit.textChanged.connect(self._filter_list)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        main_layout.addLayout(search_layout)

        content_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)
        content_layout.addWidget(self.list_widget, stretch=3)

        preview_panel = QVBoxLayout()
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 11px; color: #888;")
        preview_panel.addWidget(self.info_label)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "border: 1px dashed #444; border-radius: 4px; background: #1a1a1a;"
        )
        self.preview_label.setMinimumSize(220, 160)
        preview_panel.addWidget(self.preview_label, stretch=1)

        content_layout.addLayout(preview_panel, stretch=2)
        main_layout.addLayout(content_layout, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_insert = QPushButton(t("report.loot_insert_button", "Insert"))
        self.btn_insert.setProperty("class", "PrimaryBtn")
        self.btn_insert.setEnabled(False)
        self.btn_insert.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_insert)
        main_layout.addLayout(btn_layout)

        self._populate_list(self.screenshots)

    def _populate_list(self, entries: list[dict]) -> None:
        self.list_widget.clear()
        self._filtered_entries = list(entries)
        for entry in entries:
            title = entry.get("title", "Screenshot")
            ts = entry.get("timestamp", "")
            ip = entry.get("target_ip", "")
            sub = f"[{ip}] " if ip else ""
            item_text = f"{title}  —  {sub}{ts}" if ts else title
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)

        if entries:
            self.list_widget.setCurrentRow(0)

    def _filter_list(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            self._populate_list(self.screenshots)
            return

        filtered = []
        for e in self.screenshots:
            title = str(e.get("title", "")).lower()
            ip = str(e.get("target_ip", "")).lower()
            ts = str(e.get("timestamp", "")).lower()
            content = str(e.get("content", "")).lower()
            if query in title or query in ip or query in ts or query in content:
                filtered.append(e)
        self._populate_list(filtered)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._filtered_entries):
            self.selected_entry = None
            self.btn_insert.setEnabled(False)
            self.info_label.setText("")
            self.preview_label.clear()
            return

        entry = self._filtered_entries[row]
        self.selected_entry = entry
        self.btn_insert.setEnabled(True)

        title = entry.get("title", "Screenshot")
        ts = entry.get("timestamp", "")
        ip = entry.get("target_ip", "")
        info_lines = [f"<b>{title}</b>"]
        if ip:
            info_lines.append(f"Target: {ip}")
        if ts:
            info_lines.append(f"Zeit: {ts}")
        self.info_label.setText("<br>".join(info_lines))

        img_path = self._resolve_entry_path(entry)
        if img_path and img_path.is_file():
            from PyQt6.QtGui import QPixmap

            pixmap = QPixmap(str(img_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    220,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
            else:
                self.preview_label.setText(
                    t("report.preview_unavailable", "No preview available")
                )
        else:
            self.preview_label.setText(
                t("report.preview_unavailable", "No preview available")
            )

    def _resolve_entry_path(self, entry: dict) -> Optional[Path]:
        raw = entry.get("file_path") or ""
        if raw and Path(raw).is_file():
            return Path(raw)

        content = (entry.get("content") or "").strip()
        import re

        m = re.search(r"\((.*?)\)", content)
        path_str = m.group(1) if m else content

        p = Path(path_str)
        if p.is_file():
            return p

        if self.project_dir:
            cand = self.project_dir / path_str
            if cand.is_file():
                return cand

        return None

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        if self.selected_entry:
            self.accept()


class ReportExportTypeDialog(QDialog):
    """Dialog for choosing report export format (HTML/PDF, Obsidian, CherryTree, Markdown)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(t("report.export_dialog_title", "Export Report"))
        self.setMinimumWidth(320)
        self.selected_type: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(
            t("report.export_dialog_message", "Choose an export format for the current report.")
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addSpacing(4)

        choices = (
            (
                "html",
                t("report.export_html", "Export HTML/PDF"),
                t(
                    "report.export_html_desc",
                    "Create an editable web report or a print-ready HTML file for PDF output.",
                ),
            ),
            (
                "obsidian",
                t("report.export_obsidian", "Export to Obsidian..."),
                t(
                    "report.export_obsidian_desc",
                    "Write the report and linked screenshots into the configured Obsidian vault.",
                ),
            ),
            (
                "cherrytree",
                t("report.export_cherrytree", "Export CherryTree Package..."),
                t(
                    "report.export_cherrytree_desc",
                    "Create a portable HTML package with attachments for import into CherryTree.",
                ),
            ),
            (
                "markdown",
                t("report.export_copy", "Export MD..."),
                t(
                    "report.export_markdown_desc",
                    "Save an exact Markdown copy of the current Report Editor document.",
                ),
            ),
        )

        for export_type, label, description in choices:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.setProperty("class", "SecondaryBtn")

            def _make_handler(et: str):
                def _handle(_checked: bool = False) -> None:
                    self.selected_type = et
                    self.accept()

                return _handle

            btn.clicked.connect(_make_handler(export_type))
            layout.addWidget(btn)

            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setProperty("class", "HintLabel")
            description_label.setProperty("exportType", export_type)
            layout.addWidget(description_label)

        layout.addSpacing(4)
        cancel_btn = QPushButton(t("dialog.cancel", "Cancel"))
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    @classmethod
    def select_export_type(cls, parent: Optional[QWidget] = None) -> Optional[str]:
        dlg = cls(parent)
        dlg.exec()
        return dlg.selected_type


def select_html_export_options(parent: Optional[QWidget] = None) -> Optional[tuple[str, str]]:
    """Choose the HTML presentation profile without changing report content."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(t("report.html_profile_title", "Choose HTML Export Profile"))
    msg.setText(t("report.html_profile_message", "How should the HTML report be presented?"))
    msg.setInformativeText(
        t(
            "report.html_profile_hint",
            "Both exports remain editable in the browser; Professional Print uses a controlled A4 layout. Generate the PDF from the exported HTML file.",
        )
    )
    msg.setIcon(QMessageBox.Icon.Question)
    professional_button = msg.addButton(
        t("report.html_profile_professional", "Professional Print"),
        QMessageBox.ButtonRole.AcceptRole,
    )
    classic_web_button = msg.addButton(
        t("report.html_profile_classic_web", "Classic Web (editable)"),
        QMessageBox.ButtonRole.ActionRole,
    )
    cancel_button = msg.addButton(QMessageBox.StandardButton.Cancel)
    msg.setDefaultButton(professional_button)
    msg.setMinimumWidth(640)
    professional_button.setMinimumWidth(170)
    classic_web_button.setMinimumWidth(210)
    professional_button.setToolTip(
        t("report.html_profile_professional_tip", "Print-ready A4 presentation for browser PDF generation")
    )
    classic_web_button.setToolTip(
        t("report.html_profile_classic_web_tip", "Editable responsive web report for browser use")
    )
    cancel_button.setMinimumWidth(100)
    msg.exec()

    if msg.clickedButton() is professional_button:
        return "light", "professional_print"
    if msg.clickedButton() is classic_web_button:
        return "light", "interactive"
    return None
