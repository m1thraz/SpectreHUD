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
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def test_logger_setup_and_emit(self):
        logger = get_logger("test_module")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "spectrehud.test_module")

        # Test logging calls without throwing errors
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

if __name__ == "__main__":
    unittest.main()
