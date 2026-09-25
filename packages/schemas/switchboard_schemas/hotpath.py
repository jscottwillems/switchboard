"""In-process hot-path messages. These are not bus events and are not stored as-is."""

from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import Confidence, ContractModel


class ResponseRequest(ContractModel):
    call_session_id: UUID
    turn_index: int = Field(ge=0)
    latest_caller_text: str = Field(max_length=8000)


class ResponseDecision(ContractModel):
    text: str = Field(min_length=1, max_length=8000)
    strategy_id: str = Field(min_length=1, max_length=128)
    confidence: Confidence
