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
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QFileDialog,
    QDialog,
    QMenu,
)
from PyQt6.QtGui import QAction, QFont, QShortcut, QKeySequence

from core.report_file_manager import ReportFileManager
from core.config import ConfigManager
from core.reporting.template_engine import ReportTemplate
from core.reporting.template_repository import TemplateRepository
from ui.coordinators.export_coordinator import ExportCoordinator, ReportExportError
from core.logger import get_logger
from core.i18n import t
from core.fonts import get_report_font_stack
from core.platform.opener import open_path
from ui.report.dialogs import MarkdownTableDialog, ReportGenerationDialog
from ui.report.find_replace import FindReplaceBar
from ui.report.preview import ReportDocument, ReportPreviewEdit
from ui.report.toolbar import build_format_toolbar

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300
AUTOSAVE_INTERVAL_MS = 45_000


class ViewMode(Enum):
    EDITOR = "editor"
    SPLIT = "split"
    PREVIEW = "preview"


class ReportEditorTab(QWidget):
    """Editierbarer Markdown-Report mit Live-Vorschau für das aktive Projekt."""

    # Für main_window: signalisiert, ob ungespeicherte Änderungen vorliegen
    dirty_changed = pyqtSignal(bool)

    def __init__(
        self,
        report_file_manager: ReportFileManager,
        loot_manager,
        clipboard_watcher,
        parent: QWidget = None,
        config_manager: Optional[ConfigManager] = None,
        export_coordinator: Optional[ExportCoordinator] = None,
    ):
        super().__init__(parent)
        self.report_file_manager = report_file_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.config = config_manager
        self.export_coordinator = export_coordinator
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

        layout.addLayout(self._build_action_toolbar())

        status_row = QHBoxLayout()
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        layout.addLayout(status_row)

        self._build_editor_splitter(layout)
        self._setup_shortcuts()
        self._apply_view_mode(self._view_mode)

    def _build_action_toolbar(self) -> QHBoxLayout:
        """Build the report actions without introducing a widget factory."""
        toolbar = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("class", "ReportStatusLabel")

        # Compact view selector; shortcuts remain available for power users.
        self.btn_change_view = QPushButton(t("report.change_view", "Change View"))
        self.btn_change_view.setProperty("class", "SecondaryBtn")
        self.btn_change_view.setToolTip(t("report.change_view_tip", "Choose report editor layout"))
        self._build_view_menu()
        toolbar.addWidget(self.btn_change_view)

        self.btn_regenerate = QPushButton(t("report.regenerate", "Regenerate from Loot"))
        self.btn_regenerate.setProperty("class", "SecondaryBtn")
        self.btn_regenerate.setToolTip(
            t("report.regenerate_tip", "Updates report structure and appends new loot entries")
        )
        self.btn_regenerate.clicked.connect(self._on_regenerate_clicked)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_append_loot = QPushButton(t("report.append_loot", "Add Missing Loot"))
        self.btn_append_loot.setProperty("class", "SecondaryBtn")
        self.btn_append_loot.setToolTip(
            t(
                "report.append_loot_tip",
                "Appends missing loot entries to the report without overwriting manual notes",
            )
        )
        self.btn_append_loot.clicked.connect(self._on_append_loot_clicked)
        toolbar.addWidget(self.btn_append_loot)

        self.btn_export = QPushButton(t("report.export", "Export..."))
        self.btn_export.setProperty("class", "SecondaryBtn")
        self.btn_export.setToolTip(
            t("report.export_tip", "Choose how to export the current report")
        )
        self.btn_export.clicked.connect(self._on_export_clicked)
        toolbar.addWidget(self.btn_export)

        # Formatting belongs with the primary editing/export actions. The
        # source-only controls are hidden while the rich preview is active.
        self.format_toolbar_widget = build_format_toolbar(
            self,
            {
                "heading_1": lambda: self._format_heading(1),
                "heading_2": lambda: self._format_heading(2),
                "heading_3": lambda: self._format_heading(3),
                "heading_4": lambda: self._format_heading(4),
                "heading_5": lambda: self._format_heading(5),
                "heading_6": lambda: self._format_heading(6),
                "bold": lambda: self._format_wrap("**", "**"),
                "italic": lambda: self._format_wrap("*", "*"),
                "strikethrough": lambda: self._format_wrap("~~", "~~"),
                "code": lambda: self._format_wrap("`", "`"),
                "code_block": self._format_code_block,
                "list": lambda: self._format_list(False),
                "numbered_list": lambda: self._format_list(True),
                "quote": self._format_quote,
                "horizontal_rule": self._format_horizontal_rule,
                "link": self._format_link,
                "table": self._format_table,
            },
        )
        toolbar.addWidget(self.format_toolbar_widget)

        self.btn_save = QPushButton(t("report.save", "Save"))
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.setToolTip(
            t("report.save_tip", "Save changes to active box report.md (Ctrl+S)")
        )
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)
        return toolbar

    def _build_view_menu(self) -> None:
        """Populate the compact view selector."""
        self.view_menu = QMenu(self.btn_change_view)
        self._view_actions = {}
        for mode, key, fallback in (
            (ViewMode.EDITOR, "report.mode_editor", "📝 Editor"),
            (ViewMode.SPLIT, "report.mode_split", "◫ Split"),
            (ViewMode.PREVIEW, "report.mode_preview", "👁️ Live Preview"),
        ):
            action = QAction(t(key, fallback), self.view_menu)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self._set_view_mode(selected)
            )
            self.view_menu.addAction(action)
            self._view_actions[mode] = action
        self.btn_change_view.setMenu(self.view_menu)

    def _build_editor_splitter(self, layout: QVBoxLayout) -> None:
        """Build the Markdown editor, find bar, and live preview splitter."""
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            t(
                "report.editor_placeholder",
                "No report available for this project yet.\n\n"
                "Click 'Regenerate from Loot' above to start with an "
                "auto-generated report, or write your markdown directly here.",
            )
        )
        self.editor.setProperty("class", "ReportSourceEditor")
        self.editor.textChanged.connect(self._on_text_changed)
        from ui.markdown_highlighter import MarkdownHighlighter

        self._highlighter = MarkdownHighlighter(self.editor.document())
        self.find_replace = FindReplaceBar(self.editor, self)
        layout.addWidget(self.find_replace)
        self.splitter.addWidget(self.editor)

        self.preview_document = ReportDocument(parent=self)
        self._apply_preview_font()

        self.preview = ReportPreviewEdit()
        self.preview.setDocument(self.preview_document)
        self.preview.setReadOnly(True)
        self.preview.setProperty("class", "ReportPreview")
        self.splitter.addWidget(self.preview)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, stretch=1)

    def _setup_shortcuts(self) -> None:
        """Register report editing and view-mode shortcuts."""
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        sc_save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_save_shift = QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save)
        sc_save_shift.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_cycle = QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self._cycle_view_mode)
        sc_cycle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode1 = QShortcut(
            QKeySequence("Ctrl+1"), self, activated=lambda: self._set_view_mode(ViewMode.EDITOR)
        )
        sc_mode1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode2 = QShortcut(
            QKeySequence("Ctrl+2"), self, activated=lambda: self._set_view_mode(ViewMode.SPLIT)
        )
        sc_mode2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode3 = QShortcut(
            QKeySequence("Ctrl+3"), self, activated=lambda: self._set_view_mode(ViewMode.PREVIEW)
        )
        sc_mode3.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._shortcut_find = QShortcut(
            QKeySequence("Ctrl+F"), self.editor, activated=self.find_replace.open
        )
        self._shortcut_find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_find_close = QShortcut(
            QKeySequence("Esc"), self.find_replace, activated=self.find_replace.close_bar
        )
        self._shortcut_find_close.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for sequence, callback in (
            ("Ctrl+B", lambda: self._format_wrap("**", "**")),
            ("Ctrl+I", lambda: self._format_wrap("*", "*")),
            ("Ctrl+K", lambda: self._format_wrap("`", "`")),
            ("Ctrl+Shift+X", lambda: self._format_wrap("~~", "~~")),
            ("Ctrl+Shift+Q", self._format_quote),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.editor, activated=callback)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _format_heading(self, level: int) -> None:
        from ui.markdown_toolbar_actions import set_heading

        set_heading(self.editor, level)

    def _format_wrap(self, prefix: str, suffix: str) -> None:
        from ui.markdown_toolbar_actions import wrap_selection

        wrap_selection(self.editor, prefix, suffix)

    def _format_quote(self) -> None:
        from ui.markdown_toolbar_actions import insert_blockquote

        insert_blockquote(self.editor)

    def _format_horizontal_rule(self) -> None:
        from ui.markdown_toolbar_actions import insert_horizontal_rule

        insert_horizontal_rule(self.editor)

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

    def _report_font_key(self) -> str:
        return self.config.get("report_font", "segoe_ui") if self.config else "segoe_ui"

    def _apply_preview_font(self) -> None:
        """Apply the report font to the rich-text live preview."""
        report_font = get_report_font_stack(self._report_font_key())
        primary_font = report_font.split(",", 1)[0].strip().strip("'\"")
        preview_font = QFont(primary_font, 10)
        preview_font.setStyleHint(QFont.StyleHint.SansSerif)
        self.preview_document.setDefaultFont(preview_font)
        self.preview_document.setDefaultStyleSheet(
            """
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
        """.replace("__REPORT_FONT_STACK__", report_font)
        )

    def refresh_font_configuration(self) -> None:
        """Refresh preview typography after settings are saved."""
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
        msg.setText(
            t("report.unsaved_prompt_message", "The report has unsaved changes.\n\nSave them now?")
        )
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)

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

    def _enter_preview_mode(self) -> None:
        """Enters editable live preview mode and takes a markdown baseline snapshot."""
        if self._preview_timer.isActive():
            self._preview_timer.stop()
        self._update_preview()
        self._preview_markdown_snapshot = self.editor.toPlainText()
        self.preview.setReadOnly(False)
        self.preview.setFocus()

    def _commit_preview_to_markdown(self) -> None:
        """Commits rich-text edits from the preview document back to the markdown editor."""
        from core.reporting.loot_sync import preserve_markers_in_preview_roundtrip

        raw_markdown = self.preview_document.toMarkdown()
        new_markdown = preserve_markers_in_preview_roundtrip(
            self._preview_markdown_snapshot or "", raw_markdown
        )
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
                QMessageBox.StandardButton.No,
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

        ok = self.report_file_manager.save(
            self.editor.toPlainText(), project_name=self.current_project
        )
        if ok:
            self._set_dirty(False)
        else:
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle(t("dialog.error", "Error"))
            msg.setText(
                t("report.save_error", "The report could not be saved. Details are in the log.")
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
        return ok

    def _autosave(self) -> None:
        """Persist a dirty report without interrupting the user on failures."""
        if not self.is_dirty() or not self.current_project:
            return
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
        try:
            ok = self.report_file_manager.save(
                self.editor.toPlainText(), project_name=self.current_project
            )
        except Exception:
            logger.exception("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(
                t("report.autosave_failed", "Autosave failed — please save manually")
            )
            return
        if ok:
            self._set_dirty(False)
        else:
            logger.error("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(
                t("report.autosave_failed", "Autosave failed — please save manually")
            )

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
                template=self.active_template,
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
            msg.exec()

    def _on_append_loot_clicked(self) -> None:
        """Appends unreferenced loot entries to existing report sections without rewriting user text."""
        if not self.current_project:
            return

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        # Ensure dirty changes are saved before performing additive sync
        if self._dirty:
            if not self.save():
                logger.error(
                    "Could not save pending report edits before appending loot for project '%s'",
                    self.current_project,
                )
                return

        from core.report_file_manager import ReportBackupError, ReportSaveError

        cursor = self.editor.textCursor()
        saved_pos = cursor.position()

        try:
            result = self.report_file_manager.append_missing_loot(
                self.loot_manager,
                project_name=self.current_project,
                template=self.active_template,
            )
        except ReportBackupError as exc:
            logger.error("Append missing loot aborted due to backup error: %s", exc)
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle(t("dialog.error", "Error"))
            msg.setText(
                "Das automatische Backup des bisherigen Reports ist fehlgeschlagen.\n\n"
                "Zum Schutz deiner bestehenden Notizen wurde das Ergänzen abgebrochen."
            )
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
            return
        except ReportSaveError as exc:
            logger.error("Append missing loot: save failed: %s", exc)
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle(t("dialog.error", "Error"))
            msg.setText(
                "Der ergänzte Report konnte nicht auf die Festplatte geschrieben werden.\n\n"
                "Der bisherige Report bleibt erhalten."
            )
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
            return

        if result.added_count == 0:
            self.lbl_status.setText(
                t("report.append_loot_no_changes", "No missing loot entries found")
            )
            return

        self.editor.blockSignals(True)
        self.editor.setPlainText(result.content)
        self.editor.blockSignals(False)
        self._set_dirty(False)
        self._update_preview()

        # Restore cursor position within bounds
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(min(saved_pos, len(result.content)))
        self.editor.setTextCursor(new_cursor)

        if result.used_fallback:
            self.lbl_status.setText(
                t(
                    "report.append_loot_success_fallback",
                    "{count} entries appended · {fallback_count} category(ies) under 'Neu aus Loot ergänzt'",
                    count=result.added_count,
                    fallback_count=len(result.fallback_categories),
                )
            )
        else:
            self.lbl_status.setText(
                t(
                    "report.append_loot_success",
                    "{count} new loot entries appended",
                    count=result.added_count,
                )
            )

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
        dialog = QDialog(self)
        dialog.setWindowTitle(t("report.export_dialog_title", "Export Report"))
        dialog.setMinimumWidth(320)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel(
            t("report.export_dialog_message", "Choose an export format for the current report.")
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addSpacing(4)

        choices = (
            ("markdown", t("report.export_copy", "Export Copy...")),
            ("html", t("report.export_html", "Export HTML...")),
            ("obsidian", t("report.export_obsidian", "Export to Obsidian...")),
            ("cherrytree", t("report.export_cherrytree", "Export CherryTree Package...")),
        )

        selected: list[Optional[str]] = [None]

        for export_type, label in choices:
            btn = QPushButton(label)
            btn.setMinimumHeight(32)
            btn.setProperty("class", "SecondaryBtn")
            # capture export_type via default arg to avoid late-binding closure issue
            btn.clicked.connect(
                lambda _checked=False, et=export_type: (
                    selected.__setitem__(0, et),
                    dialog.accept(),
                )
            )
            layout.addWidget(btn)

        layout.addSpacing(4)
        cancel_btn = QPushButton(t("dialog.cancel", "Cancel"))
        cancel_btn.setMinimumHeight(32)
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.exec()
        return selected[0]

    def _on_export_copy_clicked(self) -> None:
        default_path = self.report_file_manager.get_report_path(self.current_project)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Report-Kopie exportieren", str(default_path), "Markdown (*.md)"
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".md":
            target = target.with_suffix(".md")

        coordinator = self._require_export_coordinator()
        if coordinator is None:
            return
        try:
            coordinator.export_report_markdown(target, self.editor.toPlainText())
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Exportiert")
            msg.setText(f"Kopie gespeichert: {target.name}")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except ReportExportError as exc:
            logger.error("Export der Report-Kopie nach %s fehlgeschlagen: %s", target, exc)
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Fehler")
            msg.setText(
                f"Export fehlgeschlagen: Die Datei '{target.name}' konnte nicht gespeichert werden."
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def _on_export_html_clicked(self) -> None:
        theme = self._select_html_export_theme()
        if theme is None:
            return

        default_path = self.report_file_manager.get_report_path(self.current_project).with_suffix(
            ".html"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self, "HTML-Report exportieren", str(default_path), "HTML (*.html)"
        )
        if not file_path:
            return

        target = Path(file_path)
        if target.suffix.lower() != ".html":
            target = target.with_suffix(".html")

        coordinator = self._require_export_coordinator()
        if coordinator is None:
            return
        try:
            coordinator.export_report_html(
                target=target,
                project_name=self.current_project,
                markdown=self.editor.toPlainText(),
                theme=theme,
                report_font=self._report_font_key(),
            )
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("HTML-Report exportiert")
            msg.setText(f"HTML-Report gespeichert:\n{target.name}\n\nIm Standard-Browser öffnen?")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                if not open_path(target):
                    QMessageBox.warning(
                        self.window() if self else None,
                        t("report.open_html_error_title", "Report unavailable"),
                        t(
                            "report.open_html_error_message",
                            "The exported HTML report could not be opened:\n{path}",
                            path=str(target),
                        ),
                    )
        except ReportExportError as exc:
            logger.error("Export des HTML-Reports nach %s fehlgeschlagen: %s", target, exc)
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Fehler")
            msg.setText(
                f"Export fehlgeschlagen: Die Datei '{target.name}' konnte nicht gespeichert werden."
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def _on_export_obsidian_clicked(self) -> None:
        """Delegate the current editor document to the shared export coordinator."""
        if not self.current_project:
            return
        coordinator = self._require_export_coordinator()
        if coordinator is None:
            return
        coordinator.export_report_to_obsidian(
            self,
            self.current_project,
            self.editor.toPlainText(),
        )

    def _require_export_coordinator(self) -> Optional[ExportCoordinator]:
        """Return the application export boundary or show a controlled error."""
        if self.export_coordinator is None:
            logger.error("Obsidian report export requested without a configured handler.")
            QMessageBox.warning(
                self,
                t("report.obsidian_export_failed_title", "Obsidian export failed"),
                t(
                    "report.obsidian_export_unavailable",
                    "The Obsidian export service is unavailable.",
                ),
            )
            return None
        return self.export_coordinator

    def _on_export_cherrytree_clicked(self) -> None:
        """Creates a portable HTML package; no CherryTree database is touched."""
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
        coordinator = self._require_export_coordinator()
        if coordinator is None:
            return
        try:
            result = coordinator.export_report_to_cherrytree(
                destination=Path(destination),
                project_name=self.current_project,
                markdown=self.editor.toPlainText(),
                report_font=self._report_font_key(),
            )
        except ReportExportError as exc:
            logger.error("CherryTree package export failed: %s", exc, exc_info=True)
            QMessageBox.warning(
                self,
                t("report.cherrytree_export_failed_title", "CherryTree export failed"),
                t(
                    "report.cherrytree_export_failed",
                    "The CherryTree package could not be created:\n{error}",
                    error=str(exc),
                ),
            )
            return

        message = t(
            "report.cherrytree_exported",
            "CherryTree HTML package created:\n{path}",
            path=str(result.note_path.parent),
        )
        if result.warnings:
            message += "\n\n" + t(
                "report.cherrytree_attachment_warning", "Some images could not be copied."
            )
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
        msg.setInformativeText(
            t("report.html_theme_hint", "Light is especially suitable for clients and printouts.")
        )
        msg.setIcon(QMessageBox.Icon.Question)
        dark_button = msg.addButton(
            t("report.html_theme_dark", "Dark — SpectreHUD"), QMessageBox.ButtonRole.AcceptRole
        )
        light_button = msg.addButton(
            t("report.html_theme_light", "Light — Client / Print"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_button = msg.addButton(QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(dark_button)
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
            proj_dir = self.report_file_manager.project_manager.get_project_dir(
                self.current_project
            )
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
            ViewMode.PREVIEW: "Live-Ansicht",
        }.get(self._view_mode, "Split")
        self.lbl_status.setText(f"{self.current_project} — {marker} · [{mode_label}]")
