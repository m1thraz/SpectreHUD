"""Public V1 API, compatibility, and localization invariants."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import pytest

from core.export_plugins import discover_export_plugins, parse_export_plugin_manifest
from spectrehud_plugin_api import EXPORT_PLUGIN_API_VERSION, PluginText


def _manifest() -> dict[str, object]:
    return {
        "api_version": 1,
        "plugin_version": "1.4.0",
        "minimum_host_version": "2.2.2",
        "plugin_id": "sample.public",
        "display_name": {
            "translation_key": "plugins.sample.name",
            "fallback": "Sample Export",
        },
        "description": {
            "translation_key": "plugins.sample.description",
            "fallback": "Sample public exporter",
        },
        "badge": "SAMPLE",
        "icon_name": "fa5s.file-export",
        "capabilities": ["report_export"],
        "report_data_requirements": [],
        "configuration_fields": [],
        "execution_fields": [],
        "translations": {
            "de": {
                "plugins.sample.name": "Beispielexport",
                "plugins.sample.description": "Öffentlicher Beispielexporter",
            }
        },
        "loader": "sample_public.plugin:create_plugin",
    }


def test_public_api_is_headless_and_exposes_v1_contract() -> None:
    code = (
        "import sys\n"
        "import spectrehud_plugin_api as api\n"
        "assert api.EXPORT_PLUGIN_API_VERSION == 1\n"
        "assert api.ExportResult is not None\n"
        "assert api.strip_report_markers is not None\n"
        "assert not any(name.startswith('PyQt6') for name in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert EXPORT_PLUGIN_API_VERSION == 1


def test_manifest_versions_and_inline_catalog_are_part_of_passive_metadata() -> None:
    descriptor = parse_export_plugin_manifest(_manifest(), host_version="2.2.2")

    assert descriptor.metadata.api_version == 1
    assert descriptor.metadata.plugin_version == "1.4.0"
    assert descriptor.metadata.minimum_host_version == "2.2.2"
    assert descriptor.metadata.display_name.localized("de") == "Beispielexport"
    assert descriptor.metadata.display_name.localized("de-DE") == "Beispielexport"
    assert descriptor.metadata.display_name.localized("en") is None
    with pytest.raises(TypeError):
        descriptor.metadata.display_name.translations["de"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("api_version", 2, "API version"),
        ("plugin_version", "v1", "plugin_version"),
        ("minimum_host_version", "2.3.0", "requires SpectreHUD"),
    ],
)
def test_incompatible_or_invalid_versions_are_isolated_during_discovery(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    manifest = _manifest()
    manifest[field] = value
    plugin_dir = tmp_path / "sample"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    discovery = discover_export_plugins([tmp_path], host_version="2.2.2")

    assert discovery.descriptors == ()
    assert len(discovery.issues) == 1
    assert message in discovery.issues[0].message


def test_manifest_rejects_unknown_translation_keys() -> None:
    manifest = _manifest()
    translations = manifest["translations"]
    assert isinstance(translations, dict)
    translations["de"]["plugins.sample.typo"] = "Tippfehler"

    with pytest.raises(ValueError, match="unknown translation keys"):
        parse_export_plugin_manifest(manifest, host_version="2.2.2")


def test_plugin_text_localization_has_language_and_fallback_boundaries() -> None:
    text = PluginText(
        "plugins.sample.name",
        "Sample Export",
        translations={"de": "Beispielexport", "pt-br": "Exportação de exemplo"},
    )

    assert text.localized("de-DE") == "Beispielexport"
    assert text.localized("pt-BR") == "Exportação de exemplo"
    assert text.localized("fr") is None


def test_docx_reference_manifest_version_matches_its_package_metadata() -> None:
    project_root = Path(__file__).resolve().parents[1]
    plugin_root = project_root / "plugins-src" / "spectrehud-docx"
    manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((plugin_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert manifest["plugin_version"] == project["project"]["version"]
