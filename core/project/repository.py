"""
Filesystem storage and project registry persistence layer.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from core.logger import get_logger
from core.storage import PersistenceError
from core.atomic_write import atomic_write_json, atomic_write_text
from core.validators import (
    validate_project_state,
    is_file_size_valid,
    MAX_PROJECT_STATE_FILE_SIZE,
    MAX_REGISTRY_FILE_SIZE
)
from core.project.validator import (
    sanitize_project_name,
    validate_project_name,
    validate_workspace_boundary,
    ProjectExistsError,
    InvalidProjectNameError,
    ProjectCreationError
)
from core.project.metadata import create_initial_notes, create_initial_state

logger = get_logger("projects")

PROJECT_LOOT_SUBDIRECTORIES = ("recon", "access", "privesc", "postex", "scripts", "misc", "loot")


def get_default_projects_dir() -> Path:
    """Returns the default projects workspace directory, checking SPECTRE_PROJECTS_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_PROJECTS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / "spectre_projects"


def get_default_config_dir() -> Path:
    """Returns default configuration directory, checking SPECTRE_CONFIG_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".ctf_cheatsheet_widget"


class ProjectRepository:
    """Handles disk operations, directory structures, and registry persistence for CTF projects."""

    def __init__(self, base_dir: Optional[Path] = None, config_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else get_default_projects_dir()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create base projects directory {self.base_dir}: {e}", exc_info=True)

        self.config_dir = Path(config_dir) if config_dir is not None else get_default_config_dir()
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        self.registry_file = self.config_dir / "projects_registry.json"
        self.registry: Dict[str, str] = self._load_registry()

    def _load_registry(self) -> Dict[str, str]:
        """Loads registered project paths from projects_registry.json."""
        if self.registry_file.exists():
            if not is_file_size_valid(self.registry_file, MAX_REGISTRY_FILE_SIZE):
                logger.warning(f"Project registry file {self.registry_file} exceeds maximum size limit. Ignoring.")
                return {}
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {str(k): str(v) for k, v in data.items()}
            except (json.JSONDecodeError, RecursionError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"Could not load projects registry from {self.registry_file}: {e}")
        return {}

    def _update_registry(
        self,
        additions: Optional[Dict[str, str]] = None,
        removals: Optional[set[str]] = None,
    ) -> None:
        """Atomically persist explicit changes to the active application's registry."""
        additions = dict(additions or {})
        removals = set(removals or set())
        try:
            updated_registry = dict(self.registry)
            for name in removals:
                updated_registry.pop(name, None)
            updated_registry.update(additions)
            if not atomic_write_json(self.registry_file, updated_registry, indent=2, ensure_ascii=False):
                raise OSError("Atomic registry write returned false.")
            self.registry = updated_registry
        except Exception as e:
            logger.error(f"Failed to update projects registry at {self.registry_file}: {e}", exc_info=True)
            raise PersistenceError(f"Failed to update projects registry at {self.registry_file}: {e}") from e

    def project_exists(self, name: str, base_dir: Optional[Path] = None) -> bool:
        """Returns whether a project with the strictly validated name exists."""
        clean = validate_project_name(name)
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        proj_dir = (target_base / clean).resolve()
        return clean in self.list_projects() or proj_dir.exists()

    def list_projects(self) -> List[str]:
        """
        Returns list of all available project directory names across base_dir and custom locations.

        This method is **read-only**: it does not mutate ``self.registry``.
        Call :meth:`sync_registry` explicitly to persist newly discovered projects to the registry.
        """
        from collections import defaultdict
        projects = set()
        resolved_base = self.base_dir.resolve()

        # 1. Base directory projects (auto-discovery with collision detection)
        if self.base_dir.exists():
            try:
                collision_map = defaultdict(list)
                for p in self.base_dir.iterdir():
                    if p.name.startswith("."):
                        continue

                    # Defense against Symlinks and Junctions within default workspace
                    if p.is_symlink():
                        logger.warning(f"Ignoring symlinked project folder inside base_dir: {p}")
                        continue

                    try:
                        resolved_p = p.resolve()
                    except (OSError, RuntimeError):
                        continue

                    if not resolved_p.is_relative_to(resolved_base) or resolved_p == resolved_base:
                        logger.warning(f"Ignoring escaping directory/junction inside base_dir: {p} -> {resolved_p}")
                        continue

                    if p.is_dir():
                        clean = sanitize_project_name(p.name)
                        collision_map[clean].append(resolved_p)

                for clean, cand_paths in collision_map.items():
                    if len(cand_paths) > 1:
                        logger.error(
                            f"Physical directory collision detected for project '{clean}': {cand_paths}. "
                            "Refusing automatic registration to avoid silent shadowing."
                        )
                        continue
                    projects.add(clean)
            except OSError as e:
                logger.error(f"Failed to list projects from {self.base_dir}: {e}", exc_info=True)

        # 2. Registered projects (filtered by existence on disk and invalid base_dir symlinks)
        for name, path_str in list(self.registry.items()):
            try:
                candidate_in_base = self.base_dir / name
                if candidate_in_base.exists() and candidate_in_base.is_symlink():
                    logger.warning(f"Skipping compromised symlinked registry entry during list: {name} -> {path_str}")
                    continue

                p = Path(path_str)
                if p.exists() and p.is_dir():
                    projects.add(name)
            except OSError:
                pass

        if not projects:
            projects.add("Default")

        return sorted(list(projects))

    def sync_registry(self) -> List[str]:
        """
        Discovers all projects from ``base_dir`` and explicitly registers newly found entries into
        ``self.registry``, then persists the registry to disk.

        Unlike :meth:`list_projects`, this method **mutates** ``self.registry`` and writes to disk.
        Call after workspace changes, project creation/import, or on startup bootstrap.

        Returns the sorted list of discovered project names.
        """
        from collections import defaultdict
        additions: Dict[str, str] = {}
        removals: set[str] = set()
        projects = set()
        resolved_base = self.base_dir.resolve()

        if self.base_dir.exists():
            try:
                collision_map = defaultdict(list)
                for p in self.base_dir.iterdir():
                    if p.name.startswith("."):
                        continue
                    if p.is_symlink():
                        logger.warning(f"Ignoring symlinked project folder inside base_dir during sync: {p}")
                        continue
                    try:
                        resolved_p = p.resolve()
                    except (OSError, RuntimeError):
                        continue
                    if not resolved_p.is_relative_to(resolved_base) or resolved_p == resolved_base:
                        continue
                    if p.is_dir():
                        clean = sanitize_project_name(p.name)
                        collision_map[clean].append(resolved_p)

                for clean, cand_paths in collision_map.items():
                    if len(cand_paths) > 1:
                        logger.error(
                            f"Physical directory collision detected for project '{clean}': {cand_paths}. "
                            "Skipping registration."
                        )
                        continue
                    resolved_p = cand_paths[0]
                    projects.add(clean)
                    if clean not in self.registry:
                        additions[clean] = str(resolved_p)
                        logger.debug(f"sync_registry: registered new project '{clean}' at {resolved_p}")

            except OSError as e:
                logger.error(f"Failed to sync registry from {self.base_dir}: {e}", exc_info=True)

        # Purge compromised symlinked registry entries
        for name in list(self.registry.keys()):
            try:
                candidate_in_base = self.base_dir / name
                if candidate_in_base.exists() and candidate_in_base.is_symlink():
                    logger.warning(f"Purging compromised symlinked registry entry during sync: {name}")
                    removals.add(name)
                    continue
                p = Path(self.registry.get(name, ""))
                if p.exists() and p.is_dir():
                    projects.add(name)
            except OSError:
                pass

        if not projects:
            projects.add("Default")

        self._update_registry(additions=additions, removals=removals)
        return sorted(list(projects))

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
            raise InvalidProjectNameError(f"Workspace escape attempt detected for project '{name}'.")

        return proj_dir

    def create_project_workspace(
        self,
        clean_name: str,
        target_ip: str = "",
        attacker_ip: str = "",
        port: str = "4444",
        base_dir: Optional[Path] = None,
        allow_existing: bool = False
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
                    raise ProjectCreationError(f"Project directory contains symlinked subdirectory: {sub}")
                if sub_p.exists() and not sub_p.is_dir():
                    raise OSError(f"Cannot create subfolder '{sub}' because a non-directory file exists with that name.")
                sub_p.mkdir(exist_ok=True)

            # Create notes.md if not exists
            notes_file = proj_dir / "notes.md"
            if not notes_file.exists():
                notes_content = create_initial_notes(
                    project_name=clean_name,
                    target_ip=target_ip,
                    attacker_ip=attacker_ip
                )
                if not atomic_write_text(notes_file, notes_content):
                    raise OSError(f"Failed to atomically create notes.md for {clean_name}")

            # Create project_state.json if not exists
            state_file = proj_dir / "project_state.json"
            if not state_file.exists():
                initial_state = create_initial_state(
                    project_name=clean_name,
                    target_ip=target_ip,
                    attacker_ip=attacker_ip,
                    port=port
                )
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(f"Failed to atomically write initial project_state.json for {clean_name}")

            # Register project location
            self._update_registry(additions={clean_name: str(proj_dir)})
            return proj_dir

        except Exception as e:
            logger.error(f"Project creation failed for {clean_name}: {e}. Rolling back partial files.", exc_info=True)
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
                    logger.exception("Failed to remove rolled-back project '%s' from registry", clean_name)

            raise ProjectCreationError(f"Failed to create project '{clean_name}': {e}") from e

    def import_project_workspace(self, folder_path: Union[Path, str]) -> Optional[str]:
        """Imports and registers an existing directory as a project workspace."""
        target_path = Path(folder_path).resolve()
        if not target_path.exists() or not target_path.is_dir():
            logger.warning(f"Cannot import non-existing or non-directory project folder: {folder_path}")
            return None

        try:
            clean_name = validate_project_name(target_path.name)
        except InvalidProjectNameError as e:
            logger.warning(f"Cannot import project with invalid directory name {target_path.name}: {e}")
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
                    raise ProjectCreationError(f"Imported project contains symlinked subdirectory: {sub}")
                if sub_p.exists() and not sub_p.is_dir():
                    raise ProjectCreationError(f"Imported project contains non-directory file named '{sub}'")
                sub_p.mkdir(exist_ok=True)

            state_file = target_path / "project_state.json"
            if not state_file.exists():
                initial_state = create_initial_state(project_name=clean_name)
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(f"Failed to atomically write project_state.json for imported project {clean_name}")

            self._update_registry(additions={clean_name: str(target_path)})
            logger.info(f"Successfully imported project '{clean_name}' from {target_path}")
            return clean_name
        except Exception as e:
            logger.error(f"Failed to import project folder {folder_path}: {e}", exc_info=True)
            if isinstance(e, (ProjectExistsError, ProjectCreationError, PersistenceError)):
                raise
            return None

    def load_project_state(self, name: str) -> Dict[str, Any]:
        """Loads and semantically validates state data for a project."""
        from core.validators import validate_project_state, is_file_size_valid, MAX_PROJECT_STATE_FILE_SIZE
        pname = validate_project_name(name)
        state_file = self.get_project_dir(pname) / "project_state.json"
        if state_file.exists():
            if not is_file_size_valid(state_file, MAX_PROJECT_STATE_FILE_SIZE):
                logger.error(f"Project state file {state_file} exceeds maximum size limit of {MAX_PROJECT_STATE_FILE_SIZE} bytes. Rejecting oversized file and using default state.")
                return validate_project_state(None, fallback_name=pname)
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    return validate_project_state(raw_data, fallback_name=pname)
            except (json.JSONDecodeError, RecursionError) as e:
                logger.error(f"Corrupted project_state.json for {pname}: {e}")
            except (OSError, UnicodeDecodeError) as e:
                logger.error(f"Error loading state for {pname}: {e}")

        return validate_project_state(None, fallback_name=pname)

    def save_project_state(self, name: str, state: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
        """Persists state data for an existing project without recreating it."""
        from core.validators import validate_project_state
        from core.atomic_write import atomic_write_json
        pname = validate_project_name(name)
        proj_dir = self.get_project_dir(pname)
        if not proj_dir.exists() or not proj_dir.is_dir():
            logger.error(
                "Refusing to save project '%s': expected project directory is unavailable at %s. "
                "It may have been moved or deleted outside SpectreHUD.",
                pname,
                proj_dir,
            )
            return False

        state_file = proj_dir / "project_state.json"
        final_state = self.load_project_state(pname) or {}
        if state:
            final_state.update(state)
        if kwargs:
            final_state.update(kwargs)

        final_state["name"] = pname
        final_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        valid_state = validate_project_state(final_state, fallback_name=pname)

        try:
            return atomic_write_json(state_file, valid_state, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"OS error saving state for {pname} to {state_file}: {e}", exc_info=True)
            return False
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error saving state for {pname}: {e}")
            return False

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
            logger.error(f"Error opening project folder {folder} in system file manager: {e}", exc_info=True)
            return False

    def archive_project(self, name: str, output_zip: Optional[Path] = None) -> Dict[str, Any]:
        """Archives the project workspace as a .zip file."""
        from core.box_archiver import BoxArchiver
        pname = validate_project_name(name)
        proj_dir = self.get_project_dir(pname)
        return BoxArchiver.archive_project(proj_dir, output_zip)
