"""Generate the public synthetic Professional Print report and README preview."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile
from core.atomic_write import atomic_write_bytes
from scripts.report_pdf_preflight import preflight_pdf


DEFAULT_SOURCE = REPO_ROOT / "docs" / "examples" / "sample-report-source.md"
DEFAULT_PDF = REPO_ROOT / "docs" / "examples" / "SpectreHUD-Sample-Report.pdf"
DEFAULT_PREVIEW = REPO_ROOT / "docs" / "examples" / "SpectreHUD-Sample-Report-preview.png"
SAMPLE_REQUIRED_PHRASES = (
    "DEMO - SYNTHETIC DATA",
    "Administrative Export Authorization Bypass",
    "Stored Operator Note Injection",
    "Shared Deployment Credential",
    "Verbose Build Metadata",
    "Reconnaissance & Enumeration",
    "Privilege Escalation",
    "Appendix & Evidence",
)


def _first_executable(candidates: list[str | Path | None]) -> Path | None:
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(str(candidate)) or str(candidate)
        path = Path(resolved)
        if path.is_file():
            return path
    return None


def _find_browser(override: str | None) -> Path:
    browser = _first_executable(
        [
            override,
            os.environ.get("SPECTREHUD_SAMPLE_BROWSER"),
            "google-chrome",
            "chromium",
            "chromium-browser",
            "chrome",
            "msedge",
            Path(os.environ.get("PROGRAMFILES", ""))
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", ""))
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe",
        ]
    )
    if browser is None:
        raise RuntimeError("Chrome, Chromium, or Edge is required to generate the sample PDF")
    return browser


def _find_pdftoppm(override: str | None) -> Path:
    renderer = _first_executable(
        [override, os.environ.get("SPECTREHUD_PDFTOPPM"), "pdftoppm"]
    )
    if renderer is None:
        raise RuntimeError("Poppler pdftoppm is required to generate the README preview")
    return renderer


def _render_pdf(
    browser: Path,
    html_path: Path,
    pdf_path: Path,
    *,
    temp_dir: Path | None = None,
) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.unlink(missing_ok=True)
    # A dedicated profile prevents an already-running desktop browser from
    # swallowing the headless request without producing the requested file.
    with tempfile.TemporaryDirectory(
        prefix="spectrehud-sample-browser-",
        dir=temp_dir,
        ignore_cleanup_errors=True,
    ) as profile_dir:
        completed = subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                f"--user-data-dir={profile_dir}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                break
            time.sleep(0.1)
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        diagnostics = (completed.stderr or completed.stdout).strip()
        detail = f": {diagnostics}" if diagnostics else ""
        raise RuntimeError(f"Browser did not create {pdf_path}{detail}")


def _render_preview(
    pdftoppm: Path,
    pdf_path: Path,
    preview_path: Path,
    *,
    temp_dir: Path | None = None,
) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="spectrehud-sample-preview-", dir=temp_dir
    ) as preview_temp_dir:
        prefix = Path(preview_temp_dir) / "preview"
        subprocess.run(
            [
                str(pdftoppm),
                "-f",
                "2",
                "-l",
                "2",
                "-singlefile",
                "-png",
                "-r",
                "144",
                str(pdf_path),
                str(prefix),
            ],
            check=True,
        )
        generated = prefix.with_suffix(".png")
        if not generated.is_file():
            raise RuntimeError("pdftoppm did not create the sample preview")
        shutil.copyfile(generated, preview_path)


def _publish_artifact(staged_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not atomic_write_bytes(destination, staged_path.read_bytes()):
        raise RuntimeError(f"Could not publish validated report artifact to {destination}")


def generate_sample_report(
    source_path: Path,
    pdf_path: Path,
    preview_path: Path,
    *,
    browser: Path,
    pdftoppm: Path,
    temp_dir: Path | None = None,
) -> None:
    markdown = source_path.read_text(encoding="utf-8")
    html = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Northstar Research Portal",
        language="en",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        category="pentest",
        include_toc=True,
    )
    with tempfile.TemporaryDirectory(
        prefix="spectrehud-sample-report-", dir=temp_dir
    ) as report_temp_dir:
        staging_dir = Path(report_temp_dir)
        html_path = staging_dir / "SpectreHUD-Sample-Report.html"
        staged_pdf = staging_dir / pdf_path.name
        staged_preview = staging_dir / preview_path.name
        html_path.write_text(html, encoding="utf-8")
        _render_pdf(browser, html_path, staged_pdf, temp_dir=temp_dir)
        report = preflight_pdf(
            staged_pdf,
            expected_page_count=10,
            expected_page_size=(595.28, 841.89),
            required_phrases=SAMPLE_REQUIRED_PHRASES,
        )
        _render_preview(pdftoppm, staged_pdf, staged_preview, temp_dir=temp_dir)
        _publish_artifact(staged_pdf, pdf_path)
        _publish_artifact(staged_preview, preview_path)
    print(
        f"Preflight passed: {report.page_count} pages, "
        f"{report.word_count} positioned words"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--browser", help="Path to Chrome, Chromium, or Edge")
    parser.add_argument("--pdftoppm", help="Path to Poppler pdftoppm")
    parser.add_argument("--temp-dir", type=Path, help="Optional temporary workspace directory")
    args = parser.parse_args()

    generate_sample_report(
        args.source.resolve(),
        args.output.resolve(),
        args.preview.resolve(),
        browser=_find_browser(args.browser),
        pdftoppm=_find_pdftoppm(args.pdftoppm),
        temp_dir=args.temp_dir.resolve() if args.temp_dir else None,
    )
    print(f"Generated {args.output}")
    print(f"Generated {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
