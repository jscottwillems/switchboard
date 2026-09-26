"""API projector: speech finals and conversation turns become stored rows."""

import threading
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from switchboard_api.deps import open_observation_writer
from switchboard_api.projector import ProjectorConsumer, projector_worker_enabled
from switchboard_api.settings import get_settings
from switchboard_events import ConsumerGroup, EventBus, build_envelope
from switchboard_repositories import unit_of_work
from switchboard_schemas.enums import (
    CallState,
    EventType,
    MediaStreamState,
    Producer,
    Speaker,
    TranscriptSource,
)
from switchboard_schemas.events import (
    ConversationResponseSelected,
    ConversationTurnRecorded,
    SpeechSegmentPayload,
    TelephonyCallReceived,
)
from switchboard_schemas.observations import CallSession

NOW = datetime(2026, 9, 26, 0, 10, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")
CALLBACK = "+15551234567"


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"projector tests need Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def test_worker_stays_off_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWITCHBOARD_PROJECTOR_WORKER", raising=False)
    assert projector_worker_enabled() is False


def test_lifespan_starts_the_projector_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    released = threading.Event()

    def _serve(stop: threading.Event) -> None:
        started.set()
        stop.wait()
        released.set()

    monkeypatch.setenv("SWITCHBOARD_PROJECTOR_WORKER", "1")
    monkeypatch.setattr("switchboard_api.main.serve_projector", _serve)
    from switchboard_api.main import app as api_app

    with TestClient(api_app) as client:
        assert started.wait(2)
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "api"
    assert released.wait(2)


def test_final_segment_is_stored_and_a_second_final_reuses_the_stream(redis_url: str) -> None:
    session_id = _insert_session("projector-final")
    bus = EventBus(redis_url)
    first = _final(session_id, text=f"call {CALLBACK}", sequence=0, stt_confidence=0.25)
    second = _final(session_id, text="again", sequence=1, stt_confidence=1.0)
    bus.publish(first)
    bus.publish(second)
    result = ProjectorConsumer(bus=bus).poll()
    assert result.acknowledged == 2
    assert result.retry is False

    with open_observation_writer() as models:
        segments = models.transcripts().list_for_session(session_id)
        streams = models.media_streams().list_for_session(session_id)
    assert [segment.sequence for segment in segments] == [0, 1]
    assert segments[0].text == f"call {CALLBACK}"
    assert segments[0].source is TranscriptSource.STT
    assert segments[0].provider == "mock-stt"
    assert segments[0].stt_confidence == 0.25
    assert segments[0].is_final is True
    assert segments[0].speaker is Speaker.CALLER
    assert len(streams) == 1
    assert streams[0].external_stream_id == "unscoped"
    assert streams[0].encoding == "audio/pcmu"
    assert streams[0].sample_rate_hz == 8000
    assert streams[0].state is MediaStreamState.STREAMING
    assert segments[0].media_stream_id == streams[0].id
    assert segments[1].media_stream_id == streams[0].id

    again = ProjectorConsumer(bus=bus).poll()
    assert again.acknowledged == 0
    with open_observation_writer() as models:
        assert len(models.transcripts().list_for_session(session_id)) == 2


def test_turn_is_stored_and_a_selected_event_is_not_a_turn(redis_url: str) -> None:
    session_id = _insert_session("projector-turn")
    bus = EventBus(redis_url)
    segment_id = uuid4()
    turn_id = uuid4()
    bus.publish(
        build_envelope(
            event_type=EventType.CONVERSATION_RESPONSE_SELECTED,
            producer=Producer.MEDIA_GATEWAY,
            call_session_id=session_id,
            payload=ConversationResponseSelected(
                turn_id=uuid4(),
                strategy_id="fixed.v1",
                text="Could you repeat that?",
                confidence=1.0,
            ),
            occurred_at=NOW,
        )
    )
    bus.publish(
        build_envelope(
            event_type=EventType.CONVERSATION_TURN_RECORDED,
            producer=Producer.MEDIA_GATEWAY,
            call_session_id=session_id,
            payload=ConversationTurnRecorded(
                turn_id=turn_id,
                turn_index=0,
                speaker=Speaker.CALLER,
                text=f"call {CALLBACK}",
                transcript_segment_ids=[segment_id],
                strategy_id=None,
                confidence=1.0,
            ),
            occurred_at=NOW,
        )
    )
    result = ProjectorConsumer(bus=bus).poll()
    assert result.retry is False
    with open_observation_writer() as models:
        turns = models.conversation_turns().list_for_session(session_id)
    assert len(turns) == 1
    assert turns[0].id == turn_id
    assert turns[0].turn_index == 0
    assert turns[0].speaker is Speaker.CALLER
    assert turns[0].strategy_id is None
    assert turns[0].confidence == 1.0
    assert turns[0].transcript_segment_ids == [segment_id]
    assert turns[0].text == f"call {CALLBACK}"


def test_partial_and_received_do_not_write_a_transcript(redis_url: str) -> None:
    session_id = _insert_session("projector-ignore")
    bus = EventBus(redis_url)
    bus.publish(
        _speech(
            session_id,
            event_type=EventType.SPEECH_SEGMENT_PARTIAL,
            text=f"partial {CALLBACK}",
            is_final=False,
            sequence=0,
        )
    )
    bus.publish(
        build_envelope(
            event_type=EventType.TELEPHONY_CALL_RECEIVED,
            producer=Producer.API,
            call_session_id=session_id,
            payload=TelephonyCallReceived(
                external_call_id="projector-ignore",
                carrier="mock",
                caller_number_e164="+15551212000",
                called_number_e164="+15550001001",
            ),
            occurred_at=NOW,
        )
    )
    result = ProjectorConsumer(bus=bus).poll()
    assert result.acknowledged == 2
    assert result.retry is False
    with open_observation_writer() as models:
        assert models.transcripts().list_for_session(session_id) == []
        assert models.media_streams().list_for_session(session_id) == []
        assert models.call_sessions().get(session_id) is not None


def test_missing_session_leaves_the_final_pending(redis_url: str) -> None:
    session_id = uuid4()
    bus = EventBus(redis_url)
    bus.publish(_final(session_id, text=f"call {CALLBACK}", sequence=0, stt_confidence=1.0))
    result = ProjectorConsumer(bus=bus, consumer_name="pending").poll()
    assert result.acknowledged == 0
    assert result.retry is True
    pending = bus.read(ConsumerGroup.API_PROJECTOR, "pending", count=4)
    assert len(pending) == 1
    assert pending[0].envelope.event_type is EventType.SPEECH_SEGMENT_FINAL


def test_same_event_twice_stores_one_segment(redis_url: str) -> None:
    session_id = _insert_session("projector-replay")
    bus = EventBus(redis_url)
    speech = _final(session_id, text=f"call {CALLBACK}", sequence=0, stt_confidence=0.4)
    bus.publish(speech)
    consumer = ProjectorConsumer(bus=bus, consumer_name="replay")
    delivered = bus.read(ConsumerGroup.API_PROJECTOR, "manual", count=1)
    assert consumer.handle(delivered[0]) is True
    assert consumer.handle(delivered[0]) is True
    bus.ack(ConsumerGroup.API_PROJECTOR, delivered[0])
    with open_observation_writer() as models:
        segments = models.transcripts().list_for_session(session_id)
    assert len(segments) == 1
    assert str(segments[0].id) == speech.payload["transcript_segment_id"]


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
    with unit_of_work(get_settings().database_url) as writer:
        stored, created = writer.call_sessions().insert_ringing(session)
    assert created
    return stored.id


def _final(
    session_id: UUID,
    *,
    text: str,
    sequence: int,
    stt_confidence: float,
):
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
):
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
            start_offset_ms=0,
            end_offset_ms=20,
            sequence=sequence,
        ),
        occurred_at=NOW,
    )
