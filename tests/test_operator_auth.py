"""Operator token gates call and campaign reads and nothing else."""

import os
from uuid import uuid4

from fastapi.testclient import TestClient

from switchboard_api.main import app
from switchboard_api.operator_auth import OPERATOR_TOKEN_HEADER
from switchboard_api.settings import get_settings

from tests.operator_support import OPERATOR_TOKEN

client = TestClient(app)

_MISSING = "6c0d5a2e-0000-5000-8000-000000000099"
_READS = (
    "/v1/calls",
    f"/v1/calls/{_MISSING}",
    f"/v1/calls/{_MISSING}/transcript",
    f"/v1/calls/{_MISSING}/findings",
    f"/v1/calls/{_MISSING}/attributions",
    "/v1/campaigns",
    f"/v1/campaigns/{_MISSING}",
)
_VOICE = {
    "provider_call_id": "operator-auth",
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}


def _env(**values: str) -> None:
    for key, value in values.items():
        os.environ[key] = value
    get_settings.cache_clear()


def test_missing_and_wrong_tokens_are_401_and_the_matching_token_reads() -> None:
    _env(
        SWITCHBOARD_ENV="dev",
        SWITCHBOARD_DEV_OPERATOR_BYPASS="0",
        SWITCHBOARD_OPERATOR_TOKEN=OPERATOR_TOKEN,
    )
    for path in _READS:
        missing = client.get(path)
        assert missing.status_code == 401
        assert missing.json()["error"] == "operator_unauthorized"
        assert missing.json()["message"] == "Operator token was rejected."
        assert OPERATOR_TOKEN not in missing.text

        wrong = client.get(path, headers={OPERATOR_TOKEN_HEADER: "not-the-token"})
        assert wrong.status_code == 401
        assert wrong.json()["error"] == "operator_unauthorized"
        assert "not-the-token" not in wrong.text

    unauthenticated_limit = client.get("/v1/calls", params={"limit": 0})
    assert unauthenticated_limit.status_code == 401
    assert unauthenticated_limit.json()["error"] == "operator_unauthorized"

    listing = client.get("/v1/calls", headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN})
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "next_cursor": None}
    campaigns = client.get("/v1/campaigns", headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN})
    assert campaigns.status_code == 200
    assert campaigns.json() == {"items": [], "next_cursor": None}

    unknown_call = client.get(
        f"/v1/calls/{uuid4()}",
        headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN},
    )
    assert unknown_call.status_code == 404
    assert unknown_call.json()["error"] == "call_not_found"
    unknown_campaign = client.get(
        f"/v1/campaigns/{uuid4()}",
        headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN},
    )
    assert unknown_campaign.status_code == 404
    assert unknown_campaign.json()["error"] == "campaign_not_found"


def test_bearer_is_accepted_when_the_operator_header_is_absent() -> None:
    _env(
        SWITCHBOARD_ENV="dev",
        SWITCHBOARD_DEV_OPERATOR_BYPASS="0",
        SWITCHBOARD_OPERATOR_TOKEN=OPERATOR_TOKEN,
    )
    response = client.get("/v1/calls", headers={"Authorization": f"Bearer {OPERATOR_TOKEN}"})
    assert response.status_code == 200
    rejected = client.get("/v1/campaigns", headers={"Authorization": "Bearer nope"})
    assert rejected.status_code == 401
    assert rejected.json()["error"] == "operator_unauthorized"
    basic = client.get("/v1/calls", headers={"Authorization": f"Basic {OPERATOR_TOKEN}"})
    assert basic.status_code == 401
    header_wins = client.get(
        "/v1/calls",
        headers={
            OPERATOR_TOKEN_HEADER: "not-the-token",
            "Authorization": f"Bearer {OPERATOR_TOKEN}",
        },
    )
    assert header_wins.status_code == 401
    assert header_wins.json()["error"] == "operator_unauthorized"


def test_non_dev_without_a_configured_token_fails_closed() -> None:
    _env(
        SWITCHBOARD_ENV="production",
        SWITCHBOARD_DEV_OPERATOR_BYPASS="1",
        SWITCHBOARD_OPERATOR_TOKEN="",
    )
    for path in ("/v1/calls", "/v1/campaigns"):
        response = client.get(path, headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN})
        assert response.status_code == 401
        assert response.json()["error"] == "operator_unauthorized"

    _env(SWITCHBOARD_OPERATOR_TOKEN="   ")
    blank = client.get("/v1/calls", headers={OPERATOR_TOKEN_HEADER: "   "})
    assert blank.status_code == 401
    assert blank.json()["error"] == "operator_unauthorized"


def test_dev_bypass_is_ignored_outside_dev_and_honored_only_in_dev() -> None:
    _env(
        SWITCHBOARD_ENV="staging",
        SWITCHBOARD_DEV_OPERATOR_BYPASS="1",
        SWITCHBOARD_OPERATOR_TOKEN=OPERATOR_TOKEN,
    )
    denied = client.get("/v1/calls")
    assert denied.status_code == 401
    assert denied.json()["error"] == "operator_unauthorized"

    _env(SWITCHBOARD_ENV="dev")
    allowed = client.get("/v1/calls")
    assert allowed.status_code == 200
    campaigns = client.get("/v1/campaigns")
    assert campaigns.status_code == 200


def test_health_webhooks_and_internal_routes_do_not_use_the_operator_token() -> None:
    _env(
        SWITCHBOARD_ENV="production",
        SWITCHBOARD_DEV_OPERATOR_BYPASS="0",
        SWITCHBOARD_OPERATOR_TOKEN="",
    )
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    webhook = client.post("/v1/telephony/voice/mock", json=_VOICE)
    assert webhook.status_code == 401
    assert webhook.json()["error"] == "webhook_unauthorized"

    internal = client.post(
        "/v1/internal/stream-tokens",
        json={"call_session_id": str(uuid4())},
        headers={OPERATOR_TOKEN_HEADER: "does-not-matter"},
    )
    assert internal.status_code == 401
    assert internal.json()["error"] == "unauthorized"
