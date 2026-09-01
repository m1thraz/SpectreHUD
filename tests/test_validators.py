import unittest
from core.validators import (
    validate_project_state,
    validate_loot_entry,
    validate_loot_list,
    validate_clipboard_entry,
    validate_clipboard_list,
    validate_user_snippets,
    MAX_LOOT_ENTRIES,
    MAX_TITLE_LENGTH,
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
            "loot": "banana",  # str instead of list[dict]
            "clipboard_history": 42,  # int instead of list[dict]
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
            {
                "title": "Valid Cred",
                "content": "admin:pass",
                "type": "credentials",
                "category": "access",
            },
            {"type": "note"},  # missing title, content
            None,
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
            {"text": "whoami", "lines_count": -5},
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
            "invalid_string",
        ]
        validated = validate_user_snippets(raw_snippets)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["title"], "Valid Snippet")
        self.assertEqual(validated[0]["template"], "curl -s http://target")

    def test_deterministic_id_generation(self):
        """Tests that fallback ID generation is deterministic and process-independent."""
        entry1 = validate_loot_entry({"title": "Test Title", "content": "secret_data"})
        entry2 = validate_loot_entry({"title": "Test Title", "content": "secret_data"})
        self.assertEqual(entry1["id"], entry2["id"])
        self.assertTrue(entry1["id"].startswith("loot_gen_"))

        clip1 = validate_clipboard_entry({"text": "cat /etc/passwd"})
        clip2 = validate_clipboard_entry({"text": "cat /etc/passwd"})
        self.assertEqual(clip1["id"], clip2["id"])
        self.assertTrue(clip1["id"].startswith("clip_gen_"))

    def test_validator_product_limits(self):
        """Representative product limits truncate fields and cap persisted lists."""
        loot = validate_loot_entry({"title": "T" * (MAX_TITLE_LENGTH + 1), "content": "data"})
        self.assertEqual(len(loot["title"]), MAX_TITLE_LENGTH)

        entries = [
            {"title": f"Item {index}", "content": "data"} for index in range(MAX_LOOT_ENTRIES + 1)
        ]
        self.assertEqual(len(validate_loot_list(entries)), MAX_LOOT_ENTRIES)

    def test_is_file_size_valid(self):
        """Tests that is_file_size_valid correctly checks file size bounds on disk."""
        import tempfile
        from pathlib import Path
        from core.validators import is_file_size_valid

        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test.json"
            f.write_bytes(b"A" * 1000)
            self.assertTrue(is_file_size_valid(f, 1000))
            self.assertTrue(is_file_size_valid(f, 2000))
            self.assertFalse(is_file_size_valid(f, 500))
            self.assertFalse(is_file_size_valid(Path(td) / "non_existent.json", 1000))

    def test_format_timestamp(self):
        """Tests that format_timestamp correctly formats timestamps according to 24h and 12h modes."""

    def test_validate_loot_entry_severity(self):
        """Tests severity validation, normalization, and fallback defaults."""
        self.assertEqual(validate_loot_entry({"severity": "CRITICAL"})["severity"], "critical")
        self.assertEqual(validate_loot_entry({"severity": "high"})["severity"], "high")
        self.assertEqual(validate_loot_entry({"severity": "MEDIUM"})["severity"], "medium")
        self.assertEqual(validate_loot_entry({"severity": "low"})["severity"], "low")
        self.assertEqual(validate_loot_entry({"severity": "info"})["severity"], "info")
        # Invalid / missing -> defaults to info
        self.assertEqual(validate_loot_entry({})["severity"], "info")
        self.assertEqual(validate_loot_entry({"severity": "super_critical"})["severity"], "info")
        self.assertEqual(validate_loot_entry({"severity": None})["severity"], "info")


if __name__ == "__main__":
    unittest.main()
