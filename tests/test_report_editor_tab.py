import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QMessageBox, QDialog, QLabel
from PyQt6.QtCore import QMimeData, Qt, QUrl
from PyQt6.QtGui import QShortcut

from core.project import ProjectManager
from core.loot import LootManager
from core.clipboard_history import ClipboardHistory
from core.reporting import ReportFileManager
from core.i18n import t
from ui.report.dialogs import (
    ReportExportTypeDialog,
    ReportGenerationDialog,
    ReportRegenerationConfirmDialog,
)
from ui.report.preview import ReportPreviewEdit
from ui.report.navigation import ReportLocation, ReportLocationKind
from ui.report_editor_tab import ReportEditorTab, ViewMode


pytestmark = pytest.mark.integration


class TestReportEditorTab(unittest.TestCase):
    """Tests ReportEditorTab ViewModes, editable live preview, commit, and safety guards."""

    def setUp(self):
        self.temp_path = Path(os.environ["SPECTRE_CONFIG_DIR"]).parent

        self.project_mgr = ProjectManager(base_dir=self.temp_path / "projects")
        self.project_mgr.create_project("TestBox", target_ip="10.10.10.42")
        self.loot_mgr = LootManager(storage_file=self.temp_path / "config" / "loot.json")
        self.clip_watcher = ClipboardHistory(storage_file=self.temp_path / "config" / "clip.json")
        self.report_file_mgr = ReportFileManager(self.project_mgr)

        self.tab = ReportEditorTab(self.report_file_mgr, self.loot_mgr, self.clip_watcher)
        self.tab.load_project("TestBox")
        self.tab.show()

    def tearDown(self):
        self.tab.close()
        self.tab.deleteLater()

    def test_initial_view_mode_is_workspace(self):
        """The structured workspace is the primary report experience."""
        self.assertEqual(self.tab.view_mode, ViewMode.WORKSPACE)
        self.assertTrue(self.tab.workspace_shell.navigator_glass.isVisible())
        self.assertEqual(
            self.tab.workspace_shell.center_stack.currentWidget(),
            self.tab.workspace_shell.metadata_inspector_glass,
        )
        self.assertTrue(self.tab.workspace_shell.preview.isVisible())
        self.assertTrue(self.tab.workspace_shell.preview.isReadOnly())
        self.assertTrue(self.tab.format_toolbar_widget.isHidden())
        self.assertIn("Workspace", self.tab.action_toolbar.lbl_status.text())
        self.assertEqual(
            self.tab.action_toolbar.btn_change_view.text(), t("report.mode_workspace", "Workspace")
        )
        self.assertTrue(self.tab.action_toolbar.btn_report_actions.isVisible())
        self.assertTrue(self.tab.action_toolbar.btn_append_loot.isHidden())
        self.assertTrue(self.tab.action_toolbar.btn_regenerate.isHidden())
        self.assertFalse(self.tab.action_toolbar.action_sync_loot.isEnabled())
        self.assertTrue(self.tab.action_toolbar.view_actions[ViewMode.WORKSPACE].isChecked())
        self.assertFalse(hasattr(self.tab, "btn_mode_editor"))

    def test_obsidian_export_delegates_current_editor_state(self):
        coordinator = MagicMock()
        self.tab.export_coordinator = coordinator
        self.tab.workspace_shell.editor.setPlainText("# Current report\nEvidence")

        self.tab.export_actions.on_export_obsidian_clicked()

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
        self.assertTrue(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertFalse(dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(dialog.lbl_dialog_title.text(), dialog.windowTitle())

    def test_html_export_profile_buttons_have_room_for_their_labels(self):
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel):
            self.assertIsNone(self.tab.export_actions.select_html_export_options())

        dialogs = self.tab.window().findChildren(QMessageBox)
        self.assertEqual(len(dialogs), 1)
        dialog = dialogs[0]
        self.assertGreaterEqual(dialog.minimumWidth(), 640)
        self.assertIn("HTML", dialog.informativeText())
        self.assertNotIn("header", dialog.informativeText().lower())
        buttons = {button.text(): button for button in dialog.buttons()}
        self.assertNotIn("Interactive — Dark", buttons)
        professional = buttons[t("report.html_profile_professional", "Professional Print")]
        classic_web = buttons[t("report.html_profile_classic_web", "Classic Web (editable)")]
        self.assertIs(dialog.defaultButton(), professional)
        self.assertLess(dialog.buttons().index(professional), dialog.buttons().index(classic_web))
        self.assertGreaterEqual(professional.minimumWidth(), 170)
        self.assertGreaterEqual(classic_web.minimumWidth(), 210)

    def test_export_chooser_explains_each_handoff(self):
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.assertIsNone(self.tab.export_actions.select_export_type())

        dialogs = self.tab.findChildren(QDialog)
        export_dialog = next(
            dialog
            for dialog in dialogs
            if dialog.windowTitle() == t("report.export_dialog_title", "Export Report")
        )
        descriptions = {
            label.property("exportType"): label.text()
            for label in export_dialog.findChildren(QLabel)
            if label.property("exportType")
        }
        self.assertEqual(set(descriptions), {"html", "obsidian", "cherrytree", "markdown"})
        self.assertIn("PDF", descriptions["html"])
        self.assertIn("vault", descriptions["obsidian"].lower())
        self.assertIn("CherryTree", descriptions["cherrytree"])
        self.assertIn("Markdown", descriptions["markdown"])

    def test_view_mode_switching(self):
        """Tests switching between the report view modes."""
        # 1. Switch to EDITOR mode
        self.tab.set_view_mode(ViewMode.EDITOR)
        self.assertEqual(self.tab.view_mode, ViewMode.EDITOR)
        self.assertTrue(self.tab.workspace_shell.editor.isVisible())
        self.assertFalse(self.tab.workspace_shell.preview.isVisible())
        self.assertTrue(self.tab.workspace_shell.preview.isReadOnly())
        self.assertIn("Editor", self.tab.action_toolbar.lbl_status.text())
        self.assertTrue(self.tab.action_toolbar.view_actions[ViewMode.EDITOR].isChecked())
        self.assertTrue(self.tab.action_toolbar.btn_report_actions.isHidden())
        self.assertFalse(self.tab.action_toolbar.btn_append_loot.isHidden())
        self.assertFalse(self.tab.action_toolbar.btn_regenerate.isHidden())

        # 2. Switch to PREVIEW mode (editable)
        self.tab.set_view_mode(ViewMode.PREVIEW)
        self.assertEqual(self.tab.view_mode, ViewMode.PREVIEW)
        self.assertFalse(self.tab.workspace_shell.editor.isVisible())
        self.assertTrue(self.tab.workspace_shell.preview.isVisible())
        self.assertFalse(self.tab.workspace_shell.preview.isReadOnly())
        self.assertIn(
            t("report.view_preview_short", "Live Preview"),
            self.tab.action_toolbar.lbl_status.text(),
        )

        # 3. Cycle view mode back to the primary workspace
        self.tab.cycle_view_mode()
        self.assertEqual(self.tab.view_mode, ViewMode.WORKSPACE)
        self.assertTrue(self.tab.workspace_shell.preview.isReadOnly())

    def test_live_preview_commit_to_markdown(self):
        """Tests that editing in PREVIEW mode commits markdown back to editor on mode switch."""
        self.tab.workspace_shell.editor.setPlainText("# Initial Heading\n\nSome initial content.")
        self.tab.save()
        self.assertFalse(self.tab.is_dirty())

        # Enter preview mode
        self.tab.set_view_mode(ViewMode.PREVIEW)
        self.assertFalse(self.tab.workspace_shell.preview.isReadOnly())

        # Edit rich text document directly
        cursor = self.tab.workspace_shell.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nAppended live text.")

        # Switch to SPLIT mode -> triggers _commit_preview_to_markdown
        self.tab.set_view_mode(ViewMode.SPLIT)
        self.assertTrue(self.tab.is_dirty())
        self.assertIn("Appended live text", self.tab.workspace_shell.editor.toPlainText())
        self.assertTrue(self.tab.workspace_shell.preview.isReadOnly())

    def test_preview_commit_on_save(self):
        """Tests that save() automatically commits pending preview edits."""
        self.tab.workspace_shell.editor.setPlainText("# Base Report")
        self.tab.save()

        self.tab.set_view_mode(ViewMode.PREVIEW)
        cursor = self.tab.workspace_shell.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nSaved via preview.")

        saved = self.tab.save()
        self.assertTrue(saved)
        self.assertFalse(self.tab.is_dirty())
        self.assertIn("Saved via preview", self.tab.workspace_shell.editor.toPlainText())

    def test_sanity_check_guard_against_truncation(self):
        """Tests that extreme content loss prompts warning and can be aborted/reverted."""
        long_content = "# Section\n\n" + ("Important pentest findings line.\n" * 20)
        self.tab.workspace_shell.editor.setPlainText(long_content)
        self.tab.save()

        self.tab.set_view_mode(ViewMode.PREVIEW)

        # Clear almost everything in preview document (drastic reduction)
        self.tab.workspace_shell.preview.setPlainText("Short")

        # User chooses "No" on warning dialog
        with patch(
            "ui.report_editor_tab.show_warning_dialog",
            return_value=QMessageBox.StandardButton.No,
        ):
            self.tab.set_view_mode(ViewMode.SPLIT)

        # Content should be restored from baseline snapshot
        self.assertIn(
            "Important pentest findings line", self.tab.workspace_shell.editor.toPlainText()
        )

    def test_report_preview_edit_blocks_image_mime_drops(self):
        """Tests that ReportPreviewEdit blocks image mime data drops."""
        edit = ReportPreviewEdit()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile("malicious.png")])
        edit.insertFromMimeData(mime)
        # Text should remain empty because image drop was rejected
        self.assertEqual(edit.toPlainText().strip(), "")

    def test_find_replace_and_autosave(self):
        self.tab.workspace_shell.editor.setPlainText("alpha beta alpha")
        self.tab.workspace_shell.editor.setFocus()
        self.tab.workspace_shell.find_replace.open()
        self.tab.workspace_shell.find_replace.find_input.setText("alpha")
        self.assertTrue(self.tab.workspace_shell.find_replace.isVisible())
        self.assertEqual(
            self.tab.workspace_shell.find_replace.count_label.text(),
            t("find_replace.matches_count", "{count} Treffer", count=2),
        )
        self.tab.workspace_shell.find_replace.replace_input.setText("omega")
        self.tab.workspace_shell.find_replace.replace_all()
        self.assertEqual(self.tab.workspace_shell.editor.toPlainText(), "omega beta omega")
        self.tab.workspace_shell.find_replace.close_bar()
        self.assertFalse(self.tab.workspace_shell.find_replace.isVisible())

        self.tab.save()
        self.tab.report_file_manager.save = MagicMock(return_value=True)
        self.tab.autosave()
        self.tab.report_file_manager.save.assert_not_called()
        self.tab.replace_markdown("dirty autosave content")
        self.tab.autosave()
        self.tab.report_file_manager.save.assert_called_once()

    def test_autosave_failure_is_non_modal(self):
        self.tab.replace_markdown("dirty content")
        self.tab.report_file_manager.save = MagicMock(return_value=False)
        with patch.object(QMessageBox, "exec") as message_exec:
            self.tab.autosave()
        message_exec.assert_not_called()
        self.assertTrue(self.tab.is_dirty())

    def test_btn_append_loot_exists_in_toolbar(self):
        """Ticket 24: Verify 'Aus Loot ergänzen' button exists and is positioned in the action toolbar."""
        self.assertTrue(hasattr(self.tab.action_toolbar, "btn_append_loot"))
        self.assertEqual(
            self.tab.action_toolbar.btn_append_loot.text(),
            t("report.sync_loot", "Sync Loot & Findings"),
        )

    def test_btn_save_exists_as_compact_icon_in_toolbar(self):
        """Verify compact icon-save button exists on Tier 1 next to status label."""
        self.assertTrue(hasattr(self.tab.action_toolbar, "btn_save"))
        self.assertEqual(self.tab.action_toolbar.btn_save.text(), "")
        self.assertFalse(self.tab.action_toolbar.btn_save.icon().isNull())
        self.assertEqual(
            self.tab.action_toolbar.btn_save.accessibleName(),
            self.tab.action_toolbar.btn_save.toolTip(),
        )
        self.assertIn("SaveIconBtn", self.tab.action_toolbar.btn_save.property("class"))
        self.tab.report_file_manager.save = MagicMock(return_value=True)
        self.tab.replace_markdown("changed report")
        self.tab.action_toolbar.btn_save.click()
        self.tab.report_file_manager.save.assert_called_once()
        self.assertFalse(self.tab.is_dirty())

    def test_append_loot_saves_dirty_state_first_and_preserves_manual_edits(self):
        """Ticket 25 & 38: Dirty editor content must be committed & saved before sync to ensure backup contains it."""
        initial_disk_text = "# Outdated Disk Report\n\n## 1. Reconnaissance & Enumeration\n\n*Keine Einträge in dieser Phase.*\n\n_Eigene Anmerkungen zu dieser Phase:_\n"
        self.report_file_mgr.save(initial_disk_text, "TestBox")

        # User types manual edits in the editor (making it dirty)
        manual_user_text = "# Outdated Disk Report\n\n## 1. Reconnaissance & Enumeration\n\n*Keine Einträge in dieser Phase.*\n\n_Eigene Anmerkungen zu dieser Phase:_\n\n> Important unsaved manual finding from tester!"
        self.tab.workspace_shell.editor.setPlainText(manual_user_text)
        self.assertTrue(self.tab.is_dirty())

        # Add new loot to loot_mgr
        self.loot_mgr.add_entry("note", "Port 80 HTTP", "Apache 2.4.41", category="recon")

        # User clicks "Aus Loot ergänzen"
        self.tab.action_toolbar.btn_append_loot.click()

        # 1. Editor should no longer be dirty
        self.assertFalse(self.tab.is_dirty())

        # 2. Editor content should contain BOTH manual edits and new loot
        editor_text = self.tab.workspace_shell.editor.toPlainText()
        self.assertIn("Important unsaved manual finding from tester!", editor_text)
        self.assertIn("Port 80 HTTP", editor_text)
        self.assertEqual(
            self.tab.workspace_shell.navigator.lbl_sync_state.property("syncState"), "current"
        )
        self.assertFalse(self.tab.workspace_shell.navigator.btn_sync_loot.isEnabled())
        self.assertFalse(self.tab.action_toolbar.action_sync_loot.isEnabled())

        # 3. Automatic backup must contain the manual user text (NOT the stale initial_disk_text)
        bak_path = self.report_file_mgr.get_backup_path("TestBox")
        self.assertTrue(bak_path.exists())
        self.assertEqual(bak_path.read_text(encoding="utf-8"), manual_user_text)

    def test_preview_markdown_roundtrip_preserves_markers_regression(self):
        """Ticket 0.1 & 39: Live preview roundtrip retains spectre:loot markers."""
        report_with_marker = (
            "<!-- spectre:loot:loot_abc123:deadbeef1234 -->\n### Nmap Port Scan\n\nPort 80 open\n"
        )
        self.tab.workspace_shell.editor.setPlainText(report_with_marker)
        self.tab.save()

        # Enter preview mode
        self.tab.set_view_mode(ViewMode.PREVIEW)

        # Edit rich preview document slightly
        cursor = self.tab.workspace_shell.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nExtra note from preview.")

        # Switch back to SPLIT mode
        self.tab.set_view_mode(ViewMode.SPLIT)

        result_text = self.tab.workspace_shell.editor.toPlainText()
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
        self.tab.workspace_shell.editor.setPlainText("Here is the proof:\n\n")
        cursor = self.tab.workspace_shell.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.tab.workspace_shell.editor.setTextCursor(cursor)

        self.tab.format_actions.insert_loot_entry_image(entry)
        self.assertIn(
            "![Root Proof](loot/proof.png)", self.tab.workspace_shell.editor.toPlainText()
        )

    def test_insert_report_icon_is_undoable_and_survives_preview_roundtrip(self):
        """Report icons stay ordinary project-local Markdown images end to end."""
        from ui.report.icon_assets import REPORT_ICONS

        definition = next(item for item in REPORT_ICONS if item.key == "credential")
        with patch("ui.report.format_actions.ReportIconPickerDialog") as picker:
            picker.return_value.exec.return_value = QDialog.DialogCode.Accepted
            picker.return_value.selected_icon = definition
            self.tab.format_actions.format_icon()

        markdown_link = "![Credential](assets/icons/fa5s_user-secret_32.png)"
        self.assertIn(markdown_link, self.tab.workspace_shell.editor.toPlainText())
        self.assertTrue(
            (
                self.project_mgr.get_project_dir("TestBox") / "assets/icons/fa5s_user-secret_32.png"
            ).is_file()
        )
        self.assertTrue(self.tab.is_dirty())

        self.tab.workspace_shell.editor.undo()
        self.assertNotIn(markdown_link, self.tab.workspace_shell.editor.toPlainText())
        self.tab.workspace_shell.editor.redo()
        self.assertIn(markdown_link, self.tab.workspace_shell.editor.toPlainText())

        self.tab.save()
        self.tab.set_view_mode(ViewMode.PREVIEW)
        cursor = self.tab.workspace_shell.preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText("\n\nPreview edit.")
        self.tab.set_view_mode(ViewMode.SPLIT)

        roundtrip = self.tab.workspace_shell.editor.toPlainText()
        self.assertIn(markdown_link, roundtrip)
        self.assertIn("Preview edit.", roundtrip)

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
        self.assertIn("AppendLootBtn", self.tab.action_toolbar.btn_append_loot.property("class"))
        self.assertIn("RegenerateBtn", self.tab.action_toolbar.btn_regenerate.property("class"))

    def test_action_toolbar_keeps_text_and_adds_qtawesome_icons(self):
        action_buttons = (
            self.tab.action_toolbar.btn_change_view,
            self.tab.action_toolbar.btn_navigator,
            self.tab.action_toolbar.btn_report_actions,
            self.tab.action_toolbar.btn_append_loot,
            self.tab.action_toolbar.btn_regenerate,
            self.tab.action_toolbar.btn_export,
        )
        for button in action_buttons:
            self.assertTrue(button.text())
            self.assertFalse(button.icon().isNull(), button.text())

        for action in self.tab.action_toolbar.view_actions.values():
            self.assertTrue(action.isCheckable())
            self.assertFalse(action.icon().isNull())
            self.assertNotRegex(action.text(), "[📝◫👁️]")

    def test_workspace_report_actions_menu_routes_existing_workflows(self):
        self.tab.action_toolbar.action_sync_loot.setEnabled(True)
        with (
            patch.object(self.tab.mutation_actions, "synchronize_loot") as sync_loot,
            patch.object(self.tab.mutation_actions, "regenerate") as regenerate,
        ):
            self.tab.action_toolbar.action_sync_loot.trigger()
            self.tab.action_toolbar.action_regenerate.trigger()

        sync_loot.assert_called_once_with()
        regenerate.assert_called_once_with()

    def test_semantic_navigator_rebuilds_from_current_editor_text(self):
        first = """<!-- spectre:section:start:executive_summary -->

## First Summary

<!-- spectre:section:end:executive_summary -->"""
        second = first.replace("First Summary", "Updated Summary")
        self.tab.workspace_shell.editor.setPlainText(first)

        self.tab.action_toolbar.navigator_menu.aboutToShow.emit()
        sections_menu = self.tab.action_toolbar.navigator_menu.actions()[0].menu()
        self.assertEqual(sections_menu.actions()[0].text(), "First Summary")

        self.tab.workspace_shell.editor.setPlainText(second)
        self.tab.action_toolbar.navigator_menu.aboutToShow.emit()
        sections_menu = self.tab.action_toolbar.navigator_menu.actions()[0].menu()
        self.assertEqual(sections_menu.actions()[0].text(), "Updated Summary")

    def test_semantic_navigation_preserves_document_and_dirty_state(self):
        markdown = """<!-- spectre:section:start:phase_section:recon -->

## Recon

<!-- spectre:finding:start:finding-1 -->
<!-- spectre:loot:finding-1:abcd -->
### Service Exposure

Evidence
<!-- spectre:finding:end:finding-1 -->

<!-- spectre:section:end:phase_section:recon -->"""
        self.tab.workspace_shell.editor.setPlainText(markdown)
        self.tab.save()

        self.tab.navigate_source_to(ReportLocation.finding("finding-1"))

        self.assertEqual(
            self.tab.workspace_shell.editor.textCursor().block().text(), "### Service Exposure"
        )
        self.assertEqual(self.tab.workspace_shell.editor.toPlainText(), markdown)
        self.assertFalse(self.tab.is_dirty())

    def test_semantic_navigation_leaves_preview_for_source_editor(self):
        markdown = """<!-- spectre:section:start:executive_summary -->

## Summary

Text

<!-- spectre:section:end:executive_summary -->"""
        self.tab.workspace_shell.editor.setPlainText(markdown)
        self.tab.set_view_mode(ViewMode.PREVIEW)

        self.tab.navigate_source_to(ReportLocation(ReportLocationKind.SECTION, "executive_summary"))

        self.assertEqual(self.tab.view_mode, ViewMode.EDITOR)
        self.assertEqual(self.tab.workspace_shell.editor.textCursor().block().text(), "## Summary")

    def test_report_color_toggle_only_switches_report_panes(self):
        button = self.tab.action_toolbar.btn_report_theme
        self.assertFalse(button.icon().isNull())
        self.assertFalse(self.tab.light_report_view)

        button.click()

        self.assertTrue(self.tab.light_report_view)
        self.assertTrue(self.tab.workspace_shell.editor.property("reportLight"))
        self.assertTrue(self.tab.workspace_shell.preview.property("reportLight"))
        self.assertTrue(self.tab.workspace_shell.editor_glass.property("reportLight"))
        self.assertIn("#1f2328", self.tab.workspace_shell.preview_document.defaultStyleSheet())

        button.click()

        self.assertFalse(self.tab.light_report_view)
        self.assertFalse(self.tab.workspace_shell.editor.property("reportLight"))
        self.assertIn("#f0f6fc", self.tab.workspace_shell.preview_document.defaultStyleSheet())

    def test_metadata_toggle_reveals_protected_source_markers(self):
        marker = "<!-- spectre:section:start:executive_summary -->"
        self.tab.workspace_shell.editor.setPlainText(f"{marker}\n## Summary")

        self.assertFalse(self.tab.action_toolbar.btn_report_metadata.isChecked())
        self.assertFalse(self.tab.workspace_shell.editor.document().firstBlock().isVisible())
        self.assertEqual(self.tab.workspace_shell.editor.toPlainText(), f"{marker}\n## Summary")

        self.tab.action_toolbar.btn_report_metadata.click()

        self.assertTrue(self.tab.workspace_shell.editor.metadata_visible())
        self.assertTrue(self.tab.workspace_shell.editor.document().firstBlock().isVisible())

    def test_live_preview_shows_compact_pagebreak_indicator(self):
        from core.reporting import PAGEBREAK_MARKER
        from ui.report.preview_transforms import PREVIEW_PAGEBREAK_LABEL

        self.tab.workspace_shell.editor.setPlainText(f"Before\n\n{PAGEBREAK_MARKER}\n\nAfter")
        self.tab.set_view_mode(ViewMode.PREVIEW)

        self.assertIn(PREVIEW_PAGEBREAK_LABEL, self.tab.workspace_shell.preview.toPlainText())
        self.assertNotIn(PAGEBREAK_MARKER, self.tab.workspace_shell.preview.toPlainText())

        self.tab.set_view_mode(ViewMode.EDITOR)

        self.assertIn(PAGEBREAK_MARKER, self.tab.workspace_shell.editor.toPlainText())
        self.assertNotIn(PREVIEW_PAGEBREAK_LABEL, self.tab.workspace_shell.editor.toPlainText())

    def test_live_preview_shows_spacer_size_and_preserves_marker(self):
        from ui.report.preview_transforms import PREVIEW_SPACER_LABELS

        marker = "<!-- spectre:spacer:large -->"
        self.tab.workspace_shell.editor.setPlainText(f"Before\n\n{marker}\n\nAfter")
        self.tab.set_view_mode(ViewMode.PREVIEW)

        self.assertIn(
            PREVIEW_SPACER_LABELS["large"], self.tab.workspace_shell.preview.toPlainText()
        )
        self.tab.set_view_mode(ViewMode.EDITOR)
        self.assertIn(marker, self.tab.workspace_shell.editor.toPlainText())
        self.assertNotIn(
            PREVIEW_SPACER_LABELS["large"], self.tab.workspace_shell.editor.toPlainText()
        )

    def test_toolbar_modernization_preserves_report_shortcuts(self):
        shortcuts = {shortcut.key().toString() for shortcut in self.tab.findChildren(QShortcut)}
        self.assertTrue(
            {
                "Ctrl+S",
                "Ctrl+Shift+S",
                "Ctrl+Shift+V",
                "Ctrl+1",
                "Ctrl+2",
                "Ctrl+3",
                "Ctrl+B",
                "Ctrl+I",
                "Ctrl+K",
                "Ctrl+Shift+X",
                "Ctrl+Shift+L",
                "Ctrl+Shift+E",
                "Ctrl+Shift+R",
                "Ctrl+Shift+Q",
                "Ctrl+Shift+I",
            }.issubset(shortcuts)
        )
        self.assertNotIn("Ctrl+Shift+O", shortcuts)

    def test_regenerate_confirmation_aborts_on_user_no(self):
        """Destructive regenerate must prompt user with confirmation and abort when rejected."""
        self.tab.workspace_shell.editor.setPlainText(
            "# Important Custom Report Notes\nDo not overwrite!"
        )
        self.tab.save()

        with patch.object(
            ReportRegenerationConfirmDialog,
            "exec",
            return_value=QDialog.DialogCode.Rejected,
        ) as confirm_exec:
            self.tab.mutation_actions.regenerate()
            confirm_exec.assert_called_once()

        self.assertEqual(
            self.tab.workspace_shell.editor.toPlainText(),
            "# Important Custom Report Notes\nDo not overwrite!",
        )

    def test_regenerate_saves_dirty_edits_before_backup(self):
        """Unsaved dirty edits must be saved before backup so .bak contains the latest manual notes."""
        self.tab.workspace_shell.editor.setPlainText("# Freshly Typed Draft\nUnsaved manual notes.")
        self.assertTrue(self.tab.is_dirty())

        with (
            patch.object(
                ReportRegenerationConfirmDialog,
                "exec",
                return_value=QDialog.DialogCode.Accepted,
            ),
            patch("ui.report.mutation_actions.ReportGenerationDialog") as MockGenDialog,
        ):
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_template = self.tab.active_template
            MockGenDialog.return_value = mock_dlg

            self.tab.mutation_actions.regenerate()

        bak_path = self.report_file_mgr.get_backup_path("TestBox")
        self.assertTrue(bak_path.exists())
        self.assertIn("Unsaved manual notes.", bak_path.read_text(encoding="utf-8"))

    def test_toolbar_collapse_toggles_both_levels(self):
        """Verifies that clicking the toolbar toggle button collapses and expands Ebene 1 and Ebene 2."""
        self.tab.set_view_mode(ViewMode.EDITOR)
        self.assertFalse(self.tab.action_toolbar.isHidden())
        self.assertFalse(self.tab.format_toolbar_widget.tools_container.isHidden())
        self.assertEqual(self.tab.format_toolbar_widget.btn_toggle.text(), "")
        expanded_icon_key = self.tab.format_toolbar_widget.btn_toggle.icon().cacheKey()

        # Collapse both levels
        self.tab.format_toolbar_widget.btn_toggle.click()
        self.assertTrue(self.tab.action_toolbar.isHidden())
        self.assertTrue(self.tab.format_toolbar_widget.tools_container.isHidden())
        self.assertTrue(self.tab.format_toolbar_widget.property("collapsed"))
        self.assertFalse(self.tab.format_toolbar_widget.btn_toggle.isHidden())
        self.assertEqual(self.tab.layout().spacing(), 0)
        self.assertNotEqual(
            self.tab.format_toolbar_widget.btn_toggle.icon().cacheKey(), expanded_icon_key
        )

        # Expand both levels
        self.tab.format_toolbar_widget.btn_toggle.click()
        self.assertFalse(self.tab.action_toolbar.isHidden())
        self.assertFalse(self.tab.format_toolbar_widget.tools_container.isHidden())
        self.assertFalse(self.tab.format_toolbar_widget.property("collapsed"))
        self.assertEqual(self.tab.layout().spacing(), 6)
        self.assertEqual(
            self.tab.format_toolbar_widget.btn_toggle.icon().cacheKey(), expanded_icon_key
        )

    def test_require_export_coordinator_missing_shows_warning(self):
        self.tab.export_coordinator = None
        with patch("ui.report.export_actions.show_error_dialog") as mock_warn:
            self.assertIsNone(self.tab.export_actions.require_export_coordinator())
            mock_warn.assert_called_once()

    def test_export_copy_flow_success_and_cancel(self):
        coordinator = MagicMock()
        self.tab.export_coordinator = coordinator
        self.tab.workspace_shell.editor.setPlainText("# Test Copy Content")

        # 1. Cancelled file dialog
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")):
            self.tab.export_actions.on_export_copy_clicked()
            coordinator.export_report_markdown.assert_not_called()

        # 2. Successful export
        out_path = self.temp_path / "copy_output.md"
        with (
            patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(str(out_path), "Markdown (*.md)"),
            ),
            patch.object(QMessageBox, "exec"),
        ):
            self.tab.export_actions.on_export_copy_clicked()
            coordinator.export_report_markdown.assert_called_once_with(
                out_path, "# Test Copy Content"
            )

        # 3. Export failure
        from ui.coordinators.export_coordinator import ReportExportError

        coordinator.export_report_markdown.side_effect = ReportExportError("Write failed")
        with (
            patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(str(out_path), "Markdown (*.md)"),
            ),
            patch.object(QMessageBox, "exec"),
        ):
            self.tab.export_actions.on_export_copy_clicked()

    def test_export_html_flow_success_and_cancel(self):
        coordinator = MagicMock()
        self.tab.export_coordinator = coordinator
        self.tab.workspace_shell.editor.setPlainText("# Test HTML Content")

        # 1. Cancelled theme chooser
        with patch.object(self.tab.export_actions, "select_html_export_options", return_value=None):
            self.tab.export_actions.on_export_html_clicked()
            coordinator.export_report_html.assert_not_called()

        # 2. Cancelled file dialog
        with (
            patch.object(
                self.tab.export_actions,
                "select_html_export_options",
                return_value=("light", "interactive"),
            ),
            patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")),
        ):
            self.tab.export_actions.on_export_html_clicked()
            coordinator.export_report_html.assert_not_called()

        # 3. Successful HTML export
        out_html = self.temp_path / "report.html"
        with (
            patch.object(
                self.tab.export_actions,
                "select_html_export_options",
                return_value=("light", "professional_print"),
            ),
            patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(str(out_html), "HTML (*.html)"),
            ),
            patch.object(QMessageBox, "exec", return_value=QMessageBox.StandardButton.No),
        ):
            self.tab.export_actions.on_export_html_clicked()
            coordinator.export_report_html.assert_called_once_with(
                target=out_html,
                project_name="TestBox",
                markdown="# Test HTML Content",
                theme="light",
                report_font="segoe_ui",
                language="de",
                profile="professional_print",
                category="ctf",
            )

        # 4. Export error
        from ui.coordinators.export_coordinator import ReportExportError

        coordinator.export_report_html.side_effect = ReportExportError("HTML write failed")
        with (
            patch.object(
                self.tab.export_actions,
                "select_html_export_options",
                return_value=("light", "interactive"),
            ),
            patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(str(out_html), "HTML (*.html)"),
            ),
            patch.object(QMessageBox, "exec"),
        ):
            self.tab.export_actions.on_export_html_clicked()

    def test_export_cherrytree_flow_success_and_error(self):
        coordinator = MagicMock()
        self.tab.export_coordinator = coordinator
        self.tab.workspace_shell.editor.setPlainText("# CherryTree Notes")

        # 1. Cancelled directory dialog
        with patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=""):
            self.tab.export_actions.on_export_cherrytree_clicked()
            coordinator.export_report_to_cherrytree.assert_not_called()

        # 2. Successful export without warnings
        mock_res = MagicMock()
        mock_res.note_path = Path("dest/notes.ctd")
        mock_res.warnings = []
        coordinator.export_report_to_cherrytree.return_value = mock_res

        with (
            patch(
                "PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
                return_value=str(self.temp_path),
            ),
            patch("ui.report.export_actions.show_information_dialog") as mock_info,
        ):
            self.tab.export_actions.on_export_cherrytree_clicked()
            coordinator.export_report_to_cherrytree.assert_called_once()
            mock_info.assert_called_once()

        # 3. Successful export with warnings
        mock_res.warnings = ["Image missing"]
        with (
            patch(
                "PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
                return_value=str(self.temp_path),
            ),
            patch("ui.report.export_actions.show_information_dialog") as mock_info,
        ):
            self.tab.export_actions.on_export_cherrytree_clicked()
            mock_info.assert_called_once()
            self.assertIn("Some images could not be copied", mock_info.call_args[0][2])

        # 4. Error during export
        from ui.coordinators.export_coordinator import ReportExportError

        coordinator.export_report_to_cherrytree.side_effect = ReportExportError("Package failed")
        with (
            patch(
                "PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
                return_value=str(self.temp_path),
            ),
            patch("ui.report.export_actions.show_error_dialog") as mock_warn,
        ):
            self.tab.export_actions.on_export_cherrytree_clicked()
            mock_warn.assert_called_once()

    def test_browse_and_insert_image(self):
        # 1. Cancelled
        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=("", "")):
            self.tab.workspace_shell.editor.clear()
            self.tab.format_actions.browse_and_insert_image()
            self.assertEqual(self.tab.workspace_shell.editor.toPlainText(), "")

        # 2. Selected image file
        img_file = self.temp_path / "poc.png"
        img_file.write_bytes(b"dummy image")
        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(str(img_file), "")):
            self.tab.format_actions.browse_and_insert_image()
            self.assertIn("![poc]", self.tab.workspace_shell.editor.toPlainText())

    def test_format_image_routing(self):
        # When no screenshots in loot, delegates to browse_and_insert_image
        with patch.object(self.tab.format_actions, "browse_and_insert_image") as mock_browse:
            self.tab.format_actions.format_image()
            mock_browse.assert_called_once()

        # When screenshots exist in loot, menu is shown
        self.loot_mgr.add_entry(
            "screenshot", "Admin Panel", "loot/admin.png", target_ip="10.10.10.42"
        )
        with patch("PyQt6.QtWidgets.QMenu.exec", return_value=None):
            self.tab.format_actions.format_image()

    def test_insert_loot_entry_image(self):
        # 1. Plain relative path
        self.tab.workspace_shell.editor.clear()
        self.tab.format_actions.insert_loot_entry_image(
            {"title": "SQLi POC", "content": "screenshots/sqli.png"}
        )
        self.assertIn(
            "![SQLi POC](screenshots/sqli.png)", self.tab.workspace_shell.editor.toPlainText()
        )

        # 2. Pre-formatted markdown image
        self.tab.workspace_shell.editor.clear()
        self.tab.format_actions.insert_loot_entry_image(
            {"title": "RCE", "content": "![RCE](loot/rce.png)"}
        )
        self.assertIn("![RCE](loot/rce.png)", self.tab.workspace_shell.editor.toPlainText())

    def test_append_loot_flow_success_and_errors(self):
        # 1. Nothing missing
        self.tab.workspace_shell.editor.setPlainText("# Empty")
        self.tab.save()
        self.tab.mutation_actions.append_missing_loot()
        self.assertIn("No missing loot entries found", self.tab.action_toolbar.lbl_status.text())

        # 2. With new unreferenced loot
        self.loot_mgr.add_entry(
            "credentials",
            "MySQL Root",
            "root:secret",
            target_ip="10.10.10.42",
            category="access",
        )
        self.tab.mutation_actions.append_missing_loot()
        self.assertIn("MySQL Root", self.tab.workspace_shell.editor.toPlainText())

        # 3. ReportBackupError handling
        from core.reporting import ReportBackupError, ReportSaveError

        with (
            patch.object(
                self.report_file_mgr,
                "append_missing_loot",
                side_effect=ReportBackupError("Backup failed"),
            ),
            patch.object(QMessageBox, "exec"),
        ):
            self.tab.mutation_actions.append_missing_loot()

        # 4. ReportSaveError handling
        with (
            patch.object(
                self.report_file_mgr,
                "append_missing_loot",
                side_effect=ReportSaveError("Save failed"),
            ),
            patch.object(QMessageBox, "exec"),
        ):
            self.tab.mutation_actions.append_missing_loot()

    def test_select_export_type_dialog_choices(self):
        """Test select_export_type returns selected choice or None on cancel."""
        from PyQt6.QtWidgets import QPushButton

        # 1. HTML selection: simulate clicking HTML button on dialog
        dialog = ReportExportTypeDialog(self.tab)
        for btn in dialog.findChildren(QPushButton):
            if "HTML" in btn.text():
                btn.click()
                break
        self.assertEqual(dialog.selected_type, "html")

        # Verify button options on dialog
        labels = [
            btn.text() for btn in dialog.findChildren(QPushButton) if btn != dialog.btn_dialog_close
        ]
        self.assertEqual(
            labels[:4],
            [
                t("report.export_html", "Export HTML/PDF"),
                t("report.export_obsidian", "Export to Obsidian..."),
                t(
                    "report.export_cherrytree",
                    "Export CherryTree Package...",
                ),
                t("report.export_copy", "Export MD..."),
            ],
        )
        self.assertTrue(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(
            dialog.lbl_dialog_title.text(),
            t("report.export_dialog_title", "SPECTRE // EXPORT REPORT"),
        )
        self.assertEqual(len(dialog.export_buttons), 4)

        # 2. Test export_actions delegation
        with patch.object(ReportExportTypeDialog, "select_export_type", return_value="html"):
            self.assertEqual(self.tab.export_actions.select_export_type(), "html")

        with patch.object(ReportExportTypeDialog, "select_export_type", return_value=None):
            self.assertIsNone(self.tab.export_actions.select_export_type())

    def test_open_loot_image_picker_accepted(self):
        """Test open_loot_image_picker inserts selected screenshot when dialog accepted."""
        with patch("ui.report.format_actions.LootImagePickerDialog") as MockPicker:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.selected_entry = {"title": "Loot Screen", "content": "screenshots/loot.png"}
            MockPicker.return_value = mock_dlg

            self.tab.workspace_shell.editor.clear()
            self.tab.format_actions.open_loot_image_picker([])
            self.assertIn(
                "![Loot Screen](screenshots/loot.png)",
                self.tab.workspace_shell.editor.toPlainText(),
            )

    def test_format_table_dialog_accepted(self):
        """Test format_table inserts markdown table when dialog accepted."""
        with patch("ui.report.format_actions.MarkdownTableDialog") as MockTableDialog:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
            mock_dlg.rows.value.return_value = 2
            mock_dlg.columns.value.return_value = 2
            MockTableDialog.return_value = mock_dlg

            self.tab.workspace_shell.editor.clear()
            self.tab.format_actions.format_table()
            text = self.tab.workspace_shell.editor.toPlainText()
            self.assertIn("|---|---|", text)
            self.assertTrue("Spalte" in text or "Header" in text)

    def test_load_project_draft_recovery_restore(self):
        """Test loading project with existing uncommitted draft offers restoration and restores."""
        from core.reporting import save_draft

        proj_dir = self.project_mgr.get_project_dir("TestBox")
        save_draft(proj_dir, "# Restored Draft Content")

        with patch("ui.report.session_controller.QMessageBox") as MockMsgBox:
            mock_box = MagicMock()
            MockMsgBox.return_value = mock_box
            dummy_btn = object()
            mock_box.addButton.side_effect = lambda text, role: (
                dummy_btn if "Restore" in text or "Wiederherstellen" in text else object()
            )
            mock_box.clickedButton.return_value = dummy_btn

            self.tab.load_project("TestBox")
            self.assertEqual(
                self.tab.workspace_shell.editor.toPlainText(), "# Restored Draft Content"
            )
            self.assertTrue(self.tab.is_dirty())

    def test_load_project_draft_recovery_discard(self):
        """Test loading project with draft discards it when user rejects."""
        from core.reporting import has_recoverable_draft, save_draft

        proj_dir = self.project_mgr.get_project_dir("TestBox")
        save_draft(proj_dir, "# Draft To Discard")

        with patch("ui.report.session_controller.QMessageBox") as MockMsgBox:
            mock_box = MagicMock()
            MockMsgBox.return_value = mock_box
            mock_box.clickedButton.return_value = object()  # Not btn_restore

            self.tab.load_project("TestBox")
            self.assertFalse(has_recoverable_draft(proj_dir, ""))


if __name__ == "__main__":
    unittest.main()
