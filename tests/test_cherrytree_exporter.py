import pytest

from core.export_plugins import (
    LootExportEntry,
    ProjectExportContext,
    ReportExportContext,
    ReportExportRequest,
    create_bundled_export_plugin_registry,
)


class CherryTreePluginHarness:
    """Exercise package behavior only through the V1 report capability."""

    def __init__(self, output):
        self.output = output
        loaded = create_bundled_export_plugin_registry().load("spectrehud.cherrytree")
        assert loaded is not None and loaded.plugin is not None
        self.plugin = loaded.plugin

    def export_package(
        self,
        *,
        project_name,
        project_dir,
        report_markdown,
        loot_entries,
        report_font="segoe_ui",
    ):
        loot = tuple(
            LootExportEntry(
                entry_id=str(entry.get("id", "")),
                entry_type=str(entry.get("type", "note")),
                title=str(entry.get("title", "Untitled loot")),
                content=str(entry.get("content", "")),
                recommendation=str(entry.get("recommendation", "") or ""),
                target_ip=str(entry.get("target_ip", "")),
                timestamp=str(entry.get("timestamp", "")),
            )
            for entry in loot_entries
        )
        return self.plugin.capabilities.report_export.export_report(
            ReportExportRequest(
                context=ReportExportContext(
                    project=ProjectExportContext(project_name, project_dir),
                    markdown=report_markdown,
                    loot=loot,
                    report_font=report_font,
                ),
                configuration={},
                execution_values={"destination": str(self.output)},
            )
        )


@pytest.fixture
def package_workspace(tmp_path):
    project = tmp_path / "Forest"
    (project / "loot").mkdir(parents=True)
    (project / "loot" / "proof.png").write_bytes(b"png")
    return project, tmp_path / "exports"


def test_cherrytree_export_creates_portable_html_package(package_workspace):
    project, output = package_workspace
    result = CherryTreePluginHarness(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown="# Report\n\n![Proof](loot/proof.png)",
        loot_entries=[
            {
                "id": "loot-1",
                "type": "note",
                "title": "Finding",
                "content": "SMB signing disabled",
                "recommendation": "Require SMB signing on all managed hosts.",
            }
        ],
    )

    package = output / "Forest"
    assert result.is_success is True
    assert result.note_path == package / "report.html"
    assert (package / "loot.html").exists()
    assert (package / "images" / "proof.png").read_bytes() == b"png"
    assert 'src="images/proof.png"' in result.note_path.read_text(encoding="utf-8")
    assert "SMB signing disabled" in (package / "loot.html").read_text(encoding="utf-8")
    assert "Require SMB signing" in (package / "loot.html").read_text(encoding="utf-8")
    assert len(result.artifacts) == 3
    assert result.artifacts[0].path == package / "report.html"
    assert result.artifacts[0].format == "html"
    assert result.artifacts[1].path == package / "loot.html"
    assert result.artifacts[1].format == "html"
    assert result.artifacts[2].path == package / "images" / "proof.png"
    assert result.artifacts[2].format == "image"


def test_cherrytree_report_icon_uses_generic_image_pipeline(package_workspace):
    project, output = package_workspace
    icon = project / "assets" / "icons" / "fa5s_key_32.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"png-icon")

    result = CherryTreePluginHarness(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown="![Credential](assets/icons/fa5s_key_32.png)",
        loot_entries=[],
    )

    assert 'src="images/fa5s_key_32.png"' in result.note_path.read_text(encoding="utf-8")
    assert (result.note_path.parent / "images" / "fa5s_key_32.png").read_bytes() == b"png-icon"


def test_cherrytree_export_validates_name_and_existing_project(package_workspace):
    """Normal validation rejects invalid package names and missing source folders."""
    project, output = package_workspace
    invalid_name = CherryTreePluginHarness(output).export_package(
        project_name="../escape", project_dir=project, report_markdown="x", loot_entries=[]
    )
    missing_project = CherryTreePluginHarness(output).export_package(
        project_name="Forest",
        project_dir=project / "missing",
        report_markdown="x",
        loot_entries=[],
    )
    assert invalid_name.is_success is False
    assert missing_project.is_success is False


def test_cherrytree_export_keeps_missing_image_as_report_warning(package_workspace):
    project, output = package_workspace
    result = CherryTreePluginHarness(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown="![Missing](loot/missing.png)",
        loot_entries=[],
    )
    assert result.warnings
    assert "loot/missing.png" in result.note_path.read_text(encoding="utf-8")


def test_cherrytree_export_strips_spectre_loot_markers(package_workspace):
    """Ticket 9 & 40: CherryTree report.html must not contain spectre:loot: markers."""
    project, output = package_workspace
    md = (
        "<!-- spectre:section:start:executive_summary -->\n"
        "<!-- spectre:finding:start:loot_99 -->\n"
        "<!-- spectre:loot:loot_99:deadbeef1234 -->\n# Report\n\nFinding text.\n"
        "<!-- spectre:finding:end:loot_99 -->\n"
        "<!-- spectre:section:end:executive_summary -->"
    )
    result = CherryTreePluginHarness(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown=md,
        loot_entries=[],
    )
    content = result.note_path.read_text(encoding="utf-8")
    assert "spectre:loot" not in content
    assert "spectre:section" not in content
    assert "spectre:finding" not in content
    assert "Finding text." in content
