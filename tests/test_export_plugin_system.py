"""Invariant tests for the internal V1 export-plugin boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.export_plugins import (
    ExportCapability,
    ExportDataRequirement,
    ExportPluginMetadata,
    ExportPluginRegistry,
    FieldKind,
    LootExportEntry,
    PluginAvailabilityCode,
    PluginText,
    ProjectExportContext,
    ReportExportContext,
    ReportExportRequest,
    discover_export_plugins,
    default_external_export_plugin_roots,
    create_export_plugin_registry,
)
from core.config import ConfigManager
from core.storage import InMemoryStorageBackend


def _manifest(
    plugin_id: str,
    loader: str,
    *,
    capabilities: list[str] | None = None,
    accent: str | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "plugin_id": plugin_id,
        "display_name": {
            "translation_key": f"plugins.{plugin_id}.name",
            "fallback": "Sample Export",
        },
        "description": {
            "translation_key": f"plugins.{plugin_id}.description",
            "fallback": "Sample export plugin",
        },
        "badge": "SAMPLE",
        "icon_name": "fa5s.file-export",
        "capabilities": capabilities or ["report_export"],
        "report_data_requirements": ["report_font"],
        "configuration_fields": [
            {
                "key": "destination",
                "label": {
                    "translation_key": f"plugins.{plugin_id}.destination",
                    "fallback": "Destination",
                },
                "kind": "directory",
                "required": True,
                "default": "",
            }
        ],
        "execution_fields": [],
        "loader": loader,
    }
    if accent is not None:
        manifest["accent"] = accent
    return manifest


def _write_manifest(root: Path, folder: str, payload: dict[str, object]) -> Path:
    plugin_dir = root / folder
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "plugin.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_valid_plugin_module(
    root: Path,
    module_name: str,
    plugin_id: str,
    *,
    with_loot: bool = False,
    metadata_loot: bool | None = None,
    runtime_plugin_id: str | None = None,
) -> None:
    declares_loot = with_loot if metadata_loot is None else metadata_loot
    capabilities = (
        "frozenset({ExportCapability.REPORT_EXPORT, ExportCapability.LOOT_APPEND})"
        if declares_loot
        else "frozenset({ExportCapability.REPORT_EXPORT})"
    )
    loot_capability = "LootCapability()" if with_loot else "None"
    source = f'''\
from core.export_plugins import (
    ExportCapability,
    ExportDataRequirement,
    ExportPluginMetadata,
    FieldKind,
    LoadedExportCapabilities,
    PluginAvailability,
    PluginAvailabilityCode,
    PluginField,
    PluginText,
)
from core.reporting import ExportResult


class ReportCapability:
    def export_report(self, request):
        return ExportResult.success()


class LootCapability:
    def append_loot(self, request):
        return ExportResult.success()


class SamplePlugin:
    metadata = ExportPluginMetadata(
        plugin_id={runtime_plugin_id or plugin_id!r},
        display_name=PluginText("plugins.{plugin_id}.name", "Sample Export"),
        description=PluginText("plugins.{plugin_id}.description", "Sample export plugin"),
        badge="SAMPLE",
        icon_name="fa5s.file-export",
        capabilities={capabilities},
        report_data_requirements=frozenset({{ExportDataRequirement.REPORT_FONT}}),
        configuration_fields=(
            PluginField(
                key="destination",
                label=PluginText("plugins.{plugin_id}.destination", "Destination"),
                kind=FieldKind.DIRECTORY,
                required=True,
            ),
        ),
    )
    capabilities = LoadedExportCapabilities(
        report_export=ReportCapability(),
        loot_append={loot_capability},
    )

    def validate_configuration(self, values):
        if not values.get("destination"):
            return PluginAvailability(
                PluginAvailabilityCode.INVALID_CONFIGURATION,
                "Destination is required.",
            )
        return PluginAvailability(PluginAvailabilityCode.AVAILABLE)


def create_plugin():
    return SamplePlugin()
'''
    (root / f"{module_name}.py").write_text(source, encoding="utf-8")


def test_contract_snapshots_are_immutable_and_accent_is_optional() -> None:
    metadata = ExportPluginMetadata(
        plugin_id="sample.export",
        display_name=PluginText("plugins.sample.name", "Sample"),
        description=PluginText("plugins.sample.description", "Sample exporter"),
        badge="SAMPLE",
        icon_name="fa5s.file-export",
        capabilities=frozenset({ExportCapability.REPORT_EXPORT}),
        report_data_requirements=frozenset(),
    )
    assert metadata.accent is None

    values = {"destination": "C:/exports"}
    request = ReportExportRequest(
        context=ReportExportContext(
            project=ProjectExportContext("Forest", Path("C:/projects/Forest")),
            markdown="# Report",
        ),
        configuration=values,
        execution_values={},
    )
    values["destination"] = "C:/changed"

    assert request.configuration["destination"] == "C:/exports"
    with pytest.raises(TypeError):
        request.configuration["destination"] = "C:/mutated"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        request.context.markdown = "changed"  # type: ignore[misc]


def test_loot_context_contains_only_the_documented_export_fields() -> None:
    assert set(LootExportEntry.__dataclass_fields__) == {
        "entry_id",
        "entry_type",
        "title",
        "content",
        "recommendation",
        "target_ip",
        "timestamp",
    }


def test_discovery_reads_passive_metadata_without_importing_plugin_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = tmp_path / "imported.txt"
    module_name = "passive_export_plugin"
    (tmp_path / f"{module_name}.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('imported')\n"
        "raise RuntimeError('must not run during discovery')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "passive",
        _manifest("sample.passive", f"{module_name}:create", accent="purple"),
    )

    discovery = discover_export_plugins([tmp_path])

    assert [item.metadata.plugin_id for item in discovery.descriptors] == ["sample.passive"]
    assert discovery.descriptors[0].metadata.accent == "purple"
    assert discovery.issues == ()
    assert not sentinel.exists()
    assert module_name not in sys.modules


def test_discovery_isolates_invalid_manifests_and_rejects_unknown_extensions(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path,
        "valid",
        _manifest("sample.valid", "sample_valid_plugin:create_plugin"),
    )
    invalid = _manifest("sample.future", "sample_future_plugin:create_plugin")
    invalid["feature_hooks"] = ["startup"]
    _write_manifest(tmp_path, "future", invalid)
    broken_dir = tmp_path / "broken"
    broken_dir.mkdir()
    (broken_dir / "plugin.json").write_text("{not-json", encoding="utf-8")

    discovery = discover_export_plugins([tmp_path])

    assert [item.metadata.plugin_id for item in discovery.descriptors] == ["sample.valid"]
    assert len(discovery.issues) == 2
    assert any("feature_hooks" in issue.message for issue in discovery.issues)
    assert any("JSON" in issue.message for issue in discovery.issues)


def test_registry_loads_on_demand_caches_instance_and_validates_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = "valid_export_plugin"
    _write_valid_plugin_module(tmp_path, module_name, "sample.valid")
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "valid",
        _manifest("sample.valid", f"{module_name}:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    assert module_name not in sys.modules
    assert registry.get_descriptor("sample.valid") is not None
    assert registry.get_descriptor("sample.missing") is None
    assert registry.load("sample.missing") is None

    loaded = registry.load("sample.valid")
    assert loaded is not None
    assert loaded.availability.code is PluginAvailabilityCode.AVAILABLE
    assert loaded.plugin is not None
    assert module_name in sys.modules
    assert registry.load("sample.valid").plugin is loaded.plugin

    invalid = registry.availability("sample.valid", {})
    assert invalid is not None
    assert invalid.code is PluginAvailabilityCode.INVALID_CONFIGURATION
    available = registry.availability("sample.valid", {"destination": "C:/exports"})
    assert available is not None
    assert available.code is PluginAvailabilityCode.AVAILABLE


def test_registry_loads_plugin_package_relative_to_its_manifest_without_sys_path_setup(
    tmp_path: Path,
) -> None:
    module_name = "portable_sample_plugin"
    plugin_dir = tmp_path / "portable"
    package_dir = plugin_dir / module_name
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    _write_valid_plugin_module(package_dir, "plugin", "sample.portable")
    _write_manifest(
        tmp_path,
        "portable",
        _manifest("sample.portable", f"{module_name}.plugin:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    assert str(plugin_dir) not in sys.path
    loaded = registry.load("sample.portable")

    assert loaded is not None and loaded.plugin is not None
    assert loaded.availability.code is PluginAvailabilityCode.AVAILABLE
    assert str(plugin_dir) in sys.path


def test_default_external_roots_cover_portable_windows_user_and_linux_system_locations(
    tmp_path: Path,
) -> None:
    environment = {
        "LOCALAPPDATA": str(tmp_path / "Local"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
    }

    windows = default_external_export_plugin_roots(
        system_name="Windows",
        environ=environment,
        home=tmp_path,
        executable=tmp_path / "portable" / "SpectreHUD.exe",
        frozen=True,
    )
    linux = default_external_export_plugin_roots(
        system_name="Linux",
        environ=environment,
        home=tmp_path,
        executable=Path("/usr/bin/spectrehud"),
        frozen=True,
    )

    assert windows == (
        tmp_path / "portable" / "plugins",
        tmp_path / "Local" / "SpectreHUD" / "plugins",
    )
    assert linux == (
        Path("/usr/lib/spectrehud/plugins"),
        tmp_path / "xdg-data" / "spectrehud" / "plugins",
    )


def test_combined_registry_keeps_bundled_plugin_ids_reserved(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "collision",
        _manifest("spectrehud.obsidian", "collision_plugin:create_plugin"),
    )
    _write_manifest(
        tmp_path,
        "external",
        _manifest("sample.external", "external_plugin:create_plugin"),
    )

    registry = create_export_plugin_registry(external_roots=(tmp_path,))

    descriptors = {item.metadata.plugin_id: item for item in registry.descriptors}
    assert set(descriptors) == {
        "spectrehud.cherrytree",
        "spectrehud.obsidian",
        "sample.external",
    }
    assert descriptors["spectrehud.obsidian"].loader_reference.startswith(
        "core.export_plugins.bundled.obsidian"
    )


def test_optional_loot_capability_must_match_passive_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = "loot_export_plugin"
    _write_valid_plugin_module(tmp_path, module_name, "sample.loot", with_loot=True)
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "loot",
        _manifest(
            "sample.loot",
            f"{module_name}:create_plugin",
            capabilities=["report_export", "loot_append"],
        ),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load("sample.loot")

    assert loaded is not None and loaded.plugin is not None
    assert loaded.plugin.capabilities.loot_append is not None


@pytest.mark.parametrize(
    ("declared_loot", "runtime_loot"),
    [(True, False), (False, True)],
)
def test_capability_declaration_mismatch_is_a_controlled_load_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared_loot: bool,
    runtime_loot: bool,
) -> None:
    suffix = f"{int(declared_loot)}_{int(runtime_loot)}"
    plugin_id = f"sample.mismatch.{suffix}"
    module_name = f"mismatch_export_plugin_{suffix}"
    _write_valid_plugin_module(
        tmp_path,
        module_name,
        plugin_id,
        with_loot=runtime_loot,
        metadata_loot=declared_loot,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    capabilities = ["report_export", "loot_append"] if declared_loot else ["report_export"]
    _write_manifest(
        tmp_path,
        suffix,
        _manifest(plugin_id, f"{module_name}:create_plugin", capabilities=capabilities),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load(plugin_id)

    assert loaded is not None
    assert loaded.plugin is None
    assert loaded.availability.code is PluginAvailabilityCode.LOAD_FAILED
    assert loaded.availability.details is not None
    assert "capabil" in loaded.availability.details.casefold()


def test_plugin_identity_mismatch_is_a_controlled_load_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = "wrong_identity_export_plugin"
    _write_valid_plugin_module(
        tmp_path,
        module_name,
        "sample.expected",
        runtime_plugin_id="sample.other",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "wrong-id",
        _manifest("sample.expected", f"{module_name}:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load("sample.expected")

    assert loaded is not None
    assert loaded.plugin is None
    assert loaded.availability.code is PluginAvailabilityCode.LOAD_FAILED
    assert loaded.availability.details is not None
    assert "identity" in loaded.availability.details.casefold()


def test_missing_optional_dependency_is_isolated_and_classified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_name = "dependency_export_plugin"
    (tmp_path / f"{module_name}.py").write_text(
        "import spectrehud_dependency_that_does_not_exist\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "dependency",
        _manifest("sample.dependency", f"{module_name}:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load("sample.dependency")

    assert loaded is not None
    assert loaded.plugin is None
    assert loaded.availability.code is PluginAvailabilityCode.MISSING_DEPENDENCY
    assert "spectrehud_dependency_that_does_not_exist" in loaded.availability.message


def test_broken_plugin_does_not_prevent_another_plugin_from_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_module = "isolated_good_export_plugin"
    broken_module = "isolated_broken_export_plugin"
    _write_valid_plugin_module(tmp_path, good_module, "sample.good")
    (tmp_path / f"{broken_module}.py").write_text(
        "raise RuntimeError('broken plugin')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "good",
        _manifest("sample.good", f"{good_module}:create_plugin"),
    )
    _write_manifest(
        tmp_path,
        "broken",
        _manifest("sample.broken", f"{broken_module}:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    broken = registry.load("sample.broken")
    good = registry.load("sample.good")

    assert broken is not None
    assert broken.availability.code is PluginAvailabilityCode.LOAD_FAILED
    assert good is not None
    assert good.availability.code is PluginAvailabilityCode.AVAILABLE
    assert good.plugin is not None


@pytest.mark.parametrize(
    ("exception", "details"),
    [
        ("ImportError('DLL load failed while importing etree')", "ImportError"),
        ("OSError('native dependency has an incompatible architecture')", "OSError"),
    ],
)
def test_incompatible_native_dependency_is_a_controlled_load_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception: str,
    details: str,
) -> None:
    module_name = "incompatible_native_export_plugin"
    (tmp_path / f"{module_name}.py").write_text(
        f"raise {exception}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    _write_manifest(
        tmp_path,
        "incompatible",
        _manifest("sample.incompatible", f"{module_name}:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load("sample.incompatible")

    assert loaded is not None
    assert loaded.plugin is None
    assert loaded.availability.code is PluginAvailabilityCode.LOAD_FAILED
    assert loaded.availability.details is not None
    assert details in loaded.availability.details


def test_manifest_rejects_import_and_undocumented_capabilities(tmp_path: Path) -> None:
    import_manifest = _manifest(
        "sample.import",
        "sample_import_plugin:create_plugin",
        capabilities=["report_export", "import"],
    )
    _write_manifest(tmp_path, "import", import_manifest)

    discovery = discover_export_plugins([tmp_path])

    assert discovery.descriptors == ()
    assert len(discovery.issues) == 1
    assert "import" in discovery.issues[0].message


def test_manifest_rejects_configuration_field_kinds_beyond_v1(tmp_path: Path) -> None:
    manifest = _manifest("sample.secret", "sample_secret_plugin:create_plugin")
    fields = manifest["configuration_fields"]
    assert isinstance(fields, list)
    fields[0]["kind"] = "secret"
    _write_manifest(tmp_path, "secret", manifest)

    discovery = discover_export_plugins([tmp_path])

    assert discovery.descriptors == ()
    assert len(discovery.issues) == 1
    assert "secret" in discovery.issues[0].message


@pytest.mark.parametrize(
    "accent",
    [
        {"stylesheet": "QWidget { color: red; }"},
        "QWidget { color: red; }",
    ],
)
def test_accent_rejects_style_objects_or_stylesheet_content(
    tmp_path: Path, accent: object
) -> None:
    manifest = _manifest("sample.styled", "sample_styled_plugin:create_plugin")
    manifest["accent"] = accent
    _write_manifest(tmp_path, "styled", manifest)

    discovery = discover_export_plugins([tmp_path])

    assert discovery.descriptors == ()
    assert len(discovery.issues) == 1
    assert "accent" in discovery.issues[0].message


def test_contract_import_is_headless_and_does_not_load_concrete_exporters() -> None:
    code = (
        "import sys\n"
        "import core.export_plugins\n"
        "assert not [name for name in sys.modules if name.startswith('PyQt6')]\n"
        "assert 'core.exporters.obsidian' not in sys.modules\n"
        "assert 'core.export_plugins.bundled.obsidian.plugin' not in sys.modules\n"
        "assert 'core.exporters.cherrytree' not in sys.modules\n"
        "assert 'core.export_plugins.bundled.cherrytree.plugin' not in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_bundled_plugins_are_discovered_passively_and_loaded_independently() -> None:
    code = (
        "import sys\n"
        "from core.export_plugins import (\n"
        "    PluginAvailabilityCode, create_bundled_export_plugin_registry,\n"
        ")\n"
        "obsidian = 'core.export_plugins.bundled.obsidian.plugin'\n"
        "cherrytree = 'core.export_plugins.bundled.cherrytree.plugin'\n"
        "registry = create_bundled_export_plugin_registry()\n"
        "assert [item.metadata.plugin_id for item in registry.descriptors] == "
        "['spectrehud.cherrytree', 'spectrehud.obsidian']\n"
        "assert obsidian not in sys.modules and cherrytree not in sys.modules\n"
        "loaded = registry.load('spectrehud.obsidian')\n"
        "assert loaded is not None and loaded.plugin is not None\n"
        "assert loaded.availability.code is PluginAvailabilityCode.AVAILABLE\n"
        "assert obsidian in sys.modules and cherrytree not in sys.modules\n"
        "loaded = registry.load('spectrehud.cherrytree')\n"
        "assert loaded is not None and loaded.plugin is not None\n"
        "assert loaded.availability.code is PluginAvailabilityCode.AVAILABLE\n"
        "assert cherrytree in sys.modules\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_bundled_cherrytree_declares_only_its_real_v1_requirements() -> None:
    from core.export_plugins import create_bundled_export_plugin_registry

    registry = create_bundled_export_plugin_registry()
    descriptor = registry.get_descriptor("spectrehud.cherrytree")
    assert descriptor is not None
    metadata = descriptor.metadata
    assert metadata.capabilities == frozenset({ExportCapability.REPORT_EXPORT})
    assert metadata.report_data_requirements == frozenset(
        {ExportDataRequirement.LOOT, ExportDataRequirement.REPORT_FONT}
    )
    assert metadata.configuration_fields == ()
    assert len(metadata.execution_fields) == 1
    assert metadata.execution_fields[0].kind is FieldKind.DIRECTORY

    loaded = registry.load("spectrehud.cherrytree")
    assert loaded is not None and loaded.plugin is not None
    assert loaded.plugin.capabilities.loot_append is None


def test_missing_implementation_module_is_a_controlled_load_failure(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "missing",
        _manifest("sample.missing-module", "module_that_does_not_exist:create_plugin"),
    )
    registry = ExportPluginRegistry(discover_export_plugins([tmp_path]).descriptors)

    loaded = registry.load("sample.missing-module")

    assert loaded is not None
    assert loaded.plugin is None
    assert loaded.availability.code is PluginAvailabilityCode.LOAD_FAILED


def test_contract_field_types_remain_the_three_approved_v1_types() -> None:
    assert set(FieldKind) == {FieldKind.TEXT, FieldKind.DIRECTORY, FieldKind.BOOLEAN}
    assert set(ExportCapability) == {
        ExportCapability.REPORT_EXPORT,
        ExportCapability.LOOT_APPEND,
    }
    assert set(ExportDataRequirement) == {
        ExportDataRequirement.PROJECT_NETWORK,
        ExportDataRequirement.LOOT,
        ExportDataRequirement.REPORT_FONT,
    }


def test_legacy_obsidian_settings_migrate_under_stable_plugin_id() -> None:
    storage = InMemoryStorageBackend(
        initial_data={
            "config": {
                "obsidian_vault_path": "C:/Notes",
                "obsidian_export_folder": "Exports/SpectreHUD",
                "obsidian_open_after_export": True,
            }
        }
    )

    config = ConfigManager(storage=storage)

    assert config.get("export_plugins") == {
        "spectrehud.obsidian": {
            "obsidian_vault_path": "C:/Notes",
            "obsidian_export_folder": "Exports/SpectreHUD",
            "obsidian_open_after_export": True,
        }
    }
    persisted = storage.load_json("config")
    assert all(
        key not in persisted
        for key in (
            "obsidian_vault_path",
            "obsidian_export_folder",
            "obsidian_open_after_export",
        )
    )
