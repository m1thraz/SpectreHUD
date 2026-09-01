import unittest
import tempfile
from pathlib import Path
from core.template_engine import TemplateEngine
from core.snippet_manager import SnippetManager


class TestCoreModules(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.temp_config_dir = self.temp_path / "config"
        self.temp_snippets_file = self.temp_path / "custom_snippets.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_template_engine(self):
        tmpl = "curl -H 'X-IP: {{ATTACKER_IP}}' http://{{TARGET_IP}}:{{PORT}}/"
        variables = {"target_ip": "10.10.10.99", "attacker_ip": "10.10.14.33", "port": "8080"}
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "curl -H 'X-IP: 10.10.14.33' http://10.10.10.99:8080/")

    def test_template_aliases(self):
        tmpl = "nc -lvnp {{LPORT}} # target is {{RHOST}}"
        variables = {"target_ip": "192.168.1.100", "attacker_ip": "192.168.1.50", "port": "9001"}
        rendered = TemplateEngine.render(tmpl, variables)
        self.assertEqual(rendered, "nc -lvnp 9001 # target is 192.168.1.100")

    def test_snippet_manager_load_and_search(self):
        sm = SnippetManager(user_snippets_path=self.temp_snippets_file)
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
        sm = SnippetManager(user_snippets_path=self.temp_snippets_file)
        cats = sm.get_categories()
        cat_ids = [c["id"] for c in cats]
        self.assertIn("all", cat_ids)
        self.assertIn("web_http", cat_ids)
        self.assertIn("linux_shell", cat_ids)

    def test_snippet_manager_favorites_lifecycle(self):
        fav_file = self.temp_path / "custom_favorites.json"
        sm = SnippetManager(user_snippets_path=self.temp_snippets_file, favorites_path=fav_file)
        self.assertGreater(len(sm.snippets), 2)

        target_id = sm.snippets[1]["id"]
        self.assertFalse(sm.is_favorite(target_id))

        # Toggle on
        res = sm.toggle_favorite(target_id)
        self.assertTrue(res)
        self.assertTrue(sm.is_favorite(target_id))
        self.assertTrue(fav_file.exists())

        # Pinned snippet should now be first in search results
        results = sm.search()
        self.assertEqual(results[0]["id"], target_id)
        self.assertTrue(results[0]["is_favorite"])

        # Category "favorites" should return only this snippet
        fav_results = sm.get_snippets(category_id="favorites")
        self.assertEqual(len(fav_results), 1)
        self.assertEqual(fav_results[0]["id"], target_id)

        # Check category count
        cats = sm.get_categories()
        fav_cat = next(c for c in cats if c["id"] == "favorites")
        self.assertEqual(fav_cat["count"], 1)

        # Test reload from disk
        sm2 = SnippetManager(user_snippets_path=self.temp_snippets_file, favorites_path=fav_file)
        self.assertTrue(sm2.is_favorite(target_id))
        self.assertEqual(sm2.search()[0]["id"], target_id)

        # Toggle off
        res_off = sm2.toggle_favorite(target_id)
        self.assertFalse(res_off)
        self.assertFalse(sm2.is_favorite(target_id))
        self.assertEqual(len(sm2.get_snippets(category_id="favorites")), 0)


if __name__ == "__main__":
    unittest.main()
