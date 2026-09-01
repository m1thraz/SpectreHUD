"""
Filesystem storage and project registry persistence layer.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from core.logger import get_logger
from core.storage import PersistenceError
from core.atomic_write import atomic_write_json, atomic_write_text
from core.project_lock_service import ProjectLockService
from core.project.validator import (
    validate_project_name,
    validate_workspace_boundary,
    ProjectExistsError,
    InvalidProjectNameError,
    ProjectCreationError,
)
from core.project.metadata import create_initial_notes, create_initial_state
from core.project.registry import ProjectRegistry
from core.project.state_store import ProjectStateStore
from core.platform.paths import config_dir as platform_config_dir, projects_dir

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

    def enable_pentest_mode(self, name: str, password: str) -> None:
        """Encrypt an existing state file and retain its key for this session."""
        self.state_store.enable_pentest_mode(name, password)

    def _load_registry(self) -> Dict[str, str]:
        """Loads registered project paths from projects_registry.json."""
        return self.project_registry.load()

    def _update_registry(
        self,
        additions: Optional[Dict[str, str]] = None,
        removals: Optional[set[str]] = None,
    ) -> None:
        """Atomically persist explicit changes to the active application's registry."""
        self.project_registry.update(additions=additions, removals=removals)

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

    def create_project_workspace(
        self,
        clean_name: str,
        target_ip: str = "",
        attacker_ip: str = "",
        port: str = "4444",
        base_dir: Optional[Path] = None,
        allow_existing: bool = False,
    ) -> Path:
        """
        Creates an isolated project directory structure transactionally.
        """
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        candidate = target_base / clean_name
        proj_dir = validate_workspace_boundary(candidate, target_base)

        if not allow_existing and clean_name != "Default":
            if clean_name in self.list_projects() or proj_dir.exists():
                raise ProjectExistsError(
                    f"A project with sanitized name '{clean_name}' already exists at {proj_dir}."
                )

        dir_existed_initially = proj_dir.exists()

        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
            for sub in PROJECT_LOOT_SUBDIRECTORIES:
                sub_p = proj_dir / sub
                if sub_p.is_symlink():
                    raise ProjectCreationError(
                        f"Project directory contains symlinked subdirectory: {sub}"
                    )
                if sub_p.exists() and not sub_p.is_dir():
                    raise OSError(
                        f"Cannot create subfolder '{sub}' because a non-directory file exists with that name."
                    )
                sub_p.mkdir(exist_ok=True)

            # Create notes.md if not exists
            notes_file = proj_dir / "notes.md"
            if not notes_file.exists():
                notes_content = create_initial_notes(
                    project_name=clean_name, target_ip=target_ip, attacker_ip=attacker_ip
                )
                if not atomic_write_text(notes_file, notes_content):
                    raise OSError(f"Failed to atomically create notes.md for {clean_name}")

            # Create project_state.json if not exists
            state_file = proj_dir / "project_state.json"
            if not state_file.exists():
                initial_state = create_initial_state(
                    project_name=clean_name, target_ip=target_ip, attacker_ip=attacker_ip, port=port
                )
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(
                        f"Failed to atomically write initial project_state.json for {clean_name}"
                    )

            # Register project location
            self._update_registry(additions={clean_name: str(proj_dir)})
            return proj_dir

        except Exception as e:
            logger.error(
                f"Project creation failed for {clean_name}: {e}. Rolling back partial files.",
                exc_info=True,
            )
            if not dir_existed_initially and proj_dir.exists():
                import shutil

                try:
                    shutil.rmtree(proj_dir, ignore_errors=True)
                except Exception as rb_err:
                    logger.warning(f"Rollback cleanup failed for {proj_dir}: {rb_err}")

            if clean_name in self.registry:
                try:
                    self._update_registry(removals={clean_name})
                except PersistenceError:
                    logger.exception(
                        "Failed to remove rolled-back project '%s' from registry", clean_name
                    )

            raise ProjectCreationError(f"Failed to create project '{clean_name}': {e}") from e

    def import_project_workspace(self, folder_path: Union[Path, str]) -> Optional[str]:
        """Imports and registers an existing directory as a project workspace."""
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
                raise ProjectExistsError(
                    f"Cannot import project '{clean_name}': An existing project is already registered at '{existing_loc}'."
                )

        try:
            for sub in PROJECT_LOOT_SUBDIRECTORIES:
                sub_p = target_path / sub
                if sub_p.is_symlink():
                    raise ProjectCreationError(
                        f"Imported project contains symlinked subdirectory: {sub}"
                    )
                if sub_p.exists() and not sub_p.is_dir():
                    raise ProjectCreationError(
                        f"Imported project contains non-directory file named '{sub}'"
                    )
                sub_p.mkdir(exist_ok=True)

            state_file = target_path / "project_state.json"
            if not state_file.exists():
                initial_state = create_initial_state(project_name=clean_name)
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(
                        f"Failed to atomically write project_state.json for imported project {clean_name}"
                    )

            self._update_registry(additions={clean_name: str(target_path)})
            logger.info(f"Successfully imported project '{clean_name}' from {target_path}")
            return clean_name
        except Exception as e:
            logger.error(f"Failed to import project folder {folder_path}: {e}", exc_info=True)
            if isinstance(e, (ProjectExistsError, ProjectCreationError, PersistenceError)):
                raise
            return None

    def load_project_state(self, name: str) -> Dict[str, Any]:
        """Load validated plain or encrypted state through the state store."""
        return self.state_store.load(name)

    def save_project_state(
        self, name: str, state: Optional[Dict[str, Any]] = None, **kwargs
    ) -> bool:
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

        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            return True
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(
                f"Error opening project folder {folder} in system file manager: {e}", exc_info=True
            )
            return False

    def archive_project(self, name: str, output_zip: Optional[Path] = None) -> Dict[str, Any]:
        """Archives the project workspace as a .zip file."""
        from core.box_archiver import BoxArchiver

        pname = validate_project_name(name)
        proj_dir = self.get_project_dir(pname)
        return BoxArchiver.archive_project(proj_dir, output_zip)
