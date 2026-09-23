import pytest

from core.export_plugins import (
    LootAppendRequest,
    LootExportEntry,
    PluginAvailabilityCode,
    ProjectExportContext,
    ProjectNetworkContext,
    ReportExportContext,
    ReportExportRequest,
    create_bundled_export_plugin_registry,
)


class ObsidianPluginHarness:
    """Exercise exporter behavior only through the V1 plugin capabilities."""

    def __init__(self, vault, export_folder="CTF/SpectreHUD", *, open_after_export=False):
        self.configuration = {
            "obsidian_vault_path": str(vault),
            "obsidian_export_folder": export_folder,
            "obsidian_open_after_export": open_after_export,
        }
        loaded = create_bundled_export_plugin_registry().load("spectrehud.obsidian")
        assert loaded is not None and loaded.plugin is not None
        self.plugin = loaded.plugin

    def export_report(
        self,
        *,
        project_name,
        project_dir,
        markdown,
        project_state=None,
    ):
        state = project_state or {}
        request = ReportExportRequest(
            context=ReportExportContext(
                project=ProjectExportContext(project_name, project_dir),
                markdown=markdown,
                network=ProjectNetworkContext(
                    str(state.get("target_ip", "")),
                    str(state.get("attacker_ip", "")),
                ),
            ),
            configuration=self.configuration,
            execution_values={},
        )
        return self.plugin.capabilities.report_export.export_report(request)

    def append_loot(self, *, project_name, entries, note_path=None):
        del note_path
        snapshots = tuple(
            LootExportEntry(
                entry_id=str(entry.get("id", "")),
                entry_type=str(entry.get("type", "note")),
                title=str(entry.get("title", "Untitled loot")),
                content=str(entry.get("content", "")),
                recommendation=str(entry.get("recommendation", "") or ""),
                target_ip=str(entry.get("target_ip", "")),
                timestamp=str(entry.get("timestamp", "")),
            )
            for entry in entries
        )
        capability = self.plugin.capabilities.loot_append
        assert capability is not None
        return capability.append_loot(
            LootAppendRequest(
                project=ProjectExportContext(project_name, self.configuration_path.parent),
                entries=snapshots,
                configuration=self.configuration,
            )
        )

    @property
    def configuration_path(self):
        from pathlib import Path

        return Path(str(self.configuration["obsidian_vault_path"]))


@pytest.fixture
def workspace(tmp_path):
    vault = tmp_path / "Vault"
    vault.mkdir()
    project = tmp_path / "Project"
    (project / "loot").mkdir(parents=True)
    return vault, project


def test_obsidian_report_export_creates_note_frontmatter_and_attachments(workspace):
    vault, project = workspace
    image = project / "loot" / "proof.png"
    image.write_bytes(b"png")
    exporter = ObsidianPluginHarness(vault, "CTF/SpectreHUD")

    result = exporter.export_report(
        project_name="Forest",
        project_dir=project,
        markdown="# Report\n\n![Proof](loot/proof.png)",
        project_state={
            "target_ip": "10.10.10.161",
            "attacker_ip": "10.10.14.5",
            "password": "never-export",
        },
    )

    assert result.is_success is True
    assert result.artifacts[0].path == vault / "CTF" / "SpectreHUD" / "Forest" / "Forest.md"
    assert len(result.artifacts) == 2
    assert result.artifacts[0].format == "markdown"
    assert result.artifacts[1].format == "attachment"
    content = result.artifacts[0].path.read_text(encoding="utf-8")
    assert 'target: "10.10.10.161"' in content
    assert "password" not in content
    assert "attachments/proof.png" in content
    assert (result.artifacts[0].path.parent / "attachments" / "proof.png").read_bytes() == b"png"


def test_obsidian_report_translates_spacers_to_renderable_breaks(workspace):
    vault, project = workspace
    result = ObsidianPluginHarness(vault).export_report(
        project_name="Forest",
        project_dir=project,
        markdown="Before\n\n<!-- spectre:spacer:medium -->\n\nAfter",
    )

    content = result.artifacts[0].path.read_text(encoding="utf-8")
    assert "spectre:spacer" not in content
    assert "<br>\n<br>" in content


def test_obsidian_report_strips_internal_section_markers(workspace):
    vault, project = workspace
    markdown = (
        "<!-- spectre:section:start:executive_summary -->\n\n"
        "<!-- spectre:finding:start:loot_1 -->\n"
        "## Summary\n\nManual content\n\n"
        "<!-- spectre:finding:end:loot_1 -->\n"
        "<!-- spectre:section:end:executive_summary -->"
    )
    result = ObsidianPluginHarness(vault).export_report(
        project_name="Forest", project_dir=project, markdown=markdown
    )
    content = result.artifacts[0].path.read_text(encoding="utf-8")
    assert "spectre:section" not in content
    assert "spectre:finding" not in content
    assert "Manual content" in content


def test_obsidian_report_icon_uses_generic_attachment_pipeline(workspace):
    vault, project = workspace
    icon = project / "assets" / "icons" / "fa5s_key_32.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"png-icon")

    result = ObsidianPluginHarness(vault).export_report(
        project_name="Forest",
        project_dir=project,
        markdown="![Credential](assets/icons/fa5s_key_32.png)",
    )

    content = result.artifacts[0].path.read_text(encoding="utf-8")
    assert "![Credential](attachments/fa5s_key_32.png)" in content
    assert (result.artifacts[0].path.parent / "attachments" / "fa5s_key_32.png").read_bytes() == b"png-icon"


def test_obsidian_export_preserves_existing_note_by_default(workspace):
    vault, project = workspace
    exporter = ObsidianPluginHarness(vault)
    first = exporter.export_report(project_name="Forest", project_dir=project, markdown="one")
    second = exporter.export_report(project_name="Forest", project_dir=project, markdown="two")

    assert first.artifacts[0].path.read_text(encoding="utf-8").endswith("one")
    assert second.artifacts[0].path.name == "Forest_2.md"


def test_obsidian_export_rejects_unsafe_paths_and_symlink_attachment(workspace):
    """Export destinations and copied attachments must stay inside the selected vault."""
    vault, project = workspace
    invalid = ObsidianPluginHarness(vault, "../../outside")
    availability = invalid.plugin.validate_configuration(invalid.configuration)
    assert availability.code is PluginAvailabilityCode.INVALID_CONFIGURATION

    external = vault.parent / "outside.png"
    external.write_bytes(b"not-safe")
    link = project / "loot" / "escape.png"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("Symlinks are unavailable on this host")

    result = ObsidianPluginHarness(vault).export_report(
        project_name="Forest", project_dir=project, markdown="![Escape](loot/escape.png)"
    )
    assert "attachments/escape.png" not in result.artifacts[0].path.read_text(encoding="utf-8")
    assert result.warnings


def test_obsidian_append_loot_preserves_manual_content_and_deduplicates(workspace):
    vault, project = workspace
    exporter = ObsidianPluginHarness(vault)
    note = exporter.export_report(
        project_name="Forest", project_dir=project, markdown="# Manual report"
    ).artifacts[0].path
    entry = {"id": "loot-1", "type": "credentials", "title": "Admin", "content": "admin:secret"}

    first = exporter.append_loot(project_name="Forest", entries=[entry], note_path=note)
    second = exporter.append_loot(project_name="Forest", entries=[entry], note_path=note)

    content = note.read_text(encoding="utf-8")
    assert "# Manual report" in content
    assert content.count("spectrehud-entry:loot-1") == 1
    assert not first.skipped_entry_ids
    assert second.skipped_entry_ids == ("loot-1",)


def test_obsidian_loot_export_includes_real_recommendation(workspace):
    vault, _project = workspace
    exporter = ObsidianPluginHarness(vault)
    exporter.export_report(project_name="Forest", project_dir=_project, markdown="# Report")
    entry = {
        "id": "loot-remediation",
        "type": "note",
        "title": "Authentication bypass",
        "content": "Invalid tokens were accepted.",
        "recommendation": "Reject invalid tokens and rotate signing keys.",
    }

    result = exporter.append_loot(project_name="Forest", entries=[entry])
    content = result.artifacts[0].path.read_text(encoding="utf-8")

    assert "#### Recommendation" in content
    assert "Reject invalid tokens and rotate signing keys." in content
    assert "spectre:loot" not in content


def test_obsidian_append_loot_reports_skipped_ids_from_generator(workspace):
    vault, project = workspace
    exporter = ObsidianPluginHarness(vault)
    note = exporter.export_report(
        project_name="Forest", project_dir=project, markdown="# Manual report"
    ).artifacts[0].path
    existing_entry = {
        "id": "loot-1",
        "type": "credentials",
        "title": "Admin",
        "content": "admin:secret",
    }
    new_entry = {
        "id": "loot-2",
        "type": "note",
        "title": "Host",
        "content": "10.10.10.8",
    }
    exporter.append_loot(project_name="Forest", entries=[existing_entry], note_path=note)

    entries = (entry for entry in (existing_entry, new_entry))
    result = exporter.append_loot(project_name="Forest", entries=entries, note_path=note)

    content = note.read_text(encoding="utf-8")
    assert result.skipped_entry_ids == ("loot-1",)
    assert content.count("spectrehud-entry:loot-1") == 1
    assert content.count("spectrehud-entry:loot-2") == 1


def test_suggested_open_uri_is_url_encoded(workspace):
    vault, project = workspace
    exporter = ObsidianPluginHarness(vault, "CTF Notes", open_after_export=True)
    result = exporter.export_report(project_name="Forest", project_dir=project, markdown="report")

    open_uri = str(result.metadata["suggested_open_uri"])
    assert "vault=Vault" in open_uri
    assert "file=CTF+Notes%2FForest%2FForest.md" in open_uri


def test_suggested_open_uri_is_omitted_when_open_after_export_is_disabled(workspace):
    vault, project = workspace
    result = ObsidianPluginHarness(vault).export_report(
        project_name="Forest", project_dir=project, markdown="report"
    )

    assert "suggested_open_uri" not in result.metadata


def test_obsidian_report_export_strips_spectre_loot_markers(workspace):
    """Ticket 8 & 40: Obsidian report export removes internal spectre:loot: markers."""
    vault, project = workspace
    exporter = ObsidianPluginHarness(vault)
    md = "<!-- spectre:loot:loot_123:deadbeef1234 -->\n# Findings\n<!-- user note -->\nDetails."
    result = exporter.export_report(project_name="Forest", project_dir=project, markdown=md)
    content = result.artifacts[0].path.read_text(encoding="utf-8")
    assert "spectre:loot" not in content
    assert "<!-- user note -->" in content
    assert "# Findings" in content
