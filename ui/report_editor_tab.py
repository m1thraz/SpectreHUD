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
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPlainTextEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QFileDialog
)

from core.report_file_manager import ReportFileManager
from core.logger import get_logger

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300


class ReportEditorTab(QWidget):
    """Editierbarer Markdown-Report mit Live-Vorschau für das aktive Projekt."""

    # Für main_window: signalisiert, ob ungespeicherte Änderungen vorliegen
    # (z.B. um beim Moduswechsel/Schließen nachzufragen).
    dirty_changed = pyqtSignal(bool)

    def __init__(self, report_file_manager: ReportFileManager, loot_manager, clipboard_watcher,
                 parent: QWidget = None):
        super().__init__(parent)
        self.report_file_manager = report_file_manager
        self.loot_manager = loot_manager
        self.clipboard_watcher = clipboard_watcher
        self.current_project: Optional[str] = None
        self._dirty = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._build_ui()

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

        self.btn_regenerate = QPushButton("🔄 Neu aus Loot generieren")
        self.btn_regenerate.setProperty("class", "SecondaryBtn")
        self.btn_regenerate.setToolTip(
            "Ersetzt den Report-Text durch eine frische Generierung aus Loot "
            "und Clipboard-Verlauf. Der bisherige Stand wird vorher als "
            "report.md.bak gesichert."
        )
        self.btn_regenerate.clicked.connect(self._on_regenerate_clicked)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_export_copy = QPushButton("📤 Exportieren als...")
        self.btn_export_copy.setProperty("class", "SecondaryBtn")
        self.btn_export_copy.setToolTip("Speichert eine Kopie des aktuellen Report-Texts an einem beliebigen Ort.")
        self.btn_export_copy.clicked.connect(self._on_export_copy_clicked)
        toolbar.addWidget(self.btn_export_copy)

        self.btn_save = QPushButton("💾 Speichern")
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.setToolTip("Speichert die Änderungen in die projekt-lokale report.md (Strg+S)")
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)

        layout.addLayout(toolbar)

        # --- Editor | Vorschau ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Noch kein Report für dieses Projekt vorhanden.\n\n"
            "Klicke oben auf '🔄 Neu aus Loot generieren', um mit dem "
            "automatisch zusammengestellten Report zu starten - oder "
            "schreib direkt hier los."
        )
        self.editor.setProperty("class", "ReportSourceEditor")
        self.editor.textChanged.connect(self._on_text_changed)
        splitter.addWidget(self.editor)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setProperty("class", "ReportPreview")
        splitter.addWidget(self.preview)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        # Strg+S zum Speichern, unabhängig vom Fokus innerhalb des Tabs
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)

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

        reply = QMessageBox.question(
            self, "Ungespeicherte Änderungen",
            "Der Report wurde bearbeitet, aber noch nicht gespeichert.\n\n"
            "Änderungen jetzt speichern?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
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

    # ------------------------------------------------------------------ #
    # Aktionen
    # ------------------------------------------------------------------ #

    def save(self) -> bool:
        if not self.current_project:
            return False
        ok = self.report_file_manager.save(self.editor.toPlainText(), project_name=self.current_project)
        if ok:
            self._set_dirty(False)
        else:
            QMessageBox.warning(self, "Fehler", "Report konnte nicht gespeichert werden. Details im Log.")
        return ok

    def _on_regenerate_clicked(self) -> None:
        if not self.current_project:
            return

        has_existing = self.report_file_manager.exists(self.current_project) or self._dirty
        if has_existing:
            reply = QMessageBox.question(
                self, "Report neu generieren",
                "Der aktuelle Report-Text wird durch eine frische Generierung "
                "aus Loot und Clipboard-Verlauf ERSETZT.\n\n"
                "Der bisherige Stand wird vorher als report.md.bak gesichert "
                "(überschreibt ein eventuell vorhandenes älteres Backup).\n\n"
                "Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        new_content = self.report_file_manager.regenerate(
            self.loot_manager, self.clipboard_watcher, project_name=self.current_project
        )
        self.editor.blockSignals(True)
        self.editor.setPlainText(new_content)
        self.editor.blockSignals(False)
        self._set_dirty(False)  # regenerate() hat bereits gespeichert
        self._update_preview()

    def _on_export_copy_clicked(self) -> None:
        default_path = self.report_file_manager.get_report_path(self.current_project)
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Report-Kopie exportieren", str(default_path), "Markdown (*.md)"
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(self.editor.toPlainText(), encoding="utf-8")
            QMessageBox.information(self, "Exportiert", f"Kopie gespeichert: {Path(file_path).name}")
        except OSError as e:
            logger.error(f"Export der Report-Kopie fehlgeschlagen: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Export fehlgeschlagen: {e}")

    # ------------------------------------------------------------------ #
    # Vorschau
    # ------------------------------------------------------------------ #

    def _update_preview(self) -> None:
        self.preview.setMarkdown(self.editor.toPlainText())

    def _update_status_label(self) -> None:
        if not self.current_project:
            self.lbl_status.setText("")
            return
        marker = "● Ungespeicherte Änderungen" if self._dirty else "✓ Gespeichert"
        self.lbl_status.setText(f"{self.current_project} — {marker}")
