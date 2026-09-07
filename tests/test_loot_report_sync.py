"""
Unit and integration tests for SpectreHUD loot markers, content hashing,
report status classification, byte-preserving insertion, and export stripping.
"""

import unittest
from typing import Any, Dict

from core.reporting.loot_sync import (
    FALLBACK_SECTION_TITLE,
    LootReportState,
    append_missing_loot_to_text,
    classify_loot_report_state,
    extract_report_markers,
    loot_content_hash,
    preserve_markers_in_preview_roundtrip,
    strip_report_markers,
)
from core.reporting.template_engine import (
    ReportContext,
    ReportTemplate,
    TemplateRenderer,
    TemplateSection,
)


class TestLootReportSync(unittest.TestCase):
    """Test suite covering Phase A through G requirements for additive loot synchronization."""

    def setUp(self):
        self.entry_a: Dict[str, Any] = {
            "id": "loot_11111111",
            "category": "recon",
            "title": "Nmap Port Scan",
            "content": "Port 80, 22, 443 open",
            "severity": "info",
            "type": "note",
            "target_ip": "10.10.10.42",
            "timestamp": "2026-09-01 12:00:00",
            "position": 1,
        }
        self.entry_b: Dict[str, Any] = {
            "id": "loot_22222222",
            "category": "access",
            "title": "SQL Injection in Login",
            "content": "' OR 1=1 --",
            "severity": "high",
            "type": "note",
            "target_ip": "10.10.10.42",
            "timestamp": "2026-09-01 12:30:00",
            "position": 2,
        }

    # ------------------------------------------------------------------ #
    # Ticket 28: Marker & Hash Stability
    # ------------------------------------------------------------------ #

    def test_hash_is_deterministic_and_independent_of_position(self):
        """Ticket 28: Content hash must be stable, deterministic, and ignore board position."""
        hash1 = loot_content_hash(self.entry_a)
        hash2 = loot_content_hash(self.entry_a)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 12)

        # Reordering on board (changing position) must NOT change content hash
        moved_entry = dict(self.entry_a, position=99)
        self.assertEqual(loot_content_hash(moved_entry), hash1)

    def test_hash_changes_on_render_relevant_fields(self):
        """Ticket 28: Hash must change whenever visible/render-relevant fields change."""
        base_hash = loot_content_hash(self.entry_a)
        for field, new_val in [
            ("title", "New Title"),
            ("content", "New Content"),
            ("severity", "critical"),
            ("type", "credentials"),
            ("target_ip", "192.168.1.1"),
            ("timestamp", "2026-09-01 13:00:00"),
            ("category", "priv_esc"),
        ]:
            modified = dict(self.entry_a, **{field: new_val})
            self.assertNotEqual(
                loot_content_hash(modified),
                base_hash,
                f"Hash should change when '{field}' changes",
            )

    def test_hash_preserves_legacy_empty_value_and_tracks_recommendation(self):
        legacy_hash = loot_content_hash(self.entry_a)
        self.assertEqual(
            loot_content_hash(dict(self.entry_a, recommendation="")), legacy_hash
        )
        with_recommendation = dict(
            self.entry_a,
            recommendation="Restrict the exposed service to the management network.",
        )
        self.assertNotEqual(loot_content_hash(with_recommendation), legacy_hash)
        self.assertNotEqual(
            loot_content_hash(dict(with_recommendation, recommendation="Disable the service.")),
            loot_content_hash(with_recommendation),
        )

    def test_recommendation_change_is_stale_and_never_rewrites_report(self):
        original_hash = loot_content_hash(self.entry_a)
        report = (
            f"<!-- spectre:loot:{self.entry_a['id']}:{original_hash} -->\n"
            "### Hand-edited finding\n\nPreserve this report text."
        )
        updated_entry = dict(
            self.entry_a, recommendation="Restrict the service to approved networks."
        )

        state = classify_loot_report_state(report, [updated_entry])
        result = append_missing_loot_to_text(report, [updated_entry], language="en")

        self.assertEqual([entry["id"] for entry in state.stale], [self.entry_a["id"]])
        self.assertFalse(state.missing)
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.text, report)

    # ------------------------------------------------------------------ #
    # Ticket 29: Marker Parsing & Robustness
    # ------------------------------------------------------------------ #

    def test_extract_markers_valid_and_multiple(self):
        """Ticket 29: Extract single and multiple valid markers."""
        hash_a = loot_content_hash(self.entry_a)
        hash_b = loot_content_hash(self.entry_b)
        text = f"""# Pentest Report
<!-- spectre:loot:loot_11111111:{hash_a} -->
### Nmap Port Scan
Some content

<!-- spectre:loot:loot_22222222:{hash_b} -->
### 🟠 SQL Injection in Login
Details
"""
        markers = extract_report_markers(text)
        self.assertEqual(markers.get("loot_11111111"), hash_a)
        self.assertEqual(markers.get("loot_22222222"), hash_b)

    def test_extract_markers_ignores_invalid_and_other_html_comments(self):
        """Ticket 29: Must ignore broken markers, Obsidian markers, and regular HTML comments."""
        text = """
<!-- spectrehud-entry:obsidian_123 -->
<!-- Custom user comment: do not touch -->
<!-- spectre:loot:broken_marker -->
<!-- spectre:loot:incomplete: -->
<!--spectre:loot:valid_123:abc123def456-->
<!-- spectre:loot:loot_dup:111111111111 -->
<!-- spectre:loot:loot_dup:222222222222 -->
"""
        markers = extract_report_markers(text)
        self.assertNotIn("obsidian_123", markers)
        self.assertNotIn("broken_marker", markers)
        self.assertEqual(markers.get("valid_123"), "abc123def456")
        # Duplicate ID: last valid marker wins deterministically
        self.assertEqual(markers.get("loot_dup"), "222222222222")

    def test_strip_report_markers_preserves_external_and_user_comments(self):
        text = (
            "<!-- spectrehud-entry:keep_this -->\n"
            "<!-- spectre:finding:start:loot_1 -->\n"
            "<!-- spectre:loot:loot_1:deadbeef1234 -->\n"
            "<!-- user: note -->\n"
            "### Title\n"
            "<!-- spectre:loot:loot_2:cafebabe5678 -->\n"
            "<!-- spectre:finding:end:loot_1 -->\n"
            "Content\n"
        )
        stripped = strip_report_markers(text)
        self.assertIn("<!-- spectrehud-entry:keep_this -->", stripped)
        self.assertIn("<!-- user: note -->", stripped)
        self.assertNotIn("spectre:loot", stripped)
        self.assertNotIn("spectre:finding", stripped)
        self.assertIn("### Title", stripped)
        self.assertIn("Content", stripped)

    # ------------------------------------------------------------------ #
    # Ticket 30: Status Classification
    # ------------------------------------------------------------------ #

    def test_classify_status_missing_current_stale_orphaned(self):
        """Ticket 30: Accurately classifies missing, current, stale, and orphaned states."""
        hash_a = loot_content_hash(self.entry_a)
        report_text = f"""
<!-- spectre:loot:loot_11111111:{hash_a} -->
### Current Finding

<!-- spectre:loot:loot_22222222:deadbeef9999 -->
### Stale Finding

<!-- spectre:loot:loot_deleted:cafebabe0000 -->
### Orphaned Finding
"""
        entry_c = {
            "id": "loot_33333333",
            "category": "privesc",
            "title": "Missing Finding",
            "content": "sudo -l exploit",
            "severity": "critical",
        }

        state = classify_loot_report_state(
            report_text, [self.entry_a, self.entry_b, entry_c]
        )
        self.assertIsInstance(state, LootReportState)
        self.assertEqual(len(state.current), 1)
        self.assertEqual(state.current[0]["id"], "loot_11111111")

        self.assertEqual(len(state.stale), 1)
        self.assertEqual(state.stale[0]["id"], "loot_22222222")

        self.assertEqual(len(state.missing), 1)
        self.assertEqual(state.missing[0]["id"], "loot_33333333")

        self.assertIn("loot_deleted", state.orphaned_ids)

    def test_unmarked_report_treats_all_as_missing(self):
        """Ticket 12: Reports without markers treat all entries as missing deterministically."""
        unmarked = "# My Custom Report\n\nSome notes about Nmap and SQL injection."
        state = classify_loot_report_state(unmarked, [self.entry_a, self.entry_b])
        self.assertEqual(len(state.missing), 2)
        self.assertEqual(len(state.current), 0)
        self.assertEqual(len(state.stale), 0)
        self.assertEqual(len(state.orphaned_ids), 0)

    # ------------------------------------------------------------------ #
    # Ticket 31: Byte Preservation & Structural Insertion
    # ------------------------------------------------------------------ #

    def test_byte_preservation_outside_insertion_points(self):
        """Ticket 18 & 31: All existing user bytes outside insertion slices remain strictly unchanged."""
        base_report = """# Target Report: Box 42

| Client | ACME Corp |
| Date   | 2026-09-01 |

## 1. Information Gathering / Reconnaissance

*Keine Einträge in dieser Phase.*

_Eigene Anmerkungen zu dieser Phase:_

> Manual note with special spacing:   four spaces here.
> Trailing space here:

```python
# Code fence with ## inside must not be parsed as heading
## fake_heading = True
def test():
    pass
```

## 2. Initial Access & Exploitation

*Keine Einträge in dieser Phase.*

_Eigene Anmerkungen zu dieser Phase:_

> Notes for exploitation phase.
"""
        # Append entry_a (recon) and entry_b (access)
        result = append_missing_loot_to_text(base_report, [self.entry_a, self.entry_b])
        self.assertEqual(result.added_count, 2)
        self.assertFalse(result.used_fallback)

        # Verify existing text preservation
        self.assertIn("# Target Report: Box 42", result.text)
        self.assertIn("Manual note with special spacing:   four spaces here.", result.text)
        self.assertIn("Trailing space here:", result.text)
        self.assertIn("## fake_heading = True", result.text)
        self.assertIn("> Notes for exploitation phase.", result.text)

        # Verify markers and content were inserted
        hash_a = loot_content_hash(self.entry_a)
        hash_b = loot_content_hash(self.entry_b)
        self.assertIn(f"<!-- spectre:loot:loot_11111111:{hash_a} -->", result.text)
        self.assertIn(f"<!-- spectre:loot:loot_22222222:{hash_b} -->", result.text)
        self.assertIn("SQL Injection in Login", result.text)
        self.assertIn("Nmap Port Scan", result.text)

    # ------------------------------------------------------------------ #
    # Ticket 32: Stale entries are NOT modified or duplicated
    # ------------------------------------------------------------------ #

    def test_stale_entries_are_not_appended_or_overwritten(self):
        """Ticket 32: Stale entries are ignored during append; only missing are added."""
        hash_old = "deadbeef1111"
        report_with_stale = f"""# Report
## 1. Information Gathering / Reconnaissance

<!-- spectre:loot:loot_11111111:{hash_old} -->
### Nmap Port Scan
Custom modified finding text by the user.

_Eigene Anmerkungen zu dieser Phase:_
"""
        # entry_a has a different hash now
        result = append_missing_loot_to_text(report_with_stale, [self.entry_a, self.entry_b])
        self.assertEqual(result.added_count, 1)  # only entry_b added
        # User's modified finding text for entry_a must be preserved untouched
        self.assertIn("Custom modified finding text by the user.", result.text)
        self.assertIn(f"<!-- spectre:loot:loot_11111111:{hash_old} -->", result.text)
        # Entry B added
        self.assertIn("SQL Injection in Login", result.text)

    # ------------------------------------------------------------------ #
    # Ticket 33: Fallback Section for Missing/Renamed Phases
    # ------------------------------------------------------------------ #

    def test_fallback_section_created_when_phase_heading_missing(self):
        """Ticket 15 & 33: Places missing entries in '## Neu aus Loot ergänzt' if phase is not found."""
        report_without_recon = """# Custom Report
## 2. Initial Access & Exploitation

*Keine Einträge in dieser Phase.*

_Eigene Anmerkungen zu dieser Phase:_
"""
        result = append_missing_loot_to_text(
            report_without_recon, [self.entry_a, self.entry_b]
        )
        self.assertEqual(result.added_count, 2)
        self.assertTrue(result.used_fallback)
        self.assertIn("recon", result.fallback_categories)
        self.assertIn(f"## {FALLBACK_SECTION_TITLE}", result.text)
        self.assertIn("Nmap Port Scan", result.text)
        # entry_b was placed under Initial Access
        self.assertIn("SQL Injection in Login", result.text)

    # ------------------------------------------------------------------ #
    # Ticket 35: Custom Template Section Headings
    # ------------------------------------------------------------------ #

    def test_custom_template_section_heading_mapping(self):
        """Ticket 13 & 35: Uses section.title from active template to map category to section."""
        custom_template = ReportTemplate(
            id="custom_tpl",
            name="Custom Template",
            language="de",
            category="pentest",
            complexity="simple",
            sections=[
                TemplateSection(
                    type="phase_section",
                    category_id="recon",
                    title="01 - Discovery & Footprinting",
                )
            ],
        )
        report = """# Executive Pentest
## 01 - Discovery & Footprinting

_Eigene Anmerkungen zu dieser Phase:_
"""
        result = append_missing_loot_to_text(report, [self.entry_a], template=custom_template)
        self.assertEqual(result.added_count, 1)
        self.assertFalse(result.used_fallback)
        self.assertIn("Nmap Port Scan", result.text)
        self.assertNotIn(FALLBACK_SECTION_TITLE, result.text)

    # ------------------------------------------------------------------ #
    # Ticket 36: DE and EN Notes Placeholders
    # ------------------------------------------------------------------ #

    def test_english_notes_placeholder_insertion(self):
        """Ticket 16 & 36: Inserts before English placeholder _Notes & observations for this phase:_."""
        en_report = """# English Assessment
## 1. Information Gathering / Reconnaissance

_Notes & observations for this phase:_

> Lead tester notes.
"""
        result = append_missing_loot_to_text(en_report, [self.entry_a], language="en")
        self.assertEqual(result.added_count, 1)
        # Verify Nmap Finding comes before notes
        finding_idx = result.text.find("### Nmap Port Scan")
        notes_idx = result.text.find("_Notes & observations for this phase:_")
        self.assertTrue(0 <= finding_idx < notes_idx)

    # ------------------------------------------------------------------ #
    # Phase 0 / Ticket 39: Rich Preview Roundtrip Reconciliation
    # ------------------------------------------------------------------ #

    def test_preserve_markers_in_preview_roundtrip(self):
        """Ticket 0.1 & 39: Reconciles markers lost during QTextDocument.toMarkdown()."""
        hash_a = loot_content_hash(self.entry_a)
        original_md = f"""<!-- spectre:loot:loot_11111111:{hash_a} -->
### Nmap Port Scan
Port 80, 22, 443 open
"""
        # Simulated Qt toMarkdown output (which strips HTML comments)
        qt_converted_md = """### Nmap Port Scan

Port 80, 22, 443 open
"""
        reconciled = preserve_markers_in_preview_roundtrip(original_md, qt_converted_md)
        self.assertIn(f"<!-- spectre:loot:loot_11111111:{hash_a} -->", reconciled)
        self.assertIn("### Nmap Port Scan", reconciled)

    def test_new_finding_layout_is_idempotent_and_preview_safe(self):
        report = "## 1. Reconnaissance & Enumeration\n\n*No entries captured for this phase.*\n"

        first = append_missing_loot_to_text(report, [self.entry_a], language="en")
        second = append_missing_loot_to_text(first.text, [self.entry_a], language="en")

        self.assertEqual(first.added_count, 1)
        self.assertEqual(second.added_count, 0)
        self.assertEqual(second.text, first.text)
        self.assertEqual(first.text.count("spectre:finding:start:loot_11111111"), 1)
        converted = first.text.replace(
            "<!-- spectre:finding:start:loot_11111111 -->\n", ""
        ).replace("<!-- spectre:finding:end:loot_11111111 -->\n", "")
        reconciled = preserve_markers_in_preview_roundtrip(first.text, converted)
        self.assertIn("<!-- spectre:finding:start:loot_11111111 -->", reconciled)
        self.assertIn("<!-- spectre:finding:end:loot_11111111 -->", reconciled)

    def test_new_missing_finding_includes_recommendation_without_rewriting_legacy(self):
        legacy = (
            "## 1. Reconnaissance & Enumeration\n\n"
            "<!-- spectre:loot:legacy:deadbeef1234 -->\n"
            "### Manually edited legacy finding\n\nKeep this byte-for-byte.\n"
        )
        recommended = dict(
            self.entry_a,
            id="recommended-new",
            recommendation="Restrict TCP/443 to approved source networks.",
        )

        first = append_missing_loot_to_text(legacy, [recommended], language="en")
        second = append_missing_loot_to_text(first.text, [recommended], language="en")

        self.assertIn(
            "<!-- spectre:loot:legacy:deadbeef1234 -->\n"
            "### Manually edited legacy finding\n\nKeep this byte-for-byte.",
            first.text,
        )
        self.assertIn("#### Recommendation", first.text)
        self.assertIn("Restrict TCP/443", first.text)
        self.assertEqual(first.added_count, 1)
        self.assertEqual(second.added_count, 0)
        self.assertEqual(second.text, first.text)

    def test_grouped_finding_section_adds_each_category_once_with_phase(self):
        template = ReportTemplate(
            id="grouped",
            name="Grouped",
            language="en",
            category="pentest",
            complexity="complex",
            sections=[
                TemplateSection(
                    type="finding_section",
                    title="4. Technical Findings",
                    options={"categories": ["recon", "access"]},
                )
            ],
        )
        empty_report = TemplateRenderer().render(template, ReportContext())

        first = append_missing_loot_to_text(
            empty_report,
            [self.entry_a, self.entry_b],
            template=template,
            language="en",
        )
        second = append_missing_loot_to_text(
            first.text,
            [self.entry_a, self.entry_b],
            template=template,
            language="en",
        )

        self.assertEqual(first.added_count, 2)
        self.assertFalse(first.used_fallback)
        self.assertEqual(first.text.count("## 4. Technical Findings"), 1)
        self.assertEqual(first.text.count("spectre:loot:loot_11111111:"), 1)
        self.assertEqual(first.text.count("spectre:loot:loot_22222222:"), 1)
        self.assertIn("**Phase:** Reconnaissance & Enumeration", first.text)
        self.assertIn("**Phase:** Initial Access & Exploitation", first.text)
        self.assertNotIn("*No technical findings are documented.*", first.text)
        self.assertEqual(second.added_count, 0)
        self.assertEqual(second.text, first.text)

    def test_grouped_finding_section_without_category_options_accepts_all(self):
        template = ReportTemplate(
            id="grouped-default",
            name="Grouped Default",
            language="en",
            category="pentest",
            complexity="complex",
            sections=[TemplateSection(type="finding_section", title="Findings")],
        )
        empty_report = TemplateRenderer().render(template, ReportContext())

        result = append_missing_loot_to_text(
            empty_report, [self.entry_a], template=template, language="en"
        )

        self.assertEqual(result.added_count, 1)
        self.assertFalse(result.used_fallback)
        self.assertIn("### Nmap Port Scan", result.text)
        self.assertIn("**Phase:** Reconnaissance & Enumeration", result.text)

    def test_ctf_add_missing_does_not_inject_recommendation(self):
        template = ReportTemplate(
            id="ctf",
            name="CTF",
            language="en",
            category="ctf",
            complexity="simple",
            sections=[
                TemplateSection(
                    type="phase_section",
                    category_id="recon",
                    title="Recon",
                    options={"include_recommendations": False},
                )
            ],
        )
        report = TemplateRenderer().render(template, ReportContext())
        entry = dict(self.entry_a, recommendation="Enterprise remediation text")

        result = append_missing_loot_to_text(
            report, [entry], template=template, language="en"
        )

        self.assertIn("### Nmap Port Scan", result.text)
        self.assertNotIn("#### Recommendation", result.text)
        self.assertNotIn("Enterprise remediation text", result.text)

    def test_legacy_finding_bytes_remain_untouched_when_new_loot_is_added(self):
        legacy = (
            "## 1. Reconnaissance & Enumeration\n\n"
            "<!-- spectre:loot:legacy_entry:deadbeef1234 -->\n"
            "### Legacy hand-edited finding\n\nDo not reformat this text.\n"
        )
        new_entry = dict(self.entry_a, id="new_entry", title="New structured finding")

        result = append_missing_loot_to_text(legacy, [new_entry], language="en")

        self.assertIn(
            "<!-- spectre:loot:legacy_entry:deadbeef1234 -->\n"
            "### Legacy hand-edited finding\n\nDo not reformat this text.",
            result.text,
        )
        self.assertIn("spectre:finding:start:new_entry", result.text)


if __name__ == "__main__":
    unittest.main()
