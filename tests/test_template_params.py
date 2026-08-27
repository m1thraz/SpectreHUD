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

    def test_username_password_globals(self):
        tmpl = "hydra -l {{USERNAME}} -p {{PASSWORD}} ssh://{{TARGET_IP}}:{{PORT}}"
        variables = {
            "target_ip": "10.10.10.50",
            "port": "22",
            "username": "root",
            "password": "secretpassword"
        }
        # USERNAME and PASSWORD are now recognized globals
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, [])
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "hydra -l root -p secretpassword ssh://10.10.10.50:22")

    def test_user_pass_short_aliases(self):
        tmpl = "smbclient //{{TARGET_IP}}/share -U {{USER}}%{{PASS}}"
        variables = {
            "target_ip": "10.10.10.70",
            "username": "alice",
            "password": "Password123!"
        }
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, [])
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "smbclient //10.10.10.70/share -U alice%Password123!")

    def test_full_parameter_tags_and_smart_presets(self):
        from core.template_engine import SMART_PRESETS
        all_tags = [
            "DOMAIN", "DNS_SERVER", "WORDLIST", "HASH_FILE",
            "TABLE_NAME", "DATABASE_NAME", "FILE_PATH", "FILE_NAME",
            "ENDPOINT", "SERVICE_NAME", "SUBNET", "PORT_SEQUENCE",
            "LOCAL_HOST", "LOCAL_PORT", "REQUEST_FILE", "PARAMETER",
            "EIP_VALUE", "PATTERN", "SSH_PUBLIC_KEY", "ZIP_FILE",
            "SOURCE_FILE", "OUTPUT_FILE", "OBJECT_FILE",
            "USER_FIELD", "PASS_FIELD", "FAIL_MESSAGE", "LOG_PATH"
        ]

        # Verify all 27 tags have smart presets defined
        for tag in all_tags:
            self.assertIn(tag, SMART_PRESETS, f"Missing preset for tag: {tag}")
            self.assertTrue(len(SMART_PRESETS[tag]) > 0)

        # Verify extract_unresolved_placeholders detects all of them
        constructed_tmpl = " ".join([f"{{{{{tag}}}}}" for tag in all_tags])
        extracted = TemplateEngine.extract_unresolved_placeholders(constructed_tmpl, {})
        for tag in all_tags:
            self.assertIn(tag, extracted)

if __name__ == "__main__":
    unittest.main()
