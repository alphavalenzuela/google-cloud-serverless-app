"""Google Cloud Logging compatible structured JSON logger."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class CloudLoggingFormatter(logging.Formatter):
    """Formats log records as JSON lines matching Google Cloud Logging expectations.

    Maps Python logging levels to Google Cloud severity strings:
    DEBUG -> DEBUG
    INFO -> INFO
    WARNING -> WARNING
    ERROR -> ERROR
    CRITICAL -> CRITICAL
    """

    LEVEL_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "severity": self.LEVEL_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
            "sourceLocation": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
        }

        # Include custom extra attributes if passed in logger calls
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def get_logger(name: str = "doc_processor") -> logging.Logger:
    """Creates or retrieves a logger configured with structured JSON output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CloudLoggingFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
