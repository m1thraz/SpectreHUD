import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt6.QtCore import QMimeData, QUrl

from core.project import ProjectManager
from core.loot_manager import LootManager
from core.clipboard_watcher import ClipboardWatcher
from core.report_file_manager import ReportFileManager
from core.i18n import t
from ui.report.dialogs import ReportGenerationDialog
from ui.report.preview import ReportPreviewEdit
from ui.report_editor_tab import AUTOSAVE_INTERVAL_MS, ReportEditorTab, ViewMode

app = QApplication.instance() or QApplication(sys.argv)


class TestReportEditorTab(unittest.TestCase):
    """Tests ReportEditorTab ViewModes, editable live preview, commit, and safety guards."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path / "config")
        os.environ["SPECTRE_PROJECTS_DIR"] = str(self.temp_path / "projects")

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("TestBox", target_ip="10.10.10.42")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardWatcher(storage_file=self.temp_path / "config" / "clip.json")
        self.report_file_mgr = ReportFileManager(self.project_mgr)

        self.tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        self.tab.load_project("TestBox")
        self.tab.show()

    def tearDown(self):
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_PROJECTS_DIR", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_initial_view_mode_is_split(self):
        """Default view mode must be SPLIT with preview read-only."""
        self.assertEqual(self.tab._view_mode, ViewMode.SPLIT)
        self.assertTrue(self.tab.editor.isVisible())
        self.assertTrue(self.tab.preview.isVisible())
        self.assertTrue(self.tab.preview.isReadOnly())
        self.assertIn("Split", self.tab.lbl_status.text())
        self.assertTrue(self.tab._view_actions[ViewMode.SPLIT].isChecked())
        self.assertFalse(hasattr(self.tab, "btn_mode_editor"))

    def test_obsidian_export_delegates_current_editor_state(self):
        coordinator = MagicMock()
        self.tab.export_coordinator = coordinator
        self.tab.editor.setPlainText("# Current report\nEvidence")

        self.tab._on_export_obsidian_clicked()

        coordinator.export_report_to_obsidian.assert_called_once_with(
            self.tab,
            "TestBox",
            "# Current report\nEvidence",
        )

    def test_template_selection_is_in_report_generation_dialog(self):
        """Templates are selected immediately before report generation, not in the toolbar."""
        self.assertFalse(hasattr(self.tab, "combo_templates"))

        dialog = ReportGenerationDialog(
            template_repo=self.tab.template_repo,
            selected_template=self.tab.active_template,
            has_existing_report=True,
            parent=self.tab,
        )
        self.assertGreater(dialog.combo_templates.count(), 0)
        self.assertEqual(
            dialog.windowTitle(), t("report.generate_title", "Generate Report from Loot")
        )

    def test_html_export_theme_buttons_have_room_for_their_labels(self):
        """The two long theme labels must not be elided in the export chooser."""
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel):
            self.assertIsNone(self.tab._select_html_export_theme())

        dialogs = self.tab.window().findChildren(QMessageBox)
        self.assertEqual(len(dialogs), 1)
        dialog = dialogs[0]
        self.assertGreaterEqual(dialog.minimumWidth(), 640)
        buttons = {button.text(): button for button in dialog.buttons()}
        self.assertGreaterEqual(
            buttons[t("report.html_theme_dark", "Dark — SpectreHUD")].minimumWidth(), 190
        )
        self.assertGreaterEqual(
            buttons[t("report.html_theme_light", "Light — Client / Print")].minimumWidth(), 190
        )

    def test_view_mode_switching(self):
        """Tests switching between EDITOR, PREVIEW, and SPLIT modes."""
        # 1. Switch to EDITOR mode
        self.tab._set_view_mode(ViewMode.EDITOR)
        self.assertEqual(self.tab._view_mode, ViewMode.EDITOR)
        self.assertTrue(self.tab.editor.isVisible())
        self.assertFalse(self.tab.preview.isVisible())
        self.assertTrue(self.tab.preview.isReadOnly())
        self.assertIn("Editor", self.tab.lbl_status.text())
        self.assertTrue(self.tab._view_actions[ViewMode.EDITOR].isChecked())

        # 2. Switch to PREVIEW mode (editable)
        self.tab._set_view_mode(ViewMode.PREVIEW)
        self.assertEqual(self.tab._view_mode, ViewMode.PREVIEW)
        self.assertFalse(self.tab.editor.isVisible())
        self.assertTrue(self.tab.preview.isVisible())
        self.assertFalse(self.tab.preview.isReadOnly())
        self.assertIn("Live-Ansicht", self.tab.lbl_status.text())

        # 3. Cycle view mode back to EDITOR
        self.tab._cycle_view_mode()
        self.assertEqual(self.tab._view_mode, ViewMode.EDITOR)

    def test_live_preview_commit_to_markdown(self):
        """Tests that editing in PREVIEW mode commits markdown back to editor on mode switch."""
        self.tab.editor.setPlainText("# Initial Heading\n\nSome initial content.")
        self.tab.save()
        self.assertFalse(self.tab.is_dirty())

        # Enter preview mode
        self.tab._set_view_mode(ViewMode.PREVIEW)
        self.assertFalse(self.tab.preview.isReadOnly())

        # Edit rich text document directly
        cursor = self.tab.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nAppended live text.")

        # Switch to SPLIT mode -> triggers _commit_preview_to_markdown
        self.tab._set_view_mode(ViewMode.SPLIT)
        self.assertTrue(self.tab.is_dirty())
        self.assertIn("Appended live text", self.tab.editor.toPlainText())
        self.assertTrue(self.tab.preview.isReadOnly())

    def test_preview_commit_on_save(self):
        """Tests that save() automatically commits pending preview edits."""
        self.tab.editor.setPlainText("# Base Report")
        self.tab.save()

        self.tab._set_view_mode(ViewMode.PREVIEW)
        cursor = self.tab.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nSaved via preview.")

        saved = self.tab.save()
        self.assertTrue(saved)
        self.assertFalse(self.tab.is_dirty())
        self.assertIn("Saved via preview", self.tab.editor.toPlainText())

    def test_sanity_check_guard_against_truncation(self):
        """Tests that extreme content loss prompts warning and can be aborted/reverted."""
        long_content = "# Section\n\n" + ("Important pentest findings line.\n" * 20)
        self.tab.editor.setPlainText(long_content)
        self.tab.save()

        self.tab._set_view_mode(ViewMode.PREVIEW)

        # Clear almost everything in preview document (drastic reduction)
        self.tab.preview.setPlainText("Short")

        # User chooses "No" on warning dialog
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No):
            self.tab._set_view_mode(ViewMode.SPLIT)

        # Content should be restored from baseline snapshot
        self.assertIn("Important pentest findings line", self.tab.editor.toPlainText())

    def test_report_preview_edit_blocks_image_mime_drops(self):
        """Tests that ReportPreviewEdit blocks image mime data drops."""
        edit = ReportPreviewEdit()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("malicious.png")])
        edit.insertFromMimeData(mime)
        # Text should remain empty because image drop was rejected
        self.assertEqual(edit.toPlainText().strip(), "")

    def test_find_replace_and_autosave(self):
        self.tab.editor.setPlainText("alpha beta alpha")
        self.tab.editor.setFocus()
        self.tab.find_replace.open()
        self.tab.find_replace.find_input.setText("alpha")
        self.assertTrue(self.tab.find_replace.isVisible())
        self.assertEqual(self.tab.find_replace.count_label.text(), "2 Treffer")
        self.tab.find_replace.replace_input.setText("omega")
        self.tab.find_replace.replace_all()
        self.assertEqual(self.tab.editor.toPlainText(), "omega beta omega")
        self.tab.find_replace.close_bar()
        self.assertFalse(self.tab.find_replace.isVisible())

        self.tab.report_file_manager.save = MagicMock(return_value=True)
        self.tab._set_dirty(False)
        self.tab._autosave()
        self.tab.report_file_manager.save.assert_not_called()
        self.tab._set_dirty(True)
        self.tab._autosave()
        self.tab.report_file_manager.save.assert_called_once()
        self.assertEqual(self.tab._autosave_timer.interval(), AUTOSAVE_INTERVAL_MS)

    def test_autosave_failure_is_non_modal(self):
        self.tab._set_dirty(True)
        self.tab.report_file_manager.save = MagicMock(return_value=False)
        with patch.object(QMessageBox, "exec") as message_exec:
            self.tab._autosave()
        message_exec.assert_not_called()
        self.assertTrue(self.tab.is_dirty())

    def test_btn_append_loot_exists_in_toolbar(self):
        """Ticket 24: Verify 'Aus Loot ergänzen' button exists and is positioned in the action toolbar."""
        self.assertTrue(hasattr(self.tab, "btn_append_loot"))
        self.assertEqual(self.tab.btn_append_loot.text(), t("report.append_loot", "Add Missing Loot"))

    def test_append_loot_saves_dirty_state_first_and_preserves_manual_edits(self):
        """Ticket 25 & 38: Dirty editor content must be committed & saved before sync to ensure backup contains it."""
        initial_disk_text = "# Outdated Disk Report\n\n## 1. Reconnaissance & Enumeration\n\n*Keine Einträge in dieser Phase.*\n\n_Eigene Anmerkungen zu dieser Phase:_\n"
        self.report_file_mgr.save(initial_disk_text, "TestBox")

        # User types manual edits in the editor (making it dirty)
        manual_user_text = "# Outdated Disk Report\n\n## 1. Reconnaissance & Enumeration\n\n*Keine Einträge in dieser Phase.*\n\n_Eigene Anmerkungen zu dieser Phase:_\n\n> Important unsaved manual finding from tester!"
        self.tab.editor.setPlainText(manual_user_text)
        self.assertTrue(self.tab.is_dirty())

        # Add new loot to loot_mgr
        self.loot_mgr.add_entry("note", "Port 80 HTTP", "Apache 2.4.41", category="recon")

        # User clicks "Aus Loot ergänzen"
        self.tab.btn_append_loot.click()

        # 1. Editor should no longer be dirty
        self.assertFalse(self.tab.is_dirty())

        # 2. Editor content should contain BOTH manual edits and new loot
        editor_text = self.tab.editor.toPlainText()
        self.assertIn("Important unsaved manual finding from tester!", editor_text)
        self.assertIn("Port 80 HTTP", editor_text)

        # 3. Automatic backup must contain the manual user text (NOT the stale initial_disk_text)
        bak_path = self.report_file_mgr.get_backup_path("TestBox")
        self.assertTrue(bak_path.exists())
        self.assertEqual(bak_path.read_text(encoding="utf-8"), manual_user_text)

    def test_preview_markdown_roundtrip_preserves_markers_regression(self):
        """Ticket 0.1 & 39: Live preview roundtrip retains spectre:loot markers."""
        report_with_marker = "<!-- spectre:loot:loot_abc123:deadbeef1234 -->\n### Nmap Port Scan\n\nPort 80 open\n"
        self.tab.editor.setPlainText(report_with_marker)
        self.tab.save()

        # Enter preview mode
        self.tab._set_view_mode(ViewMode.PREVIEW)

        # Edit rich preview document slightly
        cursor = self.tab.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nExtra note from preview.")

        # Switch back to SPLIT mode
        self.tab._set_view_mode(ViewMode.SPLIT)

        result_text = self.tab.editor.toPlainText()
        self.assertIn("spectre:loot:loot_abc123:deadbeef1234", result_text)
        self.assertIn("Extra note from preview.", result_text)

    def test_insert_loot_entry_image_directly_into_editor(self):
        """Verifies individual loot screenshots can be inserted into the editor without full sync."""
        entry = self.loot_mgr.add_entry(
            "screenshot",
            "Root Proof",
            "![Root Proof](loot/proof.png)",
            category="privesc",
        )
        self.tab.editor.setPlainText("Here is the proof:\n\n")
        cursor = self.tab.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.tab.editor.setTextCursor(cursor)

        self.tab._insert_loot_entry_image(entry)
        self.assertIn("![Root Proof](loot/proof.png)", self.tab.editor.toPlainText())

    def test_loot_image_picker_dialog(self):
        from ui.report.dialogs import LootImagePickerDialog

        entry1 = {
            "title": "Burp Request",
            "target_ip": "10.10.10.1",
            "timestamp": "12:00:00",
            "content": "loot/burp.png",
        }
        entry2 = {
            "title": "Nmap Scan",
            "target_ip": "10.10.10.2",
            "timestamp": "12:05:00",
            "content": "loot/nmap.png",
        }
        dialog = LootImagePickerDialog([entry1, entry2], parent=self.tab)
        self.assertEqual(dialog.list_widget.count(), 2)

        dialog.search_edit.setText("Burp")
        self.assertEqual(dialog.list_widget.count(), 1)
        self.assertIsNotNone(dialog.selected_entry)
        self.assertEqual(dialog.selected_entry["title"], "Burp Request")
        dialog.deleteLater()

    def test_btn_visual_hierarchy_and_classes(self):
        """Verifies distinct button hierarchy between safe append and destructive regenerate."""
        self.assertIn("AppendLootBtn", self.tab.btn_append_loot.property("class"))
        self.assertIn("RegenerateBtn", self.tab.btn_regenerate.property("class"))

    def test_regenerate_confirmation_aborts_on_user_no(self):
        """Destructive regenerate must prompt user with confirmation and abort when rejected."""
        self.tab.editor.setPlainText("# Important Custom Report Notes\nDo not overwrite!")
        self.tab.save()

        with patch.object(
            QMessageBox, "warning", return_value=QMessageBox.StandardButton.No
        ) as mock_warn:
            self.tab._on_regenerate_clicked()
            mock_warn.assert_called_once()

        self.assertEqual(
            self.tab.editor.toPlainText(),
            "# Important Custom Report Notes\nDo not overwrite!",
        )

    def test_regenerate_saves_dirty_edits_before_backup(self):
        """Unsaved dirty edits must be saved before backup so .bak contains the latest manual notes."""
        self.tab.editor.setPlainText("# Freshly Typed Draft\nUnsaved manual notes.")
        self.assertTrue(self.tab.is_dirty())

        with (
            patch.object(
                QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes
            ),
            patch("ui.report_editor_tab.ReportGenerationDialog") as MockGenDialog,
        ):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_template = self.tab.active_template
            MockGenDialog.return_value = mock_dlg

            self.tab._on_regenerate_clicked()

        bak_path = self.report_file_mgr.get_backup_path("TestBox")
        self.assertTrue(bak_path.exists())
        self.assertIn("Unsaved manual notes.", bak_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()



