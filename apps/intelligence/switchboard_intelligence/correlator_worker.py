"""Consumer for group intelligence.correlator. Owner: WATSON.

`intelligence.finding.proposed` for a `callback_number` loads the stored
findings that share that E.164 and replays `ExactCallbackCorrelator`.
A match inserts `attr.campaign` and `attr.campaign_attribution`, then
publishes `campaign.opened` and `campaign.attribution.proposed`.
Other envelopes are acknowledged so the group does not stall.

The correlator is built from Postgres on every event. A restart does not
depend on the in-memory clusters from the previous process. Campaign and
attribution ids stay the correlator's UUIDv5s. Event ids are UUIDv5s of
those rows, so a redelivery does not append a second stream entry.
"""

import os
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from pydantic import TypeAdapter, ValidationError

from switchboard_classification import CorrelationInput, ExactCallbackCorrelator
from switchboard_events import ConsumerGroup, DeliveredEvent, EventBus, build_envelope
from switchboard_observability import log_info
from switchboard_repositories import AttributionWriter, FindingWriter
from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE, E164
from switchboard_schemas.enums import EventType, FindingKind, Producer
from switchboard_schemas.events import (
    CampaignAttributionProposed,
    CampaignOpened,
    EventEnvelope,
    IntelligenceFindingProposed,
)
from switchboard_schemas.interpretations import IntelligenceFinding

from switchboard_intelligence.deps import event_bus, open_attribution_writer, open_finding_writer
from switchboard_intelligence.settings import get_settings

_GROUP = ConsumerGroup.INTELLIGENCE_CORRELATOR
_E164 = TypeAdapter(E164)

FindingWriterFactory = Callable[[], AbstractContextManager[FindingWriter]]
AttributionWriterFactory = Callable[[], AbstractContextManager[AttributionWriter]]


@dataclass(frozen=True)
class PollResult:
    """One read. `retry` means an entry was left pending after a write failure."""

    acknowledged: int
    retry: bool


def correlator_worker_enabled() -> bool:
    """The HTTP process starts the loop unless tests or the env flag turn it off."""

    flag = os.environ.get("SWITCHBOARD_CORRELATOR_WORKER", "")
    if flag == "0":
        return False
    if flag == "1":
        return True
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    settings = get_settings()
    return bool(settings.redis_url and settings.database_url)


def propose_callback_campaigns(
    findings: Sequence[IntelligenceFinding],
) -> tuple[list[Campaign], list[CampaignAttribution]]:
    """Replay stored findings through a fresh exact-match correlator.

    Session order follows the earliest finding time, then the session id.
    The returned campaigns and attributions use the correlator's ids.
    """

    correlator = ExactCallbackCorrelator()
    by_session: dict[UUID, list[IntelligenceFinding]] = {}
    for finding in findings:
        by_session.setdefault(finding.call_session_id, []).append(finding)
    for session_id in sorted(by_session, key=lambda item: _session_key(by_session[item], item)):
        correlator.propose(
            CorrelationInput(call_session_id=session_id, findings=by_session[session_id])
        )
    return correlator.campaigns(), correlator.attributions()


def campaign_opened_envelope(campaign: Campaign, source: EventEnvelope) -> EventEnvelope:
    """One opened event per campaign. The id is stable across redelivery."""

    return build_envelope(
        event_type=EventType.CAMPAIGN_OPENED,
        producer=Producer.INTELLIGENCE,
        call_session_id=source.call_session_id,
        payload=CampaignOpened(
            campaign_id=campaign.id,
            label=campaign.label,
            status=campaign.status,
        ),
        occurred_at=source.occurred_at,
        event_id=_opened_event_id(campaign.id),
        causation_id=source.event_id,
    )


def attribution_proposed_envelope(
    attribution: CampaignAttribution,
    source: EventEnvelope,
) -> EventEnvelope:
    """One proposed attribution event. The id is stable across redelivery.

    `call_session_id` is the call that triggered the match. The attribution
    row keeps its own session id.
    """

    return build_envelope(
        event_type=EventType.CAMPAIGN_ATTRIBUTION_PROPOSED,
        producer=Producer.INTELLIGENCE,
        call_session_id=source.call_session_id,
        payload=CampaignAttributionProposed(
            attribution_id=attribution.id,
            campaign_id=attribution.campaign_id,
            confidence=attribution.confidence,
            method=attribution.method,
            method_version=attribution.method_version,
        ),
        occurred_at=source.occurred_at,
        event_id=_attribution_event_id(attribution.id),
        causation_id=source.event_id,
    )


class CorrelatorConsumer:
    """Read `intelligence.correlator`, write `attr.*`, publish campaign events."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        open_findings: FindingWriterFactory | None = None,
        open_attributions: AttributionWriterFactory | None = None,
        consumer_name: str = "correlator",
    ) -> None:
        self._bus = event_bus() if bus is None else bus
        self._open_findings = open_finding_writer if open_findings is None else open_findings
        self._open_attributions = (
            open_attribution_writer if open_attributions is None else open_attributions
        )
        self._consumer_name = consumer_name

    def poll(self, *, count: int = 16, block_ms: int | None = None) -> PollResult:
        """Handle one batch. A failed write leaves that entry pending."""

        delivered = self._bus.read(
            _GROUP,
            self._consumer_name,
            count=count,
            block_ms=block_ms,
        )
        acknowledged = 0
        for item in delivered:
            if not self.handle(item):
                return PollResult(acknowledged=acknowledged, retry=True)
            self._bus.ack(_GROUP, item)
            acknowledged += 1
        return PollResult(acknowledged=acknowledged, retry=False)

    def handle(self, delivered: DeliveredEvent) -> bool:
        """Process one entry. True means the caller should acknowledge it.

        False leaves the entry pending so a missing finding or a failed
        write can be retried. A correlator exception is acknowledged and
        the attribution is omitted.
        """

        envelope = delivered.envelope
        if envelope.event_type is not EventType.INTELLIGENCE_FINDING_PROPOSED:
            return True
        payload = IntelligenceFindingProposed.model_validate(envelope.payload)
        if payload.kind is not FindingKind.CALLBACK_NUMBER:
            return True
        try:
            loaded = self._load(payload.finding_id)
        except Exception as exc:
            _log_write_failure(envelope, exc)
            return False
        if loaded is None:
            _log_finding_missing(envelope, payload.finding_id)
            return False
        finding, candidates = loaded
        if finding.kind is not FindingKind.CALLBACK_NUMBER or not _is_e164(finding.value):
            return True
        try:
            campaigns, attributions = propose_callback_campaigns(candidates)
        except Exception:
            _log_correlator_failure(envelope)
            return True
        if not campaigns:
            return True
        try:
            self._insert(campaigns, attributions)
        except Exception as exc:
            _log_write_failure(envelope, exc)
            return False
        for event in _campaign_events(campaigns, attributions, envelope):
            if self._bus.publish(event).failed:
                return False
        return True

    def _load(
        self,
        finding_id: UUID,
    ) -> tuple[IntelligenceFinding, list[IntelligenceFinding]] | None:
        with self._open_findings() as writer:
            finding = writer.findings().get(finding_id)
            if finding is None:
                return None
            if finding.kind is not FindingKind.CALLBACK_NUMBER:
                return finding, []
            return finding, writer.findings().list_callback_numbers(finding.value)

    def _insert(
        self,
        campaigns: Sequence[Campaign],
        attributions: Sequence[CampaignAttribution],
    ) -> None:
        with self._open_attributions() as writer:
            for campaign in campaigns:
                writer.campaigns().insert(campaign)
            for attribution in attributions:
                writer.attributions().insert(attribution)


def serve_correlator(stop: threading.Event) -> None:
    """Block until `stop` is set. Redis errors stay in this loop."""

    log_info("correlator_worker_started", group=_GROUP.value)
    consumer = CorrelatorConsumer()
    while not stop.is_set():
        try:
            result = consumer.poll(block_ms=500)
        except Exception:
            log_info("correlator_poll_failed", group=_GROUP.value, reason="consumer_exception")
            stop.wait(0.25)
            continue
        if result.retry:
            stop.wait(0.25)
    log_info("correlator_worker_stopped", group=_GROUP.value)


def _session_key(findings: Sequence[IntelligenceFinding], session_id: UUID) -> tuple[datetime, str]:
    earliest = min(finding.created_at for finding in findings)
    return (earliest, str(session_id))


def _is_e164(value: str) -> bool:
    try:
        _E164.validate_python(value)
    except ValidationError:
        return False
    return True


def _campaign_events(
    campaigns: Sequence[Campaign],
    attributions: Sequence[CampaignAttribution],
    source: EventEnvelope,
) -> list[EventEnvelope]:
    events = [campaign_opened_envelope(campaign, source) for campaign in campaigns]
    ordered = sorted(attributions, key=lambda row: (row.created_at, str(row.id)))
    events.extend(attribution_proposed_envelope(row, source) for row in ordered)
    return events


def _opened_event_id(campaign_id: UUID) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"campaign.opened|{campaign_id}")


def _attribution_event_id(attribution_id: UUID) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"campaign.attribution.proposed|{attribution_id}")


def _log_finding_missing(envelope: EventEnvelope, finding_id: UUID) -> None:
    log_info(
        "correlator_finding_missing",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        finding_id=str(finding_id),
        reason="finding_not_stored",
    )


def _log_correlator_failure(envelope: EventEnvelope) -> None:
    log_info(
        "correlator_failed",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason="correlator_exception",
    )


def _log_write_failure(envelope: EventEnvelope, exc: Exception) -> None:
    log_info(
        "correlator_write_failed",
        event_id=str(envelope.event_id),
        event_type=envelope.event_type.value,
        call_session_id=str(envelope.call_session_id),
        reason="repository_exception",
        error_type=type(exc).__name__,
    )
