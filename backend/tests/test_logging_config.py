"""Unit tests for the structured (JSON) log formatter."""

import json
import logging

from app.logging_config import JsonFormatter


def _make_record(msg="hello", level=logging.INFO, extra=None, exc_info=None):
    record = logging.LogRecord(
        name="app.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    for k, v in (extra or {}).items():
        setattr(record, k, v)
    return record


def test_formats_valid_json_with_core_fields():
    record = _make_record("something happened")
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["message"] == "something happened"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "app.test"
    assert "timestamp" in parsed


def test_extra_fields_are_included_verbatim():
    record = _make_record("user did a thing", extra={"user_id": 42, "client": "1.2.3.4"})
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["user_id"] == 42
    assert parsed["client"] == "1.2.3.4"


def test_percent_style_args_are_interpolated_into_message():
    # uvicorn's access logger formats via record.args, not extra=.
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s" %d',
        args=("127.0.0.1", "GET", "/api/health", 200),
        exc_info=None,
    )
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["message"] == '127.0.0.1 - "GET /api/health" 200'


def test_exception_info_is_included():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record("failed", level=logging.ERROR, exc_info=sys.exc_info())
    parsed = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in parsed["exc_info"]
