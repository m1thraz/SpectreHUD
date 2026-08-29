from pathlib import Path

import pytest

from core.exporters import ExternalExportError, ObsidianExporter


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
    exporter = ObsidianExporter(vault, "CTF/SpectreHUD")

    result = exporter.export_report(
        project_name="Forest",
        project_dir=project,
        markdown="# Report\n\n![Proof](loot/proof.png)",
        project_state={"target_ip": "10.10.10.161", "attacker_ip": "10.10.14.5", "password": "never-export"},
    )

    assert result.note_path == vault / "CTF" / "SpectreHUD" / "Forest" / "Forest.md"
    content = result.note_path.read_text(encoding="utf-8")
    assert 'target: "10.10.10.161"' in content
    assert "password" not in content
    assert "attachments/proof.png" in content
    assert (result.note_path.parent / "attachments" / "proof.png").read_bytes() == b"png"


def test_obsidian_export_preserves_existing_note_by_default(workspace):
    vault, project = workspace
    exporter = ObsidianExporter(vault)
    first = exporter.export_report(project_name="Forest", project_dir=project, markdown="one")
    second = exporter.export_report(project_name="Forest", project_dir=project, markdown="two")

    assert first.note_path.read_text(encoding="utf-8").endswith("one")
    assert second.note_path.name == "Forest_2.md"


def test_obsidian_export_rejects_unsafe_paths_and_symlink_attachment(workspace):
    vault, project = workspace
    with pytest.raises(ExternalExportError):
        ObsidianExporter(vault, "../../outside")

    external = vault.parent / "outside.png"
    external.write_bytes(b"not-safe")
    link = project / "loot" / "escape.png"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("Symlinks are unavailable on this host")

    result = ObsidianExporter(vault).export_report(
        project_name="Forest", project_dir=project, markdown="![Escape](loot/escape.png)"
    )
    assert "attachments/escape.png" not in result.note_path.read_text(encoding="utf-8")
    assert result.warnings


def test_obsidian_append_loot_preserves_manual_content_and_deduplicates(workspace):
    vault, project = workspace
    exporter = ObsidianExporter(vault)
    note = exporter.export_report(project_name="Forest", project_dir=project, markdown="# Manual report").note_path
    entry = {"id": "loot-1", "type": "credentials", "title": "Admin", "content": "admin:secret"}

    first = exporter.append_loot(project_name="Forest", entries=[entry], note_path=note)
    second = exporter.append_loot(project_name="Forest", entries=[entry], note_path=note)

    content = note.read_text(encoding="utf-8")
    assert "# Manual report" in content
    assert content.count("spectrehud-entry:loot-1") == 1
    assert not first.skipped_entry_ids
    assert second.skipped_entry_ids == ("loot-1",)


def test_obsidian_uri_is_url_encoded(workspace):
    vault, project = workspace
    exporter = ObsidianExporter(vault, "CTF Notes")
    result = exporter.export_report(project_name="Forest", project_dir=project, markdown="report")

    assert "vault=Vault" in result.obsidian_uri
    assert "file=CTF+Notes%2FForest%2FForest.md" in result.obsidian_uri
