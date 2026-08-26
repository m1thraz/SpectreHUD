import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ui.base_dialog import BaseHudDialog
from ui.add_snippet_dialog import AddSnippetDialog
from ui.add_loot_dialog import AddLootDialog
from ui.project_dialog import NewProjectDialog
from ui.param_prompt_dialog import ParamPromptDialog

app = QApplication.instance() or QApplication([])

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
            default_category="access"
        )
        data = dlg.get_data()
        self.assertEqual(data["title"], "Root Password")
        self.assertEqual(data["content"], "toor")
        self.assertEqual(data["target_ip"], "10.10.10.50")
        self.assertEqual(data["type"], "credentials")
        self.assertEqual(data["category"], "access")
        dlg.close()

    def test_new_project_dialog_data(self):
        custom_base = Path("C:/custom_ctf_projects")
        dlg = NewProjectDialog(default_name="BoxBravo", default_target="10.10.10.99", default_base_dir=custom_base)
        dlg.txt_name.setText("BoxBravoModified")
        dlg._update_path_preview()
        
        data = dlg.get_data()
        self.assertEqual(data["name"], "BoxBravoModified")
        self.assertEqual(data["target_ip"], "10.10.10.99")
        self.assertEqual(data["base_dir"], custom_base)
        self.assertIn("BoxBravoModified", dlg.lbl_path_preview.text())
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

if __name__ == '__main__':
    unittest.main()