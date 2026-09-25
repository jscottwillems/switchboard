import os
from uuid import uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from switchboard_api.main import app
from switchboard_api.memory_tokens import reset_token_store
from switchboard_api.settings import get_settings
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE

client = TestClient(app)

VOICE = {
    "provider_call_id": "demo-1",
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_token_store()
    get_settings.cache_clear()
    yield
    os.environ["SWITCHBOARD_ENV"] = "dev"
    os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
    reset_token_store()
    get_settings.cache_clear()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api"
    assert response.json()["status"] == "ok"


def test_webhook_requires_signature() -> None:
    response = client.post("/v1/telephony/voice/mock", json=VOICE)
    assert response.status_code == 401
    assert response.json()["error"] == "webhook_unauthorized"


def test_webhook_ack_is_deterministic_and_token_validates() -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        json=VOICE,
        headers={MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE},
    )
    assert response.status_code == 200
    body = response.json()
    expected = str(uuid5(SWITCHBOARD_ID_NAMESPACE, "mock:demo-1"))
    assert body["call_session_id"] == expected
    assert body["instruction"]["action"] == "connect_stream"
    assert body["instruction"]["stream_url"] == "ws://localhost:8001/v1/streams"
    token = body["instruction"]["stream_token"]
    validated = client.post(
        "/v1/internal/stream-tokens/validate",
        json={"token": token},
        headers={"X-Switchboard-Internal-Token": "test-internal-token"},
    )
    assert validated.status_code == 200
    assert validated.json() == {"valid": True, "call_session_id": expected}


def test_bypass_ignored_outside_dev() -> None:
    os.environ["SWITCHBOARD_ENV"] = "production"
    os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "1"
    get_settings.cache_clear()
    response = client.post("/v1/telephony/voice/mock", json=VOICE)
    assert response.status_code == 401


def test_calls_list_is_empty_and_detail_is_missing() -> None:
    listing = client.get("/v1/calls")
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "next_cursor": None}
    missing = client.get(f"/v1/calls/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"] == "call_not_found"


def test_campaign_list_and_unknown_provider() -> None:
    assert client.get("/v1/campaigns").json()["items"] == []
    rejected = client.post("/v1/telephony/voice/twilio", json=VOICE)
    assert rejected.status_code == 422
    assert rejected.json()["error"] == "invalid_request"


def test_internal_token_required() -> None:
    response = client.post(
        "/v1/internal/stream-tokens",
        json={"call_session_id": str(uuid4())},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_extra_webhook_field_rejected() -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        json={**VOICE, "unexpected": True},
        headers={MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_openapi_lists_contract_paths() -> None:
    paths = client.app.openapi()["paths"]
    assert "/health" in paths
    assert "/v1/calls" in paths
    assert "/v1/calls/{call_session_id}" in paths
    assert "/v1/telephony/voice/{provider}" in paths
    assert "/v1/telephony/status/{provider}" in paths
    assert "/v1/internal/stream-tokens" in paths
    assert "/v1/internal/stream-tokens/validate" in paths
    assert "/v1/campaigns" in paths
