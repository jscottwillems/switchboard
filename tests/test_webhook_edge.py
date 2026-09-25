"""Signature-before-parse and webhook admission on the API routes."""

from __future__ import annotations

import os
import socket

from fastapi.testclient import TestClient

from sentinel.limits import ResourceLimits
from switchboard_api.main import app
from switchboard_api.settings import get_settings
from switchboard_api.webhook_edge import MAX_WEBHOOK_BODY_BYTES, reset_webhook_edge
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE

client = TestClient(app)

VOICE = {
    "provider_call_id": "demo-edge",
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}
SIGNED = {MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE}


def test_unsigned_garbage_is_rejected_before_schema_errors() -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "webhook_unauthorized"


def test_signed_garbage_is_a_validation_error() -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        content=b"not-json",
        headers={"content-type": "application/json", **SIGNED},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_header_name_case_is_accepted() -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        json=VOICE,
        headers={"X-Switchboard-Mock-Signature": MOCK_SIGNATURE_VALUE},
    )
    assert response.status_code == 200


def test_webhook_rate_limit() -> None:
    reset_webhook_edge(ResourceLimits(max_events_per_minute=2))
    try:
        first = client.post("/v1/telephony/voice/mock", json=VOICE, headers=SIGNED)
        second = client.post("/v1/telephony/voice/mock", json=VOICE, headers=SIGNED)
        third = client.post("/v1/telephony/voice/mock", json=VOICE, headers=SIGNED)
    finally:
        reset_webhook_edge()
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"] == "webhook_rate_limited"


def test_webhook_body_cap(monkeypatch) -> None:
    monkeypatch.setattr("switchboard_api.webhook_edge.MAX_WEBHOOK_BODY_BYTES", 32)
    raw = b'{"provider_call_id":"demo-edge","padding":"' + (b"a" * 80) + b'"}'
    assert len(raw) > 32
    response = client.post(
        "/v1/telephony/voice/mock",
        content=raw,
        headers={"content-type": "application/json", **SIGNED},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "webhook_too_large"
    assert MAX_WEBHOOK_BODY_BYTES == 1_048_576


def test_health_probes_fail_closed_when_ports_refuse() -> None:
    os.environ["SWITCHBOARD_HEALTH_PROBES"] = "1"
    os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@127.0.0.1:1/switchboard"
    os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
    get_settings.cache_clear()
    try:
        response = client.get("/health")
    finally:
        os.environ.pop("SWITCHBOARD_HEALTH_PROBES", None)
        os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@localhost:5432/switchboard"
        os.environ["REDIS_URL"] = "redis://localhost:6379/0"
        get_settings.cache_clear()
    assert response.status_code == 503
    assert response.json()["error"] == "dependencies_unavailable"


def test_health_probes_pass_when_tcp_accepts() -> None:
    with socket.socket() as postgres, socket.socket() as redis:
        postgres.bind(("127.0.0.1", 0))
        redis.bind(("127.0.0.1", 0))
        postgres.listen(1)
        redis.listen(1)
        pg_port = postgres.getsockname()[1]
        redis_port = redis.getsockname()[1]
        os.environ["SWITCHBOARD_HEALTH_PROBES"] = "1"
        os.environ["DATABASE_URL"] = f"postgresql://switchboard:switchboard@127.0.0.1:{pg_port}/switchboard"
        os.environ["REDIS_URL"] = f"redis://127.0.0.1:{redis_port}/0"
        get_settings.cache_clear()
        try:
            response = client.get("/health")
        finally:
            os.environ.pop("SWITCHBOARD_HEALTH_PROBES", None)
            os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@localhost:5432/switchboard"
            os.environ["REDIS_URL"] = "redis://localhost:6379/0"
            get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
