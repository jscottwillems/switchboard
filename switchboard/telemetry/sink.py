"""Logging telemetry sink and the domain-event subscriber."""

import logging
import threading
from datetime import datetime, timezone

from switchboard.ids import new_id
from switchboard.models.events import CallEvent
from switchboard.models.telemetry import TelemetryRecord

logger = logging.getLogger(__name__)


class MemoryTelemetrySink:
    """Keep records in memory and write one structured log line per record."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[TelemetryRecord] = []

    def record(self, item: TelemetryRecord) -> None:
        with self._lock:
            self._records.append(item)
        logger.info(item.name, extra={"telemetry": item.model_dump(mode="json")})

    def snapshot(self) -> list[TelemetryRecord]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._records]


class TelemetryEventHandler:
    """Turn each domain event into a telemetry record. Cost stays unset."""

    def __init__(self, sink: MemoryTelemetrySink) -> None:
        self._sink = sink

    async def handle(self, event: CallEvent) -> None:
        self._sink.record(
            TelemetryRecord(
                record_id=new_id("tm_"),
                name=event.name,
                recorded_at=event.occurred_at,
                call_id=event.call_id,
                provider=event.provider,
                elapsed_ms=event.elapsed_ms,
                packets_in=_optional_int(event.data.get("packets_observed")),
                packets_out=_optional_int(event.data.get("packets_sent")),
                estimated_cost_usd=None,
            )
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _optional_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
