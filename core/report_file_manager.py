"""
Dateiverwaltung für den editierbaren Markdown-Report je Projekt.

Verwaltet die projekt-lokale report.md und deren Backup report.md.bak.
Nutzt denselben Pfad (proj_dir / "report.md"), den auch der Export
standardmäßig verwendet.
"""

from pathlib import Path
from typing import Optional, Any

from core.report_builder import ReportBuilder
from core.logger import get_logger

logger = get_logger("report_file_manager")


class ReportBackupError(RuntimeError):
    """Raised when backing up report.md fails before an operation that would overwrite it."""

    pass


class ReportSaveError(RuntimeError):
    """Raised when saving the newly generated report.md to disk fails."""

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

    def _read_report_checked(self, path: Path) -> Optional[str]:
        """Reads text from path with strict size limit verification and exception handling."""
        from core.validators import is_file_size_valid, MAX_REPORT_FILE_SIZE

        if not path.exists() or not path.is_file():
            return None
        if not is_file_size_valid(path, MAX_REPORT_FILE_SIZE):
            logger.error(
                f"Report file {path} exceeds maximum size limit of {MAX_REPORT_FILE_SIZE} bytes. Rejecting oversized file."
            )
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error(f"Error reading report file {path}: {e}", exc_info=True)
            return None

    def load(self, project_name: Optional[str] = None) -> str:
        """Lädt den Inhalt der report.md. Gibt leeren String zurück, falls nicht vorhanden oder ungültig."""
        path = self.get_report_path(project_name)
        content = self._read_report_checked(path)
        return content if content is not None else ""

    def save(self, content: str, project_name: Optional[str] = None) -> bool:
        """Saves only report content that can subsequently be loaded safely."""
        from core.atomic_write import atomic_write_text
        from core.validators import MAX_REPORT_FILE_SIZE

        path = self.get_report_path(project_name)
        try:
            encoded_content = content.encode("utf-8")
        except UnicodeEncodeError as exc:
            logger.error("Report content for %s cannot be encoded as UTF-8: %s", path, exc)
            return False

        if len(encoded_content) > MAX_REPORT_FILE_SIZE:
            logger.error(
                "Refusing to save oversized report %s (%d bytes; maximum %d bytes).",
                path,
                len(encoded_content),
                MAX_REPORT_FILE_SIZE,
            )
            return False
        try:
            return atomic_write_text(path, content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Fehler beim Speichern von {path}: {e}", exc_info=True)
            return False

    def backup(self, project_name: Optional[str] = None) -> bool:
        """Kopiert report.md atomar zu report.md.bak, falls report.md existiert und Größenlimits einhält."""
        from core.atomic_write import atomic_write_text

        report_path = self.get_report_path(project_name)
        backup_path = self.get_backup_path(project_name)
        content = self._read_report_checked(report_path)
        if content is None:
            return False
        try:
            return atomic_write_text(backup_path, content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Backups {backup_path}: {e}", exc_info=True)
            return False

    def restore_backup(self, project_name: Optional[str] = None) -> bool:
        """Stellt report.md aus report.md.bak wieder her, falls das Backup existiert und Größenlimits einhält."""
        backup_path = self.get_backup_path(project_name)
        content = self._read_report_checked(backup_path)
        if content is None:
            return False
        return self.save(content, project_name)

    def regenerate(
        self,
        loot_manager,
        clipboard_watcher,
        project_name: Optional[str] = None,
        template: Optional[Any] = None,
    ) -> str:
        """
        Sichert den aktuellen Stand (falls vorhanden) als report.md.bak.
        Fail-Closed: Schlägt das Backup fehl, wird ReportBackupError geworfen
        und die bestehende report.md keinesfalls überschrieben.
        """
        pname = self._resolve_project_name(project_name)
        if self.exists(pname):
            if not self.backup(pname):
                logger.error(
                    f"Automatisches Backup von report.md für {pname} fehlgeschlagen. Abbruch der Regenerierung zum Schutz von Benutzerdaten."
                )
                raise ReportBackupError(
                    f"Automatisches Backup von report.md für Projekt '{pname}' fehlgeschlagen."
                )

        builder = ReportBuilder(
            loot_manager=loot_manager,
            clipboard_watcher=clipboard_watcher,
            project_manager=self.project_manager,
        )
        content = builder.build(project_name=pname, template=template)
        if not self.save(content, project_name=pname):
            logger.error(f"Speichern des regenerierten Reports für {pname} fehlgeschlagen.")
            raise ReportSaveError(
                f"Speichern des regenerierten Reports für Projekt '{pname}' fehlgeschlagen."
            )
        return content
