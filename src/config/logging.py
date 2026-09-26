"""Project-wide logging configuration.

Uses only the Python standard library so no extra dependency is needed.
Entry points call ``configure_logging`` once at startup; every module-level
``logging.getLogger(__name__)`` then shares the same handlers and formatting.
"""

from __future__ import annotations

from logging.config import dictConfig
from pathlib import Path

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LAST_CONFIGURATION: tuple[str, str | None] | None = None


def configure_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Configure the application's logging once per effective configuration.

    Args:
        level: Root log level.
        log_file: Optional file path for a rotating log file.
    """
    global _LAST_CONFIGURATION

    normalized_level = level.upper().strip() or "INFO"
    normalized_log_file = (log_file or "").strip() or None
    configuration = (normalized_level, normalized_log_file)

    if _LAST_CONFIGURATION == configuration:
        return

    handlers: dict[str, dict[str, object]] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": normalized_level,
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }
    }
    root_handlers = ["console"]

    if normalized_log_file is not None:
        log_path = Path(normalized_log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": normalized_level,
            "formatter": "standard",
            "filename": str(log_path),
            "maxBytes": 1_048_576,
            "backupCount": 3,
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": _DEFAULT_FORMAT,
                    "datefmt": _DATE_FORMAT,
                }
            },
            "handlers": handlers,
            "root": {
                "level": normalized_level,
                "handlers": root_handlers,
            },
        }
    )

    _LAST_CONFIGURATION = configuration