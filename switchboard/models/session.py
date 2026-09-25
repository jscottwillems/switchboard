"""Call session and provider-normalized inbound fields.

CallSession is a derived interpretation. Raw provider bytes live on
RawObservation and are not copied into these fields.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CallState(str, Enum):
    RECEIVED = "received"
    CONNECTED = "connected"
    MEDIA_STARTED = "media_started"
    MEDIA_ENDED = "media_ended"
    FORWARDED = "forwarded"
    COMPLETED = "completed"
    FAILED = "failed"


class StatusCategory(str, Enum):
    IGNORE = "ignore"
    COMPLETED = "completed"
    FAILED = "failed"


class CallSession(BaseModel):
    """Normalized view of one call leg.

    record_type is always interpretation. Provider payloads that produced
    this view are stored separately as observations.
    """

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["interpretation"] = "interpretation"
    call_id: str
    provider: str
    provider_call_id: str
    from_number: str
    to_number: str
    direction: Literal["inbound", "outbound"]
    state: CallState
    created_at: datetime
    updated_at: datetime
    stream_id: str | None = None
    media_protocol: str | None = None
    media_encoding: str | None = None
    media_sample_rate: int | None = None
    packets_observed: int = 0
    packets_sent: int = 0
    forward_destination: str | None = None
    failure_reason: str | None = None
    completion_reason: str | None = None
    provider_metadata: dict[str, str] = Field(default_factory=dict)
    observation_ids: list[str] = Field(default_factory=list)


class NormalizedInbound(BaseModel):
    """Provider-neutral fields extracted from an inbound webhook."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    provider_call_id: str
    from_number: str
    to_number: str
    direction: Literal["inbound", "outbound"]
    provider_metadata: dict[str, str] = Field(default_factory=dict)


class StatusUpdate(BaseModel):
    """Provider-neutral carrier status callback."""

    model_config = ConfigDict(extra="forbid")

    provider_call_id: str
    category: StatusCategory
    reason: str
    raw_status: str


class ProviderCallStatus(BaseModel):
    """Normalized status returned by TelephonyProvider.get_call_status."""

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["interpretation"] = "interpretation"
    call_id: str
    provider: str
    provider_call_id: str
    state: CallState
    raw_status: str | None = None


class MediaStreamHandle(BaseModel):
    """Result of accepting a media stream for a session."""

    model_config = ConfigDict(extra="forbid")

    stream_id: str
    call_id: str
    protocol: str
    encoding: str
    sample_rate: int
