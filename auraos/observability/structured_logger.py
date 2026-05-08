"""Yapılandırılmış JSON logger - correlation/trace ID destekli.

Banking ortamında log'ların ELK/Loki/Splunk gibi merkezi bir sisteme akabilmesi
için JSON formatı şart. Her log satırı: ts, level, logger, msg, correlation_id,
session_id, agent, ek alanlar.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:16]
    _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str | None) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_session_id(sid: str | None) -> None:
    _session_id.set(sid)


def set_tenant_id(tid: str | None) -> None:
    _tenant_id.set(tid)


class JsonFormatter(logging.Formatter):
    """LogRecord → tek satır JSON."""

    RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = _correlation_id.get()
        if cid:
            payload["correlation_id"] = cid
        sid = _session_id.get()
        if sid:
            payload["session_id"] = sid
        tid = _tenant_id.get()
        if tid:
            payload["tenant_id"] = tid
        for k, v in record.__dict__.items():
            if k in self.RESERVED or k.startswith("_"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(level: int = logging.INFO, stream=sys.stdout) -> None:
    """Kök logger'ı JSON formatına geçirir. Idempotent."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.LoggerAdapter:
    """Standart logger ama context fields default verilmiş."""
    return logging.LoggerAdapter(logging.getLogger(name), {})
