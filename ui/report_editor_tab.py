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
    QTextEdit, QPushButton, QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QTextDocument, QImage

from core.report_file_manager import ReportFileManager
from core.reporting.template_engine import ReportTemplate
from core.reporting.template_repository import TemplateRepository
from ui.template_manager_dialog import TemplateManagerDialog
from core.logger import get_logger
from ui.styles import CYBER_DARK_QSS

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300


MAX_PREVIEW_IMAGE_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB


class ViewMode(Enum):
    EDITOR = "editor"
    SPLIT = "split"
    PREVIEW = "preview"


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


class ReportEditorTab(QWidget):
    """Editierbarer Markdown-Report mit Live-Vorschau für das aktive Projekt."""

    # Für main_window: signalisiert, ob ungespeicherte Änderungen vorliegen
    dirty_changed = pyqtSignal(bool)

    def __init__(self, report_file_manager: ReportFileManager, loot_manager, clipboard_watcher,
                 parent: QWidget = None):
        super().__init__(parent)
        self.report_file_manager = report_file_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
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

        self._build_ui()
        self._populate_templates()

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
        toolbar.addWidget(self.lbl_status)
        toolbar.addStretch()

        # View Mode Switch Buttons
        self.btn_mode_editor = QPushButton("📝 Editor")
        self.btn_mode_editor.setProperty("class", "SecondaryBtn")
        self.btn_mode_editor.setToolTip("Nur Markdown-Quelltext anzeigen (Strg+1)")
        self.btn_mode_editor.clicked.connect(lambda: self._set_view_mode(ViewMode.EDITOR))
        toolbar.addWidget(self.btn_mode_editor)

        self.btn_mode_split = QPushButton("◫ Split")
        self.btn_mode_split.setProperty("class", "SecondaryBtn")
        self.btn_mode_split.setToolTip("Geteilte Ansicht: Editor & Vorschau nebeneinander (Strg+2)")
        self.btn_mode_split.clicked.connect(lambda: self._set_view_mode(ViewMode.SPLIT))
        toolbar.addWidget(self.btn_mode_split)

        self.btn_mode_preview = QPushButton("👁️ Live-Ansicht")
        self.btn_mode_preview.setProperty("class", "SecondaryBtn")
        self.btn_mode_preview.setToolTip("Editierbare Live-Ansicht im Vollbild (Strg+3)")
        self.btn_mode_preview.clicked.connect(lambda: self._set_view_mode(ViewMode.PREVIEW))
        toolbar.addWidget(self.btn_mode_preview)

        # Template Selector Dropdown & Manager Button
        from PyQt6.QtWidgets import QComboBox
        self.combo_templates = QComboBox()
        self.combo_templates.setToolTip("Wähle das Report-Template für die Regenerierung aus")
        self.combo_templates.currentIndexChanged.connect(self._on_template_combo_changed)
        toolbar.addWidget(self.combo_templates)

        self.btn_manage_templates = QPushButton("🎨 Templates...")
        self.btn_manage_templates.setProperty("class", "SecondaryBtn")
        self.btn_manage_templates.setToolTip("Report-Templates verwalten, anpassen oder neue erstellen")
        self.btn_manage_templates.clicked.connect(self._open_template_manager)
        toolbar.addWidget(self.btn_manage_templates)

        self.btn_regenerate = QPushButton("Regenerate from Loot")
        self.btn_regenerate.setProperty("class", "SecondaryBtn")
        self.btn_regenerate.setToolTip(
            "Ersetzt den Report-Text durch eine frische Generierung aus Loot "
            "und Clipboard-Verlauf basierend auf dem gewählten Template. "
            "Der bisherige Stand wird vorher als report.md.bak gesichert."
        )
        self.btn_regenerate.clicked.connect(self._on_regenerate_clicked)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_export_copy = QPushButton("Export Copy...")
        self.btn_export_copy.setProperty("class", "SecondaryBtn")
        self.btn_export_copy.setToolTip("Speichert eine Kopie des aktuellen Report-Texts an einem beliebigen Ort.")
        self.btn_export_copy.clicked.connect(self._on_export_copy_clicked)
        toolbar.addWidget(self.btn_export_copy)

        self.btn_export_html = QPushButton("Export HTML...")
        self.btn_export_html.setProperty("class", "SecondaryBtn")
        self.btn_export_html.setToolTip("Exportiert den Report als eigenständige HTML-Datei mit Cyber-Dark Theme und eingebetteten Screenshots.")
        self.btn_export_html.clicked.connect(self._on_export_html_clicked)
        toolbar.addWidget(self.btn_export_html)

        self.btn_save = QPushButton("Save")
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.setToolTip("Speichert die Änderungen in die projekt-lokale report.md (Strg+S)")
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)

        layout.addLayout(toolbar)

        # --- Editor | Vorschau ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Noch kein Report für dieses Projekt vorhanden.\n\n"
            "Klicke oben auf 'Regenerate from Loot', um mit dem "
            "automatisch zusammengestellten Report zu starten - oder "
            "schreib direkt hier los."
        )
        self.editor.setProperty("class", "ReportSourceEditor")
        self.editor.textChanged.connect(self._on_text_changed)
        self.splitter.addWidget(self.editor)

        self.preview_document = ReportDocument(parent=self)
        
        # Crisp typography for Markdown live preview
        preview_font = QFont("Segoe UI", 10)
        preview_font.setStyleHint(QFont.StyleHint.SansSerif)
        self.preview_document.setDefaultFont(preview_font)
        self.preview_document.setDefaultStyleSheet("""
            body { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', 'Roboto', 'Helvetica Neue', Arial, sans-serif; font-size: 13px; color: #f0f6fc; line-height: 1.6; }
            h1, h2, h3, h4, h5, h6 { color: #58a6ff; font-family: 'Segoe UI', sans-serif; font-weight: 600; margin-top: 14px; margin-bottom: 6px; }
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
        """)

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

        self._apply_view_mode(self._view_mode)

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
        msg.setWindowTitle("Ungespeicherte Änderungen")
        msg.setText(
            "Der Report wurde bearbeitet, aber noch nicht gespeichert.\n\n"
            "Änderungen jetzt speichern?"
        )
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
            msg.setWindowTitle("Fehler")
            msg.setText("Report konnte nicht gespeichert werden. Details im Log.")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(CYBER_DARK_QSS)
            msg.exec()
        return ok

    def _on_regenerate_clicked(self) -> None:
        if not self.current_project:
            return

        has_existing = self.report_file_manager.exists(self.current_project) or self._dirty
        if has_existing:
            msg = QMessageBox(self.window() if self else None)
            msg.setWindowTitle("Report neu generieren")
            msg.setText(
                "Der aktuelle Report-Text wird durch eine frische Generierung "
                "aus Loot und Clipboard-Verlauf ERSETZT.\n\n"
                "Der bisherige Stand wird vorher als report.md.bak gesichert "
                "(überschreibt ein eventuell vorhandenes älteres Backup).\n\n"
                "Fortfahren?"
            )
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setStyleSheet(CYBER_DARK_QSS)

            if msg.exec() != QMessageBox.StandardButton.Yes:
                return

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

    def _populate_templates(self) -> None:
        """Loads all available templates into the toolbar combo box."""
        if not hasattr(self, "combo_templates"):
            return
        self.combo_templates.blockSignals(True)
        self.combo_templates.clear()
        all_templates = self.template_repo.get_all_templates()
        for t in all_templates:
            self.combo_templates.addItem(f"{t.name} [{t.language.upper()}]", t.id)

        if self.active_template:
            idx = self.combo_templates.findData(self.active_template.id)
            if idx >= 0:
                self.combo_templates.setCurrentIndex(idx)
        elif all_templates:
            self.active_template = all_templates[0]
            self.combo_templates.setCurrentIndex(0)

        self.combo_templates.blockSignals(False)

    def _on_template_combo_changed(self) -> None:
        """Handles selection of a template from the toolbar combo box."""
        tid = self.combo_templates.currentData()
        if tid:
            self.active_template = self.template_repo.get_template(tid)

    def _open_template_manager(self) -> None:
        """Opens the template management dialog."""
        from PyQt6.QtWidgets import QDialog
        dlg = TemplateManagerDialog(repository=self.template_repo, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_template:
            self.active_template = dlg.selected_template
            self._populate_templates()
            idx = self.combo_templates.findData(self.active_template.id)
            if idx >= 0:
                self.combo_templates.setCurrentIndex(idx)
        else:
            self._populate_templates()

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
            target_ip=""
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
