"""Failure-contained lazy loading for discovered export plugins."""

from __future__ import annotations

from importlib import import_module
from typing import Iterable, Mapping, cast

from core.export_plugins.contract import (
    ExportCapability,
    ExportPlugin,
    ExportPluginDescriptor,
    ExportPluginMetadata,
    LoadedExportCapabilities,
    PluginAvailability,
    PluginAvailabilityCode,
    PluginLoadResult,
    PluginValue,
)


class ExportPluginRegistry:
    def __init__(self, descriptors: Iterable[ExportPluginDescriptor] = ()):
        self._descriptors: dict[str, ExportPluginDescriptor] = {}
        self._loaded: dict[str, PluginLoadResult] = {}
        for descriptor in descriptors:
            plugin_id = descriptor.metadata.plugin_id
            if plugin_id in self._descriptors:
                raise ValueError(f"Duplicate export plugin descriptor: {plugin_id}")
            self._descriptors[plugin_id] = descriptor

    @property
    def descriptors(self) -> tuple[ExportPluginDescriptor, ...]:
        return tuple(self._descriptors.values())

    def get_descriptor(self, plugin_id: str) -> ExportPluginDescriptor | None:
        return self._descriptors.get(plugin_id)

    def load(self, plugin_id: str) -> PluginLoadResult | None:
        descriptor = self._descriptors.get(plugin_id)
        if descriptor is None:
            return None
        if plugin_id in self._loaded:
            return self._loaded[plugin_id]

        result = self._load_descriptor(descriptor)
        self._loaded[plugin_id] = result
        return result

    def availability(
        self,
        plugin_id: str,
        configuration: Mapping[str, PluginValue],
    ) -> PluginAvailability | None:
        loaded = self.load(plugin_id)
        if loaded is None or loaded.plugin is None:
            return loaded.availability if loaded else None
        try:
            availability = loaded.plugin.validate_configuration(configuration)
            if not isinstance(availability, PluginAvailability):
                raise TypeError("validate_configuration() returned an invalid result")
            return availability
        except BaseException as exc:
            return PluginAvailability(
                PluginAvailabilityCode.LOAD_FAILED,
                "Plugin configuration validation failed.",
                f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _load_descriptor(descriptor: ExportPluginDescriptor) -> PluginLoadResult:
        module_name, factory_path = descriptor.loader_reference.split(":", 1)
        try:
            module = import_module(module_name)
            factory: object = module
            for part in factory_path.split("."):
                factory = getattr(factory, part)
            if not callable(factory):
                raise TypeError("Plugin loader reference is not callable.")
            plugin = factory()
            ExportPluginRegistry._validate_plugin(descriptor, plugin)
            return PluginLoadResult(
                descriptor,
                cast(ExportPlugin, plugin),
                PluginAvailability(PluginAvailabilityCode.AVAILABLE),
            )
        except ModuleNotFoundError as exc:
            missing_name = exc.name or "unknown dependency"
            code = (
                PluginAvailabilityCode.LOAD_FAILED
                if missing_name == module_name
                or module_name.startswith(f"{missing_name}.")
                or missing_name.startswith(f"{module_name.split('.', 1)[0]}.")
                else PluginAvailabilityCode.MISSING_DEPENDENCY
            )
            message = (
                f"Plugin implementation module is unavailable: {missing_name}."
                if code is PluginAvailabilityCode.LOAD_FAILED
                else f"Plugin dependency is unavailable: {missing_name}."
            )
            return PluginLoadResult(
                descriptor,
                None,
                PluginAvailability(code, message, f"ModuleNotFoundError: {exc}"),
            )
        except BaseException as exc:
            return PluginLoadResult(
                descriptor,
                None,
                PluginAvailability(
                    PluginAvailabilityCode.LOAD_FAILED,
                    "Plugin could not be loaded.",
                    f"{type(exc).__name__}: {exc}",
                ),
            )

    @staticmethod
    def _validate_plugin(descriptor: ExportPluginDescriptor, plugin: object) -> None:
        metadata = getattr(plugin, "metadata", None)
        if not isinstance(metadata, ExportPluginMetadata):
            raise TypeError("Plugin metadata does not implement the V1 contract.")
        if metadata.plugin_id != descriptor.metadata.plugin_id:
            raise ValueError("Loaded plugin identity does not match its passive descriptor.")
        if metadata != descriptor.metadata:
            raise ValueError("Loaded plugin metadata does not match its passive descriptor.")

        capabilities = getattr(plugin, "capabilities", None)
        if not isinstance(capabilities, LoadedExportCapabilities):
            raise TypeError("Plugin capabilities do not implement the V1 contract.")
        if not callable(getattr(capabilities.report_export, "export_report", None)):
            raise TypeError("Plugin does not provide the required report export capability.")
        has_loot = capabilities.loot_append is not None
        declares_loot = ExportCapability.LOOT_APPEND in metadata.capabilities
        if has_loot != declares_loot:
            raise ValueError("Loaded Loot capability does not match its passive declaration.")
        if has_loot and not callable(getattr(capabilities.loot_append, "append_loot", None)):
            raise TypeError("Plugin Loot capability is invalid.")
        if not callable(getattr(plugin, "validate_configuration", None)):
            raise TypeError("Plugin does not provide configuration validation.")


__all__ = ["ExportPluginRegistry"]
