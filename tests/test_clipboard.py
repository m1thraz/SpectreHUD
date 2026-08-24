import os
import unittest
import tempfile
from pathlib import Path
from core.clipboard_watcher import ClipboardWatcher
from core.loot_manager import LootManager

class TestClipboardWatcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)
        
        self.storage_file = self.temp_path / "test_clip.json"
        self.watcher = ClipboardWatcher(storage_file=self.storage_file)

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_add_and_deduplicate(self):
        # First entry
        e1 = self.watcher.add_entry("nmap -sC -sV 10.10.10.10", target_ip="10.10.10.10")
        self.assertIsNotNone(e1)
        self.assertEqual(len(self.watcher.history), 1)

        # Duplicate entry immediately following
        e2 = self.watcher.add_entry("nmap -sC -sV 10.10.10.10", target_ip="10.10.10.10")
        self.assertIsNone(e2)
        self.assertEqual(len(self.watcher.history), 1)

        # Different entry
        e3 = self.watcher.add_entry("whoami /priv", target_ip="10.10.10.10")
        self.assertIsNotNone(e3)
        self.assertEqual(len(self.watcher.history), 2)

    def test_filter_and_search(self):
        self.watcher.add_entry("gobuster dir -u http://10.10.10.50/ -w /usr/share/wordlists/dirb/common.txt", target_ip="10.10.10.50")
        self.watcher.add_entry("LinPEAS output:\n[+] SUID Binaries found:\n/usr/bin/pkexec\n/usr/bin/sudo", target_ip="10.10.10.50")
        self.watcher.add_entry("cat /etc/passwd", target_ip="10.10.10.99")

        # Search query
        gobuster_items = self.watcher.get_history(search_query="gobuster")
        self.assertEqual(len(gobuster_items), 1)

        # Target IP filter
        target_50_items = self.watcher.get_history(target_ip="10.10.10.50")
        self.assertEqual(len(target_50_items), 2)

        # Multiline / Output filter
        outputs = self.watcher.get_history(filter_type="outputs")
        self.assertEqual(len(outputs), 1)
        self.assertIn("LinPEAS", outputs[0]["text"])

    def test_export_report_markdown(self):
        # Setup loot manager
        loot_file = self.temp_path / "test_loot.json"
        loot_mgr = LootManager(storage_file=loot_file)
        loot_mgr.add_entry("credentials", "SSH admin", "admin:SecretPass", "10.10.10.77")
        loot_mgr.add_entry("flag", "User Flag", "THM{flag_abc_123}", "10.10.10.77")

        # Add clipboard history
        self.watcher.add_entry("nmap -p 22,80 10.10.10.77", target_ip="10.10.10.77")
        self.watcher.add_entry("ssh admin@10.10.10.77", target_ip="10.10.10.77")

        report_path = self.temp_path / "ctf_report.md"
        result = self.watcher.export_report_markdown(report_path, target_ip="10.10.10.77", loot_manager=loot_mgr)

        self.assertTrue(report_path.exists())
        content = report_path.read_text(encoding="utf-8")
        self.assertIn("CTF Session Report", content)
        self.assertIn("admin:SecretPass", content)
        self.assertIn("THM{flag_abc_123}", content)
        self.assertIn("nmap -p 22,80", content)
        self.assertIn("ssh admin@10.10.10.77", content)

    def test_pause_and_clear(self):
        self.watcher.add_entry("test cmd 1")
        self.assertEqual(len(self.watcher.history), 1)

        # Verify initial default is paused for privacy
        self.assertTrue(self.watcher.is_paused)

        signals_received = []
        self.watcher.logging_state_changed.connect(lambda active: signals_received.append(active))

        # Toggle pause (paused -> active)
        is_paused = self.watcher.toggle_pause()
        self.assertFalse(is_paused)
        self.assertEqual(signals_received[-1], True)

        # Toggle pause again (active -> paused)
        is_paused = self.watcher.toggle_pause()
        self.assertTrue(is_paused)
        self.assertEqual(signals_received[-1], False)

        # Set active explicitly
        self.watcher.set_paused(False)
        self.assertFalse(self.watcher.is_paused)
        self.assertEqual(signals_received[-1], True)

        # Clear history
        self.watcher.clear_history()
        self.assertEqual(len(self.watcher.history), 0)

if __name__ == "__main__":
    unittest.main()
