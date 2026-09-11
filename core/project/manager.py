"""
ProjectManager Domain Orchestrator for SpectreHUD.
Coordinates validation, metadata generation, repository storage, and domain events.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from core.logger import get_logger
from core.event_bus import EventBus, EventType, ProjectChangedPayload
from core.project.validator import (
    validate_project_name,
    sanitize_project_name,
    ProjectCreationError,
    ProjectNotFoundError,
)
from core.project.repository import (
    ProjectRepository,
)
from core.project.lock_service import ProjectLockService
from core.project.persistence import PersistResult
from core.project.state_store import ProjectState

logger = get_logger("projects")


class ProjectManager:
    """Manages isolated CTF/Pentest workspaces across default and custom directory locations."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        repository: Optional[ProjectRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.lock_service = ProjectLockService()
        self.repository = repository or ProjectRepository(
            base_dir=base_dir, config_dir=config_dir, lock_service=self.lock_service
        )
        if repository is not None:
            self.repository.lock_service = self.lock_service
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.active_project: str = "Default"
        self._ensure_default_project()

    @property
    def base_dir(self) -> Path:
        return self.repository.base_dir

    @base_dir.setter
    def base_dir(self, val: Path) -> None:
        self.repository.base_dir = Path(val)

    @property
    def config_dir(self) -> Path:
        return self.repository.config_dir

    @config_dir.setter
    def config_dir(self, val: Path) -> None:
        self.repository.config_dir = Path(val)

    @property
    def registry_file(self) -> Path:
        return self.repository.registry_file

    @registry_file.setter
    def registry_file(self, val: Path) -> None:
        self.repository.registry_file = Path(val)

    @property
    def registry(self) -> Dict[str, str]:
        return self.repository.registry

    @registry.setter
    def registry(self, val: Dict[str, str]) -> None:
        self.repository.registry = val

    def _load_registry(self) -> Dict[str, str]:
        return self.repository._load_registry()

    def sanitize_name(self, name: str, fallback: str = "Default") -> str:
        return sanitize_project_name(name, fallback=fallback)

    def _sanitize_name(self, name: str, fallback: str = "Default") -> str:
        return self.sanitize_name(name, fallback=fallback)

    def validate_project_name(self, name: str) -> str:
        return validate_project_name(name)

    def _ensure_default_project(self) -> None:
        """Ensures a Default project exists and is registered."""
        default_dir = self.base_dir / "Default"
        if not default_dir.exists():
            self.create_project(
                "Default", target_ip="10.10.10.10", attacker_ip="10.10.14.5", allow_existing=True
            )
        else:
            registry_result = self.repository._update_registry(
                additions={"Default": str(default_dir.resolve())}
            )
            if not registry_result.success:
                logger.warning(
                    "Could not register the existing Default project: %s",
                    registry_result.failure_reason,
                )
        # Bootstrap: sync discovered projects into registry at startup
        self.repository.sync_registry()

    def project_exists(self, name: str, base_dir: Optional[Path] = None) -> bool:
        """Returns whether a project with the strictly validated name exists."""
        return self.repository.project_exists(name, base_dir=base_dir)

    def list_projects(self) -> List[str]:
        """Returns list of all available project directory names (read-only, no registry mutation)."""
        return self.repository.list_projects()

    def sync_registry(self) -> List[str]:
        """Discovers and registers new projects, then persists the registry to disk."""
        return self.repository.sync_registry()

    def get_active_project(self) -> str:
        """Returns the name of the currently active project."""
        return self.active_project

    def get_project_dir(self, name: Optional[str] = None) -> Path:
        """Returns the filesystem path for a project."""
        pname = name if name is not None else self.active_project
        return self.repository.get_project_dir(pname)

    def create_project(
        self,
        name: str,
        target_ip: str = "",
        attacker_ip: str = "",
        port: str = "4444",
        base_dir: Optional[Path] = None,
        allow_existing: bool = False,
        pentest_password: Optional[str] = None,
        lang: str = "de",
    ) -> Path:
        """
        Creates an isolated project workspace with category subfolders and loot,
        notes.md, and project_state.json, and registers its path.
        """
        clean_name = validate_project_name(name)
        proj_dir = self.repository.create_project_workspace(
            clean_name=clean_name,
            target_ip=target_ip,
            attacker_ip=attacker_ip,
            port=port,
            base_dir=base_dir,
            allow_existing=allow_existing,
            lang=lang,
        )
        if pentest_password is not None:
            pentest_result = self.repository.enable_pentest_mode(clean_name, pentest_password)
            if not pentest_result.success:
                raise ProjectCreationError(
                    f"Could not enable Pentest Mode: {pentest_result.failure_reason}"
                )
        if self.event_bus:
            self.event_bus.publish(
                EventType.PROJECT_CREATED,
                {
                    "name": clean_name,
                    "path": str(proj_dir),
                    "target_ip": target_ip,
                    "attacker_ip": attacker_ip,
                },
            )
        return proj_dir

    def import_project_folder(self, folder_path: Union[Path, str]) -> PersistResult[str]:
        """Imports and registers an existing directory as a project workspace."""
        result = self.repository.import_project_workspace(folder_path)
        if result.success and result.value:
            self.active_project = result.value
            if self.event_bus:
                self.event_bus.publish(
                    EventType.PROJECT_CHANGED,
                    ProjectChangedPayload(project_name=result.value, phase="activated"),
                )
        return result

    def load_project_state(self, name: Optional[str] = None) -> ProjectState:
        """Loads and semantically validates state data for a project."""
        pname = name or self.active_project
        return self.repository.load_project_state(pname)

    def is_pentest_mode(self, name: Optional[str] = None) -> bool:
        return self.repository.is_pentest_mode(name or self.active_project)

    def is_project_unlocked(self, name: Optional[str] = None) -> bool:
        return self.lock_service.is_unlocked(name or self.active_project)

    def unlock_project(self, name: str, password: str) -> bool:
        return self.repository.unlock_project(name, password)

    def clear_project_key(self) -> None:
        self.lock_service.clear()

    def save_project_state(
        self, name: Optional[str] = None, state: Optional[ProjectState] = None, **kwargs: Any
    ) -> PersistResult[None]:
        """Persists state data for a project."""
        pname = name or self.active_project
        return self.repository.save_project_state(pname, state=state, **kwargs)

    def activate_project(self, name: str) -> str:
        """
        Explicitly activates an existing project.
        Raises ProjectNotFoundError if the project does not exist on disk.
        """
        clean_name = validate_project_name(name)
        if clean_name not in self.list_projects():
            raise ProjectNotFoundError(
                f"Project '{name}' (resolved: '{clean_name}') does not exist."
            )

        self.active_project = clean_name
        self.lock_service.retain_only(clean_name)
        if self.event_bus:
            self.event_bus.publish(
                EventType.PROJECT_CHANGED,
                ProjectChangedPayload(project_name=clean_name, phase="activated"),
            )
        return clean_name

    def open_project_folder(self, name: Optional[str] = None) -> bool:
        """Opens the project folder in OS file manager."""
        pname = name or self.active_project
        return self.repository.open_project_folder(pname)

    def archive_project(
        self, name: Optional[str] = None, output_zip: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Archives the project workspace as a .zip file."""
        pname = name or self.active_project
        return self.repository.archive_project(pname, output_zip=output_zip)
