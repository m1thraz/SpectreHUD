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
        lambda _browser, _html, staged, **_kwargs: staged.write_bytes(b"invalid-pdf"),
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
        lambda _browser, _html, staged, **_kwargs: staged.write_bytes(b"validated-pdf"),
    )
    monkeypatch.setattr(
        sample_generator,
        "preflight_pdf",
        lambda *_args, **_kwargs: SimpleNamespace(page_count=1, word_count=4),
    )
    monkeypatch.setattr(
        sample_generator,
        "_render_preview",
        lambda _renderer, _pdf, staged, **_kwargs: staged.write_bytes(b"validated-preview"),
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


def test_headless_pdf_render_uses_an_isolated_browser_profile(tmp_path, monkeypatch):
    html_path = tmp_path / "report.html"
    pdf_path = tmp_path / "report.pdf"
    html_path.write_text("<html></html>", encoding="utf-8")
    captured: list[list[str]] = []

    def render(command, *, check, capture_output, text):
        assert check is True
        assert capture_output is True
        assert text is True
        captured.append(command)
        output_arg = next(arg for arg in command if arg.startswith("--print-to-pdf="))
        Path(output_arg.split("=", 1)[1]).write_bytes(b"pdf")
        return SimpleNamespace(stdout="", stderr="")

    monkeypatch.setattr(sample_generator.subprocess, "run", render)

    browser_temp = tmp_path / "browser-temp"
    browser_temp.mkdir()
    sample_generator._render_pdf(
        Path("browser"), html_path, pdf_path, temp_dir=browser_temp
    )

    assert pdf_path.read_bytes() == b"pdf"
    assert "--headless" in captured[0]
    profile_arg = next(arg for arg in captured[0] if arg.startswith("--user-data-dir="))
    assert str(browser_temp) in profile_arg
