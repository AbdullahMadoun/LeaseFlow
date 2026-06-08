"""Structured JSON logging. One call at startup configures root logger."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from .config import CONFIG


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k in {"args", "asctime", "created", "exc_info", "exc_text", "filename",
                     "funcName", "levelname", "levelno", "lineno", "message", "module",
                     "msecs", "msg", "name", "pathname", "process", "processName",
                     "relativeCreated", "stack_info", "thread", "threadName", "taskName"}:
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(CONFIG.log_level)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    # quiet noisy libs
    for name in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)
