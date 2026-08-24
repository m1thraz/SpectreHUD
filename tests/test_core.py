import unittest
from pathlib import Path
from core.template_engine import TemplateEngine
from core.snippet_manager import SnippetManager
from core.config import ConfigManager

class TestCoreModules(unittest.TestCase):

    def test_template_engine(self):
        tmpl = "curl -H 'X-IP: {{ATTACKER_IP}}' http://{{TARGET_IP}}:{{PORT}}/"
        variables = {
            "target_ip": "10.10.10.99",
            "attacker_ip": "10.10.14.33",
            "port": "8080"
        }
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "curl -H 'X-IP: 10.10.14.33' http://10.10.10.99:8080/")

    def test_template_aliases(self):
        tmpl = "nc -lvnp {{LPORT}} # target is {{RHOST}}"
        variables = {
            "target_ip": "192.168.1.100",
            "attacker_ip": "192.168.1.50",
            "port": "9001"
        }
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "nc -lvnp 9001 # target is 192.168.1.100")

    def test_snippet_manager_load_and_search(self):
        sm = SnippetManager()
        self.assertGreater(len(sm.snippets), 0)
        
        # Test searching for 'curl'
        curl_snippets = sm.search(query="curl")
        self.assertGreater(len(curl_snippets), 0)
        for s in curl_snippets:
            full_text = f"{s['title']} {s['description']} {s['template']} {' '.join(s.get('tags', []))}".lower()
            self.assertIn("curl", full_text)

        # Test searching for 'sql'
        sql_snippets = sm.search(query="sql")
        self.assertGreater(len(sql_snippets), 0)

    def test_snippet_categories(self):
        sm = SnippetManager()
        cats = sm.get_categories()
        cat_ids = [c["id"] for c in cats]
        self.assertIn("all", cat_ids)
        self.assertIn("web_http", cat_ids)
        self.assertIn("linux_shell", cat_ids)

if __name__ == "__main__":
    unittest.main()
