import logging
import re
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

SECRET_PATTERNS = (
    re.compile(r"KALSHI-ACCESS-SIGNATURE", re.IGNORECASE),
    re.compile(r"PRIVATE[_-]?KEY", re.IGNORECASE),
    re.compile(r"AUTHORIZATION", re.IGNORECASE),
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***"
            if any(p.search(str(key)) for p in SECRET_PATTERNS)
            else redact(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def _redact_processor(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    redacted = redact(dict(event_dict))
    return cast(MutableMapping[str, Any], redacted)


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
