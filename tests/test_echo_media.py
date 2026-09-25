"""SB-004, SB-006, and SB-020. Media parsing, mock TTS, hot-path timing."""

import base64
import hashlib
import json
import logging
import urllib.error
import urllib.request
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from switchboard_api.main import app as api_app
from switchboard_api.memory_tokens import reset_token_store
from switchboard_conversation import FIXED_REPLY, FixedResponseSelector
from switchboard_media.hotpath import respond_to_audio
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_media.ports import MOCK_TTS_FRAME_BYTES, MockTts, SttEvent
from switchboard_media.protocol import (
    TELEPHONY_DEFAULT_CHANNELS,
    TELEPHONY_DEFAULT_ENCODING,
    TELEPHONY_DEFAULT_SAMPLE_RATE_HZ,
    MediaSession,
    frame_from_websocket_message,
)
from switchboard_media.tokens import (
    INTERNAL_TOKEN_HEADER,
    VALIDATE_PATH,
    ApiStreamTokenValidator,
    StreamTokenCheckError,
)
from switchboard_schemas.api import ValidateStreamTokenResponse
from switchboard_schemas.hotpath import ResponseDecision, ResponseRequest

api = TestClient(api_app)
media = TestClient(media_app)
INTERNAL = {INTERNAL_TOKEN_HEADER: "test-internal-token"}


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Body":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _StaticValidator:
    def __init__(self, result: ValidateStreamTokenResponse) -> None:
        self._result = result
        self.tokens: list[str] = []

    def validate(self, token: str) -> ValidateStreamTokenResponse:
        self.tokens.append(token)
        return self._result


class _DownValidator:
    def validate(self, token: str) -> ValidateStreamTokenResponse:
        del token
        raise StreamTokenCheckError("validate_unavailable")


class _FinalStt:
    def __init__(self, text: str) -> None:
        self._text = text

    def push_audio(self, payload: bytes) -> list[SttEvent]:
        del payload
        return [
            SttEvent(
                text=self._text,
                is_final=True,
                start_offset_ms=0,
                end_offset_ms=20,
            )
        ]


class _BoomSelector:
    def select(self, request: ResponseRequest) -> ResponseDecision:
        del request
        raise AssertionError("selector should not run")


@pytest.fixture(autouse=True)
def _isolate_media() -> None:
    reset_token_store()
    media_app.dependency_overrides.clear()
    yield
    reset_token_store()
    media_app.dependency_overrides.clear()


def _start(session_id: UUID, *, encoding: str = "audio/pcmu", rate: int = 8000) -> dict[str, object]:
    return {
        "event": "start",
        "stream_id": "stream-1",
        "call_session_id": str(session_id),
        "media_format": {"encoding": encoding, "sample_rate_hz": rate, "channels": 1},
    }


def _bind(session_id: UUID) -> _StaticValidator:
    validator = _StaticValidator(
        ValidateStreamTokenResponse(valid=True, call_session_id=session_id)
    )
    media_app.dependency_overrides[get_stream_token_validator] = lambda: validator
    return validator


def _issue(session_id: UUID) -> str:
    response = api.post(
        "/v1/internal/stream-tokens",
        json={"call_session_id": str(session_id)},
        headers=INTERNAL,
    )
    assert response.status_code == 200
    return str(response.json()["token"])


def _api_opener(seen: list[urllib.request.Request]):
    def opener(request: urllib.request.Request, timeout: float) -> _Body:
        del timeout
        seen.append(request)
        header = request.headers.get("X-switchboard-internal-token")
        content_type = request.headers.get("Content-type", "application/json")
        response = api.post(
            VALIDATE_PATH,
            content=request.data,
            headers={
                INTERNAL_TOKEN_HEADER: header or "",
                "Content-Type": content_type,
            },
        )
        if response.status_code != 200:
            raise urllib.error.URLError(f"http {response.status_code}")
        return _Body(response.content)

    return opener


def _forward(seen: list[urllib.request.Request]) -> ApiStreamTokenValidator:
    return ApiStreamTokenValidator(
        api_base_url="http://api.test",
        internal_token="test-internal-token",
        timeout_s=2.0,
        opener=_api_opener(seen),
    )


def test_missing_token_closes_1008_without_validate() -> None:
    validator = _StaticValidator(ValidateStreamTokenResponse(valid=False, call_session_id=None))
    media_app.dependency_overrides[get_stream_token_validator] = lambda: validator
    with pytest.raises(WebSocketDisconnect) as missing:
        with media.websocket_connect("/v1/streams") as socket:
            socket.receive_json()
    assert missing.value.code == 1008
    with pytest.raises(WebSocketDisconnect) as empty:
        with media.websocket_connect("/v1/streams?token=") as socket:
            socket.receive_json()
    assert empty.value.code == 1008
    assert validator.tokens == []


def test_invalid_token_closes_1008_and_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "echo-secret-token-value"
    validator = _StaticValidator(ValidateStreamTokenResponse(valid=False, call_session_id=None))
    media_app.dependency_overrides[get_stream_token_validator] = lambda: validator
    caplog.set_level(logging.INFO, logger="switchboard")
    with pytest.raises(WebSocketDisconnect) as rejected:
        with media.websocket_connect(f"/v1/streams?token={secret}") as socket:
            socket.receive_json()
    assert rejected.value.code == 1008
    assert validator.tokens == [secret]
    switchboard_logs = " ".join(
        record.getMessage() for record in caplog.records if record.name == "switchboard"
    )
    assert secret not in switchboard_logs
    assert "invalid_token" in switchboard_logs


def test_validate_failure_closes_1008() -> None:
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _DownValidator()
    with pytest.raises(WebSocketDisconnect) as rejected:
        with media.websocket_connect("/v1/streams?token=present") as socket:
            socket.receive_json()
    assert rejected.value.code == 1008


def test_present_token_is_posted_to_internal_validate() -> None:
    session_id = uuid4()
    token = _issue(session_id)
    seen: list[urllib.request.Request] = []
    validator = _forward(seen)
    result = validator.validate(token)
    assert result == ValidateStreamTokenResponse(valid=True, call_session_id=session_id)
    assert len(seen) == 1
    request = seen[0]
    assert request.full_url == f"http://api.test{VALIDATE_PATH}"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"token": token}
    assert request.headers.get("X-switchboard-internal-token") == "test-internal-token"
    assert request.headers.get("Content-type") == "application/json"

    unknown = validator.validate("not-a-real-token")
    assert unknown.valid is False
    assert unknown.call_session_id is None


def test_wrong_internal_credential_fails_closed() -> None:
    seen: list[urllib.request.Request] = []
    validator = ApiStreamTokenValidator(
        api_base_url="http://api.test",
        internal_token="wrong-internal-token",
        timeout_s=2.0,
        opener=_api_opener(seen),
    )
    with pytest.raises(StreamTokenCheckError) as raised:
        validator.validate("not-a-real-token")
    assert raised.value.reason == "validate_unavailable"


def test_overlong_token_is_rejected_without_a_post() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> _Body:
        del request, timeout
        raise AssertionError("overlong token must not be posted")

    validator = ApiStreamTokenValidator(
        api_base_url="http://api.test",
        internal_token="test-internal-token",
        timeout_s=2.0,
        opener=opener,
    )
    result = validator.validate("x" * 257)
    assert result.valid is False
    assert result.call_session_id is None


def test_socket_accepts_a_token_the_api_validates() -> None:
    session_id = uuid4()
    token = _issue(session_id)
    seen: list[urllib.request.Request] = []
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _forward(seen)
    with media.websocket_connect(f"/v1/streams?token={token}") as socket:
        ready = socket.receive_json()
        assert ready == {"event": "ready", "protocol": "switchboard.media.v1"}
        socket.send_json(_start(session_id))
        socket.send_json({"event": "stop", "reason": "carrier hangup"})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1000
    assert json.loads(seen[0].data) == {"token": token}


def test_start_media_binary_and_stop_count_audio(caplog: pytest.LogCaptureFixture) -> None:
    session_id = uuid4()
    _bind(session_id)
    caplog.set_level(logging.INFO, logger="switchboard")
    payload_b64 = base64.b64encode(b"\xff\x00").decode("ascii")
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        assert socket.receive_json()["event"] == "ready"
        socket.send_json(_start(session_id))
        socket.send_json(
            {"event": "media", "sequence": 4, "timestamp_ms": 40, "payload_b64": payload_b64}
        )
        socket.send_bytes(b"\x00\x01")
        socket.send_json({"event": "stop"})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1000
    stopped = [
        record.getMessage()
        for record in caplog.records
        if record.name == "switchboard" and record.getMessage().startswith("media_socket_stopped")
    ]
    assert len(stopped) == 1
    assert "'audio_frames': 2" in stopped[0]
    assert "payload_b64" not in stopped[0]
    assert payload_b64 not in stopped[0]


def test_invalid_json_and_legacy_mulaw_close_1007() -> None:
    session_id = uuid4()
    _bind(session_id)
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        socket.receive_json()
        socket.send_json({"event": "start", "encoding": "audio/x-mulaw"})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1007

    _bind(session_id)
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        socket.receive_json()
        socket.send_json(_start(session_id, encoding="audio/x-mulaw"))
        with pytest.raises(WebSocketDisconnect) as mulaw:
            socket.receive_json()
    assert mulaw.value.code == 1007


def test_session_mismatch_closes_1008() -> None:
    session_id = uuid4()
    _bind(session_id)
    with media.websocket_connect("/v1/streams?token=dev-token") as socket:
        socket.receive_json()
        socket.send_json(_start(uuid4()))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1008


def test_session_parses_start_media_stop_and_binary() -> None:
    session_id = uuid4()
    session = MediaSession(session_id)
    early = session.accept_binary(b"\xff")
    assert early.close_code == 1007
    assert early.reason == "start_required"

    started = session.accept_text(json.dumps(_start(session_id, encoding="audio/pcm", rate=16000)))
    assert started.close_code is None
    assert session.encoding == "audio/pcm"
    assert session.sample_rate_hz == 16000

    media_frame = session.accept_text(
        json.dumps(
            {
                "event": "media",
                "sequence": 0,
                "timestamp_ms": 0,
                "payload_b64": base64.b64encode(b"\xff\x00").decode("ascii"),
            }
        )
    )
    assert media_frame.audio is not None
    assert media_frame.audio.source == "json"
    assert media_frame.audio.sequence == 0
    assert media_frame.audio.payload == b"\xff\x00"
    assert media_frame.audio.timestamp_ms == 0

    binary = frame_from_websocket_message(
        session,
        {"type": "websocket.receive", "bytes": b"\x00\x01"},
    )
    assert binary.audio is not None
    assert binary.audio.source == "binary"
    assert binary.audio.sequence == 1
    assert binary.audio.payload == b"\x00\x01"
    assert session.audio_frames == 2

    bad_audio = session.accept_text(
        json.dumps({"event": "media", "sequence": 2, "timestamp_ms": 20, "payload_b64": "!!!!"})
    )
    assert bad_audio.close_code == 1007
    assert bad_audio.reason == "invalid_audio"

    extra = session.accept_text('{"event":"stop","reason":"done","extra":true}')
    assert extra.close_code == 1007

    stopped = session.accept_text('{"event":"stop","reason":"done"}')
    assert stopped.stopped is True
    assert session.audio_frames == 2


def test_clear_drops_buffered_outbound_audio() -> None:
    session = MediaSession(uuid4())
    session.enqueue_outbound(b"\xff" * 160)
    session.enqueue_outbound(b"")
    session.enqueue_outbound(b"\x00\x01")
    assert session.pending_outbound_bytes() == 162
    assert session.clear_outbound().model_dump() == {"event": "clear"}
    assert session.pending_outbound_bytes() == 0


def test_mock_tts_returns_deterministic_pcmu() -> None:
    assert TELEPHONY_DEFAULT_ENCODING == "audio/pcmu"
    assert TELEPHONY_DEFAULT_SAMPLE_RATE_HZ == 8000
    assert TELEPHONY_DEFAULT_CHANNELS == 1
    assert MOCK_TTS_FRAME_BYTES == 160
    tts = MockTts()
    text = "Could you repeat that?"
    audio = tts.synthesize(text)
    assert audio == tts.synthesize(text)
    assert audio != tts.synthesize("a different line")
    assert len(audio) == MOCK_TTS_FRAME_BYTES
    assert audio[:32] == hashlib.sha256(text.encode("utf-8")).digest()
    assert tts.synthesize("") == b""


def test_hotpath_emits_stage_durations(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[str, dict[str, object]]] = []

    def capture(event: str, **fields: object) -> None:
        recorded.append((event, fields))

    monkeypatch.setattr("switchboard_media.hotpath.log_info", capture)
    audio = respond_to_audio(
        uuid4(),
        1,
        b"\xff\x00",
        stt=_FinalStt("hello"),
        selector=FixedResponseSelector(),
    )
    assert audio == MockTts().synthesize(FIXED_REPLY)
    assert audio != MockTts().synthesize("hello")
    timings = [fields for event, fields in recorded if event == "hotpath_timing"]
    assert len(timings) == 1
    assert set(timings[0]) == {"stt_ms", "select_ms", "tts_ms"}
    assert all(isinstance(value, int) and value >= 0 for value in timings[0].values())


def test_hotpath_without_final_emits_stt_only(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[str, dict[str, object]]] = []

    def capture(event: str, **fields: object) -> None:
        recorded.append((event, fields))

    monkeypatch.setattr("switchboard_media.hotpath.log_info", capture)
    assert (
        respond_to_audio(uuid4(), 0, b"\xff\xff", selector=_BoomSelector())
        == b""
    )
    assert len(recorded) == 1
    event, fields = recorded[0]
    assert event == "hotpath_timing"
    assert set(fields) == {"stt_ms"}
    assert isinstance(fields["stt_ms"], int)


def test_hotpath_returns_audio_when_timing_emit_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(event: str, **fields: object) -> None:
        raise RuntimeError(event)

    monkeypatch.setattr("switchboard_media.hotpath.log_info", explode)
    audio = respond_to_audio(
        uuid4(),
        0,
        b"\xff\x00",
        stt=_FinalStt("hello"),
        selector=FixedResponseSelector(),
    )
    assert audio == MockTts().synthesize(FIXED_REPLY)
    assert len(audio) == MOCK_TTS_FRAME_BYTES
