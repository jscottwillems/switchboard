"""Log fields that are safe to emit. Audio and secrets never qualify."""

import logging
from typing import Mapping

REDACTED_KEYS = frozenset(
    {
        "audio",
        "authorization",
        "operator_token",
        "payload",
        "payload_b64",
        "raw_body",
        "stream_token",
        "token",
    }
)

LOGGER_NAME = "switchboard"


def safe_fields(fields: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in fields.items() if key not in REDACTED_KEYS}


def log_info(event: str, **fields: object) -> None:
    logging.getLogger(LOGGER_NAME).info("%s %s", event, safe_fields(fields))
