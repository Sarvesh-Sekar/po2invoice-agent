"""Application logging.

A single stdlib `logging` setup, reused everywhere:

    from app.config.logging import get_logger

    logger = get_logger(__name__)

`configure_logging` picks the handler shape from `LOG_FORMAT`:

- ``text`` (default) — one human-readable line per event, for local debugging.
- ``json``           — one JSON object per event via :class:`StructFormatter`,
  for log shippers.

Every workflow log carries the standard context keys:
run_id, thread_id, workflow, agent, step, event, duration, status, error_code.

Messages follow one flat, greppable convention::

    node_started: quality_gate | run_id=9f3c | thread_id=po-9f3c
    node_completed: quality_gate | duration_ms=12 | step=quality_gate
    tool_started: lookup_customer | agent=extraction | arg_keys=['name']
    llm_call: model=amazon.nova-pro-v1:0 | duration_ms=2510 | stop_reason=tool_use

Sensitive data (passwords, tokens, API keys, full secrets) must never be logged.
Document bytes, graph state, and model prompts are also never logged: they carry
customer PII and are large. Log counts, names, durations, and booleans.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

TEXT_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

#: stdlib ``LogRecord`` attributes that must never reach the output payload.
_STDLIB_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

#: Third-party loggers pinned to WARNING so SDK chatter stays out of the way.
_NOISY_LOGGERS = ("boto3", "botocore", "aiobotocore", "urllib3", "httpcore", "urllib3.connectionpool")


_SENSITIVE_TOKENS = ("token", "password", "secret", "api_key", "authorization")


def _is_sensitive(key: str) -> bool:
    lowered = str(key).lower()
    return any(token in lowered for token in _SENSITIVE_TOKENS)


class StructFormatter(logging.Formatter):
    """Format log records as JSON with standard workflow context keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key in _STDLIB_ATTRS or key.startswith("_"):
                continue
            payload[key] = "***" if _is_sensitive(key) else redact(value)
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def redact(value: Any) -> Any:
    """Best-effort redaction helper for sensitive values."""
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            redacted[key] = "***" if _is_sensitive(key) else redact(val)
        return redacted
    if isinstance(value, (list, tuple)):
        return type(value)(redact(item) for item in value)
    return value


def configure_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Configure the root application logger.

    ``force=True`` is required: uvicorn installs its own root handlers and sets
    ``propagate: false`` on the ``uvicorn`` loggers, so without forcing our
    handler list would be appended to theirs rather than replacing them.
    """
    if log_format.lower() == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructFormatter())
        logging.basicConfig(level=level.upper(), format=TEXT_FORMAT, handlers=[handler], force=True)
    else:
        logging.basicConfig(level=level.upper(), format=TEXT_FORMAT, force=True)

    # Keep third-party loggers quiet unless debug is on.
    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return the named application logger."""
    return logging.getLogger(name)
