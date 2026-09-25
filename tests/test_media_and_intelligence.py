from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from switchboard_intelligence.main import app as intelligence_app
from switchboard_intelligence.settings import get_settings as intelligence_settings
from switchboard_media.hotpath import respond_to_audio
from switchboard_media.main import app as media_app
from switchboard_media.main import get_stream_token_validator
from switchboard_schemas.api import ValidateStreamTokenResponse

media = TestClient(media_app)
intelligence = TestClient(intelligence_app)


class _AcceptToken:
    def validate(self, token: str) -> ValidateStreamTokenResponse:
        del token
        return ValidateStreamTokenResponse(valid=True, call_session_id=uuid4())


def test_media_health_and_socket() -> None:
    assert media.get("/health").json()["service"] == "media_gateway"
    with pytest.raises(WebSocketDisconnect) as missing:
        with media.websocket_connect("/v1/streams") as socket:
            socket.receive_json()
    assert missing.value.code == 1008
    media_app.dependency_overrides[get_stream_token_validator] = lambda: _AcceptToken()
    try:
        with media.websocket_connect("/v1/streams?token=dev-token") as socket:
            ready = socket.receive_json()
            assert ready == {"event": "ready", "protocol": "switchboard.media.v1"}
            socket.send_json({"event": "stop"})
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
            assert closed.value.code == 1000
    finally:
        media_app.dependency_overrides.clear()


def test_hot_path_mock_returns_no_audio() -> None:
    assert respond_to_audio(uuid4(), 0, b"\xff\xff") == b""


def test_extract_requires_token_and_returns_no_findings() -> None:
    intelligence_settings.cache_clear()
    denied = intelligence.post(
        "/v1/internal/extract",
        json={"call_session_id": str(uuid4()), "segments": []},
    )
    assert denied.status_code == 401
    assert denied.json()["error"] == "unauthorized"
    allowed = intelligence.post(
        "/v1/internal/extract",
        json={"call_session_id": str(uuid4()), "segments": []},
        headers={"X-Switchboard-Internal-Token": "test-internal-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json() == {"findings": []}
