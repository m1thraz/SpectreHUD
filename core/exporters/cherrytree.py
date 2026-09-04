"""Portable HTML package export for CherryTree import workflows.

CherryTree can import HTML, but its native ``.ctb`` format is an application
database.  This exporter intentionally creates ordinary HTML and image files
instead of modifying a CherryTree database.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from core.atomic_write import atomic_write_bytes, atomic_write_text
from core.exporters.base import ExportResult, ExternalExportError
from core.exporters.obsidian import ObsidianExporter
from core.project.validator import sanitize_filename_component, validate_project_name
from core.reporting.styles import get_report_css
from core.reporting.markdown import convert_markdown_to_html
from core.reporting.loot_sync import strip_report_markers


_IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")


class CherryTreeExporter:
    """Creates a self-contained report/loot HTML package with relative images."""

    def __init__(self, output_directory: Path | str):
        raw = str(output_directory or "").strip()
        if not raw:
            raise ExternalExportError(
                "Choose a destination directory for the CherryTree export package."
            )
        self.output_directory = Path(raw)

    @staticmethod
    def _project_name(project_name: str) -> str:
        try:
            return validate_project_name(project_name)
        except ValueError as exc:
            raise ExternalExportError(
                f"Invalid project name for CherryTree export: {project_name!r}"
            ) from exc

    def _package_directory(self, project_name: str) -> Path:
        safe_name = self._project_name(project_name)
        try:
            if self.output_directory.exists() and self.output_directory.is_symlink():
                raise ExternalExportError(
                    "Refusing to export through a symlinked CherryTree destination."
                )
            self.output_directory.mkdir(parents=True, exist_ok=True)
            root = self.output_directory.resolve()
            if not root.is_dir():
                raise ExternalExportError(
                    "The CherryTree destination directory is unsafe or unavailable."
                )
            package = root / safe_name
            if package.exists() and package.is_symlink():
                raise ExternalExportError(
                    "Refusing to export through a symlinked CherryTree package directory."
                )
            package.mkdir(exist_ok=True)
            package = package.resolve()
            if not package.is_relative_to(root) or package == root:
                raise ExternalExportError("CherryTree export path escaped its chosen destination.")
            return package
        except OSError as exc:
            raise ExternalExportError(
                "Could not create the CherryTree export package directory."
            ) from exc

    @staticmethod
    def _document(title: str, body_html: str, report_font: str) -> str:
        css = get_report_css("light", report_font)
        return f"""<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>{html.escape(title)}</title><style>{css}
body {{ padding: 28px; }} .report-wrapper {{ max-width: 1080px; margin: 0 auto; }}
img.inline-img {{ max-width: 100%; height: auto; }}
</style></head><body><main class=\"report-wrapper report-body\">{body_html}</main></body></html>"""

    def _copy_images(
        self, markdown: str, project_dir: Path, package_dir: Path
    ) -> tuple[str, tuple[Path, ...], tuple[str, ...]]:
        image_dir = package_dir / "images"
        copied: list[Path] = []
        warnings: list[str] = []
        mapped: dict[Path, str] = {}
        names: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            alt_text, raw_path = match.group(1), match.group(2)
            source = ObsidianExporter._safe_attachment_source(raw_path, project_dir)
            if source is None:
                if (
                    raw_path.lower()
                    .split("?", 1)[0]
                    .endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))
                ):
                    warnings.append(f"Image was not exported: {raw_path}")
                return match.group(0)
            if source not in mapped:
                image_dir.mkdir(exist_ok=True)
                if image_dir.is_symlink():
                    raise ExternalExportError(
                        "Refusing to write images through a symlinked directory."
                    )
                base = sanitize_filename_component(source.stem, fallback="image")
                name = base + source.suffix.lower()
                index = 2
                while name in names:
                    name = f"{base}_{index}{source.suffix.lower()}"
                    index += 1
                try:
                    atomic_write_bytes(image_dir / name, source.read_bytes())
                except OSError as exc:
                    warnings.append(f"Image could not be copied: {raw_path} ({exc})")
                    return match.group(0)
                mapped[source] = name
                names.add(name)
                copied.append(image_dir / name)
            return f"![{alt_text}](images/{mapped[source]})"

        return _IMAGE_LINK_RE.sub(replace, markdown), tuple(copied), tuple(warnings)

    def export_package(
        self,
        *,
        project_name: str,
        project_dir: Path | str,
        report_markdown: str,
        loot_entries: Iterable[Mapping[str, Any]],
        report_font: str = "segoe_ui",
    ) -> ExportResult:
        source_dir = Path(project_dir).resolve()
        if not source_dir.is_dir():
            raise ExternalExportError("The active project directory is unavailable.")
        package_dir = self._package_directory(project_name)
        clean_markdown = strip_report_markers(str(report_markdown))
        rewritten, copied, warnings = self._copy_images(
            clean_markdown, source_dir, package_dir
        )
        report_html = self._document(
            f"{project_name} – Report", convert_markdown_to_html(rewritten), report_font
        )
        loot_markdown = ObsidianExporter._loot_markdown(loot_entries)
        loot_html = self._document(
            f"{project_name} – Loot", convert_markdown_to_html(loot_markdown), report_font
        )
        report_path = package_dir / "report.html"
        loot_path = package_dir / "loot.html"
        try:
            atomic_write_text(report_path, report_html)
            atomic_write_text(loot_path, loot_html)
        except OSError as exc:
            raise ExternalExportError("Could not write the CherryTree HTML package.") from exc
        return ExportResult(report_path, copied, warnings)
