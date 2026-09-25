from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import AwareDatetime, Confidence, ContractModel, E164
from switchboard_schemas.enums import (
    CallState,
    MediaStreamState,
    RecordLayer,
    Speaker,
    TranscriptSource,
)


class OperatorNumber(ContractModel):
    """Configuration for an operator-controlled honeypot number. Not a call observation."""

    id: UUID
    e164: E164
    label: str = Field(min_length=1, max_length=200)
    status: Literal["active", "retired"]
    created_at: AwareDatetime


class CallSession(ContractModel):
    record_layer: Literal[RecordLayer.OBSERVATION] = RecordLayer.OBSERVATION
    id: UUID
    operator_number_id: UUID | None
    external_call_id: str = Field(min_length=1, max_length=200)
    carrier: str = Field(min_length=1, max_length=64)
    caller_number_e164: E164
    called_number_e164: E164
    state: CallState
    started_at: AwareDatetime
    answered_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    end_reason: str | None = Field(default=None, max_length=500)


class WebhookReceipt(ContractModel):
    record_layer: Literal[RecordLayer.OBSERVATION] = RecordLayer.OBSERVATION
    id: UUID
    call_session_id: UUID | None
    provider: str = Field(min_length=1, max_length=64)
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any]
    signature_valid: bool | None
    received_at: AwareDatetime


class MediaStream(ContractModel):
    record_layer: Literal[RecordLayer.OBSERVATION] = RecordLayer.OBSERVATION
    id: UUID
    call_session_id: UUID
    external_stream_id: str = Field(min_length=1, max_length=200)
    protocol: Literal["switchboard.media.v1"] = "switchboard.media.v1"
    encoding: Literal["audio/pcmu", "audio/pcm"]
    sample_rate_hz: int = Field(gt=0, le=48000)
    state: MediaStreamState
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None


class TranscriptSegment(ContractModel):
    record_layer: Literal[RecordLayer.OBSERVATION] = RecordLayer.OBSERVATION
    id: UUID
    call_session_id: UUID
    media_stream_id: UUID
    sequence: int = Field(ge=0)
    speaker: Speaker
    source: TranscriptSource
    text: str = Field(max_length=8000)
    language: str | None = Field(default=None, max_length=16)
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(ge=0)
    is_final: bool
    stt_confidence: Confidence | None = Field(
        default=None,
        description="Provider-reported score. Not Switchboard interpretation confidence.",
    )
    provider: str = Field(min_length=1, max_length=64)
    created_at: AwareDatetime
