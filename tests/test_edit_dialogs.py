"""
Unit tests for EditHistoryDialog, EditNoteDialog, and double-click to edit on cards.
"""

import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QMouseEvent

from ui.history_edit_dialog import EditHistoryDialog
from ui.note_edit_dialog import EditNoteDialog
from ui.history_card import HistoryCard
from ui.quick_note_card import QuickNoteCard
from ui.loot_card import LootCard

app = QApplication.instance() or QApplication([])


class TestEditDialogsAndCards(unittest.TestCase):
    def test_history_edit_dialog(self):
        entry = {
            "id": "clip_123",
            "text": "nmap -sV 10.10.10.1",
            "target_ip": "10.10.10.1",
        }
        dlg = EditHistoryDialog(entry)
        self.assertEqual(dlg.txt_target.text(), "10.10.10.1")
        self.assertEqual(dlg.txt_content.toPlainText(), "nmap -sV 10.10.10.1")

        # Edit fields
        dlg.txt_target.setText("10.10.10.99")
        dlg.txt_content.setPlainText("nmap -sC -sV 10.10.10.99")

        data = dlg.get_data()
        self.assertEqual(data["target_ip"], "10.10.10.99")
        self.assertEqual(data["text"], "nmap -sC -sV 10.10.10.99")
        dlg.close()

    def test_note_edit_dialog(self):
        entry = {
            "id": "note_456",
            "text": "Found SQLi on /login.php",
            "category": "access",
            "status": "inbox",
            "target_ip": "10.10.10.5",
        }
        dlg = EditNoteDialog(entry)
        self.assertEqual(dlg.combo_cat.currentData(), "access")
        self.assertEqual(dlg.combo_status.currentData(), "inbox")
        self.assertEqual(dlg.txt_target.text(), "10.10.10.5")
        self.assertEqual(dlg.txt_text.toPlainText(), "Found SQLi on /login.php")

        # Edit fields
        dlg.combo_cat.setCurrentIndex(2)  # privesc
        dlg.combo_status.setCurrentIndex(1)  # followup
        dlg.txt_target.setText("10.10.10.6")
        dlg.txt_text.setPlainText("Updated SQLi POC")

        data = dlg.get_data()
        self.assertEqual(data["category"], "privesc")
        self.assertEqual(data["status"], "followup")
        self.assertEqual(data["target_ip"], "10.10.10.6")
        self.assertEqual(data["text"], "Updated SQLi POC")
        dlg.close()

    def test_history_card_double_click_emits_edit_requested(self):
        entry = {
            "id": "clip_789",
            "text": "whoami /all",
            "target_ip": "10.10.10.10",
        }
        card = HistoryCard(entry)
        emitted = []
        card.edit_requested.connect(emitted.append)

        # 1. Double click on card frame
        dbl_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        card.mouseDoubleClickEvent(dbl_event)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["id"], "clip_789")

        # 2. Double click on content label
        card.eventFilter(card.lbl_content, dbl_event)
        self.assertEqual(len(emitted), 2)
        card.close()

    def test_quick_note_card_double_click_emits_edit_requested(self):
        entry = {
            "id": "note_101",
            "text": "Check SMB share",
            "category": "recon",
            "status": "inbox",
        }
        card = QuickNoteCard(entry)
        emitted = []
        card.edit_requested.connect(emitted.append)

        dbl_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # 1. Double click on card frame
        card.mouseDoubleClickEvent(dbl_event)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["id"], "note_101")

        # 2. Double click on content label
        card.eventFilter(card.lbl_content, dbl_event)
        self.assertEqual(len(emitted), 2)
        card.close()

    def test_loot_card_double_click_emits_edit_requested(self):
        entry = {
            "id": "loot_202",
            "title": "Admin Password",
            "content": "P@ssword123",
            "type": "credential",
            "category": "access",
        }
        card = LootCard(entry)
        emitted = []
        card.edit_requested.connect(emitted.append)

        dbl_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        # 1. Double click on card frame
        card.mouseDoubleClickEvent(dbl_event)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]["id"], "loot_202")

        # 2. Double click on content label
        card.eventFilter(card.lbl_content, dbl_event)
        self.assertEqual(len(emitted), 2)

        # 3. Double click on title label
        card.eventFilter(card.lbl_title, dbl_event)
        self.assertEqual(len(emitted), 3)
        card.close()


if __name__ == "__main__":
    unittest.main()
