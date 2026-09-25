"""Event-shaped association payload. The platform bus is not wired yet."""

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from watson.models import CampaignAssociation


class AssociationEvent(BaseModel):
    """Provisional event WATSON would publish after a campaign decision.

    The envelope is local until ATLAS lands a shared event contract.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["campaign.association.decided"] = "campaign.association.decided"
    event_id: str
    occurred_at: datetime
    producer: Literal["watson"] = "watson"
    association: CampaignAssociation


class EventEmitter(Protocol):
    """Sink for association events. Tests use an in-memory implementation."""

    def emit(self, event: AssociationEvent) -> None:
        """Record or publish one association event."""


class InMemoryEventEmitter:
    """Collect events in order. Suitable for tests and the local CLI."""

    def __init__(self) -> None:
        self.events: list[AssociationEvent] = []

    def emit(self, event: AssociationEvent) -> None:
        self.events.append(event)
