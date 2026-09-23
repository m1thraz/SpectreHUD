"""Host registry factory for bundled export-plugin manifests."""

from pathlib import Path

from core.export_plugins.discovery import PluginDiscoveryResult, discover_export_plugins
from core.export_plugins.registry import ExportPluginRegistry


def bundled_export_plugin_root() -> Path:
    return Path(__file__).with_name("bundled")


def discover_bundled_export_plugins() -> PluginDiscoveryResult:
    return discover_export_plugins((bundled_export_plugin_root(),))


def create_bundled_export_plugin_registry() -> ExportPluginRegistry:
    discovery = discover_bundled_export_plugins()
    return ExportPluginRegistry(discovery.descriptors)


__all__ = [
    "bundled_export_plugin_root",
    "create_bundled_export_plugin_registry",
    "discover_bundled_export_plugins",
]
