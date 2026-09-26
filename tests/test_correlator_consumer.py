"""SB-012: intelligence.finding.proposed writes attr rows and campaign events."""

import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from switchboard_classification.correlator import EXACT_CALLBACK_METHOD
from switchboard_events import (
    ENVELOPE_FIELD,
    STREAM_KEY,
    STREAM_MAXLEN,
    ConsumerGroup,
    EventBus,
    build_envelope,
)
from switchboard_intelligence.correlator_worker import (
    CorrelatorConsumer,
    correlator_worker_enabled,
    propose_callback_campaigns,
)
from switchboard_intelligence.deps import open_attribution_writer, open_finding_writer
from switchboard_intelligence.extractor_worker import (
    ExtractorConsumer,
    finding_proposed_envelope,
)
from switchboard_intelligence.settings import get_settings as get_intelligence_settings
from switchboard_repositories import unit_of_work
from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.enums import (
    CallState,
    CampaignStatus,
    EventType,
    FindingKind,
    FindingStatus,
    Producer,
    Speaker,
)
from switchboard_schemas.events import (
    CampaignAttributionProposed,
    CampaignOpened,
    EventEnvelope,
    IntelligenceFindingProposed,
    SpeechSegmentPayload,
)
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import CallSession

NOW = datetime(2026, 9, 25, 23, 50, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")
GROUP = ConsumerGroup.INTELLIGENCE_CORRELATOR
SHARED = "+15551234567"
OTHER = "+15557654321"


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"SB-012 tests need Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_intelligence_settings.cache_clear()
    yield url
    get_intelligence_settings.cache_clear()


def test_worker_stays_off_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWITCHBOARD_CORRELATOR_WORKER", raising=False)
    assert correlator_worker_enabled() is False


def test_lifespan_starts_the_correlator_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    released = threading.Event()

    def _serve(stop: threading.Event) -> None:
        started.set()
        stop.wait()
        released.set()

    monkeypatch.setenv("SWITCHBOARD_CORRELATOR_WORKER", "1")
    monkeypatch.setattr("switchboard_intelligence.main.serve_correlator", _serve)
    from switchboard_intelligence.main import app as intelligence_app

    with TestClient(intelligence_app) as client:
        assert started.wait(2)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "intelligence"
    assert released.wait(2)


def test_shared_callback_opens_one_campaign_and_publishes_both_attributions(redis_url: str) -> None:
    left = _insert_session("sb012-left")
    right = _insert_session("sb012-right")
    bus = EventBus(redis_url)
    extractor = ExtractorConsumer(bus=bus)
    correlator = CorrelatorConsumer(bus=bus)

    bus.publish(_final(left, "Call +15551234567.", occurred_at=NOW))
    assert extractor.poll().retry is False
    first = correlator.poll()
    assert first.retry is False
    assert _attributions(left) == []
    assert _attributions(right) == []

    bus.publish(_final(right, "Same line +15551234567.", occurred_at=NOW + timedelta(seconds=30)))
    assert extractor.poll().retry is False
    second = correlator.poll()
    assert second.retry is False

    left_rows = _attributions(left)
    right_rows = _attributions(right)
    assert len(left_rows) == 1
    assert len(right_rows) == 1
    assert left_rows[0].campaign_id == right_rows[0].campaign_id
    campaign = _campaign(left_rows[0].campaign_id)
    assert campaign.status is CampaignStatus.HYPOTHESIZED
    assert campaign.label == f"callback {SHARED}"
    assert left_rows[0].method == EXACT_CALLBACK_METHOD
    assert right_rows[0].method == EXACT_CALLBACK_METHOD
    assert left_rows[0].confidence == 1.0
    assert SHARED in left_rows[0].rationale
    assert FindingKind.CALLBACK_NUMBER.value in left_rows[0].rationale

    stored = _findings(left) + _findings(right)
    expected_campaigns, expected_rows = propose_callback_campaigns(stored)
    assert [item.id for item in expected_campaigns] == [campaign.id]
    assert {item.id for item in expected_rows} == {left_rows[0].id, right_rows[0].id}
    cited = set(left_rows[0].supporting_finding_ids + right_rows[0].supporting_finding_ids)
    assert cited == {item.id for item in stored}

    envelopes = _stream(redis_url)
    opened = [item for item in envelopes if item.event_type is EventType.CAMPAIGN_OPENED]
    proposed = [item for item in envelopes if item.event_type is EventType.CAMPAIGN_ATTRIBUTION_PROPOSED]
    finding_events = [
        item
        for item in envelopes
        if item.event_type is EventType.INTELLIGENCE_FINDING_PROPOSED and item.call_session_id == right
    ]
    assert len(opened) == 1
    assert len(proposed) == 2
    assert len(finding_events) == 1
    opened_event = opened[0]
    assert opened_event.producer is Producer.INTELLIGENCE
    assert opened_event.call_session_id == right
    assert opened_event.causation_id == finding_events[0].event_id
    opened_payload = CampaignOpened.model_validate(opened_event.payload)
    assert opened_payload.campaign_id == campaign.id
    assert opened_payload.status is CampaignStatus.HYPOTHESIZED
    assert opened_payload.label == campaign.label
    proposed_ids = {CampaignAttributionProposed.model_validate(item.payload).attribution_id for item in proposed}
    assert proposed_ids == {left_rows[0].id, right_rows[0].id}
    assert {item.call_session_id for item in proposed} == {right}
    assert {item.causation_id for item in proposed} == {finding_events[0].event_id}


def test_distinct_callbacks_do_not_merge(redis_url: str) -> None:
    left = _insert_session("sb012-distinct-left")
    right = _insert_session("sb012-distinct-right")
    bus = EventBus(redis_url)
    extractor = ExtractorConsumer(bus=bus)
    correlator = CorrelatorConsumer(bus=bus)
    bus.publish(_final(left, f"One {SHARED}.", occurred_at=NOW))
    bus.publish(_final(right, f"Other {OTHER}.", occurred_at=NOW + timedelta(seconds=5)))
    assert extractor.poll().retry is False
    assert correlator.poll().retry is False
    assert _attributions(left) == []
    assert _attributions(right) == []
    assert _findings(left)[0].value == SHARED
    assert _findings(right)[0].value == OTHER
    opened = [item for item in _stream(redis_url) if item.event_type is EventType.CAMPAIGN_OPENED]
    assert opened == []


def test_redelivery_does_not_duplicate_rows_or_events(redis_url: str) -> None:
    left = _insert_session("sb012-replay-left")
    right = _insert_session("sb012-replay-right")
    left_finding = _insert_finding(left, SHARED, NOW)
    right_finding = _insert_finding(right, SHARED, NOW + timedelta(seconds=10))
    bus = EventBus(redis_url)
    source = _final(right, f"Again {SHARED}.", occurred_at=right_finding.created_at)
    proposed = finding_proposed_envelope(right_finding, source)
    bus.publish(proposed)
    consumer = CorrelatorConsumer(bus=bus)
    delivered = bus.read(GROUP, "manual", count=1)
    assert len(delivered) == 1
    assert consumer.handle(delivered[0]) is True
    assert consumer.handle(delivered[0]) is True
    bus.ack(GROUP, delivered[0])

    before = _campaign_events(redis_url)
    assert len([item for item in before if item.event_type is EventType.CAMPAIGN_OPENED]) == 1
    assert len([item for item in before if item.event_type is EventType.CAMPAIGN_ATTRIBUTION_PROPOSED]) == 2
    assert len(_attributions(left)) == 1
    assert len(_attributions(right)) == 1
    assert _attributions(left)[0].supporting_finding_ids == [left_finding.id]
    assert _attributions(right)[0].supporting_finding_ids == [right_finding.id]

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.xadd(
        STREAM_KEY,
        {ENVELOPE_FIELD: proposed.model_dump_json()},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    client.close()
    again = consumer.poll()
    assert again.retry is False
    assert len(_attributions(left)) == 1
    assert len(_attributions(right)) == 1
    assert _campaign_events(redis_url) == before


def test_missing_finding_stays_pending_and_other_kinds_are_acked(redis_url: str) -> None:
    session_id = _insert_session("sb012-missing")
    bus = EventBus(redis_url)
    pretext = build_envelope(
        event_type=EventType.INTELLIGENCE_FINDING_PROPOSED,
        producer=Producer.INTELLIGENCE,
        call_session_id=session_id,
        payload=IntelligenceFindingProposed(
            finding_id=uuid4(),
            kind=FindingKind.PRETEXT,
            value="bank",
            confidence=0.4,
            extractor="rule",
            extractor_version="0",
        ),
        occurred_at=NOW,
    )
    bus.publish(pretext)
    consumer = CorrelatorConsumer(bus=bus)
    ignored = consumer.poll()
    assert ignored.acknowledged == 1
    assert ignored.retry is False
    assert _attributions(session_id) == []

    missing = build_envelope(
        event_type=EventType.INTELLIGENCE_FINDING_PROPOSED,
        producer=Producer.INTELLIGENCE,
        call_session_id=session_id,
        payload=IntelligenceFindingProposed(
            finding_id=uuid4(),
            kind=FindingKind.CALLBACK_NUMBER,
            value=SHARED,
            confidence=1.0,
            extractor="e164",
            extractor_version="0.1.0",
        ),
        occurred_at=NOW,
    )
    bus.publish(missing)
    pending = consumer.poll()
    assert pending.acknowledged == 0
    assert pending.retry is True
    assert _attributions(session_id) == []


def _insert_session(external: str) -> UUID:
    session = CallSession(
        id=uuid4(),
        operator_number_id=DEV_OPERATOR_ID,
        external_call_id=external,
        carrier="mock",
        caller_number_e164="+15551212000",
        called_number_e164="+15550001001",
        state=CallState.RINGING,
        started_at=NOW,
    )
    with unit_of_work(get_intelligence_settings().database_url) as writer:
        stored, created = writer.call_sessions().insert_ringing(session)
    assert created
    return stored.id


def _insert_finding(session_id: UUID, value: str, created_at: datetime) -> IntelligenceFinding:
    finding = IntelligenceFinding(
        id=uuid4(),
        call_session_id=session_id,
        kind=FindingKind.CALLBACK_NUMBER,
        value=value,
        raw_quote=value,
        transcript_segment_ids=[uuid4()],
        extractor="e164",
        extractor_version="0.1.0",
        confidence=1.0,
        status=FindingStatus.PROPOSED,
        created_at=created_at,
    )
    with open_finding_writer() as writer:
        stored, created = writer.findings().insert(finding)
    assert created
    return stored


def _findings(session_id: UUID) -> list[IntelligenceFinding]:
    with open_finding_writer() as writer:
        return writer.findings().list_for_session(session_id)


def _attributions(session_id: UUID) -> list[CampaignAttribution]:
    with open_attribution_writer() as writer:
        return writer.attributions().list_for_session(session_id)


def _campaign(campaign_id: UUID) -> Campaign:
    with open_attribution_writer() as writer:
        campaign = writer.campaigns().get(campaign_id)
    assert campaign is not None
    return campaign


def _stream(redis_url: str) -> list[EventEnvelope]:
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        entries = client.xrange(STREAM_KEY)
    finally:
        client.close()
    return [EventEnvelope.model_validate_json(fields[ENVELOPE_FIELD]) for _stream_id, fields in entries]


def _campaign_events(redis_url: str) -> list[EventEnvelope]:
    return [
        item
        for item in _stream(redis_url)
        if item.event_type in {EventType.CAMPAIGN_OPENED, EventType.CAMPAIGN_ATTRIBUTION_PROPOSED}
    ]


def _final(session_id: UUID, text: str, *, occurred_at: datetime) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.SPEECH_SEGMENT_FINAL,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=session_id,
        payload=SpeechSegmentPayload(
            transcript_segment_id=uuid4(),
            speaker=Speaker.CALLER,
            text=text,
            is_final=True,
            stt_confidence=0.2,
            start_offset_ms=0,
            end_offset_ms=800,
            sequence=0,
        ),
        occurred_at=occurred_at,
    )
