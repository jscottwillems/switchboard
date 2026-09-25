"""SB-008. A final recognition selects, synthesizes, and publishes the turn."""

import base64
import logging
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from starlette.websockets import WebSocketDisconnect

from switchboard_conversation import FIXED_REPLY, FIXED_STRATEGY_ID
from switchboard_events import STREAM_KEY, ConsumerGroup, EventBus, PublishResult
from switchboard_media.hotpath import respond_to_audio
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_media.ports import (
    MOCK_STT_FIXTURE_FRAME,
    MOCK_STT_FINAL_TEXT,
    MOCK_TTS_FRAME_MS,
    MockStt,
    MockTts,
    SttEvent,
)
from switchboard_media.protocol import MediaSession
from switchboard_media.recognition import RecognizedFinal
from switchboard_media.reply import record_exchange
from switchboard_media.settings import get_settings as get_media_settings
from switchboard_schemas.api import ValidateStreamTokenResponse
from switchboard_schemas.enums import EventType, Speaker
from switchboard_schemas.events import EventEnvelope
from switchboard_schemas.hotpath import ResponseDecision

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


class _BoomStt:
    def push_audio(self, payload: bytes) -> list[SttEvent]:
        raise AssertionError(payload)


def _final_event(text: str = MOCK_STT_FINAL_TEXT) -> SttEvent:
    return SttEvent(text=text, is_final=True, stt_confidence=1.0, start_offset_ms=0, end_offset_ms=20)


def _recognized(text: str = MOCK_STT_FINAL_TEXT) -> RecognizedFinal:
    return RecognizedFinal(
        event=_final_event(text),
        transcript_segment_id=uuid4(),
        speech_event_id=uuid4(),
        published=True,
    )


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
        pytest.fail(f"SB-008 tests need Redis at {url}: {exc}")
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


def _until_close(socket: object) -> tuple[list[dict[str, object]], int]:
    messages: list[dict[str, object]] = []
    while True:
        try:
            message = socket.receive_json()
        except WebSocketDisconnect as exc:
            return messages, exc.code
        assert isinstance(message, dict)
        messages.append(message)


def _bind(session_id: UUID) -> None:
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _StaticValidator(session_id)


def test_recognized_final_does_not_call_stt_again() -> None:
    decisions: list[ResponseDecision] = []
    audio = respond_to_audio(
        uuid4(),
        1,
        b"not-the-frame",
        stt=_BoomStt(),
        recognized=[_final_event()],
        decisions=decisions,
    )
    assert audio == MockTts().synthesize(FIXED_REPLY)
    assert len(decisions) == 1
    assert decisions[0].text == FIXED_REPLY
    assert decisions[0].strategy_id == FIXED_STRATEGY_ID
    assert decisions[0].confidence == 1.0
    assert respond_to_audio(uuid4(), 0, b"unused", stt=_BoomStt(), recognized=[]) == b""


def test_record_exchange_publishes_selected_and_both_turns() -> None:
    bus = _CaptureBus()
    session_id = uuid4()
    final = _recognized("fixture caller segment")
    assert record_exchange(session_id, 0, (final,), _decision(), bus=bus) == 2
    assert [item.event_type for item in bus.envelopes] == [
        EventType.CONVERSATION_TURN_RECORDED,
        EventType.CONVERSATION_RESPONSE_SELECTED,
        EventType.CONVERSATION_TURN_RECORDED,
    ]
    caller, selected, honeypot = bus.envelopes
    assert caller.producer.value == "media_gateway"
    assert caller.causation_id == final.speech_event_id
    assert caller.payload["speaker"] == Speaker.CALLER.value
    assert caller.payload["text"] == "fixture caller segment"
    assert caller.payload["turn_index"] == 0
    assert caller.payload["strategy_id"] is None
    assert caller.payload["confidence"] == 1.0
    assert caller.payload["transcript_segment_ids"] == [str(final.transcript_segment_id)]
    assert selected.causation_id == final.speech_event_id
    assert selected.payload["text"] == FIXED_REPLY
    assert selected.payload["strategy_id"] == FIXED_STRATEGY_ID
    assert selected.payload["confidence"] == 1.0
    assert honeypot.causation_id == selected.event_id
    assert honeypot.payload["turn_id"] == selected.payload["turn_id"]
    assert honeypot.payload["speaker"] == Speaker.HONEYPOT.value
    assert honeypot.payload["text"] == FIXED_REPLY
    assert honeypot.payload["turn_index"] == 1
    assert honeypot.payload["strategy_id"] == FIXED_STRATEGY_ID
    assert honeypot.payload["transcript_segment_ids"] == [str(final.transcript_segment_id)]


def test_failed_conversation_publish_does_not_raise() -> None:
    final = _recognized()
    assert record_exchange(uuid4(), 4, (final,), _decision(), bus=EventBus("")) == 6


def test_clear_ends_playback() -> None:
    session = MediaSession(uuid4())
    assert session.outbound_in_progress() is False
    session.enqueue_outbound(b"\x01\x02")
    assert session.outbound_in_progress() is True
    assert session.pop_outbound() == b"\x01\x02"
    session.mark_outbound_playing()
    assert session.pending_outbound_bytes() == 0
    assert session.outbound_in_progress() is True
    assert session.clear_outbound().model_dump() == {"event": "clear"}
    assert session.outbound_in_progress() is False


def test_socket_sends_tts_and_publishes_conversation_events(
    redis_url: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_id = uuid4()
    _bind(session_id)
    calls = {"n": 0}
    original = MockStt.push_audio

    def counting(self: MockStt, payload: bytes) -> list[SttEvent]:
        calls["n"] += 1
        return original(self, payload)

    monkeypatch.setattr(MockStt, "push_audio", counting)
    caplog.set_level(logging.INFO, logger="switchboard")
    reply_b64 = base64.b64encode(MockTts().synthesize(FIXED_REPLY)).decode("ascii")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_json(_media(b"\x00\x01", 0))
        socket.send_json(_media(MOCK_STT_FIXTURE_FRAME, 1))
        socket.send_bytes(b"\xff\xff")
        socket.send_json({"event": "stop"})
        messages, code = _until_close(socket)
    assert code == 1000
    assert calls["n"] == 3
    assert messages == [
        {
            "event": "media",
            "sequence": 0,
            "timestamp_ms": 0,
            "payload_b64": reply_b64,
        }
    ]

    delivered = EventBus(redis_url).read(ConsumerGroup.API_PROJECTOR, "echo-speak")
    types = [item.envelope.event_type for item in delivered]
    assert types == [
        EventType.SPEECH_SEGMENT_FINAL,
        EventType.CONVERSATION_TURN_RECORDED,
        EventType.CONVERSATION_RESPONSE_SELECTED,
        EventType.CONVERSATION_TURN_RECORDED,
    ]
    speech, caller, selected, honeypot = (item.envelope for item in delivered)
    assert speech.payload["text"] == MOCK_STT_FINAL_TEXT
    assert caller.causation_id == speech.event_id
    assert selected.causation_id == speech.event_id
    assert selected.payload["text"] == FIXED_REPLY
    assert honeypot.causation_id == selected.event_id
    assert honeypot.payload["turn_id"] == selected.payload["turn_id"]
    assert honeypot.payload["speaker"] == "honeypot"
    assert caller.payload["transcript_segment_ids"] == [speech.payload["transcript_segment_id"]]
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    entries = client.xrange(STREAM_KEY)
    client.close()
    for _stream_id, fields in entries:
        assert reply_b64 not in fields["envelope"]
        assert "payload_b64" not in fields["envelope"]
    logs = " ".join(record.getMessage() for record in caplog.records if record.name == "switchboard")
    assert MOCK_STT_FINAL_TEXT not in logs
    assert FIXED_REPLY not in logs
    assert reply_b64 not in logs
    assert "hotpath_timing" in logs


def test_barge_in_clears_before_the_next_reply(redis_url: str) -> None:
    del redis_url
    session_id = uuid4()
    _bind(session_id)
    reply_b64 = base64.b64encode(MockTts().synthesize(FIXED_REPLY)).decode("ascii")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_bytes(MOCK_STT_FIXTURE_FRAME)
        socket.send_bytes(b"\x00")
        socket.send_bytes(MOCK_STT_FIXTURE_FRAME)
        socket.send_json({"event": "stop"})
        messages, code = _until_close(socket)
    assert code == 1000
    assert [item["event"] for item in messages] == ["media", "clear", "media"]
    assert messages[0]["payload_b64"] == reply_b64
    assert messages[1] == {"event": "clear"}
    assert messages[2]["sequence"] == 1
    assert messages[2]["timestamp_ms"] == MOCK_TTS_FRAME_MS
    assert messages[2]["payload_b64"] == reply_b64


def test_redis_outage_still_sends_audio(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1")
    get_media_settings.cache_clear()
    session_id = uuid4()
    _bind(session_id)
    caplog.set_level(logging.INFO, logger="switchboard")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_bytes(MOCK_STT_FIXTURE_FRAME)
        socket.send_json({"event": "stop"})
        messages, code = _until_close(socket)
    assert code == 1000
    assert [item["event"] for item in messages] == ["media"]
    assert "event_publish_failed" in caplog.text
    assert MOCK_STT_FINAL_TEXT not in caplog.text
    assert FIXED_REPLY not in caplog.text


def test_selector_failure_does_not_close_the_socket(
    redis_url: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    del redis_url

    def explode(*args: object, **kwargs: object) -> bytes:
        raise RuntimeError("selector down")

    monkeypatch.setattr("switchboard_media.main.respond_to_audio", explode)
    session_id = uuid4()
    _bind(session_id)
    caplog.set_level(logging.INFO, logger="switchboard")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_bytes(MOCK_STT_FIXTURE_FRAME)
        socket.send_json({"event": "stop"})
        messages, code = _until_close(socket)
    assert code == 1000
    assert messages == []
    assert "hotpath_reply_failed" in caplog.text
    assert "selector down" not in caplog.text
    assert MOCK_STT_FINAL_TEXT not in caplog.text


def _decision() -> ResponseDecision:
    return ResponseDecision(text=FIXED_REPLY, strategy_id=FIXED_STRATEGY_ID, confidence=1.0)
