"""SB-005. A fixture frame becomes one final SttEvent and speech.segment.final."""

import base64
import logging
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from starlette.websockets import WebSocketDisconnect

from switchboard_conversation import FIXED_REPLY
from switchboard_events import STREAM_KEY, ConsumerGroup, EventBus, PublishResult
from switchboard_media.hotpath import respond_to_audio
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_media.ports import (
    MOCK_STT_CONFIDENCE,
    MOCK_STT_END_OFFSET_MS,
    MOCK_STT_FIXTURE_FRAME,
    MOCK_STT_FINAL_TEXT,
    MOCK_STT_START_OFFSET_MS,
    MOCK_TTS_FRAME_BYTES,
    MockStt,
    MockTts,
    SttEvent,
)
from switchboard_media.recognition import recognize_frame
from switchboard_media.settings import get_settings as get_media_settings
from switchboard_schemas.api import ValidateStreamTokenResponse
from switchboard_schemas.enums import EventType, Producer, Speaker
from switchboard_schemas.events import EventEnvelope

media = TestClient(media_app)


class _StaticValidator:
    def __init__(self, session_id: UUID) -> None:
        self._session_id = session_id

    def validate(self, token: str) -> ValidateStreamTokenResponse:
        del token
        return ValidateStreamTokenResponse(valid=True, call_session_id=self._session_id)


class _CaptureBus(EventBus):
    def __init__(self) -> None:
        super().__init__("redis://unused")
        self.envelopes: list[EventEnvelope] = []

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        self.envelopes.append(envelope)
        return PublishResult(stream_id="1-0")


class _RefuseBus(EventBus):
    def __init__(self) -> None:
        super().__init__("redis://unused")

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        raise AssertionError(envelope.event_type)


class _MixedStt:
    def push_audio(self, payload: bytes) -> list[SttEvent]:
        del payload
        return [
            SttEvent(
                text="partial",
                is_final=False,
                start_offset_ms=0,
                end_offset_ms=10,
            ),
            SttEvent(text="", is_final=True, start_offset_ms=0, end_offset_ms=10),
            SttEvent(
                text="kept",
                is_final=True,
                stt_confidence=0.5,
                start_offset_ms=10,
                end_offset_ms=30,
            ),
        ]


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    media_app.dependency_overrides.clear()
    yield
    media_app.dependency_overrides.clear()


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"SB-005 tests need Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_media_settings.cache_clear()
    yield url
    get_media_settings.cache_clear()


def _start(session_id: UUID) -> dict[str, object]:
    return {
        "event": "start",
        "stream_id": "stream-1",
        "call_session_id": str(session_id),
        "media_format": {"encoding": "audio/pcmu", "sample_rate_hz": 8000, "channels": 1},
    }


def _media(payload: bytes, sequence: int) -> dict[str, object]:
    return {
        "event": "media",
        "sequence": sequence,
        "timestamp_ms": sequence * 20,
        "payload_b64": base64.b64encode(payload).decode("ascii"),
    }


def test_mock_stt_fixture_frame_is_one_final() -> None:
    assert len(MOCK_STT_FIXTURE_FRAME) == MOCK_TTS_FRAME_BYTES == 160
    stt = MockStt()
    events = stt.push_audio(MOCK_STT_FIXTURE_FRAME)
    assert events == stt.push_audio(bytes(MOCK_STT_FIXTURE_FRAME))
    assert len(events) == 1
    event = events[0]
    assert event.is_final is True
    assert event.text == MOCK_STT_FINAL_TEXT
    assert event.stt_confidence == MOCK_STT_CONFIDENCE
    assert event.start_offset_ms == MOCK_STT_START_OFFSET_MS == 0
    assert event.end_offset_ms == MOCK_STT_END_OFFSET_MS == 20
    for payload in (b"", b"\xff\xff", b"\xff" * 159, b"\xff" * 161, b"\x00" * 160):
        assert stt.push_audio(payload) == []


def test_fixture_final_reaches_the_existing_selector() -> None:
    audio = respond_to_audio(uuid4(), 0, MOCK_STT_FIXTURE_FRAME)
    assert audio == MockTts().synthesize(FIXED_REPLY)
    assert respond_to_audio(uuid4(), 0, b"\xff\xff") == b""


def test_other_frames_are_not_published() -> None:
    result = recognize_frame(uuid4(), b"\xff\xff", sequence=0, bus=_RefuseBus())
    assert result.events == []
    assert result.next_sequence == 0


def test_only_non_empty_finals_are_published() -> None:
    bus = _CaptureBus()
    session_id = uuid4()
    result = recognize_frame(
        session_id,
        b"unused",
        sequence=4,
        stt=_MixedStt(),
        bus=bus,
    )
    assert result.next_sequence == 5
    assert len(result.events) == 3
    assert len(bus.envelopes) == 1
    envelope = bus.envelopes[0]
    assert envelope.event_type == EventType.SPEECH_SEGMENT_FINAL
    assert envelope.producer == Producer.MEDIA_GATEWAY
    assert envelope.call_session_id == session_id
    assert envelope.event_version == 1
    assert envelope.causation_id is None
    assert envelope.payload["text"] == "kept"
    assert envelope.payload["is_final"] is True
    assert envelope.payload["speaker"] == Speaker.CALLER.value
    assert envelope.payload["sequence"] == 4
    assert envelope.payload["stt_confidence"] == 0.5
    assert envelope.payload["start_offset_ms"] == 10
    assert envelope.payload["end_offset_ms"] == 30


def test_fixture_publishes_two_finals_with_increasing_sequence() -> None:
    bus = _CaptureBus()
    session_id = uuid4()
    first = recognize_frame(session_id, MOCK_STT_FIXTURE_FRAME, sequence=0, bus=bus)
    second = recognize_frame(
        session_id,
        MOCK_STT_FIXTURE_FRAME,
        sequence=first.next_sequence,
        bus=bus,
    )
    assert first.next_sequence == 1
    assert second.next_sequence == 2
    assert [item.payload["sequence"] for item in bus.envelopes] == [0, 1]
    assert bus.envelopes[0].payload["text"] == MOCK_STT_FINAL_TEXT
    assert bus.envelopes[0].payload["is_final"] is True
    assert (
        bus.envelopes[0].payload["transcript_segment_id"]
        != bus.envelopes[1].payload["transcript_segment_id"]
    )


def test_failed_publish_does_not_raise_or_advance_sequence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="switchboard")
    result = recognize_frame(
        uuid4(),
        MOCK_STT_FIXTURE_FRAME,
        sequence=3,
        bus=EventBus(""),
    )
    assert result.next_sequence == 3
    assert len(result.events) == 1
    assert result.events[0].text == MOCK_STT_FINAL_TEXT
    assert "event_publish_failed" in caplog.text
    assert MOCK_STT_FINAL_TEXT not in caplog.text
    assert "redis_unavailable" in caplog.text


def test_socket_publishes_speech_segment_final(
    redis_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_id = uuid4()
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _StaticValidator(
        session_id
    )
    caplog.set_level(logging.INFO, logger="switchboard")
    encoded = base64.b64encode(MOCK_STT_FIXTURE_FRAME).decode("ascii")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_bytes(b"\x00\x01")
        socket.send_json(_media(MOCK_STT_FIXTURE_FRAME, 4))
        socket.send_bytes(b"\xff\xff")
        socket.send_json(_media(MOCK_STT_FIXTURE_FRAME, 6))
        socket.send_json({"event": "stop"})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1000

    bus = EventBus(redis_url)
    projected = bus.read(ConsumerGroup.API_PROJECTOR, "echo-projector")
    extracted = bus.read(ConsumerGroup.INTELLIGENCE_EXTRACTOR, "echo-extractor")
    assert len(projected) == 2
    assert len(extracted) == 2
    assert projected[0].envelope.event_id == extracted[0].envelope.event_id
    assert [item.envelope.event_type for item in projected] == [
        EventType.SPEECH_SEGMENT_FINAL,
        EventType.SPEECH_SEGMENT_FINAL,
    ]
    assert [item.envelope.producer for item in projected] == [
        Producer.MEDIA_GATEWAY,
        Producer.MEDIA_GATEWAY,
    ]
    assert [item.envelope.call_session_id for item in projected] == [session_id, session_id]
    assert [item.envelope.payload["sequence"] for item in projected] == [0, 1]
    assert [item.envelope.payload["text"] for item in projected] == [
        MOCK_STT_FINAL_TEXT,
        MOCK_STT_FINAL_TEXT,
    ]
    assert all(item.envelope.payload["is_final"] is True for item in projected)
    assert all(item.envelope.payload["speaker"] == "caller" for item in projected)
    assert all(item.envelope.payload["stt_confidence"] == 1.0 for item in projected)
    assert all(item.envelope.payload["start_offset_ms"] == 0 for item in projected)
    assert all(item.envelope.payload["end_offset_ms"] == 20 for item in projected)

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    entries = client.xrange(STREAM_KEY)
    client.close()
    assert len(entries) == 2
    for _stream_id, fields in entries:
        body = fields["envelope"]
        assert encoded not in body
        assert "payload_b64" not in body
    switchboard_logs = " ".join(
        record.getMessage() for record in caplog.records if record.name == "switchboard"
    )
    assert "hotpath_timing" not in switchboard_logs
    assert MOCK_STT_FINAL_TEXT not in switchboard_logs
    assert encoded not in switchboard_logs
    assert "media_socket_stopped" in switchboard_logs
