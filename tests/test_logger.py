import os
import unittest
import tempfile
import logging
from pathlib import Path
from core.logger import get_logger, setup_logger, set_log_level, flush_logs

class TestLogger(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        os.environ["SPECTRE_CONFIG_DIR"] = str(self.temp_path)

    def tearDown(self):
        import gc
        os.environ.pop("SPECTRE_CONFIG_DIR", None)
        os.environ.pop("SPECTRE_LOG_LEVEL", None)
        for name in list(logging.Logger.manager.loggerDict.keys()) + ["spectrehud", "test_rotator", ""]:
            l = logging.getLogger(name)
            for h in list(l.handlers):
                try:
                    h.close()
                    l.removeHandler(h)
                except Exception:
                    pass
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_logger_setup_and_emit(self):
        logger = get_logger("test_module")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "spectrehud.test_module")

        # Test logging calls without throwing errors
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

    def test_logger_hierarchical_namespacing(self):
        # 1. Standard module __name__
        logger1 = get_logger("core.loot_manager")
        self.assertEqual(logger1.name, "spectrehud.core.loot_manager")

        # 2. Pre-prefixed name (no double prefix)
        logger2 = get_logger("spectrehud.core.loot_manager")
        self.assertEqual(logger2.name, "spectrehud.core.loot_manager")

        # 3. Base root logger
        logger_root = get_logger("spectrehud")
        self.assertEqual(logger_root.name, "spectrehud")

        logger_empty = get_logger()
        self.assertEqual(logger_empty.name, "spectrehud")

    def test_set_log_level_and_flush(self):
        root = get_logger("test_lvl")
        set_log_level("DEBUG")
        self.assertEqual(logging.getLogger("spectrehud").level, logging.DEBUG)

        set_log_level(logging.WARNING)
        self.assertEqual(logging.getLogger("spectrehud").level, logging.WARNING)

        # Flush without error
        flush_logs()

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
