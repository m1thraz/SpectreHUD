import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.logger import get_logger
from core.storage import PersistenceError

class ProjectExistsError(ValueError):
    """Raised when attempting to create a project whose sanitized name already exists."""
    pass


class ProjectCreationError(RuntimeError):
    """Raised when project workspace creation fails transactionally."""
    pass


logger = get_logger("projects")

DEFAULT_NOTES_TEMPLATE = """# CTF Write-Up & Notes: {project_name}

- **Target IP:** `{target_ip}`
- **Attacker IP / LHOST:** `{attacker_ip}`
- **Erstellt am:** {created_at}

---

## 1. Reconnaissance & Port Scans
- **Nmap Initial Scan:**
```bash
# Nmap initial results
```

---

## 2. Initial Access & Exploitation
- **Schwachstelle:** 
- **Vorgehensweise:** 

---

## 3. Privilege Escalation
- **User Flag:** 
- **Root / Admin Escalation:** 
- **Root Flag:** 

---

## 4. Notizen & Gelerntes
- 
"""

def get_default_projects_dir() -> Path:
    """Returns the default projects workspace directory, checking SPECTRE_PROJECTS_DIR env var first."""
    env_dir = os.environ.get("SPECTRE_PROJECTS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / "spectre_projects"

def get_default_config_dir() -> Path:
    env_dir = os.environ.get("SPECTRE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".ctf_cheatsheet_widget"

class ProjectManager:
    """Manages isolated CTF/Pentest workspaces across default and custom directory locations."""

    def __init__(self, base_dir: Optional[Path] = None, config_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = get_default_projects_dir()
        self.base_dir = Path(base_dir)
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

        self.active_project = "Default"
        self._ensure_default_project()

    def _load_registry(self) -> Dict[str, str]:
        """Loads registered project paths from projects_registry.json."""
        if self.registry_file.exists():
            from core.validators import is_file_size_valid, MAX_REGISTRY_FILE_SIZE
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

    def _save_registry(self) -> None:
        """Persists the project registry mapping to disk."""
        try:
            from core.atomic_write import atomic_write_json
            atomic_write_json(self.registry_file, self.registry, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save projects registry to {self.registry_file}: {e}", exc_info=True)
            raise PersistenceError(f"Failed to save projects registry to {self.registry_file}: {e}") from e

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitizes project name to safe folder characters, strictly preventing
        directory traversal (e.g., '.', '..', '../foo').
        """
        if not name:
            return "Default"

        # Replace invalid path characters with underscore (collapsing consecutive invalid chars)
        clean = re.sub(r'[^a-zA-Z0-9_\-\.]+', '_', str(name).strip())

        # Strip leading and trailing dots and underscores to prevent hidden/special traversal dirs
        clean = clean.strip("._")

        # Explicitly check against dangerous names or invalid formats
        if not clean or clean in {".", ".."} or not re.match(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$', clean):
            return "Default"

        return clean

    def _ensure_default_project(self) -> None:
        """Ensures a Default project exists and is registered."""
        default_dir = self.base_dir / "Default"
        if not default_dir.exists():
            self.create_project("Default", target_ip="10.10.10.10", attacker_ip="10.10.14.5", allow_existing=True)
        else:
            self.registry["Default"] = str(default_dir.resolve())
            self._save_registry()

    def project_exists(self, name: str, base_dir: Optional[Path] = None) -> bool:
        """Returns True if a project with the given or sanitized name already exists."""
        clean = self._sanitize_name(name)
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        proj_dir = (target_base / clean).resolve()
        return clean in self.list_projects() or proj_dir.exists()

    def list_projects(self) -> List[str]:
        """Returns list of all available project directory names across base_dir and custom locations."""
        projects = set()
        resolved_base = self.base_dir.resolve()
        
        # 1. Base directory projects (auto-discovery)
        if self.base_dir.exists():
            try:
                for p in self.base_dir.iterdir():
                    if p.name.startswith("."):
                        continue

                    # Defense against Symlinks and Junctions within the default workspace
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
                        clean = self._sanitize_name(p.name)
                        projects.add(clean)
                        if clean not in self.registry:
                            self.registry[clean] = str(resolved_p)
            except OSError as e:
                logger.error(f"Failed to list projects from {self.base_dir}: {e}", exc_info=True)

        # 2. Registered projects (filtered by existence on disk and invalid base_dir symlinks)
        for name, path_str in list(self.registry.items()):
            try:
                candidate_in_base = self.base_dir / name
                # If a symlink in base_dir masquerades as this project, purge it from registry
                if candidate_in_base.exists() and candidate_in_base.is_symlink():
                    logger.warning(f"Purging compromised symlinked registry entry: {name} -> {path_str}")
                    del self.registry[name]
                    continue

                p = Path(path_str)
                if p.exists() and p.is_dir():
                    projects.add(name)
            except OSError:
                pass

        if not projects:
            projects.add("Default")

        return sorted(list(projects))

    def get_active_project(self) -> str:
        """Returns the name of the currently active project."""
        return self.active_project

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        """
        Returns the filesystem path for a project.
        Checks registered paths first, then falls back to base_dir with boundary validation.
        """
        pname = self._sanitize_name(name or self.active_project)
        resolved_base = self.base_dir.resolve()
        candidate = self.base_dir / pname

        # Defense against Symlinks/Junctions in base_dir masquerading as projects
        if candidate.exists() and candidate.is_symlink():
            logger.error(
                f"Workspace escape attempt / symlink traversal detected in base_dir: {candidate}. "
                f"Falling back to Default."
            )
            if pname in self.registry:
                del self.registry[pname]
            return (self.base_dir / "Default").resolve()

        # 1. Check registry (for legitimately imported external folders)
        if pname in self.registry:
            reg_path = Path(self.registry[pname]).resolve()
            if reg_path.exists() and reg_path.is_dir():
                return reg_path

        # 2. Base directory fallback with boundary & symlink defense
        proj_dir = candidate.resolve()

        if not proj_dir.is_relative_to(resolved_base) or proj_dir == resolved_base:
            logger.error(
                f"Workspace escape attempt / symlink traversal detected: {name!r} "
                f"(resolved to {proj_dir}). Falling back to Default."
            )
            return (self.base_dir / "Default").resolve()

        return proj_dir

    def create_project(
        self, 
        name: str, 
        target_ip: str = "", 
        attacker_ip: str = "", 
        port: str = "4444",
        base_dir: Optional[Path] = None,
        allow_existing: bool = False
    ) -> Path:
        """
        Creates an isolated project workspace with subfolders (recon, exploit, loot),
        notes.md, and project_state.json, and registers its path.
        Enforces strict boundary checks against symlink and directory traversal escapes.
        Rejects creation if a project with the sanitized name already exists.
        """
        clean_name = self._sanitize_name(name)
        target_base = Path(base_dir).resolve() if base_dir else self.base_dir.resolve()
        
        # Boundary & symlink escape validation
        candidate = target_base / clean_name
        resolved_proj = candidate.resolve()

        if not resolved_proj.is_relative_to(target_base) or resolved_proj == target_base:
            logger.error(
                f"Workspace escape attempt / symlink traversal detected for project {name!r}: "
                f"resolved to {resolved_proj}, which is outside target base {target_base}. "
                "Rejecting creation and falling back to Default inside workspace."
            )
        proj_dir = resolved_proj
        if not allow_existing and clean_name != "Default":
            if clean_name in self.list_projects() or proj_dir.exists():
                raise ProjectExistsError(
                    f"A project with sanitized name '{clean_name}' already exists at {proj_dir}."
                )

        dir_existed_initially = proj_dir.exists()

        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
            for sub in ("recon", "exploit", "loot"):
                sub_p = proj_dir / sub
                if sub_p.exists() and not sub_p.is_dir():
                    raise OSError(f"Cannot create subfolder '{sub}' because a non-directory file exists with that name.")
                sub_p.mkdir(exist_ok=True)

            # Create notes.md if not exists
            notes_file = proj_dir / "notes.md"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not notes_file.exists():
                notes_content = DEFAULT_NOTES_TEMPLATE.format(
                    project_name=clean_name,
                    target_ip=target_ip or "TBD",
                    attacker_ip=attacker_ip or "TBD",
                    created_at=now_str
                )
                from core.atomic_write import atomic_write_text
                if not atomic_write_text(notes_file, notes_content):
                    raise OSError(f"Failed to atomically create notes.md for {clean_name}")

            # Create project_state.json if not exists
            state_file = proj_dir / "project_state.json"
            if not state_file.exists():
                initial_state = {
                    "name": clean_name,
                    "target_ip": target_ip or "10.10.10.10",
                    "attacker_ip": attacker_ip or "10.10.14.5",
                    "port": port or "4444",
                    "wordlist": "/usr/share/wordlists/dirb/common.txt",
                    "created_at": now_str,
                    "updated_at": now_str,
                    "loot": [],
                    "clipboard_history": []
                }
                from core.atomic_write import atomic_write_json
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(f"Failed to atomically write initial project_state.json for {clean_name}")

            # Register project location
            self.registry[clean_name] = str(proj_dir)
            self._save_registry()
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
                del self.registry[clean_name]

            raise ProjectCreationError(f"Failed to create project '{clean_name}': {e}") from e

    def import_project_folder(self, folder_path: Path | str) -> Optional[str]:
        """
        Imports and registers an existing directory as a project workspace.
        Ensures necessary subfolders and metadata files exist.
        Protects against hijacking existing projects of the same name.
        """
        target_path = Path(folder_path).resolve()
        if not target_path.exists() or not target_path.is_dir():
            logger.warning(f"Cannot import non-existing or non-directory project folder: {folder_path}")
            return None

        clean_name = self._sanitize_name(target_path.name)
        if clean_name in self.registry and self.registry[clean_name] != str(target_path):
            existing_loc = Path(self.registry[clean_name])
            if existing_loc.exists() and existing_loc.is_dir():
                raise ProjectExistsError(
                    f"Cannot import project '{clean_name}': An existing project is already registered at '{existing_loc}'."
                )

        try:
            (target_path / "recon").mkdir(exist_ok=True)
            (target_path / "exploit").mkdir(exist_ok=True)
            (target_path / "loot").mkdir(exist_ok=True)

            state_file = target_path / "project_state.json"
            if not state_file.exists():
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                initial_state = {
                    "name": clean_name,
                    "target_ip": "10.10.10.10",
                    "attacker_ip": "10.10.14.5",
                    "port": "4444",
                    "wordlist": "/usr/share/wordlists/dirb/common.txt",
                    "created_at": now_str,
                    "updated_at": now_str,
                    "loot": [],
                    "clipboard_history": []
                }
                from core.atomic_write import atomic_write_json
                if not atomic_write_json(state_file, initial_state, indent=2, ensure_ascii=False):
                    raise OSError(f"Failed to atomically write project_state.json for imported project {clean_name}")

            self.registry[clean_name] = str(target_path)
            self._save_registry()
            self.active_project = clean_name
            logger.info(f"Successfully imported project '{clean_name}' from {target_path}")
            return clean_name
        except Exception as e:
            logger.error(f"Failed to import project folder {folder_path}: {e}", exc_info=True)
            if isinstance(e, (ProjectExistsError, PersistenceError)):
                raise
            return None

    def load_project_state(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Loads and semantically validates state data for a project."""
        from core.validators import validate_project_state, is_file_size_valid, MAX_PROJECT_STATE_FILE_SIZE
        pname = self._sanitize_name(name or self.active_project)
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

        # Return default fallback state
        return validate_project_state(None, fallback_name=pname)

    def save_project_state(self, name: Optional[str] = None, state: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
        """Persists state data for a project. Returns True on success, False on failure."""
        from core.validators import validate_project_state
        pname = self._sanitize_name(name or self.active_project)
        proj_dir = self.get_project_dir(pname)
        try:
            proj_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to ensure project dir {proj_dir}: {e}", exc_info=True)
            return False

        from core.atomic_write import atomic_write_json
        state_file = proj_dir / "project_state.json"

        # Merge state from dict and kwargs
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

    def set_active_project(self, name: str) -> None:
        """Switches the active project context."""
        clean_name = self._sanitize_name(name)
        if clean_name in self.list_projects():
            self.active_project = clean_name
        else:
            self.create_project(clean_name)
            self.active_project = clean_name

    def open_project_folder(self, name: Optional[str] = None) -> bool:
        """Opens the project folder in Windows Explorer or Linux file manager."""
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

    def archive_project(self, name: Optional[str] = None, output_zip: Optional[Path] = None) -> Dict[str, Any]:
        """Archives the project workspace as a .zip file."""
        from core.box_archiver import BoxArchiver
        pname = self._sanitize_name(name or self.active_project)
        proj_dir = self.get_project_dir(pname)
        return BoxArchiver.archive_project(proj_dir, output_zip)
