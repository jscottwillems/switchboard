from typing import Literal
from uuid import UUID

from pydantic import Field

from switchboard_schemas.common import AwareDatetime, Confidence, ContractModel
from switchboard_schemas.enums import CampaignStatus, RecordLayer


class Campaign(ContractModel):
    record_layer: Literal[RecordLayer.ATTRIBUTION] = RecordLayer.ATTRIBUTION
    id: UUID
    label: str = Field(min_length=1, max_length=200)
    status: CampaignStatus
    summary: str | None = Field(default=None, max_length=4000)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CampaignAttribution(ContractModel):
    """Links one call to a campaign. It must cite findings, which cite transcript spans."""

    record_layer: Literal[RecordLayer.ATTRIBUTION] = RecordLayer.ATTRIBUTION
    id: UUID
    campaign_id: UUID
    call_session_id: UUID
    supporting_finding_ids: list[UUID] = Field(min_length=1)
    method: str = Field(min_length=1, max_length=128)
    method_version: str = Field(min_length=1, max_length=64)
    confidence: Confidence
    rationale: str = Field(min_length=1, max_length=2000)
    created_at: AwareDatetime
