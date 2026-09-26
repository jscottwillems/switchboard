"""Mock vertical slice: webhook, fixture audio, speak-back, finding, read API.

`make test-mvp-smoke` runs this module. No live carrier, STT, or TTS account.
The dashboard is not opened; `GET /v1/calls` and `GET /v1/calls/{id}` are the
read path RADAR polls. A signed status callback then marks the session
`in_progress`, which is the live-board filter.
"""

import base64
import urllib.request
from collections.abc import Callable, Iterator
from uuid import UUID, uuid5

import pytest
import redis
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from starlette.websockets import WebSocketDisconnect

from switchboard_api.main import app as api_app
from switchboard_api.projector import PollResult as ProjectorPoll
from switchboard_api.projector import ProjectorConsumer
from switchboard_api.settings import get_settings as get_api_settings
from switchboard_conversation import FIXED_REPLY, FIXED_STRATEGY_ID
from switchboard_events import STREAM_KEY, EventBus
from switchboard_intelligence.extractor_worker import ExtractorConsumer
from switchboard_intelligence.extractor_worker import PollResult as ExtractorPoll
from switchboard_intelligence.settings import get_settings as get_intelligence_settings
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_media.ports import MOCK_STT_FIXTURE_FRAME, MOCK_STT_FINAL_TEXT, MockTts
from switchboard_media.settings import get_settings as get_media_settings
from switchboard_media.tokens import ApiStreamTokenValidator
from switchboard_schemas.api import CallDetailResponse, CallListResponse
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import CallState, EventType, FindingKind, FindingStatus, Speaker
from switchboard_schemas.events import EventEnvelope
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE

from tests.operator_support import OPERATOR_HEADERS

api = TestClient(api_app, headers=OPERATOR_HEADERS)
media = TestClient(media_app)

CALLBACK_NUMBER = "+15551234567"
PROVIDER_CALL_ID = "mvp-smoke-1"
CALLED_NUMBER = "+15550001001"
CALLER_NUMBER = "+15551212000"


class _ResponseBody:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_ResponseBody":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class _ApiOpener:
    """POST the validate route through the API test client.

    The media gateway's validator still builds the urllib request. This opener
    delivers it to that client so the token issued by the webhook is the token
    the socket checks, without a second listening port.
    """

    def __call__(self, request: urllib.request.Request, timeout: float) -> _ResponseBody:
        del timeout
        response = api.post(
            request.selector,
            content=request.data,
            headers=dict(request.header_items()),
        )
        return _ResponseBody(response.content)


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = "redis://localhost:6379/15"
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        client.ping()
    except RedisError as exc:
        pytest.fail(f"MVP smoke needs Redis at {url}: {exc}")
    client.flushdb()
    client.close()
    monkeypatch.setenv("REDIS_URL", url)
    get_api_settings.cache_clear()
    get_media_settings.cache_clear()
    get_intelligence_settings.cache_clear()
    media_app.dependency_overrides[get_stream_token_validator] = _validator
    yield url
    media_app.dependency_overrides.clear()
    get_api_settings.cache_clear()
    get_media_settings.cache_clear()
    get_intelligence_settings.cache_clear()


def _validator() -> ApiStreamTokenValidator:
    settings = get_media_settings()
    return ApiStreamTokenValidator(
        api_base_url=settings.api_base_url,
        internal_token=settings.internal_token,
        timeout_s=settings.stream_token_timeout_s,
        opener=_ApiOpener(),
    )


@pytest.mark.mvp_smoke
def test_mock_vertical_slice(redis_url: str) -> None:
    assert CALLBACK_NUMBER in MOCK_STT_FINAL_TEXT
    call_session_id, token = _webhook()
    _stream(call_session_id, token)
    published = _envelopes(redis_url)
    _assert_hot_path_events(published, call_session_id)

    extractor = ExtractorConsumer(bus=EventBus(redis_url), consumer_name="mvp-extractor")
    _drain(extractor.poll, "extractor")
    after_extract = _envelopes(redis_url)
    proposed = [
        item
        for item in after_extract
        if item.event_type is EventType.INTELLIGENCE_FINDING_PROPOSED
    ]
    assert len(proposed) == 1
    assert proposed[0].payload["kind"] == FindingKind.CALLBACK_NUMBER.value
    assert proposed[0].payload["value"] == CALLBACK_NUMBER
    assert proposed[0].call_session_id == call_session_id

    projector = ProjectorConsumer(bus=EventBus(redis_url), consumer_name="mvp-projector")
    _drain(projector.poll, "projector")

    listed = api.get("/v1/calls")
    assert listed.status_code == 200
    page = CallListResponse.model_validate(listed.json())
    assert call_session_id in [item.id for item in page.items]

    detail = api.get(f"/v1/calls/{call_session_id}")
    assert detail.status_code == 200
    body = CallDetailResponse.model_validate(detail.json())
    assert body.session.id == call_session_id
    assert body.session.state is CallState.RINGING
    assert body.session.caller_number_e164 == CALLER_NUMBER
    assert body.session.called_number_e164 == CALLED_NUMBER
    assert len(body.transcript) == 1
    segment = body.transcript[0]
    assert segment.record_layer == "observation"
    assert segment.text == MOCK_STT_FINAL_TEXT
    assert CALLBACK_NUMBER in segment.text
    assert segment.provider == "mock-stt"
    assert segment.source.value == "stt"
    callbacks = [item for item in body.findings if item.kind is FindingKind.CALLBACK_NUMBER]
    assert len(callbacks) == 1
    finding = callbacks[0]
    assert finding.record_layer == "interpretation"
    assert finding.value == CALLBACK_NUMBER
    assert finding.raw_quote == CALLBACK_NUMBER
    assert finding.status is FindingStatus.PROPOSED
    assert finding.transcript_segment_ids == [segment.id]
    assert finding.confidence == 1.0
    assert str(finding.id) == proposed[0].payload["finding_id"]
    assert [turn.speaker for turn in body.turns] == [Speaker.CALLER, Speaker.HONEYPOT]
    assert body.turns[0].text == MOCK_STT_FINAL_TEXT
    assert body.turns[0].strategy_id is None
    assert body.turns[1].text == FIXED_REPLY
    assert body.turns[1].strategy_id == FIXED_STRATEGY_ID
    assert body.attributions == []

    _answer()
    _drain(projector.poll, "projector-answered")

    live = api.get("/v1/calls")
    assert live.status_code == 200
    live_page = CallListResponse.model_validate(live.json())
    listed_row = next(item for item in live_page.items if item.id == call_session_id)
    assert listed_row.state is CallState.IN_PROGRESS

    answered = api.get(f"/v1/calls/{call_session_id}")
    assert answered.status_code == 200
    answered_body = CallDetailResponse.model_validate(answered.json())
    assert answered_body.session.id == call_session_id
    assert answered_body.session.state is CallState.IN_PROGRESS
    assert answered_body.session.answered_at is not None


def _voice() -> dict[str, object]:
    response = api.post(
        "/v1/telephony/voice/mock",
        json={
            "provider_call_id": PROVIDER_CALL_ID,
            "from_e164": CALLER_NUMBER,
            "to_e164": CALLED_NUMBER,
            "timestamp": "2026-09-26T00:00:00Z",
        },
        headers={MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    return body


def _webhook() -> tuple[UUID, str]:
    first = _voice()
    second = _voice()
    call_session_id = UUID(str(first["call_session_id"]))
    assert call_session_id == UUID(str(second["call_session_id"]))
    assert call_session_id == uuid5(SWITCHBOARD_ID_NAMESPACE, f"mock:{PROVIDER_CALL_ID}")
    instruction = first["instruction"]
    assert isinstance(instruction, dict)
    assert instruction["action"] == "connect_stream"
    token = instruction["stream_token"]
    assert isinstance(token, str) and token != ""
    return call_session_id, token


def _answer() -> None:
    """Bell status route: answered. The projector does not apply this transition."""

    response = api.post(
        "/v1/telephony/status/mock",
        json={
            "provider_call_id": PROVIDER_CALL_ID,
            "status": CallState.IN_PROGRESS.value,
            "timestamp": "2026-09-26T00:00:30Z",
        },
        headers={MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE},
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True}


def _stream(call_session_id: UUID, token: str) -> None:
    reply = MockTts().synthesize(FIXED_REPLY)
    with media.websocket_connect(f"/v1/streams?token={token}") as socket:
        ready = socket.receive_json()
        assert ready["event"] == "ready"
        socket.send_json(
            {
                "event": "start",
                "stream_id": "mvp-stream-1",
                "call_session_id": str(call_session_id),
                "media_format": {"encoding": "audio/pcmu", "sample_rate_hz": 8000, "channels": 1},
            }
        )
        socket.send_bytes(MOCK_STT_FIXTURE_FRAME)
        socket.send_json({"event": "stop"})
        messages: list[dict[str, object]] = []
        code: int | None = None
        while code is None:
            try:
                message = socket.receive_json()
            except WebSocketDisconnect as exc:
                code = exc.code
                break
            assert isinstance(message, dict)
            messages.append(message)
    assert code == 1000
    assert len(messages) == 1
    assert messages[0]["event"] == "media"
    payload = messages[0]["payload_b64"]
    assert isinstance(payload, str)
    assert base64.b64decode(payload) == reply


def _envelopes(redis_url: str) -> list[EventEnvelope]:
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        entries = client.xrange(STREAM_KEY)
    finally:
        client.close()
    return [EventEnvelope.model_validate_json(fields["envelope"]) for _stream_id, fields in entries]


def _assert_hot_path_events(envelopes: list[EventEnvelope], call_session_id: UUID) -> None:
    types = [item.event_type for item in envelopes]
    assert types == [
        EventType.TELEPHONY_CALL_RECEIVED,
        EventType.SPEECH_SEGMENT_FINAL,
        EventType.CONVERSATION_TURN_RECORDED,
        EventType.CONVERSATION_RESPONSE_SELECTED,
        EventType.CONVERSATION_TURN_RECORDED,
    ]
    assert all(item.call_session_id == call_session_id for item in envelopes)
    speech = envelopes[1]
    assert speech.payload["text"] == MOCK_STT_FINAL_TEXT
    assert speech.payload["is_final"] is True
    assert CALLBACK_NUMBER in str(speech.payload["text"])
    caller, selected, honeypot = envelopes[2], envelopes[3], envelopes[4]
    assert caller.payload["speaker"] == Speaker.CALLER.value
    assert caller.payload["text"] == MOCK_STT_FINAL_TEXT
    assert selected.payload["text"] == FIXED_REPLY
    assert selected.payload["strategy_id"] == FIXED_STRATEGY_ID
    assert honeypot.payload["speaker"] == Speaker.HONEYPOT.value
    assert honeypot.payload["text"] == FIXED_REPLY
    assert honeypot.payload["turn_id"] == selected.payload["turn_id"]


def _drain(poll: Callable[..., ProjectorPoll | ExtractorPoll], label: str) -> None:
    for _ in range(8):
        result = poll(count=32)
        assert result.retry is False, label
        if result.acknowledged == 0:
            return
    raise AssertionError(f"{label} did not drain")
