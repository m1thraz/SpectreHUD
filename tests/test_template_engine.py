import unittest
from core.reporting.template_engine import (
    TemplateSection,
    ReportContext,
    TemplateRenderer,
    LEGACY_DEFAULT_TEMPLATE,
    _render_header_metadata,
    _render_executive_summary,
    _render_phase_section,
    _render_remediation_table,
    _render_appendix,
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
        self.assertIn("🔴 1 Critical", out)
        self.assertIn("🟠 1 High", out)
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

    def test_render_remediation_table(self):
        sec = TemplateSection(type="remediation_table")
        out_de = _render_remediation_table(sec, self.context, "de")
        self.assertIn("Empfehlungen (Remediation-Plan)", out_de)
        self.assertIn("Domain Admin Credentials", out_de)
        self.assertIn("P1", out_de)

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
