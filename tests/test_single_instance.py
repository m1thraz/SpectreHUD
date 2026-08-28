import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.single_instance import (
    LOCK_FILENAME,
    acquire_application_lock,
    release_application_lock,
)


class TestSingleInstanceLock(unittest.TestCase):
    _HOLDER_SCRIPT = """
import sys
import time
from core.single_instance import acquire_application_lock

lock = acquire_application_lock(sys.argv[1])
print("LOCKED" if lock else "REJECTED", flush=True)
if lock is not None:
    time.sleep(60)
"""

    def _start_lock_holder(self, config_dir: Path) -> subprocess.Popen:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        process = subprocess.Popen(
            [sys.executable, "-c", self._HOLDER_SCRIPT, str(config_dir)],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return process

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)

    def _await_lock_result(self, process: subprocess.Popen) -> str:
        result = process.stdout.readline().strip()
        if not result:
            stderr = process.stderr.read()
            self.fail(f"Lock holder did not report a result: {stderr}")
        return result

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

    def test_simultaneous_starts_allow_exactly_one_process_to_hold_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            first = self._start_lock_holder(config_dir)
            second = self._start_lock_holder(config_dir)

            try:
                results = {self._await_lock_result(first), self._await_lock_result(second)}
            finally:
                self._stop_process(first)
                self._stop_process(second)

        self.assertEqual(results, {"LOCKED", "REJECTED"})

    def test_crashed_lock_owner_does_not_block_next_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            holder = self._start_lock_holder(config_dir)
            try:
                self.assertEqual(self._await_lock_result(holder), "LOCKED")
                self._stop_process(holder)

                recovered_lock = acquire_application_lock(config_dir)
                self.assertIsNotNone(recovered_lock)
                release_application_lock(recovered_lock)
            finally:
                self._stop_process(holder)

    def test_live_lock_owner_is_not_treated_as_stale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            holder = self._start_lock_holder(config_dir)
            try:
                self.assertEqual(self._await_lock_result(holder), "LOCKED")

                lock_path = config_dir / LOCK_FILENAME
                old_time = time.time() - 60
                os.utime(lock_path, (old_time, old_time))

                self.assertIsNone(acquire_application_lock(config_dir))
            finally:
                self._stop_process(holder)

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
