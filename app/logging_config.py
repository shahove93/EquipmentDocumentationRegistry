"""Persistent JSON Lines journal for application audit records.

Records emitted on the ``app`` logger at INFO and above are appended to a file
as one JSON object per line. Only a fixed set of fields is written: arbitrary
``extra`` values, exception text and tracebacks never reach the file.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any, Final

APP_LOGGER_NAME: Final = "app"

AUDIT_FIELDS: Final[tuple[str, ...]] = (
    "operation",
    "document_id",
    "storage_key",
    "failure_category",
    "error_type",
    "file_id",
)

_HANDLER_MARKER: Final = "_app_journal_handler"
_HANDLER_PATH: Final = "_app_journal_path"
_SCALAR_TYPES: Final = (str, int, float, bool)

_lock = threading.RLock()
_previous_level: int | None = None


class JsonLinesFormatter(logging.Formatter):
    """Render one log record as a single JSON object on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in AUDIT_FIELDS:
            value = getattr(record, field, None)
            if value is not None and isinstance(value, _SCALAR_TYPES):
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _journal_handler(logger: logging.Logger) -> logging.Handler | None:
    for handler in logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return handler
    return None


def _detach_journal_handler(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.flush()
            handler.close()


def configure_logging(log_file: str | PathLike[str]) -> logging.Handler:
    """Attach the JSON Lines journal to the ``app`` logger.

    The handler is installed at most once: a repeated call with the same path
    reuses it, and a call with another path replaces it. Parent directories are
    created as needed, and the file is opened in append mode.
    """
    raw_path = str(log_file)
    if not raw_path.strip():
        raise ValueError("log_file must not be empty")
    path = Path(raw_path).expanduser()

    with _lock:
        global _previous_level

        logger = logging.getLogger(APP_LOGGER_NAME)
        existing = _journal_handler(logger)
        if existing is not None and getattr(existing, _HANDLER_PATH, None) == path:
            handler = existing
        else:
            _detach_journal_handler(logger)
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, mode="a", encoding="utf-8")
            setattr(handler, _HANDLER_MARKER, True)
            setattr(handler, _HANDLER_PATH, path)
            handler.setFormatter(JsonLinesFormatter())
            handler.setLevel(logging.INFO)
            logger.addHandler(handler)

        if _previous_level is None:
            _previous_level = logger.level
        logger.setLevel(logging.INFO)
        return handler


def shutdown_logging() -> None:
    """Flush, close and detach the journal handler.

    Safe to call repeatedly and when no journal was configured.
    """
    with _lock:
        global _previous_level

        logger = logging.getLogger(APP_LOGGER_NAME)
        _detach_journal_handler(logger)
        if _previous_level is not None:
            logger.setLevel(_previous_level)
            _previous_level = None
