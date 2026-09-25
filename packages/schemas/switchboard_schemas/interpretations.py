from typing import Literal
from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import AwareDatetime, Confidence, ContractModel
from switchboard_schemas.enums import FindingKind, FindingStatus, RecordLayer, Speaker


class ConversationTurn(ContractModel):
    record_layer: Literal[RecordLayer.INTERPRETATION] = RecordLayer.INTERPRETATION
    id: UUID
    call_session_id: UUID
    turn_index: int = Field(ge=0)
    speaker: Speaker
    text: str = Field(max_length=8000)
    transcript_segment_ids: list[UUID]
    strategy_id: str | None = Field(default=None, max_length=128)
    confidence: Confidence
    created_at: AwareDatetime


class IntelligenceFinding(ContractModel):
    """A derived claim. It must cite at least one transcript observation."""

    record_layer: Literal[RecordLayer.INTERPRETATION] = RecordLayer.INTERPRETATION
    id: UUID
    call_session_id: UUID
    kind: FindingKind
    value: str = Field(min_length=1, max_length=2000)
    raw_quote: str = Field(min_length=1, max_length=2000)
    transcript_segment_ids: list[UUID] = Field(min_length=1)
    extractor: str = Field(min_length=1, max_length=128)
    extractor_version: str = Field(min_length=1, max_length=64)
    confidence: Confidence
    status: FindingStatus
    created_at: AwareDatetime
