"""Curated report icons and theme-independent PNG asset rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, QSize
from PyQt6.QtGui import QImage

from core.atomic_write import atomic_write_bytes
from ui.styles.icons import icon


REPORT_ICON_SIZE = 32
REPORT_ICON_COLORS = {
    "default": "#3b82f6",
    "info": "#0284c7",
    "success": "#16a34a",
    "warning": "#d97706",
    "critical": "#dc2626",
}

_ICON_NAME_RE = re.compile(r"^[a-z0-9]+\.[a-z0-9-]+$")


class ReportIconError(RuntimeError):
    """Raised when a report icon asset cannot be created safely."""


@dataclass(frozen=True)
class ReportIconDefinition:
    """One curated semantic report icon."""

    key: str
    category: str
    icon_name: str
    label_key: str


REPORT_ICON_CATEGORIES = ("general", "security", "infrastructure", "evidence")

REPORT_ICONS = (
    ReportIconDefinition("note", "general", "fa5s.sticky-note", "report.icon.note"),
    ReportIconDefinition("info", "general", "fa5s.info-circle", "report.icon.info"),
    ReportIconDefinition(
        "warning", "general", "fa5s.exclamation-triangle", "report.icon.warning"
    ),
    ReportIconDefinition("success", "general", "fa5s.check-circle", "report.icon.success"),
    ReportIconDefinition("failure", "general", "fa5s.times-circle", "report.icon.failure"),
    ReportIconDefinition("finding", "security", "fa5s.shield-alt", "report.icon.finding"),
    ReportIconDefinition("vulnerability", "security", "fa5s.bug", "report.icon.vulnerability"),
    ReportIconDefinition("exploit", "security", "fa5s.bomb", "report.icon.exploit"),
    ReportIconDefinition("credential", "security", "fa5s.user-secret", "report.icon.credential"),
    ReportIconDefinition("key", "security", "fa5s.key", "report.icon.key"),
    ReportIconDefinition("shell", "security", "fa5s.terminal", "report.icon.shell"),
    ReportIconDefinition(
        "privilege_escalation",
        "security",
        "fa5s.level-up-alt",
        "report.icon.privilege_escalation",
    ),
    ReportIconDefinition("flag", "security", "fa5s.flag", "report.icon.flag"),
    ReportIconDefinition("identity", "security", "fa5s.user", "report.icon.identity"),
    ReportIconDefinition("host", "infrastructure", "fa5s.desktop", "report.icon.host"),
    ReportIconDefinition("server", "infrastructure", "fa5s.server", "report.icon.server"),
    ReportIconDefinition(
        "network", "infrastructure", "fa5s.network-wired", "report.icon.network"
    ),
    ReportIconDefinition(
        "database", "infrastructure", "fa5s.database", "report.icon.database"
    ),
    ReportIconDefinition("cloud", "infrastructure", "fa5s.cloud", "report.icon.cloud"),
    ReportIconDefinition("web", "infrastructure", "fa5s.globe", "report.icon.web"),
    ReportIconDefinition("linux", "infrastructure", "fa5b.linux", "report.icon.linux"),
    ReportIconDefinition("windows", "infrastructure", "fa5b.windows", "report.icon.windows"),
    ReportIconDefinition("screenshot", "evidence", "fa5s.camera", "report.icon.screenshot"),
    ReportIconDefinition("terminal", "evidence", "fa5s.terminal", "report.icon.terminal"),
    ReportIconDefinition("code", "evidence", "fa5s.code", "report.icon.code"),
    ReportIconDefinition("file", "evidence", "fa5s.file-alt", "report.icon.file"),
    ReportIconDefinition("link", "evidence", "fa5s.link", "report.icon.link"),
    ReportIconDefinition("clipboard", "evidence", "fa5s.clipboard", "report.icon.clipboard"),
)


def render_report_icon(
    project_dir: Path | str,
    icon_name: str,
    size: int = REPORT_ICON_SIZE,
    variant: str | None = None,
) -> str:
    """Render a QtAwesome icon once and return its project-relative PNG path."""
    if not _ICON_NAME_RE.fullmatch(icon_name):
        raise ReportIconError(f"Invalid QtAwesome icon name: {icon_name!r}")
    if not 8 <= int(size) <= 256:
        raise ReportIconError("Report icon size must be between 8 and 256 pixels.")

    variant_name = variant or "default"
    try:
        color = REPORT_ICON_COLORS[variant_name]
    except KeyError as exc:
        raise ReportIconError(f"Unknown report icon variant: {variant_name!r}") from exc

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise ReportIconError("The active project directory is unavailable.")

    asset_dir = root / "assets" / "icons"
    try:
        asset_dir.mkdir(parents=True, exist_ok=True)
        resolved_asset_dir = asset_dir.resolve()
    except OSError as exc:
        raise ReportIconError("The report icon directory could not be created.") from exc
    if not resolved_asset_dir.is_relative_to(root) or any(
        path.is_symlink() for path in (root / "assets", asset_dir) if path.exists()
    ):
        raise ReportIconError("The report icon directory is unsafe.")

    base_name = icon_name.replace(".", "_")
    variant_suffix = "" if variant_name == "default" else f"_{variant_name}"
    filename = f"{base_name}_{int(size)}{variant_suffix}.png"
    target = resolved_asset_dir / filename

    if target.is_file():
        existing = QImage(str(target))
        if not existing.isNull() and existing.size() == QSize(int(size), int(size)):
            return target.relative_to(root).as_posix()

    rendered_icon = icon(icon_name, color=color, color_active=None)
    if rendered_icon.isNull():
        raise ReportIconError(f"QtAwesome icon is unavailable: {icon_name}")
    pixmap = rendered_icon.pixmap(QSize(int(size), int(size)))
    if pixmap.isNull():
        raise ReportIconError(f"QtAwesome icon could not be rendered: {icon_name}")

    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not pixmap.save(buffer, "PNG"):
        raise ReportIconError(f"QtAwesome icon could not be encoded as PNG: {icon_name}")
    try:
        atomic_write_bytes(target, bytes(buffer.data()))
    except OSError as exc:
        raise ReportIconError(f"Report icon asset could not be saved: {target.name}") from exc
    return target.relative_to(root).as_posix()
