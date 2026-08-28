import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.single_instance import acquire_application_lock, release_application_lock


class TestSingleInstanceLock(unittest.TestCase):
    def test_second_lock_attempt_is_rejected_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_lock = acquire_application_lock(Path(temp_dir))
            self.assertIsNotNone(first_lock)
            try:
                self.assertIsNone(acquire_application_lock(Path(temp_dir)))
            finally:
                release_application_lock(first_lock)

    def test_lock_can_be_acquired_after_clean_release(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_lock = acquire_application_lock(Path(temp_dir))
            self.assertIsNotNone(first_lock)
            release_application_lock(first_lock)

            second_lock = acquire_application_lock(Path(temp_dir))
            self.assertIsNotNone(second_lock)
            release_application_lock(second_lock)

    def test_existing_instance_stops_before_container_initialization(self):
        import main

        app = MagicMock()
        with (
            patch.object(main, "QApplication", return_value=app),
            patch.object(main, "acquire_application_lock", return_value=None),
            patch.object(main, "_create_production_container") as create_container,
            patch.object(main.QMessageBox, "information") as show_message,
        ):
            main.main()

        create_container.assert_not_called()
        show_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
