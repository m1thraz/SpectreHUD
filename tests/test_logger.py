import os
import unittest
import tempfile
import logging
from pathlib import Path
from core.logger import (
    configure_file_logging,
    flush_logs,
    get_log_directory,
    get_log_path,
    get_logger,
    is_file_logging_configured,
    set_log_level,
)


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        import gc
        from core.logger import close_log_handlers

        close_log_handlers()
        os.environ.pop("SPECTRE_LOG_LEVEL", None)
        os.environ.pop("SPECTRE_LOG_DIR", None)
        for name in list(logging.Logger.manager.loggerDict.keys()) + [
            "spectrehud",
            "test_rotator",
            "",
        ]:
            log_obj = logging.getLogger(name)
            for h in list(log_obj.handlers):
                try:
                    h.close()
                    log_obj.removeHandler(h)
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
        configured_path = configure_file_logging(
            log_dir=self.temp_path, max_bytes=500, backup_count=2
        )
        test_logger = get_logger("test_rotator")

        # Emit logs to trigger rotation (> 500 bytes)
        for i in range(20):
            test_logger.info(f"Log message line {i} to exceed max_bytes and force rollover")

        # Flush handlers
        flush_logs()

        log_dir = self.temp_path
        log_files = list(log_dir.glob("spectrehud.log*"))
        self.assertGreaterEqual(len(log_files), 1)
        self.assertEqual(configured_path, (self.temp_path / "spectrehud.log").resolve())
        self.assertEqual(get_log_directory(), self.temp_path.resolve())
        self.assertEqual(get_log_path(), configured_path)
        self.assertTrue(is_file_logging_configured())

    def test_environment_override_controls_default_log_directory(self):
        override = self.temp_path / "diagnostics"
        os.environ["SPECTRE_LOG_DIR"] = str(override)

        configured_path = configure_file_logging()

        self.assertEqual(configured_path, (override / "spectrehud.log").resolve())
        self.assertTrue(configured_path.exists())
        self.assertIn("File logging active:", configured_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
