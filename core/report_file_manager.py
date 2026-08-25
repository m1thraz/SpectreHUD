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


class ReportBackupError(RuntimeError):
    """Raised when backing up report.md fails before an operation that would overwrite it."""
    pass


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
        """Speichert den Inhalt atomar in die report.md des Projekts."""
        from core.atomic_write import atomic_write_text
        path = self.get_report_path(project_name)
        try:
            return atomic_write_text(path, content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Fehler beim Speichern von {path}: {e}", exc_info=True)
            return False

    def backup(self, project_name: Optional[str] = None) -> bool:
        """Kopiert report.md atomar zu report.md.bak, falls report.md existiert."""
        from core.atomic_write import atomic_write_text
        report_path = self.get_report_path(project_name)
        backup_path = self.get_backup_path(project_name)
        if not report_path.exists():
            return False
        try:
            content = report_path.read_text(encoding="utf-8")
            return atomic_write_text(backup_path, content, encoding="utf-8")
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
        Sichert den aktuellen Stand (falls vorhanden) als report.md.bak.
        Fail-Closed: Schlägt das Backup fehl, wird ReportBackupError geworfen
        und die bestehende report.md keinesfalls überschrieben.
        """
        pname = self._resolve_project_name(project_name)
        if self.exists(pname):
            if not self.backup(pname):
                logger.error(f"Automatisches Backup von report.md für {pname} fehlgeschlagen. Abbruch der Regenerierung zum Schutz von Benutzerdaten.")
                raise ReportBackupError(f"Automatisches Backup von report.md für Projekt '{pname}' fehlgeschlagen.")

        builder = ReportBuilder(
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=self.project_manager
        )
        content = builder.build(project_name=pname)
        self.save(content, project_name=pname)
        return content
