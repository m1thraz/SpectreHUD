"""Safe, one-way Markdown export into an Obsidian vault.

This adapter deliberately treats an Obsidian vault as a normal filesystem
folder.  It never reads Obsidian databases, watches the vault, or attempts a
two-way synchronization.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlencode

from core.atomic_write import atomic_write_bytes, atomic_write_text
from core.exporters.base import ExportResult, ExternalExportError
from core.project.validator import sanitize_filename_component, validate_project_name
from core.reporting.assets import MAX_EMBED_IMAGE_FILE_SIZE


_IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_ENTRY_MARKER_RE = re.compile(r"<!--\s*spectrehud-entry:([^\s>]+)\s*-->")
_DEFAULT_EXPORT_FOLDER = "CTF/SpectreHUD"
_LOOT_SECTION = "## SpectreHUD Loot"


class ObsidianExporter:
    """Exports reports and loot to one configured Obsidian vault."""

    def __init__(self, vault_path: Path | str, export_folder: str = _DEFAULT_EXPORT_FOLDER):
        self.vault_path = self._validate_vault(vault_path)
        self.export_folder_parts = self._validate_export_folder(export_folder)

    @staticmethod
    def _validate_vault(vault_path: Path | str) -> Path:
        raw = str(vault_path or "").strip()
        if not raw:
            raise ExternalExportError("No Obsidian vault has been configured.")
        vault = Path(raw)
        if not vault.exists() or not vault.is_dir():
            raise ExternalExportError(f"The configured Obsidian vault is unavailable: {vault}")
        try:
            return vault.resolve(strict=True)
        except OSError as exc:
            raise ExternalExportError(f"The configured Obsidian vault cannot be resolved: {vault}") from exc

    @staticmethod
    def _validate_export_folder(export_folder: str) -> tuple[str, ...]:
        raw = str(export_folder or _DEFAULT_EXPORT_FOLDER).strip().replace("\\", "/")
        candidate = PurePath(raw)
        if candidate.is_absolute() or not raw or any(part in {"", ".", ".."} for part in candidate.parts):
            raise ExternalExportError("The Obsidian export folder must be a safe relative path.")
        if any("\x00" in part for part in candidate.parts):
            raise ExternalExportError("The Obsidian export folder contains an invalid path component.")
        return tuple(candidate.parts)

    def _safe_project_name(self, project_name: str) -> str:
        try:
            return validate_project_name(project_name)
        except ValueError as exc:
            raise ExternalExportError(f"Invalid project name for Obsidian export: {project_name!r}") from exc

    def _ensure_export_directory(self, project_name: str) -> Path:
        target = self.vault_path
        for part in (*self.export_folder_parts, self._safe_project_name(project_name)):
            target = target / part
            if target.exists() and target.is_symlink():
                raise ExternalExportError(f"Refusing to export through symlinked vault directory: {part}")
            try:
                target.mkdir(exist_ok=True)
            except OSError as exc:
                raise ExternalExportError(f"Could not create Obsidian export directory: {target}") from exc
            resolved = target.resolve()
            if not resolved.is_relative_to(self.vault_path) or resolved == self.vault_path:
                raise ExternalExportError("Obsidian export path escaped the configured vault.")
            target = resolved
        return target

    @staticmethod
    def _copy_target(note_path: Path, overwrite: str) -> Path:
        if not note_path.exists():
            return note_path
        if overwrite == "overwrite":
            return note_path
        if overwrite != "copy":
            raise ExternalExportError("The Obsidian note already exists; choose overwrite or create a copy.")
        index = 2
        while True:
            candidate = note_path.with_stem(f"{note_path.stem}_{index}")
            if not candidate.exists():
                return candidate
            index += 1

    @staticmethod
    def _frontmatter(project_name: str, project_state: Mapping[str, Any]) -> str:
        fields = [("source", "SpectreHUD"), ("project", project_name)]
        for source_key, output_key in (("target_ip", "target"), ("attacker_ip", "attacker_ip")):
            value = str(project_state.get(source_key, "") or "").strip()
            if value:
                fields.append((output_key, value))
        fields.append(("exported", datetime.now().astimezone().isoformat(timespec="seconds")))
        lines = ["---"]
        lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields)
        lines.extend(["tags:", "  - ctf", "  - spectrehud", "---", ""])
        return "\n".join(lines)

    @staticmethod
    def _safe_attachment_source(raw_path: str, project_dir: Path) -> Optional[Path]:
        raw_path = raw_path.strip()
        if not raw_path or raw_path.startswith(("#", "data:", "http:", "https:")):
            return None
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return None
        resolved_project = project_dir.resolve()
        try:
            resolved = (project_dir / candidate).resolve(strict=True)
        except OSError:
            return None
        if not resolved.is_relative_to(resolved_project) or resolved.is_symlink() or not resolved.is_file():
            return None
        try:
            if resolved.stat().st_size > MAX_EMBED_IMAGE_FILE_SIZE:
                return None
        except OSError:
            return None
        return resolved

    def _copy_attachments(self, markdown: str, project_dir: Path, destination_dir: Path) -> tuple[str, tuple[Path, ...], tuple[str, ...]]:
        attachment_dir = destination_dir / "attachments"
        copied: list[Path] = []
        warnings: list[str] = []
        used_names: dict[Path, str] = {}
        names_in_use: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            alt_text, raw_path = match.group(1), match.group(2)
            source = self._safe_attachment_source(raw_path, project_dir)
            if source is None:
                if raw_path.lower().split("?", 1)[0].endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                    warnings.append(f"Attachment was not exported: {raw_path}")
                return match.group(0)
            if source not in used_names:
                attachment_dir.mkdir(parents=True, exist_ok=True)
                if attachment_dir.is_symlink() or not attachment_dir.resolve().is_relative_to(self.vault_path):
                    raise ExternalExportError("Refusing to write attachments through an unsafe vault directory.")
                safe_name = sanitize_filename_component(source.stem, fallback="attachment") + source.suffix.lower()
                index = 2
                candidate_name = safe_name
                while candidate_name in names_in_use:
                    candidate_name = f"{Path(safe_name).stem}_{index}{source.suffix.lower()}"
                    index += 1
                target = attachment_dir / candidate_name
                try:
                    atomic_write_bytes(target, source.read_bytes())
                except OSError as exc:
                    warnings.append(f"Attachment could not be copied: {raw_path} ({exc})")
                    return match.group(0)
                used_names[source] = candidate_name
                names_in_use.add(candidate_name)
                copied.append(target)
            return f"![{alt_text}](attachments/{used_names[source]})"

        return _IMAGE_LINK_RE.sub(replace, markdown), tuple(copied), tuple(warnings)

    def note_path_for(self, project_name: str) -> Path:
        safe_name = self._safe_project_name(project_name)
        return self._ensure_export_directory(safe_name) / f"{safe_name}.md"

    def build_open_uri(self, note_path: Path) -> str:
        try:
            relative_note = note_path.resolve().relative_to(self.vault_path).as_posix()
        except ValueError as exc:
            raise ExternalExportError("Cannot build an Obsidian URI outside the configured vault.") from exc
        return "obsidian://open?" + urlencode({"vault": self.vault_path.name, "file": relative_note})

    def export_report(
        self,
        *,
        project_name: str,
        project_dir: Path | str,
        markdown: str,
        project_state: Optional[Mapping[str, Any]] = None,
        overwrite: str = "copy",
    ) -> ExportResult:
        source_dir = Path(project_dir).resolve()
        if not source_dir.is_dir():
            raise ExternalExportError("The active project directory is unavailable.")
        destination_dir = self._ensure_export_directory(project_name)
        note_path = self._copy_target(destination_dir / f"{self._safe_project_name(project_name)}.md", overwrite)
        rewritten, attachments, warnings = self._copy_attachments(str(markdown), source_dir, destination_dir)
        content = self._frontmatter(project_name, project_state or {}) + rewritten.lstrip("\ufeff")
        try:
            atomic_write_text(note_path, content)
        except OSError as exc:
            raise ExternalExportError(f"Could not write Obsidian report: {note_path}") from exc
        return ExportResult(note_path, attachments, warnings, obsidian_uri=self.build_open_uri(note_path))

    @staticmethod
    def _loot_markdown(entries: Iterable[Mapping[str, Any]]) -> str:
        blocks: list[str] = []
        for entry in entries:
            entry_id = str(entry.get("id", "")).strip()
            if not entry_id:
                continue
            title = str(entry.get("title", "Untitled loot")).strip() or "Untitled loot"
            entry_type = str(entry.get("type", "note")).strip() or "note"
            timestamp = str(entry.get("timestamp", "")).strip()
            target = str(entry.get("target_ip", "")).strip()
            metadata = [f"- Type: `{entry_type}`"]
            if target:
                metadata.append(f"- Target: `{target}`")
            if timestamp:
                metadata.append(f"- Captured: `{timestamp}`")
            content = str(entry.get("content", "")).rstrip()
            fence = "```"
            while fence in content:
                fence += "`"
            blocks.append("\n".join([
                f"<!-- spectrehud-entry:{entry_id} -->",
                f"### {title}",
                *metadata,
                "",
                fence,
                content,
                fence,
            ]))
        return "\n\n".join(blocks)

    def append_loot(
        self,
        *,
        project_name: str,
        entries: Iterable[Mapping[str, Any]],
        note_path: Optional[Path | str] = None,
    ) -> ExportResult:
        target = Path(note_path) if note_path is not None else self.note_path_for(project_name)
        try:
            target = target.resolve()
        except OSError as exc:
            raise ExternalExportError("Could not resolve the Obsidian target note.") from exc
        if not target.is_relative_to(self.vault_path) or target.suffix.lower() != ".md":
            raise ExternalExportError("Refusing to append loot outside the configured Obsidian vault.")
        if target.exists() and target.is_symlink():
            raise ExternalExportError("Refusing to append through a symlinked Obsidian note.")
        try:
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
        except OSError as exc:
            raise ExternalExportError("Could not read the existing Obsidian note.") from exc
        existing_ids = set(_ENTRY_MARKER_RE.findall(existing))
        new_entries = [entry for entry in entries if str(entry.get("id", "")) not in existing_ids]
        skipped = tuple(str(entry.get("id", "")) for entry in entries if str(entry.get("id", "")) in existing_ids)
        rendered = self._loot_markdown(new_entries)
        if rendered:
            separator = "\n\n" if existing.rstrip() else ""
            if _LOOT_SECTION not in existing:
                rendered = _LOOT_SECTION + "\n\n" + rendered
            try:
                atomic_write_text(target, existing.rstrip() + separator + rendered + "\n")
            except OSError as exc:
                raise ExternalExportError("Could not append loot to the Obsidian note.") from exc
        return ExportResult(target, skipped_entry_ids=skipped, obsidian_uri=self.build_open_uri(target))
