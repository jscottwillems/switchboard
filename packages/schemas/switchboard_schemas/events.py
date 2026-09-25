"""Durable event envelope and payloads. Media frames are intentionally absent."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import AwareDatetime, Confidence, ContractModel, E164
from switchboard_schemas.enums import (
    CampaignStatus,
    EventType,
    FindingKind,
    Producer,
    Speaker,
)


class EventEnvelope(ContractModel):
    event_id: UUID
    event_type: EventType
    event_version: Literal[1] = 1
    occurred_at: AwareDatetime
    producer: Producer
    call_session_id: UUID
    causation_id: UUID | None = None
    payload: dict[str, object]


class TelephonyCallReceived(ContractModel):
    external_call_id: str = Field(min_length=1, max_length=200)
    carrier: str = Field(min_length=1, max_length=64)
    caller_number_e164: E164
    called_number_e164: E164


class TelephonyCallAnswered(ContractModel):
    external_call_id: str = Field(min_length=1, max_length=200)


class TelephonyCallCompleted(ContractModel):
    external_call_id: str = Field(min_length=1, max_length=200)
    end_reason: str | None = Field(default=None, max_length=500)


class TelephonyCallFailed(ContractModel):
    external_call_id: str = Field(min_length=1, max_length=200)
    end_reason: str = Field(min_length=1, max_length=500)


class MediaStreamStarted(ContractModel):
    media_stream_id: UUID
    encoding: Literal["audio/pcmu", "audio/pcm"]
    sample_rate_hz: int = Field(gt=0, le=48000)


class MediaStreamStopped(ContractModel):
    media_stream_id: UUID


class MediaStreamFailed(ContractModel):
    media_stream_id: UUID
    end_reason: str = Field(min_length=1, max_length=500)


class SpeechSegmentPayload(ContractModel):
    transcript_segment_id: UUID
    speaker: Speaker
    text: str = Field(max_length=8000)
    is_final: bool
    stt_confidence: Confidence | None = None
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(ge=0)
    sequence: int = Field(ge=0)


class SpeechSynthesisRequested(ContractModel):
    turn_id: UUID
    text: str = Field(min_length=1, max_length=8000)


class SpeechSynthesisCompleted(ContractModel):
    turn_id: UUID
    duration_ms: int = Field(ge=0)


class SpeechSynthesisFailed(ContractModel):
    turn_id: UUID
    end_reason: str = Field(min_length=1, max_length=500)


class ConversationResponseSelected(ContractModel):
    turn_id: UUID
    strategy_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=8000)
    confidence: Confidence


class ConversationTurnRecorded(ContractModel):
    turn_id: UUID
    turn_index: int = Field(ge=0)
    speaker: Speaker
    text: str = Field(max_length=8000)
    transcript_segment_ids: list[UUID]
    strategy_id: str | None = Field(default=None, max_length=128)
    confidence: Confidence


class IntelligenceFindingProposed(ContractModel):
    finding_id: UUID
    kind: FindingKind
    value: str = Field(min_length=1, max_length=2000)
    confidence: Confidence
    extractor: str = Field(min_length=1, max_length=128)
    extractor_version: str = Field(min_length=1, max_length=64)


class CampaignOpened(ContractModel):
    campaign_id: UUID
    label: str = Field(min_length=1, max_length=200)
    status: CampaignStatus


class CampaignAttributionProposed(ContractModel):
    attribution_id: UUID
    campaign_id: UUID
    confidence: Confidence
    method: str = Field(min_length=1, max_length=128)
    method_version: str = Field(min_length=1, max_length=64)


PAYLOAD_MODELS: dict[EventType, type[ContractModel]] = {
    EventType.TELEPHONY_CALL_RECEIVED: TelephonyCallReceived,
    EventType.TELEPHONY_CALL_ANSWERED: TelephonyCallAnswered,
    EventType.TELEPHONY_CALL_COMPLETED: TelephonyCallCompleted,
    EventType.TELEPHONY_CALL_FAILED: TelephonyCallFailed,
    EventType.MEDIA_STREAM_STARTED: MediaStreamStarted,
    EventType.MEDIA_STREAM_STOPPED: MediaStreamStopped,
    EventType.MEDIA_STREAM_FAILED: MediaStreamFailed,
    EventType.SPEECH_SEGMENT_PARTIAL: SpeechSegmentPayload,
    EventType.SPEECH_SEGMENT_FINAL: SpeechSegmentPayload,
    EventType.SPEECH_SYNTHESIS_REQUESTED: SpeechSynthesisRequested,
    EventType.SPEECH_SYNTHESIS_COMPLETED: SpeechSynthesisCompleted,
    EventType.SPEECH_SYNTHESIS_FAILED: SpeechSynthesisFailed,
    EventType.CONVERSATION_RESPONSE_SELECTED: ConversationResponseSelected,
    EventType.CONVERSATION_TURN_RECORDED: ConversationTurnRecorded,
    EventType.INTELLIGENCE_FINDING_PROPOSED: IntelligenceFindingProposed,
    EventType.CAMPAIGN_OPENED: CampaignOpened,
    EventType.CAMPAIGN_ATTRIBUTION_PROPOSED: CampaignAttributionProposed,
}


def validate_event(envelope: EventEnvelope) -> EventEnvelope:
    """Validate the payload against the model registered for event_type."""

    payload_model = PAYLOAD_MODELS[envelope.event_type]
    parsed = payload_model.model_validate(envelope.payload)
    if isinstance(parsed, SpeechSegmentPayload):
        if envelope.event_type == EventType.SPEECH_SEGMENT_PARTIAL and parsed.is_final:
            raise ValueError("speech.segment.partial requires is_final false")
        if envelope.event_type == EventType.SPEECH_SEGMENT_FINAL and not parsed.is_final:
            raise ValueError("speech.segment.final requires is_final true")
    return envelope
