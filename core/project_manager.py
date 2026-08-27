"""
Backward compatibility facade for core.project.
"""

from core.project import (
    ProjectManager,
    ProjectRepository,
    ProjectExistsError,
    InvalidProjectNameError,
    ProjectNotFoundError,
    ProjectCreationError,
    DEFAULT_NOTES_TEMPLATE,
    get_default_projects_dir,
    get_default_config_dir,
    validate_project_name,
    sanitize_project_name,
)

__all__ = [
    "ProjectManager",
    "ProjectRepository",
    "ProjectExistsError",
    "InvalidProjectNameError",
    "ProjectNotFoundError",
    "ProjectCreationError",
    "DEFAULT_NOTES_TEMPLATE",
    "get_default_projects_dir",
    "get_default_config_dir",
    "validate_project_name",
    "sanitize_project_name",
]
