import unittest
from pathlib import Path
from ui.base_dialog import BaseHudDialog
from ui.add_snippet_dialog import AddSnippetDialog
from ui.add_loot_dialog import AddLootDialog
from ui.project_dialog import NewProjectDialog
from ui.param_prompt_dialog import ParamPromptDialog
from ui.command_edit_dialog import CommandEditDialog


class TestHudDialogs(unittest.TestCase):
    def test_base_hud_dialog_attributes(self):
        dlg = BaseHudDialog(title="SPECTRE // TEST DIALOG")
        self.assertEqual(dlg.dialog_title_text, "SPECTRE // TEST DIALOG")
        self.assertEqual(dlg.lbl_dialog_title.text(), "SPECTRE // TEST DIALOG")
        dlg.close()

    def test_add_snippet_dialog_data(self):
        cats = [{"name": "Web App", "id": "web"}]
        dlg = AddSnippetDialog(existing_categories=cats)
        dlg.txt_title.setText("Test Nmap")
        dlg.txt_subcategory.setText("Scans")
        dlg.txt_template.setPlainText("nmap -sV {{TARGET_IP}}")
        dlg.txt_description.setText("Fast port scan")
        dlg.txt_tags.setText("nmap, scan")

        data = dlg.get_data()
        self.assertEqual(data["title"], "Test Nmap")
        self.assertEqual(data["subcategory"], "Scans")
        self.assertEqual(data["template"], "nmap -sV {{TARGET_IP}}")
        self.assertEqual(data["description"], "Fast port scan")
        self.assertEqual(data["tags"], ["nmap", "scan"])
        dlg.close()

    def test_add_loot_dialog_data(self):
        dlg = AddLootDialog(
            default_title="Root Password",
            default_content="toor",
            target_ip="10.10.10.50",
            default_type="credentials",
            default_category="access",
        )
        data = dlg.get_data()
        self.assertEqual(data["title"], "Root Password")
        self.assertEqual(data["content"], "toor")
        self.assertEqual(data["target_ip"], "10.10.10.50")
        self.assertEqual(data["type"], "credentials")
        self.assertEqual(data["category"], "access")
        self.assertEqual(data["recommendation"], "")
        self.assertEqual(data["report_role"], "evidence")
        self.assertIsNotNone(dlg.txt_recommendation)
        dlg.txt_recommendation.setPlainText("Rotate the password")
        self.assertEqual(dlg.get_data()["recommendation"], "Rotate the password")
        dlg.chk_report_finding.setChecked(True)
        self.assertEqual(dlg.get_data()["report_role"], "finding")
        dlg.txt_target.setText("10.10.10.50, /api/v1/auth")
        dlg.txt_cvss_score.setText("8.8")
        dlg.txt_cvss_vector.setText("CVSS:3.1/AV:N/AC:L")
        dlg.combo_finding_status.setCurrentIndex(dlg.combo_finding_status.findData("in_progress"))
        dlg.txt_references.setPlainText("CVE-2026-1234\nhttps://example.test")
        enriched = dlg.get_data()
        self.assertEqual(enriched["targets"], ["10.10.10.50", "/api/v1/auth"])
        self.assertEqual(enriched["cvss_score"], 8.8)
        self.assertEqual(enriched["finding_status"], "in_progress")
        self.assertEqual(len(enriched["references"]), 2)
        dlg.close()

    def test_edit_loot_dialog_exposes_multiline_recommendation(self):
        dlg = AddLootDialog(
            entry_id="loot-1",
            is_edit=True,
            default_title="Finding",
            default_content="Evidence",
            default_recommendation="First action\nSecond action",
        )

        self.assertIsNotNone(dlg.txt_recommendation)
        self.assertEqual(dlg.txt_recommendation.toPlainText(), "First action\nSecond action")
        self.assertEqual(dlg.get_data()["recommendation"], "First action\nSecond action")
        dlg.close()

    def test_finding_details_are_progressive_and_restore_existing_values(self):
        dlg = AddLootDialog(
            entry_id="loot-1",
            is_edit=True,
            default_report_role="finding",
            default_title="Finding",
            default_content="Evidence",
            default_targets=["host.local", "/admin"],
            default_cvss_score=7.5,
            default_cvss_vector="CVSS:3.1/AV:N/AC:H",
            default_finding_status="accepted_risk",
            default_references=["https://example.test/advisory"],
        )

        self.assertFalse(dlg.finding_details_widget.isHidden())
        data = dlg.get_data()
        self.assertEqual(data["targets"], ["host.local", "/admin"])
        self.assertEqual(data["cvss_score"], 7.5)
        self.assertEqual(data["finding_status"], "accepted_risk")
        self.assertEqual(data["references"], ["https://example.test/advisory"])
        dlg.chk_report_finding.setChecked(False)
        self.assertTrue(dlg.finding_details_widget.isHidden())
        dlg.close()

    def test_loot_details_progressive_disclosure(self):
        AddLootDialog._details_expanded = False

        dlg1 = AddLootDialog()
        self.assertTrue(dlg1.details_widget.isHidden())
        self.assertIn("▶", dlg1.btn_toggle_details.text())

        dlg1.btn_toggle_details.click()
        self.assertFalse(dlg1.details_widget.isHidden())
        self.assertIn("▼", dlg1.btn_toggle_details.text())
        self.assertTrue(AddLootDialog._details_expanded)
        dlg1.close()

        dlg2 = AddLootDialog()
        self.assertFalse(dlg2.details_widget.isHidden())
        dlg2.close()

        AddLootDialog._details_expanded = False

        dlg_with_details = AddLootDialog(
            default_recommendation="Fix it immediately",
            default_report_role="evidence",
        )
        self.assertFalse(dlg_with_details.details_widget.isHidden())
        dlg_with_details.close()

        AddLootDialog._details_expanded = False

    def test_new_project_dialog_data(self):
        custom_base = Path("C:/custom_ctf_projects")
        dlg = NewProjectDialog(
            default_name="BoxBravo", default_target="10.10.10.99", default_base_dir=custom_base
        )
        dlg.txt_name.setText("BoxBravoModified")
        dlg._update_path_preview()

        data = dlg.get_data()
        self.assertEqual(data["name"], "BoxBravoModified")
        self.assertEqual(data["target_ip"], "10.10.10.99")
        self.assertEqual(data["base_dir"], custom_base)
        self.assertIn("BoxBravoModified", dlg.lbl_path_preview.text())
        dlg.close()

    def test_new_project_dialog_includes_pentest_mode_password(self):
        dlg = NewProjectDialog(default_name="SecureBox")
        dlg.chk_pentest_mode.setChecked(True)
        dlg.txt_pentest_password.setText("correct password")
        dlg.txt_pentest_password_confirm.setText("correct password")

        data = dlg.get_data()
        self.assertTrue(data["pentest_mode"])
        self.assertEqual(data["pentest_password"], "correct password")
        dlg.close()

    def test_param_prompt_dialog_data(self):
        template = "curl http://{{TARGET_IP}}:{{PORT}}/{{ENDPOINT}}"
        vars = {"target_ip": "10.10.10.10", "port": "8080"}
        unresolved = ["ENDPOINT"]
        dlg = ParamPromptDialog(template=template, variables=vars, unresolved_params=unresolved)
        dlg.param_inputs["ENDPOINT"].setText("api/v1/users")

        self.assertEqual(dlg.get_values()["ENDPOINT"], "api/v1/users")
        self.assertEqual(dlg.txt_preview.toPlainText(), "curl http://10.10.10.10:8080/api/v1/users")
        dlg.close()

    def test_command_edit_dialog_data(self):
        dlg = CommandEditDialog("nmap -sV 10.10.10.10")
        dlg.txt_command.setPlainText("nmap -sV -Pn 10.10.10.10")

        self.assertEqual(dlg.get_command(), "nmap -sV -Pn 10.10.10.10")
        dlg.close()

    def test_loot_controller_open_add_dialog_non_modal(self):
        from unittest.mock import MagicMock
        from ui.controllers.loot_controller import LootController

        loot_mgr = MagicMock()
        project_mgr = MagicMock()
        ctrl = LootController(loot_mgr, project_mgr)

        accepted_data = []
        result = ctrl.open_add_dialog(
            modal=False,
            target_ip="10.10.10.42",
            default_title="Flag 1",
            default_content="flag{123}",
            on_accepted=lambda d: accepted_data.append(d),
        )
        self.assertTrue(result)
        self.assertIsNotNone(ctrl._active_add_dialog)
        dlg = ctrl._active_add_dialog
        self.assertEqual(dlg.current_target_ip, "10.10.10.42")
        self.assertEqual(dlg.initial_title, "Flag 1")

        # Second call returns existing instance (single-instance protection)
        result2 = ctrl.open_add_dialog(modal=False)
        self.assertTrue(result2)
        self.assertIs(ctrl._active_add_dialog, dlg)

        # Simulating accept
        dlg.accept()
        self.assertIsNone(ctrl._active_add_dialog)
        loot_mgr.add_entry.assert_called_once()
        self.assertEqual(len(accepted_data), 1)


if __name__ == "__main__":
    unittest.main()
