"""Persistent project registry and workspace discovery."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from core.atomic_write import atomic_write_json
from core.logger import get_logger
from core.storage import PersistenceError
from core.validators import MAX_REGISTRY_FILE_SIZE, is_file_size_valid
from core.project.validator import sanitize_project_name

logger = get_logger("projects")


class ProjectRegistry:
    """Owns registry persistence and read-only/committing workspace discovery."""

    def __init__(self, registry_file: Path):
        self.registry_file = Path(registry_file)
        self.entries: Dict[str, str] = self.load()

    def load(self) -> Dict[str, str]:
        if self.registry_file.exists():
            if not is_file_size_valid(self.registry_file, MAX_REGISTRY_FILE_SIZE):
                logger.warning(
                    "Project registry file %s exceeds maximum size limit. Ignoring.",
                    self.registry_file,
                )
                return {}
            try:
                with self.registry_file.open("r", encoding="utf-8") as file:
                    data = json.load(file)
                if isinstance(data, dict):
                    return {str(key): str(value) for key, value in data.items()}
            except (json.JSONDecodeError, RecursionError, OSError, UnicodeDecodeError) as exc:
                logger.warning(
                    "Could not load projects registry from %s: %s", self.registry_file, exc
                )
        return {}

    def update(
        self, additions: Optional[Dict[str, str]] = None, removals: Optional[set[str]] = None
    ) -> None:
        additions = dict(additions or {})
        removals = set(removals or set())
        try:
            updated = dict(self.entries)
            for name in removals:
                updated.pop(name, None)
            updated.update(additions)
            if not atomic_write_json(self.registry_file, updated, indent=2, ensure_ascii=False):
                raise OSError("Atomic registry write returned false.")
            self.entries = updated
        except Exception as exc:
            logger.error(
                "Failed to update projects registry at %s: %s",
                self.registry_file,
                exc,
                exc_info=True,
            )
            raise PersistenceError(
                f"Failed to update projects registry at {self.registry_file}: {exc}"
            ) from exc

    @staticmethod
    def _discover_base(base_dir: Path) -> Dict[str, Path]:
        discovered: Dict[str, Path] = {}
        if not base_dir.exists():
            return discovered
        resolved_base = base_dir.resolve()
        collisions: Dict[str, List[Path]] = defaultdict(list)
        try:
            for candidate in base_dir.iterdir():
                if candidate.name.startswith(".") or candidate.is_symlink():
                    continue
                try:
                    resolved = candidate.resolve()
                except (OSError, RuntimeError):
                    continue
                if not resolved.is_relative_to(resolved_base) or resolved == resolved_base:
                    continue
                if candidate.is_dir():
                    collisions[sanitize_project_name(candidate.name)].append(resolved)
        except OSError as exc:
            logger.error("Failed to list projects from %s: %s", base_dir, exc, exc_info=True)
            return discovered
        for name, paths in collisions.items():
            if len(paths) == 1:
                discovered[name] = paths[0]
            else:
                logger.error(
                    "Physical directory collision detected for project '%s': %s.", name, paths
                )
        return discovered

    def list_projects(self, base_dir: Path) -> List[str]:
        base_dir = Path(base_dir)
        projects = set(self._discover_base(base_dir))
        for name, path_text in list(self.entries.items()):
            try:
                candidate_in_base = base_dir / name
                if candidate_in_base.exists() and candidate_in_base.is_symlink():
                    continue
                path = Path(path_text)
                if path.exists() and path.is_dir():
                    projects.add(name)
            except OSError:
                pass
        return sorted(projects or {"Default"})

    def sync(self, base_dir: Path) -> List[str]:
        base_dir = Path(base_dir)
        discovered = self._discover_base(base_dir)
        projects = set(discovered)
        additions = {
            name: str(path) for name, path in discovered.items() if name not in self.entries
        }
        removals: set[str] = set()
        for name, path_text in list(self.entries.items()):
            try:
                candidate_in_base = base_dir / name
                if candidate_in_base.exists() and candidate_in_base.is_symlink():
                    removals.add(name)
                    continue
                path = Path(path_text)
                if path.exists() and path.is_dir():
                    projects.add(name)
            except OSError:
                pass
        self.update(additions=additions, removals=removals)
        return sorted(projects or {"Default"})
