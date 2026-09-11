"""
Filesystem storage and project registry persistence layer.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from core.logger import get_logger
from core.storage import PersistenceError
from core.atomic_write import atomic_write_json, atomic_write_text
from core.project.lock_service import ProjectLockService
from core.project.persistence import (
    PersistFailureReason,
    PersistResult,
    classify_persistence_error,
)
from core.project.validator import (
    validate_project_name,
    validate_workspace_boundary,
    ProjectExistsError,
    InvalidProjectNameError,
    ProjectCreationError,
)
from core.project.metadata import create_initial_notes, create_initial_state
from core.project.registry import ProjectRegistry
from core.project.state_store import ProjectState, ProjectStateStore
from core.platform import config_dir as platform_config_dir, projects_dir
from core.platform import open_path

logger = get_logger("projects")

PROJECT_LOOT_SUBDIRECTORIES = ("recon", "access", "privesc", "postex", "scripts", "misc", "loot")


def get_default_projects_dir() -> Path:
    """Compatibility entry point for the central workspace path source."""
    return projects_dir()


def get_default_config_dir() -> Path:
    """Compatibility entry point for the central platform path source."""
    return platform_config_dir()


class ProjectRepository:
    """Handles disk operations, directory structures, and registry persistence for CTF projects."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        lock_service: Optional[ProjectLockService] = None,
    ):
        self.base_dir = Path(base_dir) if base_dir else get_default_projects_dir()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                f"Failed to create base projects directory {self.base_dir}: {e}", exc_info=True
            )

        self.config_dir = Path(config_dir) if config_dir is not None else get_default_config_dir()
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        self.project_registry = ProjectRegistry(self.config_dir / "projects_registry.json")
        self._lock_service = lock_service or ProjectLockService()
        self.state_store = ProjectStateStore(self.get_project_dir, self._lock_service)

    @property
    def lock_service(self) -> ProjectLockService:
        return self._lock_service

    @lock_service.setter
    def lock_service(self, value: ProjectLockService) -> None:
        self._lock_service = value
        if hasattr(self, "state_store"):
            self.state_store.lock_service = value

    @property
    def registry_file(self) -> Path:
        return self.project_registry.registry_file

    @registry_file.setter
    def registry_file(self, value: Path) -> None:
        self.project_registry.registry_file = Path(value)

    @property
    def registry(self) -> Dict[str, str]:
        return self.project_registry.entries

    @registry.setter
    def registry(self, value: Dict[str, str]) -> None:
        self.project_registry.entries = value

    def is_pentest_mode(self, name: str) -> bool:
        return self.state_store.is_pentest_mode(name)

    def unlock_project(self, name: str, password: str) -> bool:
        return self.state_store.unlock(name, password)

    def enable_pentest_mode(self, name: str, password: str) -> PersistResult[None]:
        """Encrypt an existing state file and retain its key for this session."""
        return self.state_store.enable_pentest_mode(name, password)

    def _load_registry(self) -> Dict[str, str]:
        """Loads registered project paths from projects_registry.json."""
        return self.project_registry.load()

    def _update_registry(
        self,
        additions: Optional[Dict[str, str]] = None,
        removals: Optional[set[str]] = None,
    ) -> PersistResult[None]:
        """Atomically persist explicit changes to the active application's registry."""
        try:
            self.project_registry.update(additions=additions, removals=removals)
            return PersistResult.ok()
        except PersistenceError as exc:
            cause = exc.__cause__ if isinstance(exc.__cause__, BaseException) else exc
            return PersistResult.failed(classify_persistence_error(cause))

    def project_exists(self, name: str, base_dir: Optional[Path] = None) -> bool:
        """Returns whether a project with the strictly validated name exists."""
        clean = validate_project_name(name)
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        proj_dir = (target_base / clean).resolve()
        return clean in self.list_projects() or proj_dir.exists()

    def list_projects(self) -> List[str]:
        """Return discovered and registered projects without persisting changes."""
        return self.project_registry.list_projects(self.base_dir)

    def sync_registry(self) -> List[str]:
        """Discover workspace projects and atomically persist registry changes."""
        return self.project_registry.sync(self.base_dir)

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        """
        Returns the filesystem path for a project.
        Checks registered paths first, then falls back to base_dir with boundary validation.
        Raises InvalidProjectNameError if name is invalid or attempts traversal.
        """
        if name is None:
            pname = "Default"
        else:
            pname = validate_project_name(name)

        resolved_base = self.base_dir.resolve()
        candidate = self.base_dir / pname

        if candidate.exists() and candidate.is_symlink():
            logger.warning(
                f"Ignored malicious symlink masquerading as project in base_dir: {candidate}"
            )
            raise InvalidProjectNameError(f"Project '{pname}' is a malicious symlink.")

        if pname in self.registry:
            reg_path = Path(self.registry[pname]).resolve()
            if reg_path.exists() and reg_path.is_dir():
                return reg_path

        proj_dir = candidate.resolve()
        if not proj_dir.is_relative_to(resolved_base) or proj_dir == resolved_base:
            logger.error(
                f"Workspace escape attempt / symlink traversal detected: {name!r} "
                f"(resolved to {proj_dir})."
            )
            raise InvalidProjectNameError(
                f"Workspace escape attempt detected for project '{name}'."
            )

        return proj_dir

    def _validate_create_candidate(
        self, clean_name: str, base_dir: Optional[Path], allow_existing: bool
    ) -> Path:
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        candidate = target_base / clean_name
        proj_dir = validate_workspace_boundary(candidate, target_base)

        if not allow_existing and clean_name != "Default":
            if clean_name in self.list_projects() or proj_dir.exists():
                raise ProjectExistsError(
                    f"A project with sanitized name '{clean_name}' already exists at {proj_dir}."
                )
        return proj_dir

    def _validate_import_candidate(
        self, folder_path: Union[Path, str]
    ) -> Optional[tuple[Path, str]]:
        target_path = Path(folder_path).resolve()
        if not target_path.exists() or not target_path.is_dir():
            logger.warning(
                f"Cannot import non-existing or non-directory project folder: {folder_path}"
            )
            return None

        try:
            clean_name = validate_project_name(target_path.name)
        except InvalidProjectNameError as e:
            logger.warning(
                f"Cannot import project with invalid directory name {target_path.name}: {e}"
            )
            return None

        if clean_name in self.registry and self.registry[clean_name] != str(target_path):
            existing_loc = Path(self.registry[clean_name])
            if existing_loc.exists() and existing_loc.is_dir():
                return None
        return target_path, clean_name

    def _ensure_project_subdirectories(self, proj_dir: Path, *, is_import: bool = False) -> None:
        proj_dir.mkdir(parents=True, exist_ok=True)
        prefix = "Imported project contains " if is_import else "Project directory contains "
        for sub in PROJECT_LOOT_SUBDIRECTORIES:
            sub_p = proj_dir / sub
            if sub_p.is_symlink():
                raise ProjectCreationError(f"{prefix}symlinked subdirectory: {sub}")
            if sub_p.exists() and not sub_p.is_dir():
                if is_import:
                    raise ProjectCreationError(
                        f"Imported project contains non-directory file named '{sub}'"
                    )
                raise OSError(
                    f"Cannot create subfolder '{sub}' because a non-directory file exists with that name."
                )
            sub_p.mkdir(exist_ok=True)

    def _ensure_initial_project_files(
        self,
        proj_dir: Path,
        clean_name: str,
        target_ip: str,
        attacker_ip: str,
        port: str,
        lang: str,
    ) -> None:
        notes_file = proj_dir / "notes.md"
        if not notes_file.exists():
            notes_content = create_initial_notes(
                project_name=clean_name,
                target_ip=target_ip,
                attacker_ip=attacker_ip,
                lang=lang,
            )
            if not atomic_write_text(notes_file, notes_content):
                raise OSError(f"Failed to atomically create notes.md for {clean_name}")

        state_file = proj_dir / "project_state.json"
        if not state_file.exists():
            initial_state = create_initial_state(
                project_name=clean_name,
                target_ip=target_ip,
                attacker_ip=attacker_ip,
                port=port,
            )
            if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                raise OSError(
                    f"Failed to atomically write initial project_state.json for {clean_name}"
                )

    def _rollback_workspace_paths(
        self,
        managed_paths: list[Path],
        existing_managed_paths: set[Path],
        proj_dir: Path,
        dir_existed_initially: bool,
    ) -> bool:
        rollback_performed = False
        for path in reversed(managed_paths):
            if path in existing_managed_paths:
                continue
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                    rollback_performed = True
                elif path.is_dir():
                    path.rmdir()
                    rollback_performed = True
            except OSError as rollback_error:
                logger.warning(
                    "Rollback could not remove newly created path %s: %s",
                    path,
                    rollback_error,
                )
        if not dir_existed_initially and proj_dir.exists():
            try:
                proj_dir.rmdir()
                rollback_performed = True
            except OSError as rollback_error:
                logger.warning(
                    "Rollback could not remove new project directory %s: %s",
                    proj_dir,
                    rollback_error,
                )
        return rollback_performed

    def _rollback_registry_entry(
        self,
        clean_name: str,
        registry_had_entry: bool,
        registry_entry_before: Optional[str],
    ) -> bool:
        try:
            if registry_had_entry:
                if self.registry.get(clean_name) != registry_entry_before:
                    registry_result = self._update_registry(
                        additions={clean_name: str(registry_entry_before)}
                    )
                    return registry_result.success
            elif clean_name in self.registry:
                registry_result = self._update_registry(removals={clean_name})
                return registry_result.success
        except Exception:
            logger.exception("Failed to restore registry during rollback.")
        return False

    def _ensure_imported_state_file(self, target_path: Path, clean_name: str) -> None:
        state_file = target_path / "project_state.json"
        if not state_file.exists():
            initial_state = create_initial_state(project_name=clean_name)
            if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                raise OSError(
                    f"Failed to atomically write project_state.json for imported project {clean_name}"
                )

    def _handle_workspace_failure(
        self,
        error: Exception,
        managed_paths: List[Path],
        existing_managed_paths: set[Path],
        target_dir: Path,
        dir_existed_initially: bool,
        clean_name: str,
        registry_had_entry: bool,
        registry_entry_before: Optional[str],
        operation_failure_reason: Optional[PersistFailureReason],
    ) -> PersistResult[Any]:
        rb_paths = self._rollback_workspace_paths(
            managed_paths, existing_managed_paths, target_dir, dir_existed_initially
        )
        rb_reg = self._rollback_registry_entry(
            clean_name, registry_had_entry, registry_entry_before
        )
        rollback_performed = rb_paths or rb_reg
        cause = error.__cause__ if isinstance(error.__cause__, BaseException) else error
        reason = operation_failure_reason or (
            PersistFailureReason.VALIDATION_FAILED
            if isinstance(error, (ProjectExistsError, ProjectCreationError))
            else classify_persistence_error(cause)
        )
        return PersistResult.failed(reason, rollback_performed=rollback_performed)

    def create_project_workspace(
        self,
        clean_name: str,
        target_ip: str = "",
        attacker_ip: str = "",
        port: str = "4444",
        base_dir: Optional[Path] = None,
        allow_existing: bool = False,
        lang: str = "de",
    ) -> Path:
        """Creates an isolated project directory structure transactionally."""
        proj_dir = self._validate_create_candidate(clean_name, base_dir, allow_existing)
        dir_existed_initially = proj_dir.exists()

        managed_paths = [
            *(proj_dir / sub for sub in PROJECT_LOOT_SUBDIRECTORIES),
            proj_dir / "project_state.json",
            proj_dir / "notes.md",
        ]
        existing_managed_paths = {
            path for path in managed_paths if path.exists() or path.is_symlink()
        }
        registry_had_entry = clean_name in self.registry
        registry_entry_before = self.registry.get(clean_name)

        try:
            self._ensure_project_subdirectories(proj_dir, is_import=False)
            self._ensure_initial_project_files(
                proj_dir, clean_name, target_ip, attacker_ip, port, lang
            )
            registry_result = self._update_registry(additions={clean_name: str(proj_dir)})
            if not registry_result.success:
                raise PersistenceError(
                    f"Could not register project '{clean_name}': {registry_result.failure_reason or PersistFailureReason.UNKNOWN}"
                )
            logger.info(f"Project '{clean_name}' successfully created at {proj_dir}")
            return proj_dir
        except Exception as e:
            logger.error(
                f"Project creation failed for {clean_name}: {e}. Rolling back partial files.",
                exc_info=True,
            )
            self._rollback_workspace_paths(
                managed_paths, existing_managed_paths, proj_dir, dir_existed_initially
            )
            self._rollback_registry_entry(clean_name, registry_had_entry, registry_entry_before)
            raise ProjectCreationError(f"Failed to create project '{clean_name}': {e}") from e

    def import_project_workspace(self, folder_path: Union[Path, str]) -> PersistResult[str]:
        """Imports and registers an existing directory as a project workspace."""
        candidate = self._validate_import_candidate(folder_path)
        if candidate is None:
            return PersistResult.failed(PersistFailureReason.VALIDATION_FAILED)
        target_path, clean_name = candidate

        managed_paths = [
            *(target_path / sub for sub in PROJECT_LOOT_SUBDIRECTORIES),
            target_path / "project_state.json",
        ]
        existing_managed_paths = {
            path for path in managed_paths if path.exists() or path.is_symlink()
        }
        registry_had_entry = clean_name in self.registry
        registry_entry_before = self.registry.get(clean_name)
        operation_failure_reason: Optional[PersistFailureReason] = None

        try:
            self._ensure_project_subdirectories(target_path, is_import=True)
            self._ensure_imported_state_file(target_path, clean_name)
            registry_result = self._update_registry(additions={clean_name: str(target_path)})
            if not registry_result.success:
                operation_failure_reason = registry_result.failure_reason
                raise PersistenceError(
                    f"Could not register imported project: "
                    f"{registry_result.failure_reason or PersistFailureReason.UNKNOWN}"
                )
            logger.info(f"Successfully imported project '{clean_name}' from {target_path}")
            return PersistResult.ok(clean_name)
        except Exception as e:
            logger.error(f"Failed to import project folder {folder_path}: {e}", exc_info=True)
            return self._handle_workspace_failure(
                e,
                managed_paths,
                existing_managed_paths,
                target_path,
                True,
                clean_name,
                registry_had_entry,
                registry_entry_before,
                operation_failure_reason,
            )

    def load_project_state(self, name: str) -> ProjectState:
        """Load validated plain or encrypted state through the state store."""
        return self.state_store.load(name)

    def save_project_state(
        self, name: str, state: Optional[ProjectState] = None, **kwargs: Any
    ) -> PersistResult[None]:
        """Persist validated plain or encrypted state through the state store."""
        return self.state_store.save(name, state=state, **kwargs)

    def open_project_folder(self, name: str) -> bool:
        """Opens the project folder in OS file manager."""
        folder = self.get_project_dir(name)
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create project folder before opening {folder}: {e}")

        if open_path(folder):
            return True
        logger.error("Could not open project folder %s in the system file manager", folder)
        return False

    def archive_project(self, name: str, output_zip: Optional[Path] = None) -> Dict[str, Any]:
        """Archives the project workspace as a .zip file."""
        from core.box_archiver import BoxArchiver

        pname = validate_project_name(name)
        proj_dir = self.get_project_dir(pname)
        return BoxArchiver.archive_project(proj_dir, output_zip)
