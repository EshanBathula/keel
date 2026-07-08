"""Structured (JSON) logging for the app's own logger and for uvicorn's
access/error logs, so every line — ours or uvicorn's — is one JSON object
with consistent fields. No dependency added: a ~30-line formatter is enough
for "structured", and log aggregators (Docker logs, CloudWatch, etc.) only
need valid JSON per line, not a specific library's schema.
"""

import json
import logging
import sys

_RESERVED_KEYS = frozenset(
    logging.LogRecord(
        "",
        0,
        "",
        0,
        "",
        (),
        None,
    ).__dict__.keys()
) | {"message", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Anything attached via `logger.info(..., extra={...})` — e.g.
        # user_id, request path — rides along as its own JSON field.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_KEYS:
                payload.setdefault(key, value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers/formatters when it starts; overriding
    # them here (this module is imported by app.main, which uvicorn loads
    # after its own logging setup) makes access/error lines JSON too, and
    # keeps them off the root logger so they don't get formatted twice.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
