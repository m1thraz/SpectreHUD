"""
Report-Editor-Tab: bearbeitet die projekt-lokale report.md direkt im
Fenster, kein externer Editor nötig.

Layout: QSplitter mit Markdown-Quelltext links (QPlainTextEdit) und
gerenderter Live-Vorschau rechts (QTextEdit.setMarkdown - Qt-Bordmittel,
keine zusätzliche Markdown-Dependency nötig). Vorschau wird debounced
(300ms nach letzter Änderung) aktualisiert, damit schnelles Tippen nicht
bei jedem Tastendruck neu rendert.

Bewusste Trennung von core.report_file_manager.ReportFileManager: dieses
Widget kennt nur "lade Text rein / hol Text raus", die eigentliche
Backup-vor-Regenerierung-Logik lebt im FileManager, nicht hier - damit
sie ohne Qt testbar bleibt.
"""
from enum import Enum
import urllib.parse
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPlainTextEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QFileDialog, QDialog, QLineEdit, QMenu, QSpinBox,
    QComboBox, QFormLayout
)
from PyQt6.QtGui import QAction, QFont, QShortcut, QKeySequence, QTextDocument, QTextCursor, QImage

from core.report_file_manager import ReportFileManager
from core.config import ConfigManager
from core.reporting.template_engine import ReportTemplate
from core.reporting.template_repository import TemplateRepository
from ui.template_manager_dialog import TemplateManagerDialog
from core.logger import get_logger
from core.i18n import t
from ui.styles import CYBER_DARK_QSS, build_app_theme
from ui.styles.fonts import get_report_font_stack

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300
AUTOSAVE_INTERVAL_MS = 45_000


MAX_PREVIEW_IMAGE_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB


class ViewMode(Enum):
    EDITOR = "editor"
    SPLIT = "split"
    PREVIEW = "preview"


class MarkdownTableDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(t("report.table_title", "Insert Table"))
        self.setStyleSheet(CYBER_DARK_QSS)
        layout = QVBoxLayout(self)
        self.rows = QSpinBox(); self.rows.setRange(1, 10); self.rows.setValue(2)
        self.columns = QSpinBox(); self.columns.setRange(1, 10); self.columns.setValue(3)
        layout.addWidget(QLabel(t("report.table_rows", "Rows:"))); layout.addWidget(self.rows)
        layout.addWidget(QLabel(t("report.table_columns", "Columns:"))); layout.addWidget(self.columns)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton(t("dialog.cancel", "Cancel")); cancel.clicked.connect(self.reject); buttons.addWidget(cancel)
        insert = QPushButton(t("report.table_insert", "Insert Table")); insert.setProperty("class", "PrimaryBtn"); insert.clicked.connect(self.accept); buttons.addWidget(insert)
        layout.addLayout(buttons)


class ReportPreviewEdit(QTextEdit):
    """Custom QTextEdit for live Markdown preview and editing with sandbox protection against unvalidated drag/drop and image insertions."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(False)

    def insertFromMimeData(self, source):
        # Prevent pasting images directly into the editable preview to maintain sandbox integrity
        if source and (source.hasImage() or (source.hasUrls() and any(u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) for u in source.urls()))):
            logger.warning("Blocked raw image paste/drop into editable preview document.")
            return
        super().insertFromMimeData(source)


class ReportDocument(QTextDocument):
    """Custom QTextDocument that dynamically resolves project-relative image paths and loot screenshots within the project sandbox."""

    def __init__(self, project_dir: Optional[Path] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project_dir = Path(project_dir) if project_dir else None
        self._image_cache: Dict[str, QImage] = {}

    def set_project_dir(self, project_dir: Optional[Path]) -> None:
        new_dir = Path(project_dir) if project_dir else None
        if self.project_dir != new_dir:
            self.project_dir = new_dir
            self._image_cache.clear()
            if self.project_dir and self.project_dir.exists():
                try:
                    self.setBaseUrl(QUrl.fromLocalFile(str(self.project_dir.resolve()) + "/"))
                except OSError:
                    pass

    def loadResource(self, r_type: int, name: QUrl):
        if r_type == int(QTextDocument.ResourceType.ImageResource) or r_type == 2:
            url_str = name.toString() if hasattr(name, "toString") else str(name)
            if url_str in self._image_cache:
                return self._image_cache[url_str]

            if not self.project_dir:
                return super().loadResource(r_type, name)

            try:
                proj_resolved = self.project_dir.resolve()
            except (OSError, RuntimeError) as e:
                logger.warning(f"Could not resolve project directory: {e}")
                return super().loadResource(r_type, name)

            clean_path = urllib.parse.unquote(url_str).strip()
            if clean_path.startswith("file:///"):
                clean_path = clean_path[8:]
            elif clean_path.startswith("file://"):
                clean_path = clean_path[7:]

            p = Path(clean_path)
            candidate_paths = []
            if p.is_absolute():
                candidate_paths.append(p)
            else:
                candidate_paths.append(self.project_dir / p)
                candidate_paths.append(self.project_dir / "loot" / p.name)

            for candidate in candidate_paths:
                try:
                    cand_resolved = candidate.resolve()
                except (OSError, RuntimeError):
                    continue

                # STRICT SANDBOX BOUNDARY CHECK:
                # Disallow any path traversal escaping the active project workspace
                try:
                    if not cand_resolved.is_relative_to(proj_resolved):
                        logger.warning(
                            f"Blocked path traversal image preview attempt outside project sandbox: {candidate} -> {cand_resolved}"
                        )
                        continue
                except (ValueError, AttributeError):
                    continue

                # Must exist and be a regular file
                if not cand_resolved.exists() or not cand_resolved.is_file():
                    continue

                # DoS Protection: Size limit check before decoding
                try:
                    file_size = cand_resolved.stat().st_size
                    if file_size > MAX_PREVIEW_IMAGE_FILE_SIZE or file_size == 0:
                        logger.warning(
                            f"Rejected oversized/empty image preview file ({file_size} bytes): {cand_resolved}"
                        )
                        continue
                except OSError:
                    continue

                # Load and decode image
                img = QImage(str(cand_resolved))
                if not img.isNull():
                    # Downscale oversized screenshots for preview performance & clean rendering
                    if img.width() > 1400:
                        img = img.scaledToWidth(1400, Qt.TransformationMode.SmoothTransformation)
                    self._image_cache[url_str] = img
                    return img
                else:
                    logger.warning(f"Could not decode QImage from candidate: {cand_resolved}")

        return super().loadResource(r_type, name)


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
        self.setStyleSheet(CYBER_DARK_QSS)
        self._build_ui(has_existing_report)
        self._populate_templates()

    def _build_ui(self, has_existing_report: bool) -> None:
        layout = QVBoxLayout(self)

        description = QLabel(
            t("report.generate_description", "Creates a structured report from current loot and clipboard history.")
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        if has_existing_report:
            warning = QLabel(
                t("report.generate_warning", "The existing report will be replaced. It is backed up as <b>report.md.bak</b> first.")
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #f0b429; margin-top: 6px;")
            layout.addWidget(warning)

        form = QFormLayout()
        self.combo_templates = QComboBox()
        self.combo_templates.setToolTip(t("report.template_tip", "Select a template for the newly generated report"))
        form.addRow(t("report.template_label", "Report Template:"), self.combo_templates)
        layout.addLayout(form)

        self.btn_manage_templates = QPushButton(t("report.manage_templates", "🎨 Templates..."))
        self.btn_manage_templates.setProperty("class", "SecondaryBtn")
        self.btn_manage_templates.clicked.connect(self._open_template_manager)
        layout.addWidget(self.btn_manage_templates, alignment=Qt.AlignmentFlag.AlignLeft)

        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        btn_generate = QPushButton(t("report.generate", "Generate Report"))
        btn_generate.setProperty("class", "PrimaryBtn")
        btn_generate.clicked.connect(self._accept_selection)
        buttons.addWidget(btn_generate)
        layout.addLayout(buttons)

    def _populate_templates(self) -> None:
        selected_id = self.selected_template.id if self.selected_template else None
        templates = self.template_repo.get_all_templates()
        self.combo_templates.blockSignals(True)
        self.combo_templates.clear()
        for template in templates:
            self.combo_templates.addItem(f"{template.name} [{template.language.upper()}]", template.id)

        index = self.combo_templates.findData(selected_id) if selected_id else -1
        if index >= 0:
            self.combo_templates.setCurrentIndex(index)
        elif templates:
            self.combo_templates.setCurrentIndex(0)
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
            QMessageBox.warning(self, t("report.no_template_title", "No Template"), t("report.no_template_message", "Please select a report template."))
            return
        self.selected_template = template
        self.accept()


class ReportEditorTab(QWidget):
    """Editierbarer Markdown-Report mit Live-Vorschau für das aktive Projekt."""

    # Für main_window: signalisiert, ob ungespeicherte Änderungen vorliegen
    dirty_changed = pyqtSignal(bool)

    def __init__(self, report_file_manager: ReportFileManager, loot_manager, clipboard_watcher,
                 parent: QWidget = None, config_manager: Optional[ConfigManager] = None):
        super().__init__(parent)
        self.report_file_manager = report_file_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.config = config_manager
        self.template_repo = TemplateRepository()
        self.active_template: Optional[ReportTemplate] = None
        self.current_project: Optional[str] = None
        self._dirty = False
        self._view_mode = ViewMode.SPLIT
        self._preview_markdown_snapshot: Optional[str] = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

        self._build_ui()
        self._ensure_active_template()

    # ------------------------------------------------------------------ #
    # UI-Aufbau
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("class", "ReportStatusLabel")

        # Compact view selector; shortcuts remain available for power users.
        self.btn_change_view = QPushButton(t("report.change_view", "Change View"))
        self.btn_change_view.setProperty("class", "SecondaryBtn")
        self.btn_change_view.setToolTip(t("report.change_view_tip", "Choose report editor layout"))
        self.view_menu = QMenu(self.btn_change_view)
        self._view_actions = {}
        for mode, key, fallback in (
            (ViewMode.EDITOR, "report.mode_editor", "📝 Editor"),
            (ViewMode.SPLIT, "report.mode_split", "◫ Split"),
            (ViewMode.PREVIEW, "report.mode_preview", "👁️ Live Preview"),
        ):
            action = QAction(t(key, fallback), self.view_menu)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, selected=mode: self._set_view_mode(selected))
            self.view_menu.addAction(action)
            self._view_actions[mode] = action
        self.btn_change_view.setMenu(self.view_menu)
        toolbar.addWidget(self.btn_change_view)

        self.btn_regenerate = QPushButton(t("report.regenerate", "Regenerate from Loot"))
        self.btn_regenerate.setProperty("class", "SecondaryBtn")
        self.btn_regenerate.setToolTip(
            t(
                "report.regenerate_tip",
                "Updates report structure and appends new loot entries"
            )
        )
        self.btn_regenerate.clicked.connect(self._on_regenerate_clicked)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_export = QPushButton(t("report.export", "Export..."))
        self.btn_export.setProperty("class", "SecondaryBtn")
        self.btn_export.setToolTip(t("report.export_tip", "Choose how to export the current report"))
        self.btn_export.clicked.connect(self._on_export_clicked)
        toolbar.addWidget(self.btn_export)

        # Formatting belongs with the primary editing/export actions.  The
        # source-only controls are still hidden while the rich live preview is
        # active (see _apply_view_mode).
        self.format_toolbar_widget = QWidget()
        format_toolbar = QHBoxLayout(self.format_toolbar_widget)
        format_toolbar.setContentsMargins(0, 0, 0, 0)
        format_toolbar.setSpacing(3)
        self._add_format_button(format_toolbar, "H1", "report.format_h1", "Heading 1", lambda: self._format_heading(1))
        self._add_format_button(format_toolbar, "H2", "report.format_h2", "Heading 2", lambda: self._format_heading(2))
        self._add_format_button(format_toolbar, "H3", "report.format_h3", "Heading 3", lambda: self._format_heading(3))
        self._add_format_button(format_toolbar, "B", "report.format_bold", "Bold", lambda: self._format_wrap("**", "**"))
        self._add_format_button(format_toolbar, "I", "report.format_italic", "Italic", lambda: self._format_wrap("*", "*"))
        self._add_format_button(format_toolbar, "</>", "report.format_code", "Inline Code", lambda: self._format_wrap("`", "`"))
        self._add_format_button(format_toolbar, "```", "report.format_code_block", "Code Block", self._format_code_block)
        self._add_format_button(format_toolbar, "•", "report.format_list", "Bullet List", lambda: self._format_list(False))
        self._add_format_button(format_toolbar, "1.", "report.format_numbered_list", "Numbered List", lambda: self._format_list(True))
        self._add_format_button(format_toolbar, "🔗", "report.format_link", "Link", self._format_link)
        self._add_format_button(format_toolbar, "▦", "report.format_table", "Table", self._format_table)
        toolbar.addWidget(self.format_toolbar_widget)

        self.btn_save = QPushButton(t("report.save", "Save"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.setToolTip(t("report.save_tip", "Save changes to active box report.md (Ctrl+S)"))
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)

        layout.addLayout(toolbar)

        status_row = QHBoxLayout()
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.find_bar = QWidget()
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(4, 2, 4, 2)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Suchen …")
        self.find_input.textChanged.connect(self._update_find_count)
        self.find_input.returnPressed.connect(self._find_next)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Ersetzen durch …")
        self.find_count_label = QLabel("0 Treffer")
        btn_previous = QPushButton("↑")
        btn_previous.setToolTip("Vorheriger Treffer")
        btn_previous.clicked.connect(self._find_previous)
        btn_next = QPushButton("↓")
        btn_next.setToolTip("Nächster Treffer")
        btn_next.clicked.connect(self._find_next)
        btn_replace = QPushButton("Ersetzen")
        btn_replace.clicked.connect(self._replace_current)
        btn_replace_all = QPushButton("Alle ersetzen")
        btn_replace_all.clicked.connect(self._replace_all)
        btn_close_find = QPushButton("×")
        btn_close_find.setToolTip("Suche schließen (Esc)")
        btn_close_find.clicked.connect(self._close_find_bar)
        for widget in (self.find_input, self.replace_input, self.find_count_label, btn_previous,
                       btn_next, btn_replace, btn_replace_all, btn_close_find):
            find_layout.addWidget(widget)
        self.find_bar.hide()
        layout.addWidget(self.find_bar)

        # --- Editor | Vorschau ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            t(
                "report.editor_placeholder",
                "No report available for this project yet.\n\n"
                "Click 'Regenerate from Loot' above to start with an "
                "auto-generated report, or write your markdown directly here."
            )
        )
        self.editor.setProperty("class", "ReportSourceEditor")
        self.editor.textChanged.connect(self._on_text_changed)
        from ui.markdown_highlighter import MarkdownHighlighter
        self._highlighter = MarkdownHighlighter(self.editor.document())
        self.splitter.addWidget(self.editor)

        self.preview_document = ReportDocument(parent=self)
        self._apply_preview_font()
        self.setStyleSheet(build_app_theme(self._ui_font_key(), self._code_font_key()))

        self.preview = ReportPreviewEdit()
        self.preview.setDocument(self.preview_document)
        self.preview.setReadOnly(True)
        self.preview.setProperty("class", "ReportPreview")
        self.splitter.addWidget(self.preview)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, stretch=1)

        # Shortcuts für Speichern und View-Modi
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        sc_save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_save_shift = QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save)
        sc_save_shift.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_cycle = QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self._cycle_view_mode)
        sc_cycle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode1 = QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._set_view_mode(ViewMode.EDITOR))
        sc_mode1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode2 = QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._set_view_mode(ViewMode.SPLIT))
        sc_mode2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode3 = QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self._set_view_mode(ViewMode.PREVIEW))
        sc_mode3.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self.editor, activated=self._open_find_bar)
        self._shortcut_find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_find_close = QShortcut(QKeySequence("Esc"), self.find_bar, activated=self._close_find_bar)
        self._shortcut_find_close.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for sequence, callback in (("Ctrl+B", lambda: self._format_wrap("**", "**")), ("Ctrl+I", lambda: self._format_wrap("*", "*")), ("Ctrl+K", lambda: self._format_wrap("`", "`"))):
            shortcut = QShortcut(QKeySequence(sequence), self.editor, activated=callback)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._apply_view_mode(self._view_mode)

    def _ui_font_key(self) -> str:
        return self.config.get("ui_font", "segoe_ui") if self.config else "segoe_ui"

    def _add_format_button(self, layout: QHBoxLayout, label: str, key: str, fallback: str, callback) -> None:
        button = QPushButton(label)
        button.setProperty("class", "SecondaryBtn")
        button.setToolTip(t(key, fallback))
        button.clicked.connect(callback)
        layout.addWidget(button)

    def _format_heading(self, level: int) -> None:
        from ui.markdown_toolbar_actions import set_heading
        set_heading(self.editor, level)

    def _format_wrap(self, prefix: str, suffix: str) -> None:
        from ui.markdown_toolbar_actions import wrap_selection
        wrap_selection(self.editor, prefix, suffix)

    def _format_code_block(self) -> None:
        from ui.markdown_toolbar_actions import insert_fenced_code
        insert_fenced_code(self.editor)

    def _format_list(self, numbered: bool) -> None:
        from ui.markdown_toolbar_actions import prefix_lines
        prefix_lines(self.editor, numbered)

    def _format_link(self) -> None:
        from ui.markdown_toolbar_actions import insert_link
        insert_link(self.editor)

    def _format_table(self) -> None:
        dialog = MarkdownTableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from ui.markdown_toolbar_actions import insert_table
            insert_table(self.editor, dialog.rows.value(), dialog.columns.value())

    def _code_font_key(self) -> str:
        return self.config.get("code_font", "consolas") if self.config else "consolas"

    def _report_font_key(self) -> str:
        return self.config.get("report_font", "segoe_ui") if self.config else "segoe_ui"

    def _apply_preview_font(self) -> None:
        """Apply the report font to the rich-text live preview."""
        report_font = get_report_font_stack(self._report_font_key())
        primary_font = report_font.split(",", 1)[0].strip().strip("'\"")
        preview_font = QFont(primary_font, 10)
        preview_font.setStyleHint(QFont.StyleHint.SansSerif)
        self.preview_document.setDefaultFont(preview_font)
        self.preview_document.setDefaultStyleSheet("""
            body { font-family: __REPORT_FONT_STACK__; font-size: 13px; color: #f0f6fc; line-height: 1.6; }
            h1, h2, h3, h4, h5, h6 { color: #58a6ff; font-family: __REPORT_FONT_STACK__; font-weight: 600; margin-top: 14px; margin-bottom: 6px; }
            h1 { font-size: 18px; border-bottom: 1px solid #30363d; padding-bottom: 4px; }
            h2 { font-size: 15px; border-bottom: 1px solid #21262d; padding-bottom: 3px; color: #79c0ff; }
            h3 { font-size: 14px; color: #a5d6ff; }
            code { font-family: 'Cascadia Code', 'Consolas', 'Fira Code', monospace; background-color: #161b22; color: #7ee787; padding: 2px 4px; border-radius: 4px; font-size: 12px; }
            pre { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px; }
            blockquote { border-left: 3px solid #388bfd; margin: 8px 0; padding-left: 10px; color: #8b949e; }
            hr { border: 0; border-top: 1px solid #30363d; margin: 14px 0; }
            a { color: #58a6ff; text-decoration: none; }
            img { max-width: 100%; border-radius: 6px; border: 1px solid #30363d; margin: 8px 0; }
            ul, ol { padding-left: 20px; margin: 6px 0; }
            li { margin: 3px 0; }
            p { margin: 6px 0; }
        """.replace("__REPORT_FONT_STACK__", report_font))

    def refresh_font_configuration(self) -> None:
        """Refresh QSS and preview typography after settings are saved."""
        self.setStyleSheet(build_app_theme(self._ui_font_key(), self._code_font_key()))
        self._apply_preview_font()
        self._update_preview()

    # ------------------------------------------------------------------ #
    # Projekt-Wechsel / Laden
    # ------------------------------------------------------------------ #

    def load_project(self, project_name: str) -> None:
        """
        Lädt den Report des angegebenen Projekts in den Editor.
        Muss von main_window bei jedem Projektwechsel aufgerufen werden -
        prüft NICHT selbst auf ungespeicherte Änderungen im vorherigen
        Projekt, das ist Aufgabe des Aufrufers (siehe confirm_discard_if_dirty).
        """
        self.current_project = project_name
        proj_dir = self.report_file_manager.project_manager.get_project_dir(project_name)
        self.preview_document.set_project_dir(proj_dir)

        content = self.report_file_manager.load(project_name)
        # setPlainText löst textChanged aus -> _dirty würde faelschlich True
        # werden, deshalb Signal kurz blocken.
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        self._set_dirty(False)
        self._update_preview()
        self._update_status_label()

    # ------------------------------------------------------------------ #
    # Dirty-State
    # ------------------------------------------------------------------ #

    def is_dirty(self) -> bool:
        return self._dirty

    def confirm_discard_if_dirty(self) -> bool:
        """
        Fragt bei ungespeicherten Änderungen nach, ob gespeichert, verworfen
        oder abgebrochen werden soll. Gibt True zurück, wenn der Aufrufer
        fortfahren darf (gespeichert oder bewusst verworfen), False bei
        Abbruch (z.B. Projekt-/Moduswechsel soll NICHT stattfinden).
        """
        if not self._dirty:
            return True

        msg = QMessageBox(self.window() if self else None)
        msg.setWindowTitle(t("report.unsaved_prompt_title", "Unsaved Changes"))
        msg.setText(t("report.unsaved_prompt_message", "The report has unsaved changes.\n\nSave them now?"))
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)
        msg.setStyleSheet(CYBER_DARK_QSS)

        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Save:
            return self.save()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    def _set_dirty(self, value: bool) -> None:
        if value != self._dirty:
            self._dirty = value
            self.dirty_changed.emit(value)
        self._update_status_label()

    def _on_text_changed(self) -> None:
        self._set_dirty(True)
        self._preview_timer.start()  # debounced

    def _open_find_bar(self) -> None:
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._update_find_count()

    def _close_find_bar(self) -> None:
        self.find_bar.hide()
        self.editor.setFocus()

    def _update_find_count(self) -> None:
        needle = self.find_input.text()
        if not needle:
            self.find_count_label.setText("0 Treffer")
            return
        document = self.editor.document()
        cursor = document.find(needle)
        count = 0
        while not cursor.isNull():
            count += 1
            cursor = document.find(needle, cursor)
        self.find_count_label.setText(f"{count} Treffer")

    def _find(self, backwards: bool = False) -> None:
        needle = self.find_input.text()
        if not needle:
            return
        flags = QTextDocument.FindFlag.FindBackward if backwards else QTextDocument.FindFlag(0)
        cursor = self.editor.document().find(needle, self.editor.textCursor(), flags)
        if cursor.isNull():
            cursor = self.editor.document().find(needle, QTextCursor(), flags)
        if not cursor.isNull():
            self.editor.setTextCursor(cursor)

    def _find_next(self) -> None:
        self._find(False)

    def _find_previous(self) -> None:
        self._find(True)

    def _replace_current(self) -> None:
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self._find_next()

    def _replace_all(self) -> None:
        needle = self.find_input.text()
        if not needle:
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(cursor.MoveOperation.Start)
        while True:
            match = self.editor.document().find(needle, cursor)
            if match.isNull():
                break
            match.insertText(self.replace_input.text())
            cursor = match
        cursor.endEditBlock()
        self._update_find_count()

    def _enter_preview_mode(self) -> None:
        """Enters editable live preview mode and takes a markdown baseline snapshot."""
        self._preview_markdown_snapshot = self.editor.toPlainText()
        self.preview.setReadOnly(False)
        self.preview.setFocus()

    def _commit_preview_to_markdown(self) -> None:
        """Commits rich-text edits from the preview document back to the markdown editor."""
        new_markdown = self.preview_document.toMarkdown()
        old_len = len(self._preview_markdown_snapshot or "")
        new_len = len(new_markdown)

        # Sanity check against severe conversion loss
        if old_len > 200 and new_len < old_len * 0.6:
            reply = QMessageBox.warning(
                self.window() if self else None,
                "Ungewöhnlich große Änderung",
                "Die Bearbeitung in der Live-Ansicht hat den Inhalt stark verkürzt "
                "(möglicher Konvertierungsverlust).\n\nTrotzdem übernehmen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                # Discard: reset preview to previous markdown
                self._update_preview()
                self._preview_markdown_snapshot = None
                return

        if new_markdown != self._preview_markdown_snapshot:
            self.editor.blockSignals(True)
            self.editor.setPlainText(new_markdown)
            self.editor.blockSignals(False)
            self._set_dirty(True)

        self._preview_markdown_snapshot = None

    def _set_view_mode(self, mode: ViewMode) -> None:
        """Switches the view mode and handles preview commit / readonly transitions."""
        if mode == self._view_mode:
            return

        # Leaving PREVIEW mode -> commit edits and make preview read-only
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
            self.preview.setReadOnly(True)

        # Entering PREVIEW mode -> make editable and take snapshot
        if mode == ViewMode.PREVIEW:
            self._enter_preview_mode()

        self._view_mode = mode
        self._apply_view_mode(mode)
        self._update_status_label()

    def _apply_view_mode(self, mode: ViewMode) -> None:
        """Applies visibility and splitter layout for the selected view mode."""
        for action_mode, action in self._view_actions.items():
            action.setChecked(action_mode == mode)
        self.format_toolbar_widget.setVisible(mode != ViewMode.PREVIEW)
        if mode == ViewMode.EDITOR:
            self.editor.setVisible(True)
            self.preview.setVisible(False)
        elif mode == ViewMode.PREVIEW:
            self.editor.setVisible(False)
            self.preview.setVisible(True)
        elif mode == ViewMode.SPLIT:
            self.editor.setVisible(True)
            self.preview.setVisible(True)
            total_w = self.splitter.width() or 800
            self.splitter.setSizes([total_w // 2, total_w // 2])

    def _cycle_view_mode(self) -> None:
        """Cycles through EDITOR -> SPLIT -> PREVIEW -> EDITOR."""
        modes = [ViewMode.EDITOR, ViewMode.SPLIT, ViewMode.PREVIEW]
        idx = modes.index(self._view_mode)
        self._set_view_mode(modes[(idx + 1) % len(modes)])

    def save(self) -> bool:
        if not self.current_project:
            return False

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        ok = self.report_file_manager.save(self.editor.toPlainText(), project_name=self.current_project)
        if ok:
            self._set_dirty(False)
        else:
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle(t("dialog.error", "Error"))
            msg.setText(t("report.save_error", "The report could not be saved. Details are in the log."))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
        return ok

    def _autosave(self) -> None:
        """Persist a dirty report without interrupting the user on failures."""
        if not self.is_dirty() or not self.current_project:
            return
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
        try:
            ok = self.report_file_manager.save(self.editor.toPlainText(), project_name=self.current_project)
        except Exception:
            logger.exception("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(t("report.autosave_failed", "Autosave failed — please save manually"))
            return
        if ok:
            self._set_dirty(False)
        else:
            logger.error("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(t("report.autosave_failed", "Autosave failed — please save manually"))

    def closeEvent(self, event) -> None:
        self._autosave_timer.stop()
        super().closeEvent(event)

    def _on_regenerate_clicked(self) -> None:
        if not self.current_project:
            return

        has_existing = self.report_file_manager.exists(self.current_project) or self._dirty
        dialog = ReportGenerationDialog(
            template_repo=self.template_repo,
            selected_template=self.active_template,
            has_existing_report=has_existing,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_template is None:
            return
        self.active_template = dialog.selected_template

        from core.report_file_manager import ReportBackupError, ReportSaveError
        try:
            new_content = self.report_file_manager.regenerate(
                self.loot_manager,
                self.clipboard_watcher,
                project_name=self.current_project,
                template=self.active_template
            )
            self.editor.blockSignals(True)
            self.editor.setPlainText(new_content)
            self.editor.blockSignals(False)
            self._set_dirty(False)  # regenerate() hat bereits erfolgreich gespeichert
            self._update_preview()
        except ReportBackupError as e:
            logger.error(f"Regenerierung abgebrochen wegen Backup-Fehler: {e}")
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Backup fehlgeschlagen")
            msg.setText(
                "Das automatische Backup des bisherigen Reports ist fehlgeschlagen.\n\n"
                "Zum Schutz deiner bestehenden Notizen wurde die Regenerierung abgebrochen."
            )
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
        except ReportSaveError as e:
            logger.error(f"Regenerierung: Speichern fehlgeschlagen: {e}")
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Speichern fehlgeschlagen")
            msg.setText(
                "Der neu generierte Report konnte nicht auf die Festplatte geschrieben werden.\n\n"
                "Der bisherige Report bleibt erhalten."
            )
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()

    def _ensure_active_template(self) -> None:
        """Keeps the most recently selected template available for the next dialog."""
        templates = self.template_repo.get_all_templates()
        if self.active_template is None and templates:
            self.active_template = templates[0]

    def _on_export_clicked(self) -> None:
        """Opens the single export chooser and delegates to the selected workflow."""
        export_type = self._select_export_type()
        if export_type == "markdown":
            self._on_export_copy_clicked()
        elif export_type == "html":
            self._on_export_html_clicked()
        elif export_type == "obsidian":
            self._on_export_obsidian_clicked()
        elif export_type == "cherrytree":
            self._on_export_cherrytree_clicked()

    def _select_export_type(self) -> Optional[str]:
        """Returns the selected export workflow without duplicating export logic."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("report.export_dialog_title", "Export Report"))
        dialog.setText(t("report.export_dialog_message", "Choose an export format for the current report."))
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStyleSheet(CYBER_DARK_QSS)

        choices = (
            ("markdown", t("report.export_copy", "Export Copy...")),
            ("html", t("report.export_html", "Export HTML...")),
            ("obsidian", t("report.export_obsidian", "Export to Obsidian...")),
            ("cherrytree", t("report.export_cherrytree", "Export CherryTree Package...")),
        )
        buttons = {
            export_type: dialog.addButton(label, QMessageBox.ButtonRole.ActionRole)
            for export_type, label in choices
        }
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()

        selected_button = dialog.clickedButton()
        return next(
            (export_type for export_type, button in buttons.items() if button is selected_button),
            None,
        )

    def _on_export_copy_clicked(self) -> None:
        from core.atomic_write import atomic_write_text
        default_path = self.report_file_manager.get_report_path(self.current_project)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Report-Kopie exportieren", str(default_path), "Markdown (*.md)"
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".md":
            target = target.with_suffix(".md")

        success = atomic_write_text(target, self.editor.toPlainText())
        if success:
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Exportiert")
            msg.setText(f"Kopie gespeichert: {target.name}")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
        else:
            logger.error(f"Export der Report-Kopie nach {target} fehlgeschlagen")
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Fehler")
            msg.setText(f"Export fehlgeschlagen: Die Datei '{target.name}' konnte nicht gespeichert werden.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()

    def _on_export_html_clicked(self) -> None:
        from core.html_report_exporter import HtmlReportExporter
        from PyQt6.QtGui import QDesktopServices
        theme = self._select_html_export_theme()
        if theme is None:
            return

        default_path = self.report_file_manager.get_report_path(self.current_project).with_suffix(".html")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "HTML-Report exportieren", str(default_path), "HTML (*.html)"
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".html":
            target = target.with_suffix(".html")

        proj_dir = self.report_file_manager.project_manager.get_project_dir(self.current_project)
        success = HtmlReportExporter.export_to_file(
            markdown_content=self.editor.toPlainText(),
            output_path=target,
            project_dir=proj_dir,
            project_name=self.current_project,
            target_ip="",
            theme=theme,
            report_font=self._report_font_key()
        )
        if success:
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("HTML-Report exportiert")
            msg.setText(f"HTML-Report gespeichert:\n{target.name}\n\nIm Standard-Browser öffnen?")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            msg.setStyleSheet(CYBER_DARK_QSS)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))
        else:
            logger.error(f"Export des HTML-Reports nach {target} fehlgeschlagen")
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Fehler")
            msg.setText(f"Export fehlgeschlagen: Die Datei '{target.name}' konnte nicht gespeichert werden.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()

    def _on_export_obsidian_clicked(self) -> None:
        """Exports the current editor state without coupling core export to Qt."""
        from core.exporters import ExternalExportError, ObsidianExporter
        from PyQt6.QtGui import QDesktopServices

        if not self.current_project:
            return
        if self.config is None or not self.config.get("obsidian_vault_path", "").strip():
            msg = QMessageBox(self)
            msg.setWindowTitle(t("report.obsidian_not_configured_title", "Obsidian is not configured"))
            msg.setText(t("report.obsidian_not_configured", "Choose an existing Obsidian vault in Settings before exporting."))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
            return

        try:
            exporter = ObsidianExporter(
                self.config.get("obsidian_vault_path"),
                self.config.get("obsidian_export_folder", "CTF/SpectreHUD"),
            )
            project_dir = self.report_file_manager.project_manager.get_project_dir(self.current_project)
            project_state = self.report_file_manager.project_manager.load_project_state(self.current_project)
            result = exporter.export_report(
                project_name=self.current_project,
                project_dir=project_dir,
                markdown=self.editor.toPlainText(),
                project_state=project_state,
                overwrite="copy",
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            logger.error("Obsidian report export failed: %s", exc, exc_info=True)
            msg = QMessageBox(self)
            msg.setWindowTitle(t("report.obsidian_export_failed_title", "Obsidian export failed"))
            msg.setText(t("report.obsidian_export_failed", "The report could not be exported to Obsidian:\n{error}", error=str(exc)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
            return

        message = t("report.obsidian_exported", "Exported to Obsidian:\n{path}", path=str(result.note_path))
        if result.warnings:
            message += "\n\n" + t("report.obsidian_attachment_warning", "Some attachments could not be copied.")
        msg = QMessageBox(self)
        msg.setWindowTitle(t("report.obsidian_exported_title", "Obsidian export complete"))
        msg.setText(message)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStyleSheet(CYBER_DARK_QSS)
        msg.exec()

        if self.config.get("obsidian_open_after_export", False):
            if not QDesktopServices.openUrl(QUrl(result.obsidian_uri)):
                logger.warning("Obsidian could not open export URI: %s", result.obsidian_uri)

    def _on_export_cherrytree_clicked(self) -> None:
        """Creates a portable HTML package; no CherryTree database is touched."""
        from core.exporters import CherryTreeExporter, ExternalExportError

        if not self.current_project:
            return
        project_dir = self.report_file_manager.project_manager.get_project_dir(self.current_project)
        default_directory = project_dir / "exports"
        destination = QFileDialog.getExistingDirectory(
            self,
            t("report.cherrytree_directory_title", "Choose CherryTree export directory"),
            str(default_directory if default_directory.exists() else project_dir),
        )
        if not destination:
            return
        try:
            result = CherryTreeExporter(destination).export_package(
                project_name=self.current_project,
                project_dir=project_dir,
                report_markdown=self.editor.toPlainText(),
                loot_entries=self.loot_manager.get_all_entries(),
                report_font=self._report_font_key(),
            )
        except (ExternalExportError, OSError, RuntimeError) as exc:
            logger.error("CherryTree package export failed: %s", exc, exc_info=True)
            QMessageBox.warning(
                self,
                t("report.cherrytree_export_failed_title", "CherryTree export failed"),
                t("report.cherrytree_export_failed", "The CherryTree package could not be created:\n{error}", error=str(exc)),
            )
            return

        message = t("report.cherrytree_exported", "CherryTree HTML package created:\n{path}", path=str(result.note_path.parent))
        if result.warnings:
            message += "\n\n" + t("report.cherrytree_attachment_warning", "Some images could not be copied.")
        QMessageBox.information(
            self,
            t("report.cherrytree_exported_title", "CherryTree package complete"),
            message,
        )

    def _select_html_export_theme(self) -> Optional[str]:
        """Asks which visual design the standalone HTML report should use."""
        msg = QMessageBox(self.window() if self else None)
        msg.setWindowTitle(t("report.html_theme_title", "Choose HTML Design"))
        msg.setText(t("report.html_theme_message", "Which design should the HTML report use?"))
        msg.setInformativeText(t("report.html_theme_hint", "Light is especially suitable for clients and printouts."))
        msg.setIcon(QMessageBox.Icon.Question)
        dark_button = msg.addButton(t("report.html_theme_dark", "Dark — SpectreHUD"), QMessageBox.ButtonRole.AcceptRole)
        light_button = msg.addButton(t("report.html_theme_light", "Light — Client / Print"), QMessageBox.ButtonRole.ActionRole)
        cancel_button = msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(dark_button)
        msg.setStyleSheet(CYBER_DARK_QSS)
        # QMessageBox otherwise calculates its width from the text labels and
        # can elide the two longer theme choices on Windows.
        msg.setMinimumWidth(640)
        dark_button.setMinimumWidth(190)
        light_button.setMinimumWidth(190)
        cancel_button.setMinimumWidth(100)
        msg.exec()

        if msg.clickedButton() is dark_button:
            return "dark"
        if msg.clickedButton() is light_button:
            return "light"
        return None

    # ------------------------------------------------------------------ #
    # Vorschau & Status
    # ------------------------------------------------------------------ #

    def _update_preview(self) -> None:
        if self.current_project:
            proj_dir = self.report_file_manager.project_manager.get_project_dir(self.current_project)
            self.preview_document.set_project_dir(proj_dir)
        self.preview.setMarkdown(self.editor.toPlainText())

    def _update_status_label(self) -> None:
        if not self.current_project:
            self.lbl_status.setText("")
            return
        marker = "● Ungespeicherte Änderungen" if self._dirty else "✓ Gespeichert"
        mode_label = {
            ViewMode.EDITOR: "Editor",
            ViewMode.SPLIT: "Split",
            ViewMode.PREVIEW: "Live-Ansicht"
        }.get(self._view_mode, "Split")
        self.lbl_status.setText(f"{self.current_project} — {marker} · [{mode_label}]")
