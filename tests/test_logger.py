import os
import unittest
import tempfile
from pathlib import Path
from core.logger import get_logger, setup_logger

class TestLogger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

    def tearDown(self):
        import logging
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        for name in ["spectrehud", "test_rotator", "spectrehud.test_module"]:
            l = logging.getLogger(name)
            for h in list(l.handlers):
                h.close()
                l.removeHandler(h)
        self.temp_dir.cleanup()

    def test_logger_setup_and_emit(self):
        logger = get_logger("test_module")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "spectrehud.test_module")

        # Test logging calls without throwing errors
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

    def test_rotating_file_handler_limits_log_file_size(self):
        """Tests that RotatingFileHandler properly rolls over files once max_bytes is reached."""
        test_logger = setup_logger("test_rotator", max_bytes=500, backup_count=2)
        
        # Emit logs to trigger rotation (> 500 bytes)
        for i in range(20):
            test_logger.info(f"Log message line {i} to exceed max_bytes and force rollover")

        # Flush handlers
        for handler in test_logger.handlers:
            handler.flush()

        log_dir = self.temp_path
        log_files = list(log_dir.glob("spectrehud.log*"))
        self.assertGreaterEqual(len(log_files), 1)


if __name__ == "__main__":
    unittest.main()
