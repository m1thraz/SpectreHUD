"""Tests for pure Quick-Note to report Markdown formatting."""

from core.reporting.note_formatter import append_report_note, format_report_note


def test_format_report_note_includes_available_metadata():
    note = {
        "text": "  Confirmed administrative access.  ",
        "category": "privesc",
        "target_ip": " 10.10.10.42 ",
        "timestamp": "2026-09-04 15:30:00",
    }

    assert format_report_note(note) == (
        "### Note (PRIVESC) - [10.10.10.42] (2026-09-04 15:30:00)\n\n"
        "Confirmed administrative access."
    )


def test_format_report_note_rejects_blank_text():
    assert format_report_note({"text": "  "}) is None


def test_append_report_note_creates_heading_for_empty_report():
    result = append_report_note("", "Blue", {"text": "Finding", "category": "recon"})

    assert result == "# CTF Report - Blue\n\n### Note (RECON)\n\nFinding\n"


def test_append_report_note_preserves_existing_content_and_input():
    note = {"text": "Finding", "target_ip": "10.10.10.5"}
    original_note = dict(note)

    result = append_report_note("# Existing\n\nBody\n\n", "Ignored", note)

    assert result == "# Existing\n\nBody\n\n### Note (MISC) - [10.10.10.5]\n\nFinding\n"
    assert note == original_note
