from pathlib import Path

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "examples" / "sample-report-source.md"


def test_public_sample_report_is_clearly_synthetic_and_exportable():
    markdown = SOURCE.read_text(encoding="utf-8")

    assert "DEMO - SYNTHETIC DATA" in markdown
    assert "Northstar Research Labs (Fictional)" in markdown
    assert "portal.example.test" in markdown
    assert "192.0.2.45" in markdown

    rendered = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Northstar Research Portal",
        language="en",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        category="pentest",
    )

    assert "spectre:section" not in rendered
    assert "spectre:finding" not in rendered
    assert "DEMO - SYNTHETIC DATA" in rendered
    assert "Initial Access &amp; Exploitation" in rendered
    assert "Privilege Escalation" in rendered
    assert "Reconnaissance &amp; Enumeration" in rendered
    assert "Administrative Export Authorization Bypass" in rendered
    assert "Stored Operator Note Injection" in rendered
