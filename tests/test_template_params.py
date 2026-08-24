import unittest
import tempfile
from pathlib import Path
from core.template_engine import TemplateEngine
from core.config import ConfigManager

class TestTemplateParams(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_config_dir = Path(self.temp_dir.name) / "config"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_all_placeholders(self):
        tmpl = "gobuster dir -u http://{{TARGET_IP}}:{{PORT}}/ -w {{WORDLIST}} -x {{EXTENSIONS}}"
        placeholders = TemplateEngine.extract_all_placeholders(tmpl)
        self.assertEqual(placeholders, ["TARGET_IP", "PORT", "WORDLIST", "EXTENSIONS"])

    def test_extract_unresolved_placeholders(self):
        # TARGET_IP and PORT are global, WORDLIST and PARAM are custom
        tmpl = "curl -X POST http://{{TARGET_IP}}:{{PORT}}/search -d '{{PARAM}}=test' -w {{WORDLIST}}"
        variables = {"target_ip": "10.10.10.10", "port": "8080"}
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, ["PARAM", "WORDLIST"])

    def test_no_unresolved_placeholders(self):
        tmpl = "nmap -sC -sV -p {{PORT}} {{TARGET_IP}}"
        variables = {"target_ip": "10.10.10.10", "port": "8080"}
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, [])

    def test_render_with_custom(self):
        tmpl = "hashcat -m {{MODE}} -a 0 {{HASH_FILE}} {{WORDLIST}}"
        variables = {"target_ip": "10.10.10.10"}
        custom = {
            "MODE": "1000",
            "HASH_FILE": "ntlm.txt",
            "WORDLIST": "/usr/share/wordlists/rockyou.txt"
        }
        rendered = TemplateEngine.render_with_custom(tmpl, variables, custom)
        self.assertEqual(rendered, "hashcat -m 1000 -a 0 ntlm.txt /usr/share/wordlists/rockyou.txt")

    def test_session_param_cache(self):
        cfg = ConfigManager(config_dir=self.temp_config_dir)
        cfg.set_cached_param("WORDLIST", "/usr/share/wordlists/rockyou.txt")
        self.assertEqual(cfg.get_cached_param("WORDLIST"), "/usr/share/wordlists/rockyou.txt")
        self.assertEqual(cfg.get_cached_param("NON_EXISTENT", "default"), "default")

if __name__ == "__main__":
    unittest.main()
