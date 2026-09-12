from pathlib import Path
import sys

from core.reporting import (
    ReportContext,
    ReportMetadata,
    ReportEvidenceItem,
    ReportFindingItem,
    ReportNarrativeSection,
    ReportWorkspaceDocument,
    TemplateRenderer,
    TemplateRepository,
)


def test_evidence_and_narrative_sections():
    """Test serialization of evidence items and narrative sections."""
    img_ev = ReportEvidenceItem(
        id="ev-1",
        type="screenshot",
        caption="Dashboard",
        content="images/dash.png",
    )
    assert img_ev.to_markdown() == "![Dashboard](images/dash.png)"

    code_ev = ReportEvidenceItem(
        id="ev-2",
        type="terminal",
        content="whoami && id",
    )
    assert "```bash\nwhoami && id\n```" == code_ev.to_markdown()

    narrative = ReportNarrativeSection(
        identity="scope_limitations",
        section_type="scope_limitations",
        title="Scope",
        content="## Scope\n\n- 192.168.1.1",
        page_break_before=True,
    )
    md = narrative.to_markdown()
    assert "<!-- spectre:pagebreak -->" in md
    assert "<!-- spectre:section:start:scope_limitations -->" in md
    assert "<!-- spectre:section:end:scope_limitations -->" in md


def test_core_isolation():
    """Ensure workspace_model remains pure core headless Python."""
    assert "core.reporting.workspace_model" in sys.modules
    import core.reporting.workspace_model as wm
    source = Path(wm.__file__).read_text(encoding="utf-8")
    assert "PyQt6" not in source
    assert "ui." not in source


def test_report_metadata_table_roundtrip():
    md_table = (
        "# Security Assessment Report: TargetCorp\n\n"
        "| Eigenschaft | Wert |\n"
        "|---|---|\n"
        "| **Auftraggeber / Client** | `TargetCorp GmbH` |\n"
        "| **Tester** | `SecLab Analyst` |\n"
        "| **Ziel(e) / Scope** | `10.10.10.0/24` |\n"
        "| **Testzeitraum** | `01.09.2026 - 05.09.2026` |\n"
        "| **Berichtsdatum** | `2026-09-12` |\n"
        "| **Klassifizierung** | `Vertraulich` |\n"
        "| **Report-Version** | `v1.2` |\n"
        "| **Audit-Id** | `AUD-9982` |\n"
    )
    meta = ReportMetadata.from_markdown_table(md_table)
    assert meta.title == "Security Assessment Report: TargetCorp"
    assert meta.client == "TargetCorp GmbH"
    assert meta.tester == "SecLab Analyst"
    assert meta.target_scope == "10.10.10.0/24"
    assert meta.timeframe == "01.09.2026 - 05.09.2026"
    assert meta.date == "2026-09-12"
    assert meta.classification == "Vertraulich"
    assert meta.version == "v1.2"
    assert meta.custom_fields.get("audit-id") == "AUD-9982"

    exported = meta.to_markdown_table(language="de")
    assert "TargetCorp GmbH" in exported
    assert "AUD-9982" in exported
    assert "| **Report-Version** | `v1.2` |" in exported


def test_report_finding_item_parsing_and_serialization():
    raw_finding_block = (
        "<!-- spectre:finding:start:loot-42 -->\n"
        "<!-- spectre:loot:recon:a1b2c3d4 -->\n"
        "### Remote Code Execution in Webhook Service\n\n"
        "**Severity:** [HIGH]  \n"
        "**Target:** `10.10.10.5`  \n"
        "**Phase:** Access  \n"
        "**Beobachtet:** `2026-09-12 14:00`  \n"
        "**Status:** Offen\n\n"
        "#### Beschreibung\n\n"
        "Unauthenticated command execution via crafted payload.\n\n"
        "```bash\n"
        "curl -X POST http://10.10.10.5/api -d '{\"cmd\": \"id\"}'\n"
        "```\n\n"
        "![PoC Screenshot](images/poc.png)\n\n"
        "#### Empfehlung\n\n"
        "Input validation and disable debug endpoints.\n\n"
        "#### Referenzen\n\n"
        "- CVE-2026-9999\n"
        "- https://example.com/advisory\n\n"
        "<!-- spectre:finding:end:loot-42 -->"
    )

    finding = ReportFindingItem.from_markdown(raw_finding_block, entry_id="loot-42", language="de")
    assert finding.id == "loot-42"
    assert finding.title == "Remote Code Execution in Webhook Service"
    assert finding.severity == "high"
    assert finding.phase == "access"
    assert "10.10.10.5" in finding.targets
    assert finding.status == "open"
    assert "Unauthenticated command execution" in finding.description
    assert "Input validation" in finding.recommendation
    assert len(finding.references) == 2
    assert "CVE-2026-9999" in finding.references
    assert len(finding.evidence_items) == 2
    assert finding.loot_marker == "<!-- spectre:loot:recon:a1b2c3d4 -->"

    # Test serialization
    serialized = finding.to_markdown(language="de")
    assert "<!-- spectre:finding:start:loot-42 -->" in serialized
    assert "<!-- spectre:finding:end:loot-42 -->" in serialized
    assert "<!-- spectre:loot:recon:a1b2c3d4 -->" in serialized
    assert "### Remote Code Execution in Webhook Service" in serialized
    assert "severity-high" in serialized and "HIGH" in serialized
    assert "#### Beschreibung" in serialized
    assert "#### Empfehlung" in serialized
    assert "#### Referenzen" in serialized
    assert "CVE-2026-9999" in serialized


def test_workspace_document_crud_and_filters():
    doc = ReportWorkspaceDocument(language="de")
    f1 = ReportFindingItem(id="f1", title="SQLi", severity="critical", phase="access")
    f2 = ReportFindingItem(id="f2", title="XSS", severity="medium", phase="recon")
    f3 = ReportFindingItem(id="f3", title="Info Leak", severity="info", phase="recon")

    doc.add_finding(f1)
    doc.add_finding(f2)
    doc.add_finding(f3)
    assert len(doc.findings) == 3

    # Retrieval
    assert doc.get_finding("f2") == f2
    assert doc.get_finding("f99") is None

    # Grouping by severity
    by_sev = doc.get_findings_by_severity()
    assert len(by_sev["critical"]) == 1
    assert len(by_sev["medium"]) == 1
    assert len(by_sev["info"]) == 1
    assert len(by_sev["high"]) == 0

    # Grouping by phase
    by_phase = doc.get_findings_by_phase()
    assert len(by_phase["access"]) == 1
    assert len(by_phase["recon"]) == 2

    # Update
    updated_f2 = ReportFindingItem(id="f2", title="Stored XSS", severity="high", phase="access")
    assert doc.update_finding(updated_f2) is True
    assert doc.get_finding("f2").title == "Stored XSS"
    assert doc.get_finding("f2").severity == "high"

    # Reorder
    doc.reorder_findings(["f3", "f1", "f2"])
    assert [f.id for f in doc.findings] == ["f3", "f1", "f2"]

    # Delete
    assert doc.remove_finding("f1") is True
    assert len(doc.findings) == 2
    assert doc.get_finding("f1") is None


def test_roundtrip_fidelity_with_template_renderer():
    """Renders a standard report with TemplateRenderer, parses into WorkspaceDocument, and verifies fidelity."""
    repo = TemplateRepository()
    template = repo.get_template("pentest_standard_de")
    assert template is not None

    context = ReportContext(
        project_name="MegaCorp Audit",
        target_ip="192.168.10.50",
        metadata={
            "client": "MegaCorp AG",
            "tester": "Lead Auditor",
            "timeframe": "KW 37",
            "classification": "Streng Vertraulich",
            "version": "v1.0",
        },
        loot_entries=[
            {
                "id": "loot-1",
                "title": "Default Credentials in Admin Panel",
                "severity": "critical",
                "category": "access",
                "type": "credentials",
                "content": "admin:admin123",
                "recommendation": "Change default passwords immediately.",
                "timestamp": "2026-09-12 10:00",
                "target_ip": "192.168.10.50",
            },
            {
                "id": "loot-2",
                "title": "Nmap Scan Results",
                "severity": "info",
                "category": "recon",
                "type": "note",
                "content": "Port 80, 443, 8080 open",
                "timestamp": "2026-09-12 09:30",
                "target_ip": "192.168.10.50",
            },
        ],
    )

    renderer = TemplateRenderer()
    rendered_md = renderer.render(template, context)

    # Parse into ReportWorkspaceDocument
    doc = ReportWorkspaceDocument.from_markdown(rendered_md)
    assert doc.language == "de"
    assert doc.metadata.client == "MegaCorp AG"
    assert doc.metadata.tester == "Lead Auditor"
    assert doc.metadata.classification == "Streng Vertraulich"
    assert doc.metadata.version == "v1.0"
    assert len(doc.findings) == 2

    crit_finding = doc.get_finding("loot-1")
    assert crit_finding is not None
    assert crit_finding.title == "Default Credentials in Admin Panel"
    assert crit_finding.severity == "critical"
    assert "admin:admin123" in crit_finding.description

    # Re-serialize to markdown
    serialized_md = doc.to_markdown()

    # Section markers must be retained
    assert "<!-- spectre:section:start:header_metadata -->" in serialized_md
    assert "<!-- spectre:section:start:executive_summary -->" in serialized_md
    assert "<!-- spectre:section:start:scope_limitations -->" in serialized_md
    assert "<!-- spectre:section:start:remediation_table -->" in serialized_md
    assert "<!-- spectre:section:start:appendix -->" in serialized_md

    # Finding markers must be retained
    assert "<!-- spectre:finding:start:loot-1 -->" in serialized_md
    assert "<!-- spectre:finding:end:loot-1 -->" in serialized_md

    # Re-parse serialized markdown and verify identical properties
    doc2 = ReportWorkspaceDocument.from_markdown(serialized_md)
    assert doc2.metadata.client == doc.metadata.client
    assert doc2.metadata.classification == doc.metadata.classification
    assert len(doc2.findings) == len(doc.findings)
    assert doc2.get_finding("loot-1").title == crit_finding.title
    assert doc2.get_finding("loot-1").severity == crit_finding.severity


def test_compatibility_across_all_builtin_templates():
    """Verify parsing and serialization across all 8 built-in report templates."""
    repo = TemplateRepository()
    templates = repo.get_all_templates()
    assert len(templates) >= 8

    renderer = TemplateRenderer()
    sample_context = ReportContext(
        project_name="CrossTemplate Validation",
        target_ip="10.0.0.1",
        metadata={
            "client": "Global Security Ltd",
            "tester": "Spectre Auditor",
            "timeframe": "2026-Q3",
            "classification": "Confidential",
            "version": "1.0",
        },
        loot_entries=[
            {
                "id": "entry-test-1",
                "title": "Open SMB Share",
                "severity": "high",
                "category": "recon",
                "content": "\\\\10.0.0.1\\public accessible without auth",
                "recommendation": "Restrict share permissions",
                "timestamp": "2026-09-12 11:00",
            }
        ],
    )

    for tmpl in templates:
        rendered = renderer.render(tmpl, sample_context)
        assert rendered, f"Template {tmpl.id} rendered empty markdown"
        doc = ReportWorkspaceDocument.from_markdown(rendered)
        assert doc.metadata.client in ("Global Security Ltd", "")
        # Round-trip back to markdown
        re_exported = doc.to_markdown()
        assert re_exported, f"Template {tmpl.id} re-exported empty markdown"
        assert "<!-- spectre:section:start:header_metadata -->" in re_exported


def test_finding_evidence_attach_detach_update():
    f = ReportFindingItem(
        id="f1",
        title="Test Finding",
        description="Initial description without evidence.",
    )
    assert len(f.evidence_items) == 0

    # 1. Attach screenshot evidence
    ev_sc = ReportEvidenceItem(
        id="ev1",
        type="screenshot",
        caption="Nmap Scan",
        content="screenshots/nmap.png",
    )
    f.attach_evidence(ev_sc, insert_into_description=True)
    assert len(f.evidence_items) == 1
    assert "![Nmap Scan](screenshots/nmap.png)" in f.description

    # 2. Attach terminal evidence
    ev_term = ReportEvidenceItem(
        id="ev2",
        type="terminal",
        caption="Terminal PoC",
        content="curl -v http://target/api",
    )
    f.attach_evidence(ev_term, insert_into_description=True)
    assert len(f.evidence_items) == 2
    assert "```bash\ncurl -v http://target/api\n```" in f.description

    # 3. Update caption
    assert f.update_evidence("ev1", caption="Nmap Port Scan Result") is True
    assert f.evidence_items[0].caption == "Nmap Port Scan Result"
    assert "![Nmap Port Scan Result](screenshots/nmap.png)" in f.description

    # 4. Detach screenshot evidence
    removed = f.detach_evidence("ev1", remove_from_description=True)
    assert removed is not None
    assert removed.id == "ev1"
    assert len(f.evidence_items) == 1
    assert "screenshots/nmap.png" not in f.description
    assert "```bash\ncurl -v http://target/api\n```" in f.description

    # 5. Detach terminal evidence
    removed2 = f.detach_evidence("ev2", remove_from_description=True)
    assert removed2 is not None
    assert len(f.evidence_items) == 0
    assert "curl -v" not in f.description

