import unittest
from core.reporting import (
    LEGACY_DEFAULT_TEMPLATE,
    ReportContext,
    TemplateRenderer,
    TemplateSection,
)
from core.reporting.template_engine import (
    _render_appendix,
    _render_attack_path,
    _render_executive_summary,
    _render_finding_section,
    _render_header_metadata,
    _render_loot_entry_block,
    _render_phase_section,
    _render_remediation_table,
)



class TestTemplateEngine(unittest.TestCase):
    """Unit tests for the modular Report Template Engine and section renderers."""

    def setUp(self):
        self.sample_loot = [
            {
                "id": "loot_1",
                "type": "credentials",
                "category": "access",
                "severity": "critical",
                "title": "Domain Admin Credentials",
                "content": "admin:P@ssword123",
                "target_ip": "10.10.10.50",
                "timestamp": "2026-08-28 10:00:00",
            },
            {
                "id": "loot_2",
                "type": "note",
                "category": "recon",
                "severity": "info",
                "title": "Open Ports",
                "content": "22/tcp open ssh, 80/tcp open http",
                "target_ip": "10.10.10.50",
                "timestamp": "2026-08-28 09:30:00",
            },
            {
                "id": "loot_3",
                "type": "screenshot",
                "category": "privesc",
                "severity": "high",
                "title": "Root Proof",
                "content": "loot/proof.png",
                "target_ip": "10.10.10.50",
                "timestamp": "2026-08-28 10:15:00",
            },
        ]
        self.sample_history = [
            {
                "text": "nmap -sC -sV 10.10.10.50",
                "timestamp": "2026-08-28 09:15:00",
                "target_ip": "10.10.10.50",
            },
            {
                "text": "ssh admin@10.10.10.50",
                "timestamp": "2026-08-28 10:01:00",
                "target_ip": "10.10.10.50",
            },
        ]
        self.context = ReportContext(
            loot_entries=self.sample_loot,
            clipboard_history=self.sample_history,
            project_name="HackTheBox_Legacy",
            target_ip="10.10.10.50",
            metadata={"classification": "INTERNAL USE ONLY", "tester": "Alice"},
        )
        self.renderer = TemplateRenderer()

    def test_render_header_metadata_de_and_en(self):
        sec = TemplateSection(type="header_metadata")
        out_de = _render_header_metadata(sec, self.context, "de")
        self.assertIn("# Pentest Report: HackTheBox_Legacy", out_de)
        self.assertIn("10.10.10.50", out_de)
        self.assertIn("INTERNAL USE ONLY", out_de)

        out_en = _render_header_metadata(sec, self.context, "en")
        self.assertIn("# Security Assessment Report: HackTheBox_Legacy", out_en)
        self.assertIn("Lead Tester", out_en)

    def test_render_executive_summary_metrics(self):
        sec = TemplateSection(type="executive_summary")
        out = _render_executive_summary(sec, self.context, "de")
        self.assertIn(
            '<span class="severity-pill severity-critical">CRITICAL</span> 1', out
        )
        self.assertIn('<span class="severity-pill severity-high">HIGH</span> 1', out)
        self.assertNotRegex(out, "[🔴🟠🟡🟢🔵]")
        self.assertIn("Domain Admin Credentials", out)
        self.assertIn("CRITICAL", out)

    def test_render_phase_section(self):
        sec_access = TemplateSection(type="phase_section", category_id="access")
        out_access = _render_phase_section(sec_access, self.context, "de")
        self.assertIn("2. Initial Access & Exploitation", out_access)
        self.assertIn("Domain Admin Credentials", out_access)
        self.assertIn("admin:P@ssword123", out_access)

        sec_empty = TemplateSection(type="phase_section", category_id="postex")
        out_empty = _render_phase_section(sec_empty, self.context, "de")
        self.assertIn("*Keine Einträge in dieser Phase.*", out_empty)

    def test_phase_section_can_suppress_recommendations_for_ctf_templates(self):
        section = TemplateSection(
            type="phase_section",
            category_id="access",
            options={"include_recommendations": False},
        )
        context = ReportContext(
            loot_entries=[
                dict(self.sample_loot[0], recommendation="Rotate these credentials.")
            ]
        )

        rendered = _render_phase_section(section, context, "en")

        self.assertIn("Domain Admin Credentials", rendered)
        self.assertNotIn("#### Recommendation", rendered)
        self.assertNotIn("Rotate these credentials.", rendered)

    def test_attack_path_uses_only_observed_categories_and_titles(self):
        section = TemplateSection(
            type="attack_path",
            options={"categories": ["recon", "access", "postex"]},
        )

        rendered = _render_attack_path(section, self.context, "en")

        self.assertIn("1. **Reconnaissance & Enumeration** — Open Ports", rendered)
        self.assertIn("2. **Initial Access & Exploitation** — Domain Admin Credentials", rendered)
        self.assertNotIn("Post-Exploitation", rendered)
        self.assertNotIn("Business Impact", rendered)

    def test_attack_path_localizes_empty_and_untitled_entries(self):
        section = TemplateSection(type="attack_path", options={"categories": ["misc"]})
        empty = _render_attack_path(section, self.context, "de")
        context = ReportContext(loot_entries=[{"category": "misc", "title": ""}])
        untitled = _render_attack_path(section, context, "de")

        self.assertIn("*Kein dokumentierter Angriffspfad vorhanden.*", empty)
        self.assertIn("Unbenannt", untitled)

    def test_grouped_findings_preserve_category_identity_as_metadata(self):
        section = TemplateSection(
            type="finding_section",
            title="4. Technical Findings",
            options={"categories": ["recon", "access", "postex"]},
        )

        rendered = _render_finding_section(section, self.context, "en")

        self.assertEqual(rendered.count("## 4. Technical Findings"), 1)
        self.assertIn("### Open Ports", rendered)
        self.assertIn("### Domain Admin Credentials", rendered)
        self.assertIn("**Phase:** Reconnaissance & Enumeration", rendered)
        self.assertIn("**Phase:** Initial Access & Exploitation", rendered)
        self.assertNotIn("Post-Exploitation & Lateral Movement", rendered)
        self.assertEqual(rendered.count("spectre:finding:start:"), 2)
        self.assertEqual(rendered.count("spectre:loot:"), 2)

    def test_generated_finding_uses_only_available_metadata_and_preserves_content(self):
        entry = dict(
            self.sample_loot[0],
            content="Credential evidence\n\n```bash\nid && sudo -l\n```",
        )
        rendered = "\n".join(_render_loot_entry_block(entry, lang="en"))

        self.assertIn("<!-- spectre:finding:start:loot_1 -->", rendered)
        self.assertRegex(
            rendered,
            r"spectre:loot:loot_1:[a-f0-9]{12} -->\n### Domain Admin Credentials",
        )
        self.assertIn(
            '**Severity:** <span class="severity-pill severity-critical">CRITICAL</span>',
            rendered,
        )
        self.assertIn("**Target:** `10.10.10.50`", rendered)
        self.assertIn("**Observed:** `2026-08-28 10:00:00`", rendered)
        self.assertIn("#### Description", rendered)
        self.assertIn("Credential evidence\n\n```bash\nid && sudo -l\n```", rendered)
        self.assertIn("<!-- spectre:finding:end:loot_1 -->", rendered)
        self.assertNotIn("**Phase:**", rendered)
        self.assertNotIn("Impact", rendered)
        self.assertNotIn("Recommendation", rendered)

    def test_generated_finding_omits_missing_optional_metadata(self):
        entry = {
            "id": "loot_minimal",
            "type": "note",
            "category": "misc",
            "severity": "info",
            "title": "Minimal finding",
            "content": "",
        }
        rendered = "\n".join(_render_loot_entry_block(entry, lang="en"))

        self.assertIn("**Severity:", rendered)
        self.assertNotIn("**Target:**", rendered)
        self.assertNotIn("**Observed:**", rendered)
        self.assertNotIn("#### Description", rendered)
        self.assertNotIn("#### Recommendation", rendered)

    def test_generated_finding_preserves_multiline_recommendation(self):
        entry = dict(
            self.sample_loot[0],
            recommendation=(
                "Rotate the exposed credentials.\n\n"
                "```bash\npasswd administrator\n```"
            ),
        )

        rendered = "\n".join(_render_loot_entry_block(entry, lang="en"))

        self.assertIn("#### Description", rendered)
        self.assertIn("#### Recommendation", rendered)
        self.assertIn("Rotate the exposed credentials.", rendered)
        self.assertIn("```bash\npasswd administrator\n```", rendered)

    def test_render_remediation_table(self):
        sec = TemplateSection(type="remediation_table")
        context = ReportContext(
            loot_entries=[
                dict(
                    self.sample_loot[1],
                    severity="medium",
                    recommendation="Restrict service exposure.",
                ),
                dict(
                    self.sample_loot[2],
                    recommendation="Remove the privileged writable path.",
                ),
                dict(self.sample_loot[0], recommendation=""),
            ]
        )
        out_de = _render_remediation_table(sec, context, "de")
        self.assertIn("Empfehlungen (Remediation-Plan)", out_de)
        self.assertIn("Remove the privileged writable path.", out_de)
        self.assertIn("Restrict service exposure.", out_de)
        self.assertNotIn("Domain Admin Credentials", out_de)
        self.assertNotIn("Root Proof", out_de)
        self.assertLess(out_de.index("| P2 |"), out_de.index("| P3 |"))
        self.assertIn("Finding #2", out_de)

    def test_remediation_table_without_real_actions_keeps_only_editing_scaffold(self):
        out = _render_remediation_table(
            TemplateSection(type="remediation_table"), self.context, "en"
        )

        self.assertIn("| | | |", out)
        for entry in self.sample_loot:
            self.assertNotIn(entry["title"], out)

    def test_remediation_sort_is_stable_within_priority(self):
        entries = [
            dict(
                self.sample_loot[0],
                id="high-first",
                severity="high",
                recommendation="First high-priority action.",
            ),
            dict(
                self.sample_loot[1],
                id="critical",
                severity="critical",
                recommendation="Critical action.",
            ),
            dict(
                self.sample_loot[2],
                id="high-second",
                severity="high",
                recommendation="Second high-priority action.",
            ),
        ]

        rendered = _render_remediation_table(
            TemplateSection(type="remediation_table"),
            ReportContext(loot_entries=entries),
            "en",
        )

        self.assertLess(rendered.index("Critical action."), rendered.index("First high"))
        self.assertLess(rendered.index("First high"), rendered.index("Second high"))

    def test_render_appendix(self):
        sec = TemplateSection(type="appendix")
        out = _render_appendix(sec, self.context, "de")
        self.assertIn("Anhang A: Chronologischer Befehlsverlauf", out)
        self.assertIn("nmap -sC -sV 10.10.10.50", out)
        self.assertIn("Anhang B: Screenshots", out)
        self.assertIn("![Root Proof](loot/proof.png)", out)

    def test_render_complete_legacy_template(self):
        output = self.renderer.render(LEGACY_DEFAULT_TEMPLATE, self.context)
        self.assertIn("# Pentest Report: HackTheBox_Legacy", output)
        self.assertIn("## Executive Summary", output)
        self.assertIn("## Scope & Limitations", output)
        self.assertIn("## 1. Reconnaissance & Enumeration", output)
        self.assertIn("## 2. Initial Access & Exploitation", output)
        self.assertIn("## 3. Privilege Escalation", output)
        self.assertIn("## Empfehlungen (Remediation-Plan)", output)
        self.assertIn("## Anhang A: Chronologischer Befehlsverlauf", output)
        self.assertIn("Erstellt mit SpectreHUD Pentest & CTF Companion", output)


if __name__ == "__main__":
    unittest.main()
