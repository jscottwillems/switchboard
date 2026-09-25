"""JSON logs for the telephony process."""

import json
import logging
from datetime import datetime, timezone

from switchboard.config import Settings

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        telemetry = getattr(record, "telemetry", None)
        if telemetry is not None:
            payload["telemetry"] = telemetry
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("switchboard")
    logger.setLevel(settings.log_level.upper())
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True
    if settings.mock_webhook_secret == settings.default_mock_secret:
        logger.warning("SWITCHBOARD_MOCK_WEBHOOK_SECRET is the local default")
