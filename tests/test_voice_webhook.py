import os
from uuid import uuid4, uuid5

import pytest
import redis
from fastapi.testclient import TestClient

from switchboard_api.main import app
from switchboard_api.memory_tokens import token_count
from switchboard_api.routes import telephony as telephony_routes
from switchboard_api.settings import get_settings
from switchboard_api.telephony_events import EVENT_STREAM_KEY
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import EventType, Producer
from switchboard_schemas.events import EventEnvelope, validate_event
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE, VoiceInstructionRenderer
from tests.postgres_support import DEV_OPERATOR_ID, execute, query_all

client = TestClient(app)

VOICE = {
    "provider_call_id": "demo-1",
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}
SIGNED = {MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE}


@pytest.fixture(autouse=True)
def _clear_event_stream() -> None:
    stream = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=1, socket_timeout=1)
    try:
        stream.delete(EVENT_STREAM_KEY)
    finally:
        stream.close()


def test_enrolled_call_is_stored_and_idempotent() -> None:
    first = _post_voice(VOICE)
    second_body = {**VOICE, "from_e164": "+15557654321", "provider_call_id": "demo-1"}
    second = _post_voice(second_body)
    expected = str(uuid5(SWITCHBOARD_ID_NAMESPACE, "mock:demo-1"))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["call_session_id"] == expected
    assert second.json()["call_session_id"] == expected
    assert "?" not in first.json()["instruction"]["stream_url"]
    assert first.json()["instruction"]["stream_token"] not in first.json()["instruction"]["stream_url"]
    assert first.json()["instruction"]["stream_token"] != second.json()["instruction"]["stream_token"]
    assert token_count() == 2

    sessions = query_all("SELECT * FROM obs.call_session")
    assert len(sessions) == 1
    session = sessions[0]
    assert str(session["id"]) == expected
    assert str(session["operator_number_id"]) == DEV_OPERATOR_ID
    assert session["external_call_id"] == "demo-1"
    assert session["carrier"] == "mock"
    assert session["caller_number_e164"] == "+15551212000"
    assert session["called_number_e164"] == "+15550001001"
    assert session["state"] == "ringing"
    assert session["answered_at"] is None
    assert session["ended_at"] is None

    receipts = query_all(
        "SELECT call_session_id, provider, event_type, signature_valid, payload FROM obs.webhook_receipt ORDER BY received_at"
    )
    assert len(receipts) == 2
    assert all(str(row["call_session_id"]) == expected for row in receipts)
    assert all(row["provider"] == "mock" and row["event_type"] == "voice" for row in receipts)
    assert all(row["signature_valid"] is True for row in receipts)
    assert receipts[1]["payload"]["from_e164"] == "+15557654321"

    envelopes = _published_envelopes()
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope.event_type is EventType.TELEPHONY_CALL_RECEIVED
    assert envelope.event_type.value == "telephony.call.received"
    assert envelope.producer is Producer.API
    assert envelope.event_version == 1
    assert str(envelope.call_session_id) == expected
    assert envelope.payload["external_call_id"] == "demo-1"
    assert envelope.payload["carrier"] == "mock"
    assert envelope.payload["caller_number_e164"] == "+15551212000"
    assert envelope.payload["called_number_e164"] == "+15550001001"


def test_unknown_and_retired_numbers_store_a_receipt_without_a_token() -> None:
    retired_id = uuid4()
    retired = "+15550001999"
    execute("DELETE FROM ops.operator_number WHERE e164 = %s", (retired,))
    execute(
        """
        INSERT INTO ops.operator_number (id, e164, label, status)
        VALUES (%s, %s, %s, 'retired')
        """,
        (retired_id, retired, "retired-test"),
    )
    try:
        unknown = _post_voice({**VOICE, "to_e164": "+15558880000", "provider_call_id": "unknown-1"})
        retired_response = _post_voice({**VOICE, "to_e164": retired, "provider_call_id": "retired-1"})
        for response in (unknown, retired_response):
            assert response.status_code == 403
            assert response.json()["error"] == "number_not_enrolled"
            assert "stream_token" not in response.json()
            assert "+1555" not in response.json()["message"]
        assert token_count() == 0
        assert query_all("SELECT id FROM obs.call_session") == []
        receipts = query_all(
            "SELECT call_session_id, signature_valid FROM obs.webhook_receipt ORDER BY received_at"
        )
        assert len(receipts) == 2
        assert all(row["call_session_id"] is None for row in receipts)
        assert all(row["signature_valid"] is True for row in receipts)
        assert _published_envelopes() == []
    finally:
        execute(
            """
            DELETE FROM obs.webhook_receipt
            WHERE call_session_id IN (
                SELECT id FROM obs.call_session WHERE operator_number_id = %s
            )
            """,
            (retired_id,),
        )
        execute("DELETE FROM obs.call_session WHERE operator_number_id = %s", (retired_id,))
        execute("DELETE FROM ops.operator_number WHERE id = %s", (retired_id,))


def test_rejected_signature_is_stored_without_a_session() -> None:
    response = client.post("/v1/telephony/voice/mock", json=VOICE)
    assert response.status_code == 401
    assert response.json()["error"] == "webhook_unauthorized"
    assert token_count() == 0
    assert query_all("SELECT id FROM obs.call_session") == []
    receipts = query_all("SELECT call_session_id, signature_valid FROM obs.webhook_receipt")
    assert len(receipts) == 1
    assert receipts[0]["call_session_id"] is None
    assert receipts[0]["signature_valid"] is False
    assert _published_envelopes() == []


def test_dev_bypass_records_that_the_verifier_did_not_run() -> None:
    os.environ["SWITCHBOARD_ENV"] = "dev"
    os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "1"
    get_settings.cache_clear()
    response = client.post("/v1/telephony/voice/mock", json=VOICE)
    assert response.status_code == 200
    receipts = query_all("SELECT signature_valid, call_session_id FROM obs.webhook_receipt")
    assert len(receipts) == 1
    assert receipts[0]["signature_valid"] is None
    assert receipts[0]["call_session_id"] is not None


def test_redis_outage_still_stores_the_session_and_issues_a_token() -> None:
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"
    get_settings.cache_clear()
    response = _post_voice(VOICE)
    assert response.status_code == 200
    assert token_count() == 1
    sessions = query_all("SELECT id, state FROM obs.call_session")
    assert len(sessions) == 1
    assert sessions[0]["state"] == "ringing"
    assert response.json()["call_session_id"] == str(sessions[0]["id"])


def test_voice_route_renders_connect_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    renderer = telephony_routes._renderer
    original = renderer.render

    def record(action, *, stream_url=None, stream_token=None):
        calls.append(action)
        return original(action, stream_url=stream_url, stream_token=stream_token)

    monkeypatch.setattr(renderer, "render", record)
    response = _post_voice(VOICE)
    assert response.status_code == 200
    assert calls == ["connect_stream"]
    assert response.json()["instruction"]["action"] == "connect_stream"


def _post_voice(body: dict[str, str]):
    return client.post("/v1/telephony/voice/mock", json=body, headers=SIGNED)


def _published_envelopes() -> list[EventEnvelope]:
    stream = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=1, socket_timeout=1)
    try:
        rows = stream.xrange(EVENT_STREAM_KEY)
    finally:
        stream.close()
    envelopes: list[EventEnvelope] = []
    for _entry_id, fields in rows:
        envelope = EventEnvelope.model_validate_json(fields[b"envelope"])
        validate_event(envelope)
        envelopes.append(envelope)
    return envelopes
