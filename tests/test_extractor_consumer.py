"""SB-010: speech.segment.final becomes a finding and a proposed event."""

import logging
import threading
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from starlette.websockets import WebSocketDisconnect

from switchboard_classification import E164FindingExtractor
from switchboard_events import (
    ENVELOPE_FIELD,
    STREAM_KEY,
    STREAM_MAXLEN,
    ConsumerGroup,
    DeliveredEvent,
    EventBus,
    build_envelope,
)
from switchboard_intelligence.deps import open_finding_writer
from switchboard_intelligence.extractor_worker import (
    ExtractorConsumer,
    extractor_worker_enabled,
    transcript_from_final,
)
from switchboard_intelligence.settings import get_settings as get_intelligence_settings
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_repositories import unit_of_work
from switchboard_schemas.api import ValidateStreamTokenResponse
from switchboard_schemas.enums import CallState, EventType, FindingKind, Producer, Speaker
from switchboard_schemas.events import (
    EventEnvelope,
    IntelligenceFindingProposed,
    SpeechSegmentPayload,
    TelephonyCallReceived,
)
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import CallSession, TranscriptSegment

from tests.postgres_support import query_all

NOW = datetime(2026, 9, 25, 23, 40, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")
GROUP = ConsumerGroup.INTELLIGENCE_EXTRACTOR


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"SB-010 tests need Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_intelligence_settings.cache_clear()
    yield url
    get_intelligence_settings.cache_clear()


def test_worker_stays_off_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWITCHBOARD_EXTRACTOR_WORKER", raising=False)
    assert extractor_worker_enabled() is False


def test_lifespan_starts_the_extractor_thread_without_touching_the_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    released = threading.Event()

    def _serve(stop: threading.Event) -> None:
        started.set()
        stop.wait()
        released.set()

    monkeypatch.setenv("SWITCHBOARD_EXTRACTOR_WORKER", "1")
    monkeypatch.setattr("switchboard_intelligence.main.serve_extractor", _serve)
    from switchboard_intelligence.main import app as intelligence_app

    with TestClient(intelligence_app) as client:
        assert started.wait(2)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "intelligence"
    assert released.wait(2)


class _FixedToken:
    def __init__(self, call_session_id: UUID) -> None:
        self._call_session_id = call_session_id

    def validate(self, token: str) -> ValidateStreamTokenResponse:
        del token
        return ValidateStreamTokenResponse(valid=True, call_session_id=self._call_session_id)


class _Boom:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        self.calls += 1
        raise RuntimeError("leaked transcript +15551234567")


class _Counting:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, segments: Sequence[TranscriptSegment]) -> list[IntelligenceFinding]:
        self.calls += 1
        return E164FindingExtractor().extract(segments)


def test_final_segment_with_e164_inserts_a_finding_and_publishes(redis_url: str) -> None:
    session_id = _insert_session("sb010-hit")
    bus = EventBus(redis_url)
    bus.publish(_received(session_id))
    speech = _final(
        session_id,
        text="Please call me back at +15551234567 today.",
        stt_confidence=0.25,
    )
    bus.publish(speech)
    consumer = ExtractorConsumer(bus=bus)
    first = consumer.poll()
    assert first.acknowledged == 2
    assert first.retry is False

    findings = _findings(session_id)
    assert len(findings) == 1
    finding = findings[0]
    payload = SpeechSegmentPayload.model_validate(speech.payload)
    expected = E164FindingExtractor().extract([transcript_from_final(speech, payload)])
    assert finding.id == expected[0].id
    assert finding.kind is FindingKind.CALLBACK_NUMBER
    assert finding.value == "+15551234567"
    assert finding.raw_quote == "+15551234567"
    assert finding.transcript_segment_ids == [payload.transcript_segment_id]
    assert finding.confidence == 1.0
    assert finding.confidence != payload.stt_confidence
    assert finding.extractor == "e164"
    assert _transcript_count(session_id) == 0

    proposed = _proposed(bus)
    assert len(proposed) == 1
    event = proposed[0].envelope
    assert event.producer is Producer.INTELLIGENCE
    assert event.causation_id == speech.event_id
    assert event.call_session_id == session_id
    assert "stt_confidence" not in event.payload
    parsed = IntelligenceFindingProposed.model_validate(event.payload)
    assert parsed.finding_id == finding.id
    assert parsed.confidence == finding.confidence
    assert parsed.value == finding.value
    assert parsed.kind is FindingKind.CALLBACK_NUMBER

    second = consumer.poll()
    assert second.acknowledged == 1
    assert len(_findings(session_id)) == 1


def test_final_segment_without_e164_inserts_nothing(redis_url: str) -> None:
    session_id = _insert_session("sb010-miss")
    bus = EventBus(redis_url)
    bus.publish(
        _final(
            session_id,
            text="Please call me back at the office.",
            stt_confidence=0.91,
        )
    )
    bus.publish(
        _speech(
            session_id,
            event_type=EventType.SPEECH_SEGMENT_PARTIAL,
            text="Partial +15551234567",
            is_final=False,
            sequence=1,
        )
    )
    result = ExtractorConsumer(bus=bus).poll()
    assert result.acknowledged == 2
    assert result.retry is False
    assert _findings(session_id) == []
    assert _proposed(bus) == []


def test_extractor_exception_is_acked_and_the_next_final_still_lands(
    redis_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_id = _insert_session("sb010-boom")
    bus = EventBus(redis_url)
    boom = _Boom()
    consumer = ExtractorConsumer(bus=bus, extractor=boom)
    bus.publish(_final(session_id, text="Call +15551234567 now.", sequence=0))
    with caplog.at_level(logging.INFO, logger="switchboard"):
        failed = consumer.poll()
    assert failed.acknowledged == 1
    assert failed.retry is False
    assert boom.calls == 1
    assert "extractor_failed" in caplog.text
    assert "+15551234567" not in caplog.text
    assert "leaked transcript" not in caplog.text
    assert _findings(session_id) == []

    bus.publish(_final(session_id, text="Later +15557654321.", sequence=1))
    landed = ExtractorConsumer(bus=bus).poll()
    assert landed.acknowledged == 1
    assert [item.value for item in _findings(session_id)] == ["+15557654321"]


def test_extractor_exception_does_not_close_the_media_socket(redis_url: str) -> None:
    call_id = uuid4()
    bus = EventBus(redis_url)
    bus.publish(_final(call_id, text="Call +15551234567.", sequence=0))
    media = TestClient(media_app)
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _FixedToken(call_id)
    try:
        with media.websocket_connect("/v1/streams?token=dev-token") as socket:
            assert socket.receive_json() == {"event": "ready", "protocol": "switchboard.media.v1"}
            result = ExtractorConsumer(bus=bus, extractor=_Boom()).poll()
            assert result.acknowledged == 1
            socket.send_json(
                {
                    "event": "start",
                    "stream_id": "stream-1",
                    "call_session_id": str(call_id),
                    "media_format": {
                        "encoding": "audio/pcmu",
                        "sample_rate_hz": 8000,
                        "channels": 1,
                    },
                }
            )
            socket.send_bytes(b"\xff\x00")
            socket.send_json({"event": "stop"})
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
    finally:
        media_app.dependency_overrides.clear()
    assert closed.value.code == 1000


def test_redelivery_of_the_same_event_id_does_not_duplicate_the_finding(redis_url: str) -> None:
    session_id = _insert_session("sb010-replay")
    bus = EventBus(redis_url)
    speech = _final(session_id, text="Reach us at +15550001111.", stt_confidence=0.4)
    bus.publish(speech)
    counting = _Counting()
    consumer = ExtractorConsumer(bus=bus, extractor=counting, consumer_name="extractor")
    delivered = bus.read(GROUP, "manual", count=1)
    assert len(delivered) == 1
    assert consumer.handle(delivered[0]) is True
    assert consumer.handle(delivered[0]) is True
    assert counting.calls == 2
    bus.ack(GROUP, delivered[0])
    assert len(_findings(session_id)) == 1
    assert len(_proposed(bus)) == 1

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    client.xadd(
        STREAM_KEY,
        {ENVELOPE_FIELD: speech.model_dump_json()},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    client.close()
    again = consumer.poll()
    assert again.retry is False
    assert counting.calls == 2
    assert len(_findings(session_id)) == 1
    assert [item.confidence for item in _findings(session_id)] == [1.0]


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


def _findings(session_id: UUID) -> list[IntelligenceFinding]:
    with open_finding_writer() as writer:
        return writer.findings().list_for_session(session_id)


def _transcript_count(session_id: UUID) -> int:
    rows = query_all(
        "SELECT id FROM obs.transcript_segment WHERE call_session_id = %s",
        (session_id,),
    )
    return len(rows)


def _proposed(bus: EventBus) -> list[DeliveredEvent]:
    delivered = bus.read(ConsumerGroup.INTELLIGENCE_CORRELATOR, "correlator-test", count=32)
    return [
        item
        for item in delivered
        if item.envelope.event_type is EventType.INTELLIGENCE_FINDING_PROPOSED
    ]


def _received(session_id: UUID) -> EventEnvelope:
    return build_envelope(
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        producer=Producer.API,
        call_session_id=session_id,
        payload=TelephonyCallReceived(
            external_call_id="sb010-received",
            carrier="mock",
            caller_number_e164="+15551212000",
            called_number_e164="+15550001001",
        ),
        occurred_at=NOW,
    )


def _final(
    session_id: UUID,
    *,
    text: str,
    sequence: int = 0,
    stt_confidence: float | None = 0.25,
) -> EventEnvelope:
    return _speech(
        session_id,
        event_type=EventType.SPEECH_SEGMENT_FINAL,
        text=text,
        is_final=True,
        sequence=sequence,
        stt_confidence=stt_confidence,
    )


def _speech(
    session_id: UUID,
    *,
    event_type: EventType,
    text: str,
    is_final: bool,
    sequence: int,
    stt_confidence: float | None = None,
) -> EventEnvelope:
    return build_envelope(
        event_type=event_type,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=session_id,
        payload=SpeechSegmentPayload(
            transcript_segment_id=uuid4(),
            speaker=Speaker.CALLER,
            text=text,
            is_final=is_final,
            stt_confidence=stt_confidence,
            start_offset_ms=sequence * 1000,
            end_offset_ms=sequence * 1000 + 800,
            sequence=sequence,
        ),
        occurred_at=NOW,
    )
