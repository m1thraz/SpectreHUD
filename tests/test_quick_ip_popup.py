"""
Tests for QuickIpPopup and its integration with VariableBar and AppController.
"""

import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent

from ui.quick_ip_popup import QuickIpPopup
from ui.variable_bar import VariableBar

# Ensure QApplication exists for GUI tests
app = QApplication.instance() or QApplication([])


class TestQuickIpPopup(unittest.TestCase):
    def setUp(self):
        self.popup = QuickIpPopup(target_ip="10.10.10.10", attacker_ip="10.10.14.5")

    def tearDown(self):
        self.popup.close()

    def test_initial_values(self):
        self.assertEqual(self.popup.txt_target.text(), "10.10.10.10")
        self.assertEqual(self.popup.txt_attacker.text(), "10.10.14.5")

    def test_set_values_does_not_emit_signals(self):
        target_emitted = []
        attacker_emitted = []
        self.popup.target_changed.connect(target_emitted.append)
        self.popup.attacker_changed.connect(attacker_emitted.append)

        self.popup.set_values("192.168.1.50", "192.168.1.100")
        self.assertEqual(self.popup.txt_target.text(), "192.168.1.50")
        self.assertEqual(self.popup.txt_attacker.text(), "192.168.1.100")
        self.assertEqual(len(target_emitted), 0)
        self.assertEqual(len(attacker_emitted), 0)

    def test_live_keystroke_signals(self):
        target_emitted = []
        attacker_emitted = []
        self.popup.target_changed.connect(target_emitted.append)
        self.popup.attacker_changed.connect(attacker_emitted.append)

        self.popup.txt_target.setText("10.10.10.99")
        self.assertIn("10.10.10.99", target_emitted)

        self.popup.txt_attacker.setText("10.10.14.77")
        self.assertIn("10.10.14.77", attacker_emitted)

    @patch("core.net_detector.NetDetector.detect_attacker_ip")
    def test_auto_detect_success(self, mock_detect):
        mock_detect.return_value = "10.10.14.88"
        attacker_emitted = []
        self.popup.attacker_changed.connect(attacker_emitted.append)

        self.popup.btn_auto.click()

        self.assertEqual(self.popup.txt_attacker.text(), "10.10.14.88")
        self.assertIn("10.10.14.88", attacker_emitted)
        self.assertIn("10.10.14.88", self.popup.btn_auto.text())

    @patch("core.net_detector.NetDetector.detect_attacker_ip")
    def test_auto_detect_failure(self, mock_detect):
        mock_detect.return_value = None

        self.popup.btn_auto.click()

        self.assertNotEqual(self.popup.btn_auto.text(), "Auto")

    def test_esc_key_closes_popup(self):
        self.popup.show()
        self.assertTrue(self.popup.isVisible())

        # Simulate Escape on txt_target through eventFilter
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        handled = self.popup.eventFilter(self.popup.txt_target, esc_event)
        self.assertTrue(handled)
        self.assertFalse(self.popup.isVisible())

    def test_show_at_cursor_focuses_target_field(self):
        self.popup.show_at_cursor()
        app.processEvents()
        self.assertTrue(self.popup.isVisible())
        self.assertTrue(self.popup.txt_target.hasFocus())

    def test_focus_loss_dismissal(self):
        self.popup.show_at_cursor()
        app.processEvents()
        self.assertTrue(self.popup.isVisible())
        self.assertTrue(self.popup._has_been_active)

        # Simulate activation loss
        event = QEvent(QEvent.Type.ActivationChange)
        with patch.object(self.popup, "isActiveWindow", return_value=False):
            self.popup.changeEvent(event)
        self.assertFalse(self.popup.isVisible())

    def test_variable_bar_live_synchronization(self):
        """Verify that changes in QuickIpPopup immediately propagate to VariableBar."""
        var_bar = VariableBar(initial_vars={"target_ip": "10.10.10.10", "attacker_ip": "10.10.14.5"})
        popup = QuickIpPopup(parent=None)

        popup.target_changed.connect(var_bar.txt_target.setText)
        popup.attacker_changed.connect(var_bar.txt_attacker.setText)

        # Prepopulate
        popup.set_values(var_bar.txt_target.text(), var_bar.txt_attacker.text())

        # Change in popup
        popup.txt_target.setText("172.16.1.10")
        self.assertEqual(var_bar.txt_target.text(), "172.16.1.10")
        self.assertEqual(var_bar.get_variables()["target_ip"], "172.16.1.10")

        popup.txt_attacker.setText("172.16.1.50")
        self.assertEqual(var_bar.txt_attacker.text(), "172.16.1.50")
        self.assertEqual(var_bar.get_variables()["attacker_ip"], "172.16.1.50")

        popup.close()


class TestAppControllerQuickIp(unittest.TestCase):
    def test_app_controller_quick_ip_wiring(self):
        from ui.app_controller import AppController

        controller = MagicMock(spec=AppController)
        var_bar = VariableBar(initial_vars={"target_ip": "10.10.10.10", "attacker_ip": "10.10.14.5"})
        controller.var_bar = var_bar
        controller._quick_ip_popup = None

        # Bind the real methods
        controller.trigger_quick_ip = AppController.trigger_quick_ip.__get__(controller)
        controller._open_quick_ip_popup = AppController._open_quick_ip_popup.__get__(controller)
        controller._on_quick_ip_target_changed = AppController._on_quick_ip_target_changed.__get__(controller)
        controller._on_quick_ip_attacker_changed = AppController._on_quick_ip_attacker_changed.__get__(controller)

        controller.trigger_quick_ip()

        self.assertIsNotNone(controller._quick_ip_popup)
        self.assertEqual(controller._quick_ip_popup.txt_target.text(), "10.10.10.10")
        self.assertEqual(controller._quick_ip_popup.txt_attacker.text(), "10.10.14.5")

        # Edit in popup
        controller._quick_ip_popup.txt_target.setText("10.129.1.50")
        self.assertEqual(var_bar.txt_target.text(), "10.129.1.50")

        controller._quick_ip_popup.txt_attacker.setText("10.10.16.10")
        self.assertEqual(var_bar.txt_attacker.text(), "10.10.16.10")

        controller._quick_ip_popup.close()
