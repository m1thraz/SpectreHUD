"""Tests for publication checks applied to generated report PDFs."""

from scripts.report_pdf_preflight import PdfImage, PdfPage, PdfWord, analyze_pdf_pages


def _word(text: str, *, x0: float = 24, top: float = 24) -> PdfWord:
    return PdfWord(text, x0=x0, x1=x0 + 20, top=top, bottom=top + 10)


def test_pdf_preflight_accepts_expected_geometry_and_content():
    words = tuple(
        _word(text, top=80 + index * 40)
        for index, text in enumerate(("DEMO", "SYNTHETIC", "Report", "Finding"))
    )
    pages = (PdfPage(595.28, 841.89, words),)

    report = analyze_pdf_pages(
        pages,
        expected_page_count=1,
        expected_page_size=(595.28, 841.89),
        required_phrases=("DEMO SYNTHETIC",),
        min_words_per_page=4,
    )

    assert report.ok
    assert report.word_count == 4


def test_pdf_preflight_reports_layout_content_and_marker_failures():
    pages = (
        PdfPage(
            600,
            800,
            (
                _word("spectre:pagebreak", x0=2),
                PdfWord("clipped", x0=24, x1=620, top=24, bottom=34),
            ),
        ),
    )

    report = analyze_pdf_pages(
        pages,
        expected_page_count=2,
        expected_page_size=(595.28, 841.89),
        required_phrases=("Required heading",),
        min_words_per_page=3,
    )

    assert not report.ok
    assert any("expected 2 pages" in issue for issue in report.issues)
    assert any("unexpected size" in issue for issue in report.issues)
    assert any("unexpectedly sparse" in issue for issue in report.issues)
    assert any("unsafe page edge" in issue for issue in report.issues)
    assert any("out-of-bounds text" in issue for issue in report.issues)
    assert any("internal marker leaked" in issue for issue in report.issues)
    assert any("required text is missing" in issue for issue in report.issues)


def test_pdf_preflight_reports_low_main_content_coverage_even_with_enough_words():
    words = tuple(_word(f"word-{index}", top=120) for index in range(12))

    report = analyze_pdf_pages((PdfPage(595.28, 841.89, words),))

    assert any("very low main-content coverage" in issue for issue in report.issues)


def test_pdf_preflight_counts_large_images_as_meaningful_page_content():
    words = tuple(_word(f"caption-{index}", top=680) for index in range(12))
    image = PdfImage(x0=60, x1=535, top=90, bottom=660)

    report = analyze_pdf_pages((PdfPage(595.28, 841.89, words, (image,)),))

    assert report.ok
