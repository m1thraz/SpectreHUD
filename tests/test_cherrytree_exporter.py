import pytest

from core.exporters import CherryTreeExporter, ExternalExportError


@pytest.fixture
def package_workspace(tmp_path):
    project = tmp_path / "Forest"
    (project / "loot").mkdir(parents=True)
    (project / "loot" / "proof.png").write_bytes(b"png")
    return project, tmp_path / "exports"


def test_cherrytree_export_creates_portable_html_package(package_workspace):
    project, output = package_workspace
    result = CherryTreeExporter(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown="# Report\n\n![Proof](loot/proof.png)",
        loot_entries=[
            {"id": "loot-1", "type": "note", "title": "Finding", "content": "SMB signing disabled"}
        ],
    )

    package = output / "Forest"
    assert result.note_path == package / "report.html"
    assert (package / "loot.html").exists()
    assert (package / "images" / "proof.png").read_bytes() == b"png"
    assert 'src="images/proof.png"' in result.note_path.read_text(encoding="utf-8")
    assert "SMB signing disabled" in (package / "loot.html").read_text(encoding="utf-8")


def test_cherrytree_report_icon_uses_generic_image_pipeline(package_workspace):
    project, output = package_workspace
    icon = project / "assets" / "icons" / "fa5s_key_32.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"png-icon")

    result = CherryTreeExporter(output).export_package(
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
    with pytest.raises(ExternalExportError):
        CherryTreeExporter(output).export_package(
            project_name="../escape", project_dir=project, report_markdown="x", loot_entries=[]
        )
    with pytest.raises(ExternalExportError):
        CherryTreeExporter(output).export_package(
            project_name="Forest",
            project_dir=project / "missing",
            report_markdown="x",
            loot_entries=[],
        )


def test_cherrytree_export_keeps_missing_image_as_report_warning(package_workspace):
    project, output = package_workspace
    result = CherryTreeExporter(output).export_package(
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
    md = "<!-- spectre:loot:loot_99:deadbeef1234 -->\n# Report\n\nFinding text."
    result = CherryTreeExporter(output).export_package(
        project_name="Forest",
        project_dir=project,
        report_markdown=md,
        loot_entries=[],
    )
    content = result.note_path.read_text(encoding="utf-8")
    assert "spectre:loot" not in content
    assert "Finding text." in content
