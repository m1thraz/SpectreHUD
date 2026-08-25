import unittest
from core.validators import (
    validate_project_state,
    validate_loot_entry,
    validate_loot_list,
    validate_clipboard_entry,
    validate_clipboard_list,
    validate_user_snippets
)


class TestSemanticValidators(unittest.TestCase):
    """
    Tests semantic validation of JSON data structures against corruption,
    type confusion, missing fields, and manual user editing errors.
    """

    def test_validate_project_state_type_confusion(self):
        """Tests that passing string, int, or corrupted structures returns a healthy default schema."""
        # Non-dict inputs
        self.assertEqual(validate_project_state("invalid")["name"], "Default")
        self.assertEqual(validate_project_state(12345)["target_ip"], "10.10.10.10")
        self.assertEqual(validate_project_state(None)["loot"], [])

        # Corrupted fields inside dict
        corrupted = {
            "name": "BoxCorrupt",
            "target_ip": 10101010,  # int instead of str
            "port": None,
            "loot": "banana",       # str instead of list[dict]
            "clipboard_history": 42 # int instead of list[dict]
        }
        state = validate_project_state(corrupted, fallback_name="BoxCorrupt")
        self.assertEqual(state["name"], "BoxCorrupt")
        self.assertEqual(state["target_ip"], "10101010")
        self.assertEqual(state["port"], "4444")
        self.assertIsInstance(state["loot"], list)
        self.assertEqual(state["loot"], [])
        self.assertIsInstance(state["clipboard_history"], list)
        self.assertEqual(state["clipboard_history"], [])

    def test_validate_loot_list_with_mixed_malformed_items(self):
        """Tests that malformed items inside a loot list are filtered or normalized."""
        raw_loot = [
            "string_instead_of_dict",
            123,
            {"title": "Valid Cred", "content": "admin:pass", "type": "credentials", "category": "access"},
            {"type": "note"},  # missing title, content
            None
        ]
        validated = validate_loot_list(raw_loot)
        self.assertEqual(len(validated), 2)
        self.assertEqual(validated[0]["title"], "Valid Cred")
        self.assertEqual(validated[0]["content"], "admin:pass")
        self.assertEqual(validated[1]["title"], "Unbenannter Eintrag")
        self.assertEqual(validated[1]["type"], "note")

    def test_validate_clipboard_list_with_mixed_malformed_items(self):
        """Tests that invalid clipboard entries (e.g. empty text, non-dict) are handled safely."""
        raw_history = [
            {"text": "nmap -sV 10.10.10.10", "is_multiline": "not_a_bool"},
            {"text": ""},  # empty text should be skipped
            "not_a_dict",
            {"text": "whoami", "lines_count": -5}
        ]
        validated = validate_clipboard_list(raw_history)
        self.assertEqual(len(validated), 2)
        self.assertEqual(validated[0]["text"], "nmap -sV 10.10.10.10")
        self.assertEqual(validated[1]["text"], "whoami")
        self.assertEqual(validated[1]["lines_count"], 1)

    def test_validate_user_snippets(self):
        """Tests user snippets validation against incomplete or invalid JSON."""
        raw_snippets = [
            {"title": "Valid Snippet", "template": "curl -s http://target"},
            {"title": "Missing Template"},
            {"template": "Missing Title"},
            "invalid_string"
        ]
        validated = validate_user_snippets(raw_snippets)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["title"], "Valid Snippet")
        self.assertEqual(validated[0]["template"], "curl -s http://target")
        self.assertTrue(validated[0]["is_custom"])


if __name__ == "__main__":
    unittest.main()
