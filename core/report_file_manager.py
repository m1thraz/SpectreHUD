"""
Dateiverwaltung für den editierbaren Markdown-Report je Projekt.

Verwaltet die projekt-lokale report.md und deren Backup report.md.bak.
Nutzt denselben Pfad (proj_dir / "report.md"), den auch der Export
standardmäßig verwendet.
"""
from pathlib import Path
from typing import Optional

from core.report_builder import ReportBuilder
from core.logger import get_logger

logger = get_logger("report_file_manager")


class ReportFileManager:
    """Verwaltet das Laden, Speichern und Sichern der projekt-lokalen report.md."""

    def __init__(self, project_manager):
        self.project_manager = project_manager

    def _resolve_project_name(self, project_name: Optional[str]) -> str:
        if project_name:
            return project_name
        return self.project_manager.get_active_project()

    def get_report_path(self, project_name: Optional[str] = None) -> Path:
        pname = self._resolve_project_name(project_name)
        proj_dir = self.project_manager.get_project_dir(pname)
        return proj_dir / "report.md"

    def get_backup_path(self, project_name: Optional[str] = None) -> Path:
        pname = self._resolve_project_name(project_name)
        proj_dir = self.project_manager.get_project_dir(pname)
        return proj_dir / "report.md.bak"

    def exists(self, project_name: Optional[str] = None) -> bool:
        path = self.get_report_path(project_name)
        return path.exists() and path.is_file()

    def load(self, project_name: Optional[str] = None) -> str:
        """Lädt den Inhalt der report.md. Gibt leeren String zurück, falls nicht vorhanden."""
        path = self.get_report_path(project_name)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error(f"Fehler beim Laden von {path}: {e}", exc_info=True)
            return ""

    def save(self, content: str, project_name: Optional[str] = None) -> bool:
        """Speichert den Inhalt in die report.md des Projekts."""
        path = self.get_report_path(project_name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return True
        except OSError as e:
            logger.error(f"Fehler beim Speichern von {path}: {e}", exc_info=True)
            return False

    def backup(self, project_name: Optional[str] = None) -> bool:
        """Kopiert report.md zu report.md.bak, falls report.md existiert."""
        report_path = self.get_report_path(project_name)
        backup_path = self.get_backup_path(project_name)
        if not report_path.exists():
            return False
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
            return True
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Backups {backup_path}: {e}", exc_info=True)
            return False

    def restore_backup(self, project_name: Optional[str] = None) -> bool:
        """Stellt report.md aus report.md.bak wieder her, falls das Backup existiert."""
        backup_path = self.get_backup_path(project_name)
        if not backup_path.exists():
            return False
        try:
            content = backup_path.read_text(encoding="utf-8")
            return self.save(content, project_name)
        except OSError as e:
            logger.error(f"Fehler beim Wiederherstellen des Backups {backup_path}: {e}", exc_info=True)
            return False

    def regenerate(self, loot_manager, clipboard_watcher, project_name: Optional[str] = None) -> str:
        """
        Sichert den aktuellen Stand (falls vorhanden) als report.md.bak,
        generiert einen frischen Report via ReportBuilder, speichert ihn in
        die report.md und gibt den generierten Inhalt zurück.
        """
        pname = self._resolve_project_name(project_name)
        if self.exists(pname):
            self.backup(pname)

        builder = ReportBuilder(
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=self.project_manager
        )
        content = builder.build(project_name=pname)
        self.save(content, project_name=pname)
        return content
