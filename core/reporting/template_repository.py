"""
Template Repository for SpectreHUD.

Manages discovery, validation, storage, and retrieval of built-in and user-defined report templates.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.reporting.template_engine import ReportTemplate, TemplateSection, LEGACY_DEFAULT_TEMPLATE
from core.validators import is_file_size_valid, MAX_TEMPLATE_FILE_SIZE
from core.atomic_write import atomic_write_json
from core.logger import get_logger

logger = get_logger("template_repository")

TEMPLATE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def is_valid_template_id(template_id: str) -> bool:
    """Validates that a template ID contains only alphanumeric characters, underscores, and hyphens (1-64 chars)."""
    if not isinstance(template_id, str):
        return False
    return bool(TEMPLATE_ID_PATTERN.match(template_id.strip()))


def template_to_dict(template: ReportTemplate) -> Dict[str, Any]:
    """Serializes a ReportTemplate dataclass to a dictionary."""
    return {
        "id": template.id,
        "name": template.name,
        "language": template.language,
        "category": template.category,
        "complexity": template.complexity,
        "is_builtin": template.is_builtin,
        "sections": [
            {
                "type": s.type,
                **({"title": s.title} if s.title else {}),
                **({"category_id": s.category_id} if s.category_id else {}),
                **({"options": s.options} if s.options else {}),
                **({"page_break_before": True} if s.page_break_before else {}),
            }
            for s in template.sections
        ],
    }


def dict_to_template(data: Dict[str, Any], is_builtin: bool = False) -> Optional[ReportTemplate]:
    """Deserializes and validates a dictionary into a ReportTemplate dataclass."""
    if not isinstance(data, dict):
        return None

    template_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    if not is_valid_template_id(template_id) or not name:
        logger.warning(
            f"dict_to_template rejected template with invalid id ({template_id!r}) or name ({name!r})"
        )
        return None

    language = str(data.get("language", "de")).lower()
    if language not in ("de", "en"):
        language = "de"

    category = str(data.get("category", "pentest")).lower()
    if category not in ("ctf", "pentest"):
        category = "pentest"

    complexity = str(data.get("complexity", "complex")).lower()
    if complexity not in ("simple", "complex"):
        complexity = "complex"

    raw_sections = data.get("sections", [])
    if not isinstance(raw_sections, list):
        return None

    sections: List[TemplateSection] = []
    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        sec_type = str(s.get("type", "")).strip()
        if not sec_type:
            continue
        title = s.get("title")
        cat_id = s.get("category_id")
        options = s.get("options", {}) if isinstance(s.get("options"), dict) else {}
        page_break_before = bool(s.get("page_break_before", False))
        sections.append(
            TemplateSection(
                type=sec_type,
                title=str(title) if title else None,
                category_id=str(cat_id) if cat_id else None,
                options=options,
                page_break_before=page_break_before,
            )
        )

    if not sections:
        return None

    return ReportTemplate(
        id=template_id,
        name=name,
        language=language,
        category=category,
        complexity=complexity,
        sections=sections,
        is_builtin=is_builtin,
    )


class TemplateRepository:
    """Repository handling loading, saving, and managing report templates."""

    def __init__(
        self, user_templates_dir: Optional[Path] = None, builtin_dir: Optional[Path] = None
    ):
        if builtin_dir:
            self.builtin_dir = Path(builtin_dir)
        else:
            # PyInstaller one-file builds unpack data into ``_MEIPASS``;
            # source and wheel installations retain the normal repository
            # layout next to ``core``.
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                self.builtin_dir = Path(sys._MEIPASS) / "data" / "report_templates"
            else:
                self.builtin_dir = (
                    Path(__file__).resolve().parent.parent.parent / "data" / "report_templates"
                )

        if user_templates_dir:
            self.user_templates_dir = Path(user_templates_dir)
        else:
            from core.config import get_default_config_dir

            self.user_templates_dir = get_default_config_dir() / "report_templates"

        self.user_templates_dir.mkdir(parents=True, exist_ok=True)

    def _load_template_file(self, file_path: Path, is_builtin: bool) -> Optional[ReportTemplate]:
        try:
            if not file_path.exists() or not file_path.is_file():
                return None
            if not is_file_size_valid(file_path, MAX_TEMPLATE_FILE_SIZE):
                logger.warning(f"Template file rejected due to size limit: {file_path}")
                return None

            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return dict_to_template(data, is_builtin=is_builtin)
        except Exception as e:
            logger.warning(f"Failed to parse template from {file_path}: {e}")
            return None

    def get_builtin_templates(self) -> List[ReportTemplate]:
        """Discovers and parses all built-in templates from data/report_templates/."""
        templates: List[ReportTemplate] = []
        if self.builtin_dir.exists() and self.builtin_dir.is_dir():
            for f in sorted(self.builtin_dir.glob("*.json")):
                t = self._load_template_file(f, is_builtin=True)
                if t:
                    templates.append(t)

        if not templates:
            templates.append(LEGACY_DEFAULT_TEMPLATE)
        return templates

    def get_user_templates(self) -> List[ReportTemplate]:
        """Discovers and parses all user custom templates from user config directory."""
        templates: List[ReportTemplate] = []
        if self.user_templates_dir.exists() and self.user_templates_dir.is_dir():
            for f in sorted(self.user_templates_dir.glob("*.json")):
                t = self._load_template_file(f, is_builtin=False)
                if t:
                    templates.append(t)
        return templates

    def get_all_templates(self) -> List[ReportTemplate]:
        """
        Returns all templates.
        User-defined templates override built-in templates with the same ID.
        """
        template_map: Dict[str, ReportTemplate] = {}
        for t in self.get_builtin_templates():
            template_map[t.id] = t
        for t in self.get_user_templates():
            template_map[t.id] = t
        return list(template_map.values())

    def _get_safe_user_path(self, template_id: str) -> Optional[Path]:
        """Resolves and validates that the user template path is strictly within user_templates_dir."""
        if not is_valid_template_id(template_id):
            logger.warning(f"Rejected template operation with invalid template_id: {template_id!r}")
            return None
        path = (self.user_templates_dir / f"{template_id}.json").resolve()
        try:
            if not path.is_relative_to(self.user_templates_dir.resolve()):
                logger.warning(f"Path traversal detected for template_id: {template_id!r}")
                return None
        except AttributeError:
            if self.user_templates_dir.resolve() not in path.parents:
                return None
        return path

    def _get_safe_builtin_path(self, template_id: str) -> Optional[Path]:
        """Resolves and validates that the built-in template path is strictly within builtin_dir."""
        if not is_valid_template_id(template_id):
            return None
        path = (self.builtin_dir / f"{template_id}.json").resolve()
        try:
            if not path.is_relative_to(self.builtin_dir.resolve()):
                return None
        except AttributeError:
            if self.builtin_dir.resolve() not in path.parents:
                return None
        return path

    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """Gets a template by its ID, checking user overrides first, then built-ins."""
        user_path = self._get_safe_user_path(template_id)
        if user_path and user_path.exists():
            t = self._load_template_file(user_path, is_builtin=False)
            if t:
                return t

        builtin_path = self._get_safe_builtin_path(template_id)
        if builtin_path and builtin_path.exists():
            t = self._load_template_file(builtin_path, is_builtin=True)
            if t:
                return t

        if template_id == LEGACY_DEFAULT_TEMPLATE.id:
            return LEGACY_DEFAULT_TEMPLATE

        for t in self.get_all_templates():
            if t.id == template_id:
                return t

        return None

    def save_user_template(self, template: ReportTemplate) -> bool:
        """Saves a user template as a JSON file atomically."""
        if not is_valid_template_id(template.id):
            logger.warning(f"Rejected save_user_template with invalid template ID: {template.id!r}")
            return False
        user_path = self._get_safe_user_path(template.id)
        if not user_path:
            return False
        data = template_to_dict(template)
        data["is_builtin"] = False
        return atomic_write_json(user_path, data)

    def delete_user_template(self, template_id: str) -> bool:
        """
        Deletes a user template.
        If the template is also a built-in, this resets it back to factory defaults.
        """
        user_path = self._get_safe_user_path(template_id)
        if not user_path or not user_path.exists():
            return False
        try:
            user_path.unlink()
            return True
        except OSError as e:
            logger.error(f"Failed to delete user template {template_id}: {e}")
            return False

    def reset_to_defaults(self, template_id: Optional[str] = None) -> bool:
        """Removes user overrides for a specific template or all templates."""
        if template_id:
            return self.delete_user_template(template_id)

        ok = True
        if self.user_templates_dir.exists():
            for f in self.user_templates_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    ok = False
        return ok
