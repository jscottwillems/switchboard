"""Domain events emitted by the call lifecycle.

These names are the contract. Telemetry counters are not domain events.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EventName = Literal[
    "call.received",
    "call.connected",
    "call.media.started",
    "call.media.ended",
    "call.forwarded",
    "call.completed",
    "call.failed",
]

EVENT_NAMES: tuple[EventName, ...] = (
    "call.received",
    "call.connected",
    "call.media.started",
    "call.media.ended",
    "call.forwarded",
    "call.completed",
    "call.failed",
)


class CallEvent(BaseModel):
    """A derived lifecycle fact.

    record_type is interpretation. The webhook or audio bytes that led here
    remain on RawObservation records.
    """

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["interpretation"] = "interpretation"
    event_id: str
    name: EventName
    occurred_at: datetime
    call_id: str
    provider: str
    elapsed_ms: int
    data: dict[str, Any] = Field(default_factory=dict)
