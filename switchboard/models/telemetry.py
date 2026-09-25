"""Cost and timing telemetry. These records are not domain events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TelemetryRecord(BaseModel):
    """Structured timing and cost hook.

    estimated_cost_usd stays null until a provider rate card exists.
    """

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["telemetry"] = "telemetry"
    record_id: str
    name: str
    recorded_at: datetime
    call_id: str | None = None
    provider: str | None = None
    elapsed_ms: int | None = None
    duration_ms: int | None = None
    packets_in: int | None = None
    packets_out: int | None = None
    estimated_cost_usd: float | None = None
