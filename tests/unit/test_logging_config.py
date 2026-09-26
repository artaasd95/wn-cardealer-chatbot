from __future__ import annotations

import logging
from pathlib import Path

from config.logging import configure_logging


class TestLoggingConfiguration:
    """Tests for the project-wide logging setup."""

    def test_configure_logging_sets_the_root_level(self) -> None:
        """The configured root logger uses the requested log level."""
        configure_logging(level="DEBUG")

        assert logging.getLogger().getEffectiveLevel() == logging.DEBUG

    def test_configure_logging_can_write_to_a_file(self, tmp_path: Path) -> None:
        """An optional rotating file handler is created when requested."""
        log_file = tmp_path / "app.log"
        configure_logging(level="INFO", log_file=str(log_file))

        logger = logging.getLogger("tests.logging")
        logger.info("hello from logging test")

        for handler in logging.getLogger().handlers:
            handler.flush()

        assert log_file.exists()
        assert "hello from logging test" in log_file.read_text(encoding="utf-8")
