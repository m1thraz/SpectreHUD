"""Generate the public synthetic Professional Print report and README preview."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.reporting.exporter import HtmlReportExporter
from core.reporting.profiles import ReportExportProfile


DEFAULT_SOURCE = REPO_ROOT / "docs" / "examples" / "sample-report-source.md"
DEFAULT_PDF = REPO_ROOT / "docs" / "examples" / "SpectreHUD-Sample-Report.pdf"
DEFAULT_PREVIEW = REPO_ROOT / "docs" / "examples" / "SpectreHUD-Sample-Report-preview.png"


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


def _render_pdf(browser: Path, html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.unlink(missing_ok=True)
    subprocess.run(
        [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
    )
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Browser did not create {pdf_path}")


def _render_preview(pdftoppm: Path, pdf_path: Path, preview_path: Path) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="spectrehud-sample-preview-") as temp_dir:
        prefix = Path(temp_dir) / "preview"
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


def generate_sample_report(
    source_path: Path,
    pdf_path: Path,
    preview_path: Path,
    *,
    browser: Path,
    pdftoppm: Path,
) -> None:
    markdown = source_path.read_text(encoding="utf-8")
    html = HtmlReportExporter.build_full_html(
        markdown,
        project_name="Northstar Research Portal",
        language="en",
        profile=ReportExportProfile.PROFESSIONAL_PRINT,
        category="pentest",
    )
    with tempfile.TemporaryDirectory(prefix="spectrehud-sample-report-") as temp_dir:
        html_path = Path(temp_dir) / "SpectreHUD-Sample-Report.html"
        html_path.write_text(html, encoding="utf-8")
        _render_pdf(browser, html_path, pdf_path)
    _render_preview(pdftoppm, pdf_path, preview_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--browser", help="Path to Chrome, Chromium, or Edge")
    parser.add_argument("--pdftoppm", help="Path to Poppler pdftoppm")
    args = parser.parse_args()

    generate_sample_report(
        args.source.resolve(),
        args.output.resolve(),
        args.preview.resolve(),
        browser=_find_browser(args.browser),
        pdftoppm=_find_pdftoppm(args.pdftoppm),
    )
    print(f"Generated {args.output}")
    print(f"Generated {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
