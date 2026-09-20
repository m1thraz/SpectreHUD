"""
Dateiverwaltung für den editierbaren Markdown-Report je Projekt.

Verwaltet die projekt-lokale report.md und deren Backup report.md.bak.
Nutzt denselben Pfad (proj_dir / "report.md"), den auch der Export
standardmäßig verwendet.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import stat
from typing import Optional, Any, Tuple

from core.reporting.loot_sync import append_missing_loot_to_text
from core.reporting.loot_reconciliation import (
    LootReconciliationAction,
    LootReconciliationResult,
    LootReconciliationSelection,
    reconcile_loot_report,
)
from core.reporting.builder import ReportBuilder
from core.logger import get_logger

logger = get_logger("report_file_manager")


@dataclass(frozen=True)
class AppendMissingLootResult:
    """Result of append_missing_loot operation in ReportFileManager."""

    content: str
    added_count: int
    used_fallback: bool
    fallback_categories: Tuple[str, ...]


class ReportReadStatus(str, Enum):
    """Semantic outcome of reading a project report from disk."""

    NOT_FOUND = "not_found"
    LOADED = "loaded"
    READ_FAILED = "read_failed"


@dataclass(frozen=True)
class ReportReadResult:
    """Distinguishes an absent report from an unreadable report."""

    status: ReportReadStatus
    path: Path
    content: str = ""
    detail: str = ""


class ReportReadError(RuntimeError):
    """Raised when an existing report cannot safely be loaded."""

    def __init__(self, result: ReportReadResult):
        super().__init__(result.detail or f"Report could not be read: {result.path}")
        self.result = result


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

    def resolve_project_name(self, project_name: Optional[str]) -> str:
        if project_name:
            return project_name
        return self.project_manager.get_active_project()

    def _resolve_project_name(self, project_name: Optional[str]) -> str:
        return self.resolve_project_name(project_name)

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
        return self._read_report_checked(path).status is ReportReadStatus.LOADED

    def _read_report_checked(self, path: Path) -> ReportReadResult:
        """Read a bounded UTF-8 report without collapsing access failures into absence."""
        from core.validators import MAX_REPORT_FILE_SIZE

        try:
            file_stat = path.stat()
        except FileNotFoundError:
            return ReportReadResult(ReportReadStatus.NOT_FOUND, path)
        except OSError as exc:
            logger.error("Could not inspect report file %s: %s", path, exc, exc_info=True)
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=str(exc))

        if not stat.S_ISREG(file_stat.st_mode):
            detail = f"Report path is not a regular file: {path}"
            logger.error(detail)
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=detail)
        if file_stat.st_size > MAX_REPORT_FILE_SIZE:
            detail = (
                f"Report file exceeds the maximum size of {MAX_REPORT_FILE_SIZE} bytes: {path}"
            )
            logger.error(
                "%s (%d bytes)",
                detail,
                file_stat.st_size,
            )
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=detail)
        try:
            raw_content = path.read_bytes()
        except OSError as exc:
            logger.error("Error reading report file %s: %s", path, exc, exc_info=True)
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=str(exc))
        if len(raw_content) > MAX_REPORT_FILE_SIZE:
            detail = f"Report grew beyond the maximum size while being read: {path}"
            logger.error(detail)
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=detail)
        try:
            content = raw_content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError as exc:
            logger.error("Report file is not valid UTF-8: %s", path, exc_info=True)
            return ReportReadResult(ReportReadStatus.READ_FAILED, path, detail=str(exc))
        return ReportReadResult(ReportReadStatus.LOADED, path, content=content)

    def load_result(self, project_name: Optional[str] = None) -> ReportReadResult:
        """Return the explicit disk read state for report.md."""
        return self._read_report_checked(self.get_report_path(project_name))

    def load(self, project_name: Optional[str] = None) -> str:
        """Return report content, empty only when absent, and fail closed on read errors."""
        result = self.load_result(project_name)
        if result.status is ReportReadStatus.READ_FAILED:
            raise ReportReadError(result)
        return result.content

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
        result = self._read_report_checked(report_path)
        if result.status is not ReportReadStatus.LOADED:
            return False
        try:
            return atomic_write_text(backup_path, result.content, encoding="utf-8")
        except OSError as e:
            logger.error(f"Fehler beim Erstellen des Backups {backup_path}: {e}", exc_info=True)
            return False

    def restore_backup(self, project_name: Optional[str] = None) -> bool:
        """Stellt report.md aus report.md.bak wieder her, falls das Backup existiert und Größenlimits einhält."""
        backup_path = self.get_backup_path(project_name)
        result = self._read_report_checked(backup_path)
        if result.status is not ReportReadStatus.LOADED:
            return False
        return self.save(result.content, project_name)

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
        read_result = self.load_result(pname)
        if read_result.status is ReportReadStatus.READ_FAILED:
            raise ReportReadError(read_result)
        if read_result.status is ReportReadStatus.LOADED:
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

    def append_missing_loot(
        self,
        loot_manager,
        project_name: Optional[str] = None,
        template: Optional[Any] = None,
    ) -> AppendMissingLootResult:
        """Additively inserts missing loot entries into the existing report.md.

        Fail-Closed:
        - If no loot entries are missing: returns immediately without creating backups or writing to disk.
        - If entries are added and backup fails: raises ReportBackupError; report.md is left untouched.
        - If saving fails: raises ReportSaveError.
        """
        pname = self._resolve_project_name(project_name)
        read_result = self.load_result(project_name=pname)
        if read_result.status is ReportReadStatus.READ_FAILED:
            raise ReportReadError(read_result)
        current_content = read_result.content
        loot_entries = loot_manager.get_all_entries() if loot_manager else []

        result = append_missing_loot_to_text(
            report_text=current_content,
            loot_entries=loot_entries,
            template=template,
            language=getattr(template, "language", "de") if template else "de",
        )

        if result.added_count == 0:
            return AppendMissingLootResult(
                content=current_content,
                added_count=0,
                used_fallback=False,
                fallback_categories=(),
            )

        if read_result.status is ReportReadStatus.LOADED:
            if not self.backup(pname):
                logger.error(
                    f"Automatisches Backup vor 'Aus Loot ergänzen' für {pname} fehlgeschlagen. Abbruch zum Schutz von Benutzerdaten."
                )
                raise ReportBackupError(
                    f"Automatisches Backup von report.md für Projekt '{pname}' fehlgeschlagen."
                )

        if not self.save(result.text, project_name=pname):
            logger.error(f"Speichern des ergänzten Reports für {pname} fehlgeschlagen.")
            raise ReportSaveError(
                f"Speichern des ergänzten Reports für Projekt '{pname}' fehlgeschlagen."
            )

        return AppendMissingLootResult(
            content=result.text,
            added_count=result.added_count,
            used_fallback=result.used_fallback,
            fallback_categories=result.fallback_categories,
        )

    def reconcile_loot(
        self,
        loot_manager: Any,
        decisions: dict[str, LootReconciliationAction | LootReconciliationSelection | str],
        *,
        append_missing: bool = False,
        project_name: Optional[str] = None,
        template: Optional[Any] = None,
    ) -> LootReconciliationResult:
        """Persist one explicit Loot/report reconciliation as a fail-closed mutation."""
        pname = self._resolve_project_name(project_name)
        read_result = self.load_result(project_name=pname)
        if read_result.status is ReportReadStatus.READ_FAILED:
            raise ReportReadError(read_result)
        current_content = read_result.content
        loot_entries = loot_manager.get_all_entries() if loot_manager else []
        result = reconcile_loot_report(
            current_content,
            loot_entries,
            decisions,
            append_missing=append_missing,
            template=template,
            language=getattr(template, "language", "de") if template else "de",
        )
        if not result.changed:
            return result

        if read_result.status is ReportReadStatus.LOADED and not self.backup(pname):
            raise ReportBackupError(
                f"Automatisches Backup von report.md für Projekt '{pname}' fehlgeschlagen."
            )
        if not self.save(result.text, project_name=pname):
            raise ReportSaveError(
                f"Speichern des abgeglichenen Reports für Projekt '{pname}' fehlgeschlagen."
            )
        return result

    def import_image(self, src_path: Path | str, project_name: Optional[str] = None) -> str:
        """
        Imports an image into the project's screenshots/ directory if it is not already
        inside the project directory.
        Returns the relative POSIX path from the project directory (e.g. 'screenshots/recon.png').
        """
        src = Path(src_path).resolve()
        pname = self._resolve_project_name(project_name)
        proj_dir = self.project_manager.get_project_dir(pname).resolve()

        try:
            rel = src.relative_to(proj_dir)
            return rel.as_posix()
        except ValueError:
            # Outside project dir -> copy to screenshots/
            screenshots_dir = proj_dir / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            dest = screenshots_dir / src.name
            if dest.exists() and dest.resolve() != src:
                import time

                dest = screenshots_dir / f"{src.stem}_{int(time.time())}{src.suffix}"
            import shutil

            shutil.copy2(src, dest)
            return dest.relative_to(proj_dir).as_posix()
