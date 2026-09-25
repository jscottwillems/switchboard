"""Media frames and raw observations.

Observations keep the bytes that arrived. Interpretations live on CallSession
and CallEvent.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MediaObservationMeta(BaseModel):
    """Envelope facts copied from a media frame, not an analysis of it."""

    model_config = ConfigDict(extra="forbid")

    sequence: int
    timestamp_ms: int
    encoding: str
    sample_rate: int
    track: str


class RawObservation(BaseModel):
    """Exact bytes received from a carrier webhook or media frame."""

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["observation"] = "observation"
    observation_id: str
    call_id: str
    provider: str
    observed_at: datetime
    source: Literal["webhook", "status", "media"]
    content_type: str
    raw_b64: str
    byte_length: int
    sha256: str
    media: MediaObservationMeta | None = None


class InboundMediaPacket(BaseModel):
    """Normalized inbound audio after framing, before any speech pipeline."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    sequence: int
    timestamp_ms: int = 0
    encoding: str = "audio/x-mulaw"
    sample_rate: int = 8000
    payload: bytes
    track: str = "inbound"


class OutboundAudioFrame(BaseModel):
    """Audio the media gateway should send back to the carrier."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    encoding: Literal["audio/x-mulaw"] = "audio/x-mulaw"
    sample_rate: Literal[8000] = 8000
    payload: bytes
    source: str


class StartCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["start"] = "start"
    call_id: str | None = None
    provider_call_id: str | None = None
    stream_id: str | None = None
    encoding: str = "audio/x-mulaw"
    sample_rate: int = 8000


class AudioCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    command: Literal["audio"] = "audio"
    sequence: int
    timestamp_ms: int = 0
    encoding: str = "audio/x-mulaw"
    sample_rate: int = 8000
    payload: bytes
    track: str = "inbound"


class StopCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["stop"] = "stop"


class HangupCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["hangup"] = "hangup"
    reason: str = "caller_hangup"
    call_id: str | None = None


class IgnoreCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["ignore"] = "ignore"


class UnknownCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["unknown"] = "unknown"
    detail: str


MediaCommand = StartCommand | AudioCommand | StopCommand | HangupCommand | IgnoreCommand | UnknownCommand


class ReadyOutbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbound: Literal["ready"] = "ready"
    call_id: str
    stream_id: str
    protocol: str


class AudioOutbound(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    outbound: Literal["audio"] = "audio"
    call_id: str
    stream_id: str | None
    sequence: int
    encoding: str
    sample_rate: int
    payload: bytes
    source: str


class MediaEndedOutbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbound: Literal["media_ended"] = "media_ended"
    call_id: str


class CompletedOutbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbound: Literal["completed"] = "completed"
    call_id: str
    reason: str


class ErrorOutbound(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbound: Literal["error"] = "error"
    detail: str


OutboundMessage = ReadyOutbound | AudioOutbound | MediaEndedOutbound | CompletedOutbound | ErrorOutbound
