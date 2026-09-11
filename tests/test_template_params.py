import unittest
import tempfile
from pathlib import Path
from core.snippets import SMART_PRESETS, TemplateEngine


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
        tmpl = (
            "curl -X POST http://{{TARGET_IP}}:{{PORT}}/search -d '{{PARAM}}=test' -w {{WORDLIST}}"
        )
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
            "WORDLIST": "/usr/share/wordlists/rockyou.txt",
        }
        rendered = TemplateEngine.render_with_custom(tmpl, variables, custom)
        self.assertEqual(rendered, "hashcat -m 1000 -a 0 ntlm.txt /usr/share/wordlists/rockyou.txt")

    def test_blank_standard_values_keep_presets_and_placeholders(self):
        tmpl = "{{TARGET_IP}} {{ATTACKER_IP}} {{PORT}} {{WORDLIST}} {{USERNAME}}"
        variables = {
            "target_ip": "",
            "attacker_ip": "   ",
            "port": "",
            "wordlist": "\t",
            "username": "",
        }

        rendered = TemplateEngine.render(tmpl, variables)

        self.assertEqual(
            rendered,
            f"10.10.10.10 10.10.14.5 4444 {SMART_PRESETS['WORDLIST']} {{{{USERNAME}}}}",
        )

    def test_blank_custom_value_keeps_placeholder_visible(self):
        rendered = TemplateEngine.render_with_custom(
            "curl {{TARGET_IP}}/{{ENDPOINT}}",
            {"target_ip": "10.10.10.20"},
            {"ENDPOINT": ""},
        )

        self.assertEqual(rendered, "curl 10.10.10.20/{{ENDPOINT}}")

    def test_non_blank_alias_value_still_overrides_default(self):
        rendered = TemplateEngine.render("connect {{RHOST}}", {"RHOST": "192.0.2.10"})

        self.assertEqual(rendered, "connect 192.0.2.10")

    def test_username_password_globals(self):
        tmpl = "hydra -l {{USERNAME}} -p {{PASSWORD}} ssh://{{TARGET_IP}}:{{PORT}}"
        variables = {
            "target_ip": "10.10.10.50",
            "port": "22",
            "username": "root",
            "password": "secretpassword",
        }
        # USERNAME and PASSWORD are now recognized globals
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, [])
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "hydra -l root -p secretpassword ssh://10.10.10.50:22")

    def test_user_pass_short_aliases(self):
        tmpl = "smbclient //{{TARGET_IP}}/share -U {{USER}}%{{PASS}}"
        variables = {"target_ip": "10.10.10.70", "username": "alice", "password": "Password123!"}
        unresolved = TemplateEngine.extract_unresolved_placeholders(tmpl, variables)
        self.assertEqual(unresolved, [])
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "smbclient //10.10.10.70/share -U alice%Password123!")

    def test_full_parameter_tags_and_smart_presets(self):
        all_tags = [
            "DOMAIN",
            "DNS_SERVER",
            "WORDLIST",
            "HASH_FILE",
            "TABLE_NAME",
            "DATABASE_NAME",
            "FILE_PATH",
            "FILE_NAME",
            "ENDPOINT",
            "SERVICE_NAME",
            "SUBNET",
            "PORT_SEQUENCE",
            "LOCAL_HOST",
            "LOCAL_PORT",
            "REQUEST_FILE",
            "PARAMETER",
            "EIP_VALUE",
            "PATTERN",
            "SSH_PUBLIC_KEY",
            "ZIP_FILE",
            "SOURCE_FILE",
            "OUTPUT_FILE",
            "OBJECT_FILE",
            "USER_FIELD",
            "PASS_FIELD",
            "FAIL_MESSAGE",
            "LOG_PATH",
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
