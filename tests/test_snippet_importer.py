import os
import sys
import unittest
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.snippet_manager import SnippetManager
from core.snippet_importer import (
    parse_snippets_json,
    parse_snippets_markdown,
    normalize_template_variables,
    import_snippets_from_file
)


class TestSnippetImporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        (self.temp_path / "config").mkdir(parents=True, exist_ok=True)
        self.mgr = SnippetManager(user_snippets_path=self.temp_path / "config" / "user_snippets.json")

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_normalize_template_variables(self):
        raw = "nmap $TARGET -p $PORT -e tun0; nc $ATTACKER $LPORT"
        norm = normalize_template_variables(raw)
        self.assertIn("{{TARGET_IP}}", norm)
        self.assertIn("{{PORT}}", norm)
        self.assertIn("{{ATTACKER_IP}}", norm)

    def test_parse_snippets_json_list(self):
        json_data = """
        [
            {
                "title": "Ping Sweep",
                "category": "Network",
                "subcategory": "ICMP",
                "template": "ping -c 1 $TARGET",
                "description": "Check host alive",
                "tags": ["ping", "icmp"]
            }
        ]
        """
        snippets = parse_snippets_json(json_data)
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0]["title"], "Ping Sweep")
        self.assertEqual(snippets[0]["template"], "ping -c 1 {{TARGET_IP}}")
        self.assertTrue(snippets[0]["is_custom"])

    def test_parse_snippets_markdown(self):
        md_data = """
# Reconnaissance
## Port Scanning

### Nmap Quick TCP
Scans top 100 ports
```bash
nmap -F $TARGET
```

### Banner Grabbing
```bash
nc -v $TARGET 80
```
        """
        snippets = parse_snippets_markdown(md_data)
        self.assertEqual(len(snippets), 2)
        self.assertEqual(snippets[0]["title"], "Nmap Quick TCP")
        self.assertEqual(snippets[0]["category"], "Reconnaissance")
        self.assertEqual(snippets[0]["subcategory"], "Port Scanning")
        self.assertEqual(snippets[0]["template"], "nmap -F {{TARGET_IP}}")
        self.assertEqual(snippets[0]["description"], "Scans top 100 ports")

        self.assertEqual(snippets[1]["title"], "Banner Grabbing")
        self.assertEqual(snippets[1]["template"], "nc -v {{TARGET_IP}} 80")

    def test_import_from_file_json(self):
        fpath = self.temp_path / "test_import.json"
        fpath.write_text('[{"title": "Custom Cmd", "template": "echo 123"}]', encoding="utf-8")
        
        count = self.mgr.import_from_file(fpath)
        self.assertEqual(count, 1)
        
        loaded = self.mgr.get_snippets()
        custom_snips = [s for s in loaded if s.get("title") == "Custom Cmd"]
        self.assertEqual(len(custom_snips), 1)

    def test_import_from_file_markdown(self):
        fpath = self.temp_path / "cheatsheet.md"
        fpath.write_text("""
# Web & HTTP
## Enumeration

### Gobuster Directory Search
```bash
gobuster dir -u http://$TARGET -w /wordlists/dir.txt
```
""", encoding="utf-8")

        count = self.mgr.import_from_file(fpath)
        self.assertEqual(count, 1)

        custom_snips = [s for s in self.mgr.get_snippets() if "Gobuster" in s.get("title", "")]
        self.assertEqual(len(custom_snips), 1)
        self.assertEqual(custom_snips[0]["template"], "gobuster dir -u http://{{TARGET_IP}} -w /wordlists/dir.txt")


if __name__ == "__main__":
    unittest.main()
