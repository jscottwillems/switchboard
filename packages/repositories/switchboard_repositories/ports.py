"""Ports for the writer boundaries in docs/DATA_MODEL.md.

Apps depend on these protocols. Postgres implementations live beside them.
A unit of work shares one connection so a session insert and its receipt commit
or roll back together.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.enums import CallState, CampaignStatus, FindingStatus, MediaStreamState
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding
from switchboard_schemas.observations import (
    CallSession,
    MediaStream,
    OperatorNumber,
    TranscriptSegment,
    WebhookReceipt,
)


class OperatorNumberRepository(Protocol):
    def insert(self, number: OperatorNumber) -> tuple[OperatorNumber, bool]: ...

    def get(self, operator_id: UUID) -> OperatorNumber | None: ...

    def find_active_id(self, e164: str) -> UUID | None: ...


class CallSessionRepository(Protocol):
    def insert_ringing(self, session: CallSession) -> tuple[CallSession, bool]: ...

    def get(self, session_id: UUID) -> CallSession | None: ...

    def get_by_carrier_call(self, carrier: str, external_call_id: str) -> CallSession | None: ...

    def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[CallSession], str | None]: ...

    def apply_state(
        self,
        session_id: UUID,
        *,
        state: CallState,
        answered_at: datetime | None = None,
        ended_at: datetime | None = None,
        end_reason: str | None = None,
    ) -> CallSession: ...


class WebhookReceiptRepository(Protocol):
    def insert(
        self,
        *,
        provider: str,
        event_type: str,
        payload: dict[str, Any],
        signature_valid: bool | None,
        call_session_id: UUID | None,
        receipt_id: UUID | None = None,
        received_at: datetime | None = None,
    ) -> WebhookReceipt: ...

    def get(self, receipt_id: UUID) -> WebhookReceipt | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[WebhookReceipt]: ...


class MediaStreamRepository(Protocol):
    def insert(self, stream: MediaStream) -> tuple[MediaStream, bool]: ...

    def get(self, stream_id: UUID) -> MediaStream | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[MediaStream]: ...

    def apply_state(
        self,
        stream_id: UUID,
        *,
        state: MediaStreamState,
        ended_at: datetime | None = None,
    ) -> MediaStream: ...


class TranscriptRepository(Protocol):
    def insert(self, segment: TranscriptSegment) -> tuple[TranscriptSegment, bool]: ...

    def get(self, segment_id: UUID) -> TranscriptSegment | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[TranscriptSegment]: ...


class ConversationTurnRepository(Protocol):
    def insert(self, turn: ConversationTurn) -> tuple[ConversationTurn, bool]: ...

    def get(self, turn_id: UUID) -> ConversationTurn | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[ConversationTurn]: ...


class FindingRepository(Protocol):
    def insert(self, finding: IntelligenceFinding) -> tuple[IntelligenceFinding, bool]: ...

    def get(self, finding_id: UUID) -> IntelligenceFinding | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[IntelligenceFinding]: ...

    def list_callback_numbers(self, value: str) -> list[IntelligenceFinding]: ...

    def set_status(self, finding_id: UUID, status: FindingStatus) -> IntelligenceFinding: ...


class CampaignRepository(Protocol):
    def insert(self, campaign: Campaign) -> tuple[Campaign, bool]: ...

    def get(self, campaign_id: UUID) -> Campaign | None: ...

    def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[Campaign], str | None]: ...

    def set_status(self, campaign_id: UUID, status: CampaignStatus) -> Campaign: ...


class AttributionRepository(Protocol):
    def insert(self, attribution: CampaignAttribution) -> tuple[CampaignAttribution, bool]: ...

    def get(self, attribution_id: UUID) -> CampaignAttribution | None: ...

    def list_for_session(self, call_session_id: UUID) -> list[CampaignAttribution]: ...

    def list_for_campaign(self, campaign_id: UUID) -> list[CampaignAttribution]: ...


class ObservationWriter(Protocol):
    """API projector writes. obs.* and interp.conversation_turn."""

    def operator_numbers(self) -> OperatorNumberRepository: ...

    def call_sessions(self) -> CallSessionRepository: ...

    def webhook_receipts(self) -> WebhookReceiptRepository: ...

    def media_streams(self) -> MediaStreamRepository: ...

    def transcripts(self) -> TranscriptRepository: ...

    def conversation_turns(self) -> ConversationTurnRepository: ...


class FindingWriter(Protocol):
    """Extractor writes. interp.intelligence_finding only."""

    def findings(self) -> FindingRepository: ...


class AttributionWriter(Protocol):
    """Correlator writes. attr.* only."""

    def campaigns(self) -> CampaignRepository: ...

    def attributions(self) -> AttributionRepository: ...


class ReadModels(Protocol):
    """Fetch side used by the read API. Call and campaign routes bind to this port."""

    def operator_numbers(self) -> OperatorNumberRepository: ...

    def call_sessions(self) -> CallSessionRepository: ...

    def webhook_receipts(self) -> WebhookReceiptRepository: ...

    def media_streams(self) -> MediaStreamRepository: ...

    def transcripts(self) -> TranscriptRepository: ...

    def conversation_turns(self) -> ConversationTurnRepository: ...

    def findings(self) -> FindingRepository: ...

    def campaigns(self) -> CampaignRepository: ...

    def attributions(self) -> AttributionRepository: ...
