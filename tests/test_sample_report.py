from pathlib import Path
from types import SimpleNamespace

import pytest

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile
from scripts import generate_sample_report as sample_generator
from scripts.report_pdf_preflight import PdfPreflightError


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


def test_sample_generation_preserves_published_artifacts_when_preflight_fails(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.md"
    output = tmp_path / "sample.pdf"
    preview = tmp_path / "preview.png"
    source.write_text("# Synthetic report", encoding="utf-8")
    output.write_bytes(b"last-good-pdf")
    preview.write_bytes(b"last-good-preview")

    monkeypatch.setattr(
        sample_generator,
        "_render_pdf",
        lambda _browser, _html, staged: staged.write_bytes(b"invalid-pdf"),
    )
    monkeypatch.setattr(
        sample_generator,
        "preflight_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PdfPreflightError("bad layout")),
    )

    with pytest.raises(PdfPreflightError, match="bad layout"):
        sample_generator.generate_sample_report(
            source,
            output,
            preview,
            browser=Path("browser"),
            pdftoppm=Path("pdftoppm"),
        )

    assert output.read_bytes() == b"last-good-pdf"
    assert preview.read_bytes() == b"last-good-preview"


def test_sample_generation_publishes_only_validated_artifacts(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    output = tmp_path / "sample.pdf"
    preview = tmp_path / "preview.png"
    source.write_text("# Synthetic report", encoding="utf-8")

    monkeypatch.setattr(
        sample_generator,
        "_render_pdf",
        lambda _browser, _html, staged: staged.write_bytes(b"validated-pdf"),
    )
    monkeypatch.setattr(
        sample_generator,
        "preflight_pdf",
        lambda *_args, **_kwargs: SimpleNamespace(page_count=1, word_count=4),
    )
    monkeypatch.setattr(
        sample_generator,
        "_render_preview",
        lambda _renderer, _pdf, staged: staged.write_bytes(b"validated-preview"),
    )

    sample_generator.generate_sample_report(
        source,
        output,
        preview,
        browser=Path("browser"),
        pdftoppm=Path("pdftoppm"),
    )

    assert output.read_bytes() == b"validated-pdf"
    assert preview.read_bytes() == b"validated-preview"
