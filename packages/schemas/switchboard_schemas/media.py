"""Switchboard Media Protocol v1.

Carrier-native media messages stop at the telephony adapter.
Past that boundary, only these messages exist.
Audio bytes never go on the event bus.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import ContractModel

MEDIA_PROTOCOL = "switchboard.media.v1"
MAX_FRAME_B64_CHARS = 120_000


class MediaFormat(ContractModel):
    encoding: Literal["audio/pcmu", "audio/pcm"]
    sample_rate_hz: int = Field(gt=0, le=48000)
    channels: Literal[1] = 1


class StreamStart(ContractModel):
    event: Literal["start"] = "start"
    stream_id: str = Field(min_length=1, max_length=200)
    call_session_id: UUID
    media_format: MediaFormat


class StreamMedia(ContractModel):
    event: Literal["media"] = "media"
    sequence: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    payload_b64: str = Field(min_length=1, max_length=MAX_FRAME_B64_CHARS)


class StreamStop(ContractModel):
    event: Literal["stop"] = "stop"
    reason: str | None = Field(default=None, max_length=500)


class StreamMark(ContractModel):
    event: Literal["mark"] = "mark"
    name: str = Field(min_length=1, max_length=200)


class StreamClear(ContractModel):
    event: Literal["clear"] = "clear"


class StreamReady(ContractModel):
    event: Literal["ready"] = "ready"
    protocol: Literal["switchboard.media.v1"] = MEDIA_PROTOCOL


InboundMediaMessage = Annotated[
    StreamStart | StreamMedia | StreamStop,
    Field(discriminator="event"),
]

OutboundMediaMessage = Annotated[
    StreamReady | StreamMedia | StreamMark | StreamClear,
    Field(discriminator="event"),
]
