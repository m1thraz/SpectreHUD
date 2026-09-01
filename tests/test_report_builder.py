import os
import unittest
import tempfile
from pathlib import Path
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_builder import ReportBuilder


class TestReportBuilder(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

        self.loot_file = self.temp_path / "test_loot.json"
        self.clip_file = self.temp_path / "test_clip.json"

        self.loot_mgr = LootManager(storage_file=self.loot_file)
        self.clip_watcher = ClipboardWatcher(storage_file=self.clip_file)
        self.builder = ReportBuilder(
            loot_manager=self.loot_mgr, clipboard_watcher=self.clip_watcher
        )

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_empty_report(self):
        """Report with no loot and no history still contains all categories and summary."""
        report = self.builder.build(project_name="EmptyBox")

        self.assertIn("# Pentest Report: EmptyBox", report)
        self.assertIn("**Auftraggeber / Client**", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("### Findings-Übersicht", report)
        self.assertIn("## Scope & Limitations", report)
        self.assertIn("## 1. Reconnaissance & Enumeration", report)
        self.assertIn("## 2. Initial Access & Exploitation", report)
        self.assertIn("## 3. Privilege Escalation", report)
        self.assertIn("## 4. Post-Exploitation & Lateral Movement", report)
        self.assertIn("## 5. Custom Scripts & PoCs", report)
        self.assertIn("## 6. Miscellaneous", report)
        self.assertIn("## Empfehlungen (Remediation-Plan)", report)
        self.assertIn("## Anhang A: Chronologischer Befehlsverlauf (Terminal History)", report)
        self.assertIn("## Anhang B: Screenshots", report)
        self.assertIn("*Keine Einträge in dieser Phase.*", report)
        self.assertIn("*Keine Clipboard-Historie aufgezeichnet.*", report)
        self.assertIn("*Keine Screenshots in diesem Projekt vorhanden.*", report)
        self.assertIn("Erstellt mit SpectreHUD Pentest & CTF Companion", report)

    def test_categorized_loot_rendering(self):
        """Loot is correctly rendered into its respective category sections in order."""
        self.loot_mgr.add_entry(
            "directory", "Open Port 80", "/admin/login", "10.10.10.50", category="recon"
        )
        self.loot_mgr.add_entry(
            "credentials", "SSH Key", "id_rsa_key_content", "10.10.10.50", category="access"
        )
        self.loot_mgr.add_entry(
            "flag", "User Flag", "THM{user_123}", "10.10.10.50", category="access"
        )
        self.loot_mgr.add_entry(
            "hash", "Shadow Hash", "$6$root$...", "10.10.10.50", category="privesc"
        )
        self.loot_mgr.add_entry(
            "screenshot", "Root PoC", "loot/screenshot_root.png", "10.10.10.50", category="privesc"
        )
        self.loot_mgr.add_entry(
            "note", "Pivot Note", "Found subnet 192.168.1.0/24", "10.10.10.50", category="postex"
        )

        report = self.builder.build(target_ip="10.10.10.50", project_name="BoxAlpha")

        # Verify section order
        idx_recon = report.find("## 1. Reconnaissance & Enumeration")
        idx_access = report.find("## 2. Initial Access & Exploitation")
        idx_privesc = report.find("## 3. Privilege Escalation")
        idx_postex = report.find("## 4. Post-Exploitation & Lateral Movement")
        idx_misc = report.find("## 6. Miscellaneous")

        self.assertTrue(idx_recon < idx_access < idx_privesc < idx_postex < idx_misc)

        # Verify formatting
        self.assertIn("`/admin/login`", report)
        self.assertIn("```\nid_rsa_key_content\n```", report)
        self.assertIn("```\nTHM{user_123}\n```", report)
        self.assertIn("```\n$6$root$...\n```", report)
        self.assertIn("![Root PoC](loot/screenshot_root.png)", report)
        self.assertIn("Found subnet 192.168.1.0/24", report)

    def test_target_ip_filtering(self):
        """Entries from other targets are filtered out when target_ip is specified."""
        self.loot_mgr.add_entry(
            "credentials", "Target 1 Creds", "alice:pass1", "10.10.10.10", category="access"
        )
        self.loot_mgr.add_entry(
            "credentials", "Target 2 Creds", "bob:pass2", "10.10.10.20", category="access"
        )

        report_10 = self.builder.build(target_ip="10.10.10.10")
        self.assertIn("alice:pass1", report_10)
        self.assertNotIn("bob:pass2", report_10)

    def test_standalone_builder_without_clipboard_watcher(self):
        """ReportBuilder works safely with only LootManager and no ClipboardWatcher."""
        standalone_builder = ReportBuilder(loot_manager=self.loot_mgr, clipboard_watcher=None)
        self.loot_mgr.add_entry("credentials", "Standalone Admin", "admin:123", category="access")
        report = standalone_builder.build()
        self.assertIn("admin:123", report)
        self.assertIn("*Keine Clipboard-Historie aufgezeichnet.*", report)

    def test_standalone_builder_without_loot_manager(self):
        """ReportBuilder works safely with only ClipboardWatcher and no LootManager."""
        standalone_builder = ReportBuilder(loot_manager=None, clipboard_watcher=self.clip_watcher)
        self.clip_watcher.add_entry("whoami")
        report = standalone_builder.build()
        self.assertIn("## 1. Reconnaissance & Enumeration", report)
        self.assertIn("*Keine Einträge in dieser Phase.*", report)
        self.assertIn("whoami", report)

    def test_export_file(self):
        """Export writes file cleanly and enforces .md extension."""
        self.loot_mgr.add_entry("flag", "Flag", "CTF{flag}", category="privesc")
        out_file = self.temp_path / "test_report.txt"  # intentionally .txt

        msg = self.builder.export(out_file, project_name="ExportTest")
        expected_md = self.temp_path / "test_report.md"

        self.assertTrue(expected_md.exists())
        self.assertIn("CTF{flag}", expected_md.read_text(encoding="utf-8"))
        self.assertIn("Report erfolgreich generiert", msg)


if __name__ == "__main__":
    unittest.main()
