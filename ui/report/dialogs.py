from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.export_plugins import ExportPluginMetadata
from ui.message_boxes import show_warning_dialog
from ui.plugin_text import plugin_text
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
from ui.styles.icons import get_theme_color, icon
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
        self.selected_icon = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
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
            warning.setStyleSheet(f"color: {get_theme_color('WARNING')}; margin-top: 6px;")
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
        overwrite = QPushButton(t("report.regenerate_overwrite_button", "Regenerate & Overwrite"))
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
        self.info_label.setStyleSheet(f"font-size: 11px; color: {get_theme_color('TEXT_MUTED')};")
        preview_panel.addWidget(self.info_label)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            f"border: 1px dashed {get_theme_color('BORDER_DEFAULT')}; border-radius: 4px; background: {get_theme_color('BG_DARK')};"
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
                self.preview_label.setText(t("report.preview_unavailable", "No preview available"))
        else:
            self.preview_label.setText(t("report.preview_unavailable", "No preview available"))

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


class LootEntryPickerDialog(QDialog):
    """Dialog to select loot entries (credentials, hashes, flags, commands, notes) as report evidence."""

    def __init__(
        self,
        entries: list[dict],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.entries = [e for e in entries if isinstance(e, dict)]
        self.selected_entry: Optional[dict] = None
        self._filtered_entries: list[dict] = []

        self.setWindowTitle(t("report.loot_picker_title", "Select Evidence from Loot"))
        self.resize(720, 460)
        self.setMinimumSize(540, 340)

        main_layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        search_lbl = QLabel(t("report.search_label", "Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            t(
                "report.loot_entry_search_placeholder",
                "Filter by title, content, target IP, type...",
            )
        )
        self.search_edit.textChanged.connect(self._filter_list)
        top_row.addWidget(search_lbl)
        top_row.addWidget(self.search_edit, stretch=1)

        self.cmb_category = QComboBox()
        self.cmb_category.addItem(t("report.category_all", "All Categories"), "all")
        self.cmb_category.addItem(t("report.category_creds", "Credentials / Hashes"), "creds")
        self.cmb_category.addItem(t("report.category_flag", "Flags"), "flag")
        self.cmb_category.addItem(t("report.category_command", "Commands / Terminal"), "command")
        self.cmb_category.addItem(t("report.category_note", "Notes"), "note")
        self.cmb_category.currentIndexChanged.connect(self._filter_list)
        top_row.addWidget(self.cmb_category)

        main_layout.addLayout(top_row)

        content_layout = QHBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)
        content_layout.addWidget(self.list_widget, stretch=3)

        preview_panel = QVBoxLayout()
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"font-size: 11px; color: {get_theme_color('TEXT_MUTED')};")
        preview_panel.addWidget(self.info_label)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; "
            f"background: {get_theme_color('BG_SURFACE')}; color: {get_theme_color('TEXT_PRIMARY')}; border: 1px solid {get_theme_color('BORDER_DEFAULT')}; border-radius: 4px;"
        )
        preview_panel.addWidget(self.txt_preview, stretch=1)

        content_layout.addLayout(preview_panel, stretch=4)
        main_layout.addLayout(content_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.setIcon(icon("fa5s.times", color=get_theme_color("ERROR")))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_insert = QPushButton(t("report.loot_attach_evidence", "Attach as Evidence"))
        self.btn_insert.setProperty("class", "PrimaryBtn")
        self.btn_insert.setIcon(icon("fa5s.check", color=get_theme_color("SUCCESS")))
        self.btn_insert.setEnabled(False)
        self.btn_insert.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_insert)

        main_layout.addLayout(btn_layout)

        self._filter_list()

    def _filter_list(self) -> None:
        query = self.search_edit.text().strip().lower()
        cat_filter = str(self.cmb_category.currentData() or "all")

        self.list_widget.clear()
        self._filtered_entries = []

        for entry in self.entries:
            e_type = str(entry.get("type") or "").lower()
            e_cat = str(entry.get("category") or "").lower()
            title = str(entry.get("title") or "")
            content = str(entry.get("content") or "")
            ip = str(entry.get("target_ip") or "")

            if cat_filter != "all":
                if cat_filter == "creds" and e_type not in (
                    "credential",
                    "credentials",
                    "hash",
                    "creds",
                ):
                    continue
                elif cat_filter == "flag" and e_type != "flag":
                    continue
                elif cat_filter == "command" and e_type not in ("command", "terminal", "output"):
                    continue
                elif cat_filter == "note" and e_type not in ("note", "notes"):
                    continue

            if query:
                combined = f"{title} {content} {ip} {e_type} {e_cat}".lower()
                if query not in combined:
                    continue

            self._filtered_entries.append(entry)

            item = QListWidgetItem()
            item.setText(title or t("report.unnamed_entry", "Untitled Entry"))

            if e_type in ("credential", "credentials", "creds"):
                item.setIcon(icon("fa5s.key", color=get_theme_color("WARNING")))
            elif e_type == "hash":
                item.setIcon(icon("fa5s.hashtag", color=get_theme_color("WARNING")))
            elif e_type == "flag":
                item.setIcon(icon("fa5s.flag", color=get_theme_color("ERROR")))
            elif e_type in ("command", "terminal", "output"):
                item.setIcon(icon("fa5s.terminal", color=get_theme_color("SUCCESS")))
            elif e_type in ("screenshot", "image"):
                item.setIcon(icon("fa5s.camera", color=get_theme_color("ACCENT_BRAND")))
            else:
                item.setIcon(icon("fa5s.sticky-note", color=get_theme_color("ACCENT_BRAND")))

            self.list_widget.addItem(item)

        if self._filtered_entries:
            self.list_widget.setCurrentRow(0)
        else:
            self._on_selection_changed(-1)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._filtered_entries):
            self.selected_entry = None
            self.btn_insert.setEnabled(False)
            self.info_label.setText("")
            self.txt_preview.clear()
            return

        entry = self._filtered_entries[row]
        self.selected_entry = entry
        self.btn_insert.setEnabled(True)

        title = entry.get("title", "")
        e_type = entry.get("type", "note")
        ts = entry.get("timestamp", "")
        ip = entry.get("target_ip", "")
        sev = entry.get("severity", "info")

        type_label = t("report.dialog_type", "Type:")
        sev_label = t("report.dialog_severity", "Severity:")
        info_lines = [
            f"<b>{title}</b>",
            f"{type_label} <code>{e_type}</code> | {sev_label} <code>{sev}</code>",
        ]
        if ip:
            info_lines.append(f"Target: {ip}")
        if ts:
            info_lines.append(t("report.dialog_time", "Time: {time}", time=ts))
        self.info_label.setText("<br>".join(info_lines))

        content = entry.get("content") or ""
        self.txt_preview.setPlainText(content)

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        if self.selected_entry:
            self.accept()


class LootFindingPromotionDialog(QDialog):
    """Select one primary Loot source and zero or more supporting evidence entries."""

    def __init__(
        self,
        primary_entries: list[dict],
        evidence_entries: Optional[list[dict]] = None,
        parent: Optional[QWidget] = None,
        *,
        suggestions_enabled: bool = True,
        correlation_window_seconds: int = 90,
    ):
        super().__init__(parent)
        from core.reporting import normalize_correlation_window_seconds

        self.suggestions_enabled = bool(suggestions_enabled)
        self.correlation_window_seconds = normalize_correlation_window_seconds(correlation_window_seconds)
        self.primary_entries = [entry for entry in primary_entries if isinstance(entry, dict)]
        self.evidence_entries = [
            entry
            for entry in (evidence_entries if evidence_entries is not None else primary_entries)
            if isinstance(entry, dict)
        ]
        self.selected_entry: Optional[dict] = None
        self.selected_evidence_entries: list[dict] = []

        self.setWindowTitle(t("report.promote_loot_title", "Create Finding from Loot"))
        self.resize(880, 500)
        self.setMinimumSize(680, 400)

        layout = QVBoxLayout(self)
        hint = QLabel(
            t(
                "report.promote_loot_hint",
                "Choose the Loot entry that defines the finding, then select any additional Loot to attach as supporting evidence.",
            )
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "ReportInspectorHint")
        layout.addWidget(hint)

        lists = QHBoxLayout()
        primary_column = QVBoxLayout()
        primary_column.addWidget(QLabel(t("report.promote_primary", "1. Finding source")))
        self.primary_list = QListWidget()
        self.primary_list.currentRowChanged.connect(self._on_primary_changed)
        primary_column.addWidget(self.primary_list, stretch=1)
        lists.addLayout(primary_column, stretch=1)

        evidence_column = QVBoxLayout()
        ev_header = QHBoxLayout()
        self.lbl_evidence = QLabel(
            t("report.promote_evidence", "2. Supporting evidence (optional)")
        )
        ev_header.addWidget(self.lbl_evidence)
        ev_header.addStretch()

        self.btn_suggest = QPushButton()
        self.btn_suggest.setProperty("class", "SecondaryBtn FormatToolBtn")
        self.btn_suggest.setIcon(icon("fa5s.magic", color=get_theme_color("ACCENT_BRAND")))
        self.btn_suggest.setVisible(False)
        self.btn_suggest.clicked.connect(self._on_apply_suggestions_clicked)
        ev_header.addWidget(self.btn_suggest)

        evidence_column.addLayout(ev_header)
        self.evidence_list = QListWidget()
        self.evidence_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.evidence_list.itemSelectionChanged.connect(self._on_evidence_selection_changed)
        evidence_column.addWidget(self.evidence_list, stretch=1)
        lists.addLayout(evidence_column, stretch=1)
        layout.addLayout(lists, stretch=1)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMaximumHeight(110)
        self.txt_preview.setPlaceholderText(t("report.promote_preview", "Primary Loot preview"))
        layout.addWidget(self.txt_preview)

        buttons = QHBoxLayout()
        self.lbl_selection = QLabel("")
        self.lbl_selection.setProperty("class", "ReportInspectorHint")
        buttons.addWidget(self.lbl_selection)
        buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.setProperty("class", "SecondaryBtn")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.btn_promote = QPushButton(t("report.promote_loot_action", "Create Finding"))
        self.btn_promote.setProperty("class", "PrimaryBtn")
        self.btn_promote.setIcon(icon("fa5s.file-medical", color=get_theme_color("SUCCESS")))
        self.btn_promote.setEnabled(False)
        self.btn_promote.clicked.connect(self.accept)
        buttons.addWidget(self.btn_promote)
        layout.addLayout(buttons)

        self._current_suggestions: list = []
        self._populate_primary_entries()

    @staticmethod
    def _entry_label(entry: dict) -> str:
        entry_type = str(entry.get("type", "note") or "note").upper()
        title = str(entry.get("title", "") or t("report.unnamed_entry", "Untitled Entry"))
        target = str(entry.get("target_ip", "") or "")
        suffix = f" · {target}" if target else ""
        return f"[{entry_type}] {title}{suffix}"

    def _populate_primary_entries(self) -> None:
        self.primary_list.clear()
        for entry in self.primary_entries:
            item = QListWidgetItem(self._entry_label(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.primary_list.addItem(item)
        if self.primary_list.count():
            self.primary_list.setCurrentRow(0)

    def _on_primary_changed(self, row: int) -> None:
        item = self.primary_list.item(row) if row >= 0 else None
        self.selected_entry = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        self.btn_promote.setEnabled(self.selected_entry is not None)
        self.txt_preview.setPlainText(
            str(self.selected_entry.get("content", "")) if self.selected_entry else ""
        )
        self._populate_evidence_entries()

    def _populate_evidence_entries(self) -> None:
        primary_id = str(self.selected_entry.get("id", "")) if self.selected_entry else ""
        self.evidence_list.clear()
        for entry in self.evidence_entries:
            if str(entry.get("id", "")) == primary_id:
                continue
            item = QListWidgetItem(self._entry_label(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.evidence_list.addItem(item)
        self._update_evidence_suggestions()
        self._on_evidence_selection_changed()

    def _update_evidence_suggestions(self) -> None:
        if not self.suggestions_enabled or not self.selected_entry:
            self._current_suggestions = []
            self.btn_suggest.setVisible(False)
            return

        from core.reporting import EvidenceCandidate, suggest_related_evidence

        anchor_type = (
            "screenshot"
            if str(self.selected_entry.get("type") or "") == "screenshot"
            else "loot"
        )
        anchor = EvidenceCandidate(source_type=anchor_type, entry=self.selected_entry)

        candidates = [
            EvidenceCandidate(
                source_type=(
                    "screenshot"
                    if str(e.get("type") or "") == "screenshot"
                    else "loot"
                ),
                entry=e,
            )
            for e in self.evidence_entries
            if str(e.get("id", "")) != anchor.id
        ]

        self._current_suggestions = suggest_related_evidence(
            anchor,
            candidates,
            proximity_seconds=self.correlation_window_seconds,
        )
        count = len(self._current_suggestions)
        if count > 0:
            self.btn_suggest.setText(
                t(
                    "report.promote_suggest_evidence",
                    "{count} verwandte Evidenzen auswählen",
                    count=count,
                )
            )
            self.btn_suggest.setToolTip(
                t(
                    "report.promote_suggest_tooltip",
                    "Basierend auf Phase, Target und Aufnahmezeit vorgeschlagen",
                )
            )
            self.btn_suggest.setVisible(True)
        else:
            self.btn_suggest.setVisible(False)

    def _on_apply_suggestions_clicked(self) -> None:
        if not getattr(self, "_current_suggestions", None):
            return
        suggested_ids = {s.candidate.id for s in self._current_suggestions}
        for idx in range(self.evidence_list.count()):
            item = self.evidence_list.item(idx)
            if item is None:
                continue
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry and str(entry.get("id", "")) in suggested_ids:
                item.setSelected(True)

    def _on_evidence_selection_changed(self) -> None:
        self.selected_evidence_entries = [
            item.data(Qt.ItemDataRole.UserRole) for item in self.evidence_list.selectedItems()
        ]
        self.lbl_selection.setText(
            t(
                "report.promote_selected_evidence",
                "{count} supporting entries selected",
                count=len(self.selected_evidence_entries),
            )
        )


class ClipboardHistoryPickerDialog(QDialog):
    """Dialog to select text or command output from clipboard history for report evidence."""

    def __init__(
        self,
        history: list[dict],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.history = [h for h in history if isinstance(h, dict)]
        self.selected_entry: Optional[dict] = None
        self._filtered_entries: list[dict] = []

        self.setWindowTitle(
            t("report.clipboard_picker_title", "Select Terminal / PoC from Clipboard History")
        )
        self.resize(720, 460)
        self.setMinimumSize(540, 340)

        main_layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        search_lbl = QLabel(t("report.search_label", "Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            t("report.clipboard_search_placeholder", "Filter by text, target IP...")
        )
        self.search_edit.textChanged.connect(self._filter_list)
        search_layout.addWidget(search_lbl)
        search_layout.addWidget(self.search_edit)

        self.chk_only_report = QCheckBox(
            t("report.clipboard_picker_only_marked", "Show marked for report only")
        )
        self.chk_only_report.toggled.connect(self._filter_list)
        search_layout.addWidget(self.chk_only_report)

        main_layout.addLayout(search_layout)

        content_layout = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)
        content_layout.addWidget(self.list_widget, stretch=3)

        preview_panel = QVBoxLayout()
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"font-size: 11px; color: {get_theme_color('TEXT_MUTED')};")
        preview_panel.addWidget(self.info_label)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px; "
            f"background: {get_theme_color('BG_SURFACE')}; color: {get_theme_color('TEXT_PRIMARY')}; border: 1px solid {get_theme_color('BORDER_DEFAULT')}; border-radius: 4px;"
        )
        preview_panel.addWidget(self.txt_preview, stretch=1)

        content_layout.addLayout(preview_panel, stretch=4)
        main_layout.addLayout(content_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.setIcon(icon("fa5s.times", color=get_theme_color("ERROR")))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_insert = QPushButton(
            t("report.clipboard_attach_evidence", "Attach as Terminal PoC")
        )
        self.btn_insert.setProperty("class", "PrimaryBtn")
        self.btn_insert.setIcon(icon("fa5s.check", color=get_theme_color("SUCCESS")))
        self.btn_insert.setEnabled(False)
        self.btn_insert.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_insert)

        main_layout.addLayout(btn_layout)

        self._filter_list()

    def _filter_list(self) -> None:
        query = self.search_edit.text().strip().lower()
        only_report = self.chk_only_report.isChecked()

        self.list_widget.clear()
        self._filtered_entries = []

        for entry in self.history:
            if only_report and not entry.get("include_in_report", False):
                continue

            text = str(entry.get("text") or "")
            ip = str(entry.get("target_ip") or "")

            if query and query not in text.lower() and query not in ip.lower():
                continue

            self._filtered_entries.append(entry)

            first_line = text.strip().splitlines()[0] if text.strip() else "(empty)"
            if len(first_line) > 60:
                first_line = first_line[:57] + "..."

            is_report_marked = bool(entry.get("include_in_report", False))
            prefix = "[Report] " if is_report_marked else ""

            item = QListWidgetItem()
            item.setText(f"{prefix}{first_line}")
            item.setIcon(
                icon(
                    "fa5s.star" if is_report_marked else "fa5s.terminal",
                    color=get_theme_color("SUCCESS"),
                )
            )
            self.list_widget.addItem(item)

        if self._filtered_entries:
            self.list_widget.setCurrentRow(0)
        else:
            self._on_selection_changed(-1)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._filtered_entries):
            self.selected_entry = None
            self.btn_insert.setEnabled(False)
            self.info_label.setText("")
            self.txt_preview.clear()
            return

        entry = self._filtered_entries[row]
        self.selected_entry = entry
        self.btn_insert.setEnabled(True)

        text = entry.get("text") or ""
        ts = entry.get("timestamp", "")
        ip = entry.get("target_ip", "")
        lines_cnt = len(text.splitlines())
        chars_cnt = len(text)

        lines_chars = t(
            "report.dialog_lines_chars",
            "Lines: {lines} | Characters: {chars}",
            lines=lines_cnt,
            chars=chars_cnt,
        )
        info_parts = [lines_chars]
        if ip:
            info_parts.append(f"Target: {ip}")
        if ts:
            info_parts.append(t("report.dialog_time", "Time: {time}", time=ts))
        self.info_label.setText(" | ".join(info_parts))

        self.txt_preview.setPlainText(text)

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        if self.selected_entry:
            self.accept()


class ReportExportTypeDialog(BaseHudDialog):
    """Dialog for host and discovered report export choices."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        plugin_metadata: Sequence[ExportPluginMetadata] = (),
    ):
        title = t("report.export_dialog_title", "SPECTRE // EXPORT REPORT")
        super().__init__(title=title, parent=parent)
        self.setObjectName("ReportExportTypeDialog")
        self.set_dialog_title(title)
        self.setMinimumWidth(540)
        self.selected_type: Optional[str] = None
        self.export_buttons: list[QPushButton] = []
        self.plugin_metadata = tuple(plugin_metadata)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = self.body_layout
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 16)

        lbl = QLabel(
            t("report.export_dialog_message", "Choose an export format for the current report.")
        )
        lbl.setObjectName("ExportDialogIntro")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        choices = [
            (
                "html",
                t("report.export_html", "Export HTML/PDF"),
                "WEB / PDF",
                t(
                    "report.export_html_desc",
                    "Create an editable web report or a print-ready HTML file for PDF output.",
                ),
                "fa5s.file-pdf",
                "CYBER_CYAN",
                "CYAN_A15",
                "CYAN_A35",
            ),
            (
                "markdown",
                t("report.export_copy", "Export MD..."),
                ".MD RAW",
                t(
                    "report.export_markdown_desc",
                    "Save an exact Markdown copy of the current Report Editor document.",
                ),
                "fa5s.file-alt",
                "CYBER_BLUE",
                "BLUE_A25",
                "BLUE_A40",
            ),
        ]

        accent_tokens = {
            "purple": ("STATUS_PURPLE", "PURPLE_A20", "PURPLE_A40"),
            "green": ("STATUS_SUCCESS", "SUCCESS_A20", "SUCCESS_A40"),
            "cyan": ("CYBER_CYAN", "CYAN_A15", "CYAN_A35"),
        }
        plugin_choices = []
        for metadata in self.plugin_metadata:
            plugin_name = plugin_text(metadata.display_name)
            accent_token, bg_token, border_token = accent_tokens.get(
                metadata.accent or "", ("CYBER_BLUE", "BLUE_A25", "BLUE_A40")
            )
            plugin_choices.append(
                (
                    f"plugin:{metadata.plugin_id}",
                    t("report.export_plugin", "Export to {plugin}...", plugin=plugin_name),
                    metadata.badge,
                    plugin_text(metadata.description),
                    metadata.icon_name,
                    accent_token,
                    bg_token,
                    border_token,
                )
            )
        choices[1:1] = plugin_choices

        for (
            export_type,
            label,
            badge,
            description,
            icon_name,
            accent_token,
            bg_tint_token,
            border_tint_token,
        ) in choices:
            accent_color = get_theme_color(accent_token)
            bg_tint = get_theme_color(bg_tint_token)
            border_tint = get_theme_color(border_tint_token)
            card = QFrame()
            card.setObjectName("ExportOptionCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(14)

            # Icon Box
            icon_box = QFrame()
            icon_box.setObjectName("ExportIconBox")
            icon_box.setProperty("exportType", export_type)
            icon_box.setFixedSize(40, 40)
            icon_box.setStyleSheet(
                f"QFrame#ExportIconBox {{ background: {bg_tint}; border: 1px solid {border_tint}; border-radius: 8px; }}"
            )
            ib_layout = QVBoxLayout(icon_box)
            ib_layout.setContentsMargins(0, 0, 0, 0)
            ib_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_icon = QLabel()
            lbl_icon.setPixmap(icon(icon_name, color=accent_color).pixmap(20, 20))
            ib_layout.addWidget(lbl_icon)
            card_layout.addWidget(icon_box)

            # Center text layout
            text_layout = QVBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(3)

            title_row = QHBoxLayout()
            title_row.setSpacing(8)
            lbl_title = QLabel(label)
            lbl_title.setObjectName("ExportOptionTitle")
            title_row.addWidget(lbl_title)

            lbl_badge = QLabel(badge)
            lbl_badge.setObjectName("ExportOptionBadge")
            title_row.addWidget(lbl_badge)
            title_row.addStretch()
            text_layout.addLayout(title_row)

            desc_label = QLabel(description)
            desc_label.setObjectName("ExportOptionDesc")
            desc_label.setWordWrap(True)
            desc_label.setProperty("class", "HintLabel")
            desc_label.setProperty("exportType", export_type)
            text_layout.addWidget(desc_label)

            card_layout.addLayout(text_layout, stretch=1)

            # Action button
            btn = QPushButton(label)
            btn.setObjectName("ExportOptionBtn")
            btn.setProperty("class", "SecondaryBtn")
            btn.setProperty("exportType", export_type)
            btn.setIcon(icon("fa5s.arrow-right", color=get_theme_color("CYBER_BLUE_LIGHT")))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            def _make_handler(et: str):
                def _handle(_checked: bool = False) -> None:
                    self.selected_type = et
                    self.accept()

                return _handle

            handler = _make_handler(export_type)
            btn.clicked.connect(handler)
            self.export_buttons.append(btn)
            card_layout.addWidget(btn)

            # Clicking anywhere on the card triggers the button
            def _make_card_click(b: QPushButton):
                def _mouse_press(e) -> None:
                    b.click()

                return _mouse_press

            card.mousePressEvent = _make_card_click(btn)  # type: ignore[assignment]
            layout.addWidget(card)

        layout.addSpacing(6)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton(t("dialog.cancel", "Cancel"))
        cancel_btn.setProperty("class", "SecondaryBtn")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        layout.addLayout(footer)

    @classmethod
    def select_export_type(
        cls,
        parent: Optional[QWidget] = None,
        plugin_metadata: Sequence[ExportPluginMetadata] = (),
    ) -> Optional[str]:
        dlg = cls(parent, plugin_metadata=plugin_metadata)
        dlg.exec()
        return dlg.selected_type


@dataclass(frozen=True)
class HtmlExportOptions:
    theme: str
    profile: str
    include_toc: bool = False


def select_html_export_options(parent: Optional[QWidget] = None) -> Optional[HtmlExportOptions]:
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
    toc_checkbox = QCheckBox(
        t(
            "report.html_profile_include_toc",
            "Include a linked table of contents in Professional Print",
        ),
        msg,
    )
    toc_checkbox.setChecked(True)
    toc_checkbox.setToolTip(
        t(
            "report.html_profile_include_toc_tip",
            "Lists report sections and findings after the cover page without page numbers",
        )
    )
    msg.setCheckBox(toc_checkbox)
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
        t(
            "report.html_profile_professional_tip",
            "Print-ready A4 presentation for browser PDF generation",
        )
    )
    classic_web_button.setToolTip(
        t("report.html_profile_classic_web_tip", "Editable responsive web report for browser use")
    )
    cancel_button.setMinimumWidth(100)
    msg.exec()

    if msg.clickedButton() is professional_button:
        return HtmlExportOptions(
            theme="light",
            profile="professional_print",
            include_toc=toc_checkbox.isChecked(),
        )
    if msg.clickedButton() is classic_web_button:
        return HtmlExportOptions(theme="light", profile="interactive")
    return None
