"""Structured logging and request context."""

import logging
import time
import uuid

from flask import g, request


LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "request_id=%(request_id)s %(message)s"
)


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-")
        return True


def configure_logging(level=logging.INFO):
    root = logging.getLogger()

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.addFilter(RequestContextFilter())
        root.addHandler(handler)

    root.setLevel(level)


def start_request_context():
    g.request_id = (
        request.headers.get("X-Request-ID")
        or str(uuid.uuid4())
    )
    g.request_started_at = time.monotonic()

    return g.request_id


def request_log_fields():
    return {
        "request_id": getattr(g, "request_id", "-"),
        "method": request.method,
        "path": request.path
    }