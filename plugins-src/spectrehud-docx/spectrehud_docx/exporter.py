"""Filesystem-safe DOCX report export implementation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from docx import Document

from spectrehud_plugin_api import ExportArtifact, ExportResult, strip_report_markers

from spectrehud_docx.markdown_renderer import DocxMarkdownRenderer


_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(project_name: str) -> str:
    value = _UNSAFE_NAME_RE.sub("_", project_name.strip()).strip("._")
    return value or "SpectreHUD-Report"


def _copy_target(destination: Path, project_name: str) -> Path:
    base = destination / f"{_safe_name(project_name)}.docx"
    if not base.exists():
        return base
    counter = 2
    while True:
        candidate = destination / f"{base.stem}_{counter}.docx"
        if not candidate.exists():
            return candidate
        counter += 1


def export_docx(
    *,
    destination: Path,
    project_name: str,
    project_dir: Path,
    markdown: str,
    report_font: str,
) -> ExportResult:
    destination.mkdir(parents=True, exist_ok=True)
    if not destination.is_dir():
        raise OSError(f"DOCX destination is not a directory: {destination}")
    target = _copy_target(destination, project_name)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    document = Document()
    document.core_properties.title = project_name
    renderer = DocxMarkdownRenderer(document, project_dir, report_font)
    warnings = renderer.render(strip_report_markers(markdown))
    try:
        document.save(temporary)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return ExportResult.success(
        artifacts=(
            ExportArtifact(
                path=target,
                format="docx",
                bytes_written=target.stat().st_size,
            ),
        ),
        warnings=warnings,
    )


__all__ = ["export_docx"]
