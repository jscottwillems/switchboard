"""Campaign correlation port. Owner: WATSON. Writes attribution, not findings."""

from typing import Protocol
from uuid import UUID

from pydantic import Field

from switchboard_schemas.attribution import CampaignAttribution
from switchboard_schemas.common import ContractModel
from switchboard_schemas.interpretations import IntelligenceFinding


class CorrelationInput(ContractModel):
    call_session_id: UUID
    findings: list[IntelligenceFinding] = Field(default_factory=list)


class CampaignCorrelator(Protocol):
    def propose(self, item: CorrelationInput) -> list[CampaignAttribution]:
        """Propose attributions that cite finding ids."""


class NullCampaignCorrelator:
    def propose(self, item: CorrelationInput) -> list[CampaignAttribution]:
        del item
        return []
