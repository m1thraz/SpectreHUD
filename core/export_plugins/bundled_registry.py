"""Host registry factory for bundled export-plugin manifests."""

import logging
from pathlib import Path
from typing import Iterable

from core.export_plugins.discovery import PluginDiscoveryResult, discover_export_plugins
from core.export_plugins.installation import default_external_export_plugin_roots
from core.export_plugins.registry import ExportPluginRegistry


logger = logging.getLogger(__name__)


def bundled_export_plugin_root() -> Path:
    return Path(__file__).with_name("bundled")


def discover_bundled_export_plugins() -> PluginDiscoveryResult:
    return discover_export_plugins((bundled_export_plugin_root(),))


def create_bundled_export_plugin_registry() -> ExportPluginRegistry:
    discovery = discover_bundled_export_plugins()
    return ExportPluginRegistry(discovery.descriptors)


def create_export_plugin_registry(
    *, external_roots: Iterable[Path | str] | None = None
) -> ExportPluginRegistry:
    """Compose bundled and separately installed plugins with bundled IDs taking precedence."""
    roots = tuple(
        default_external_export_plugin_roots() if external_roots is None else external_roots
    )
    discovery = discover_export_plugins((bundled_export_plugin_root(), *roots))
    for issue in discovery.issues:
        logger.warning("Export plugin manifest ignored: %s (%s)", issue.manifest_path, issue.message)
    return ExportPluginRegistry(discovery.descriptors)


__all__ = [
    "bundled_export_plugin_root",
    "create_bundled_export_plugin_registry",
    "create_export_plugin_registry",
    "discover_bundled_export_plugins",
]
