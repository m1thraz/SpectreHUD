"""
Project domain package for SpectreHUD.
Provides isolation, validation, metadata generation, repository storage, and lifecycle management.
"""

from core.project.validator import (
    ProjectExistsError,
    InvalidProjectNameError,
    ProjectNotFoundError,
    ProjectCreationError,
    WorkspaceError,
    validate_project_name,
    sanitize_project_name,
    validate_workspace_boundary,
    validate_workspace_directory
)
from core.project.metadata import (
    DEFAULT_NOTES_TEMPLATE,
    create_initial_notes,
    create_initial_state
)
from core.project.repository import (
    ProjectRepository,
    get_default_projects_dir,
    get_default_config_dir
)
from core.project.manager import ProjectManager

__all__ = [
    "ProjectManager",
    "ProjectRepository",
    "ProjectExistsError",
    "InvalidProjectNameError",
    "ProjectNotFoundError",
    "ProjectCreationError",
    "WorkspaceError",
    "validate_project_name",
    "sanitize_project_name",
    "validate_workspace_boundary",
    "validate_workspace_directory",
    "DEFAULT_NOTES_TEMPLATE",
    "create_initial_notes",
    "create_initial_state",
    "get_default_projects_dir",
    "get_default_config_dir",
]
