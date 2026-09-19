"""Geometry and content preflight checks for generated report PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PdfWord:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True)
class PdfPage:
    width: float
    height: float
    words: tuple[PdfWord, ...]


@dataclass(frozen=True)
class PdfPreflightReport:
    page_count: int
    word_count: int
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class PdfPreflightError(RuntimeError):
    """Raised when a generated PDF fails its publication checks."""


def analyze_pdf_pages(
    pages: Sequence[PdfPage],
    *,
    expected_page_count: int | None = None,
    expected_page_size: tuple[float, float] | None = None,
    required_phrases: Iterable[str] = (),
    min_words_per_page: int = 8,
    safe_edge_margin: float = 8.0,
    size_tolerance: float = 2.0,
) -> PdfPreflightReport:
    """Check page geometry and visible text without depending on a PDF backend."""
    issues: list[str] = []
    if not pages:
        issues.append("PDF contains no pages")
    if expected_page_count is not None and len(pages) != expected_page_count:
        issues.append(f"expected {expected_page_count} pages, found {len(pages)}")

    all_text: list[str] = []
    word_count = 0
    for page_number, page in enumerate(pages, start=1):
        if expected_page_size is not None:
            expected_width, expected_height = expected_page_size
            if (
                abs(page.width - expected_width) > size_tolerance
                or abs(page.height - expected_height) > size_tolerance
            ):
                issues.append(
                    f"page {page_number} has unexpected size "
                    f"{page.width:.2f} x {page.height:.2f} pt"
                )

        word_count += len(page.words)
        page_text = " ".join(word.text for word in page.words)
        all_text.append(page_text)
        if len(page.words) < min_words_per_page:
            issues.append(
                f"page {page_number} looks unexpectedly sparse ({len(page.words)} words)"
            )

        has_out_of_bounds_text = False
        has_unsafe_edge_text = False
        for word in page.words:
            if (
                word.x0 < 0
                or word.x1 > page.width
                or word.top < 0
                or word.bottom > page.height
            ) and not has_out_of_bounds_text:
                issues.append(
                    f"page {page_number} contains out-of-bounds text: {word.text!r}"
                )
                has_out_of_bounds_text = True
            if (
                word.x0 < safe_edge_margin
                or word.x1 > page.width - safe_edge_margin
                or word.top < safe_edge_margin
                or word.bottom > page.height - safe_edge_margin
            ) and not has_unsafe_edge_text:
                issues.append(
                    f"page {page_number} contains text inside the unsafe page edge: "
                    f"{word.text!r}"
                )
                has_unsafe_edge_text = True

    document_text = "\n".join(all_text)
    lowered_text = document_text.lower()
    for marker in ("spectre:section", "spectre:finding", "spectre:pagebreak"):
        if marker in lowered_text:
            issues.append(f"internal marker leaked into the PDF: {marker}")
    for phrase in required_phrases:
        if phrase not in document_text:
            issues.append(f"required text is missing: {phrase!r}")

    return PdfPreflightReport(len(pages), word_count, tuple(issues))


def load_pdf_pages(pdf_path: Path) -> tuple[PdfPage, ...]:
    """Load the small layout model through the optional development dependency."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF preflight requires pdfplumber; install the project development extras"
        ) from exc

    pages: list[PdfPage] = []
    with pdfplumber.open(pdf_path) as document:
        for page in document.pages:
            words = tuple(
                PdfWord(
                    text=str(word["text"]),
                    x0=float(word["x0"]),
                    x1=float(word["x1"]),
                    top=float(word["top"]),
                    bottom=float(word["bottom"]),
                )
                for word in page.extract_words()
            )
            pages.append(PdfPage(float(page.width), float(page.height), words))
    return tuple(pages)


def preflight_pdf(
    pdf_path: Path,
    *,
    expected_page_count: int | None = None,
    expected_page_size: tuple[float, float] | None = None,
    required_phrases: Iterable[str] = (),
    min_words_per_page: int = 8,
    safe_edge_margin: float = 8.0,
    size_tolerance: float = 2.0,
) -> PdfPreflightReport:
    """Validate a PDF and raise one actionable error containing every issue."""
    report = analyze_pdf_pages(
        load_pdf_pages(pdf_path),
        expected_page_count=expected_page_count,
        expected_page_size=expected_page_size,
        required_phrases=required_phrases,
        min_words_per_page=min_words_per_page,
        safe_edge_margin=safe_edge_margin,
        size_tolerance=size_tolerance,
    )
    if not report.ok:
        details = "\n".join(f"- {issue}" for issue in report.issues)
        raise PdfPreflightError(f"PDF preflight failed for {pdf_path}:\n{details}")
    return report
