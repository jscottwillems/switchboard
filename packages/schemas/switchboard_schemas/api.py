"""HTTP request and response bodies shared by the apps."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.common import AwareDatetime, ContractModel, E164
from switchboard_schemas.enums import CallState
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding
from switchboard_schemas.observations import CallSession, MediaStream, TranscriptSegment


class ErrorBody(ContractModel):
    error: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=500)


class HealthResponse(ContractModel):
    service: Literal["api", "media_gateway", "intelligence", "dashboard"]
    status: Literal["ok"]
    version: str


class CallSessionSummary(ContractModel):
    """List-row read model. Not a stored record layer."""

    id: UUID
    state: CallState
    caller_number_e164: E164
    called_number_e164: E164
    started_at: AwareDatetime
    ended_at: AwareDatetime | None


class CallListResponse(ContractModel):
    items: list[CallSessionSummary]
    next_cursor: str | None


class CallDetailResponse(ContractModel):
    session: CallSession
    media_streams: list[MediaStream]
    transcript: list[TranscriptSegment]
    turns: list[ConversationTurn]
    findings: list[IntelligenceFinding]
    attributions: list[CampaignAttribution]


class TranscriptListResponse(ContractModel):
    call_session_id: UUID
    segments: list[TranscriptSegment]


class FindingListResponse(ContractModel):
    call_session_id: UUID
    findings: list[IntelligenceFinding]


class AttributionListResponse(ContractModel):
    call_session_id: UUID
    attributions: list[CampaignAttribution]


class CampaignListResponse(ContractModel):
    items: list[Campaign]
    next_cursor: str | None


class MockVoiceWebhook(ContractModel):
    provider_call_id: str = Field(min_length=1, max_length=200)
    from_e164: E164
    to_e164: E164
    timestamp: AwareDatetime


class MockStatusWebhook(ContractModel):
    provider_call_id: str = Field(min_length=1, max_length=200)
    status: CallState
    timestamp: AwareDatetime
    end_reason: str | None = Field(default=None, max_length=500)


class VoiceInstruction(ContractModel):
    action: Literal["connect_stream", "hangup", "reject"]
    stream_url: str | None = None
    stream_token: str | None = None

    @model_validator(mode="after")
    def connect_stream_requires_target(self) -> "VoiceInstruction":
        if self.action == "connect_stream" and (not self.stream_url or not self.stream_token):
            raise ValueError("connect_stream requires stream_url and stream_token")
        if self.action != "connect_stream" and (self.stream_url or self.stream_token):
            raise ValueError("stream fields are only valid for connect_stream")
        return self


class TelephonyWebhookAck(ContractModel):
    call_session_id: UUID
    instruction: VoiceInstruction


class StatusAccepted(ContractModel):
    accepted: Literal[True] = True


class IssueStreamTokenRequest(ContractModel):
    call_session_id: UUID


class IssueStreamTokenResponse(ContractModel):
    token: str = Field(min_length=16, max_length=256)
    expires_at: AwareDatetime
    stream_url: str = Field(min_length=1, max_length=500)


class ValidateStreamTokenRequest(ContractModel):
    token: str = Field(min_length=1, max_length=256)


class ValidateStreamTokenResponse(ContractModel):
    valid: bool
    call_session_id: UUID | None = None


class ExtractRequest(ContractModel):
    call_session_id: UUID
    segments: list[TranscriptSegment]


class ExtractResponse(ContractModel):
    findings: list[IntelligenceFinding]
