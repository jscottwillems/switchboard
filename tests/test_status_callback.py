"""Status callbacks update obs.call_session and publish telephony events."""

import os
from datetime import datetime, timezone
from uuid import uuid5

import pytest
import redis
from fastapi.testclient import TestClient

from switchboard_api.main import app
from switchboard_api.settings import get_settings
from switchboard_api.telephony_events import EVENT_STREAM_KEY
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import EventType, Producer
from switchboard_schemas.events import EventEnvelope, validate_event
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE
from tests.postgres_support import query_all

client = TestClient(app)

SIGNED = {MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE}
VOICE = {
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}


@pytest.fixture(autouse=True)
def _clear_event_stream() -> None:
    stream = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=1, socket_timeout=1)
    try:
        stream.delete(EVENT_STREAM_KEY)
        for key in stream.scan_iter("switchboard.events:id:*"):
            stream.delete(key)
    finally:
        stream.close()


def test_completed_status_sets_ended_at_and_publishes_once() -> None:
    _open("done-1")
    first = _post_status(_status("done-1", "completed", "2026-09-25T20:05:00Z", "hangup"))
    second = _post_status(_status("done-1", "completed", "2026-09-25T20:09:00Z", "remote-hangup"))
    assert first.status_code == 200
    assert first.json() == {"accepted": True}
    assert second.status_code == 200
    assert second.json() == {"accepted": True}

    session = _session_row()
    expected = str(uuid5(SWITCHBOARD_ID_NAMESPACE, "mock:done-1"))
    assert str(session["id"]) == expected
    assert session["state"] == "completed"
    assert session["answered_at"] is None
    assert _instant(session["ended_at"]) == _instant(datetime.fromisoformat("2026-09-25T20:05:00+00:00"))
    assert session["end_reason"] == "hangup"

    completed = _of_type(EventType.TELEPHONY_CALL_COMPLETED)
    assert len(completed) == 1
    envelope = completed[0]
    assert envelope.event_type.value == "telephony.call.completed"
    assert envelope.producer is Producer.API
    assert envelope.event_version == 1
    assert str(envelope.call_session_id) == expected
    assert envelope.payload["external_call_id"] == "done-1"
    assert envelope.payload["end_reason"] == "hangup"
    assert _instant(envelope.occurred_at) == _instant(session["ended_at"])

    receipts = query_all(
        """
        SELECT event_type, signature_valid, call_session_id
        FROM obs.webhook_receipt
        WHERE event_type = 'status'
        ORDER BY received_at
        """
    )
    assert len(receipts) == 2
    assert all(row["signature_valid"] is True for row in receipts)
    assert all(str(row["call_session_id"]) == expected for row in receipts)


def test_answered_then_completed_keeps_answered_at() -> None:
    _open("live-1")
    answered = _post_status(_status("live-1", "in_progress", "2026-09-25T20:01:00Z"))
    completed = _post_status(_status("live-1", "completed", "2026-09-25T20:04:00Z", "hangup"))
    assert answered.status_code == 200
    assert completed.status_code == 200
    session = _session_row()
    assert session["state"] == "completed"
    assert _instant(session["answered_at"]) == _instant(datetime.fromisoformat("2026-09-25T20:01:00+00:00"))
    assert _instant(session["ended_at"]) == _instant(datetime.fromisoformat("2026-09-25T20:04:00+00:00"))
    assert session["end_reason"] == "hangup"
    types = [item.event_type for item in _published_envelopes()]
    assert types == [
        EventType.TELEPHONY_CALL_RECEIVED,
        EventType.TELEPHONY_CALL_ANSWERED,
        EventType.TELEPHONY_CALL_COMPLETED,
    ]
    answered_event = _of_type(EventType.TELEPHONY_CALL_ANSWERED)[0]
    assert answered_event.event_type.value == "telephony.call.answered"
    assert answered_event.payload == {"external_call_id": "live-1"}
    assert _instant(answered_event.occurred_at) == _instant(session["answered_at"])


def test_failed_status_sets_ended_at_and_publishes() -> None:
    _open("fail-1")
    assert _post_status(_status("fail-1", "in_progress", "2026-09-25T20:01:00Z")).status_code == 200
    failed = _post_status(_status("fail-1", "failed", "2026-09-25T20:02:00Z", "busy"))
    assert failed.status_code == 200
    assert failed.json() == {"accepted": True}
    session = _session_row()
    assert session["state"] == "failed"
    assert session["answered_at"] is not None
    assert _instant(session["ended_at"]) == _instant(datetime.fromisoformat("2026-09-25T20:02:00+00:00"))
    assert session["end_reason"] == "busy"
    failed_event = _of_type(EventType.TELEPHONY_CALL_FAILED)
    assert len(failed_event) == 1
    assert failed_event[0].event_type.value == "telephony.call.failed"
    assert failed_event[0].producer is Producer.API
    assert failed_event[0].payload == {"external_call_id": "fail-1", "end_reason": "busy"}


def test_failed_without_end_reason_uses_failed() -> None:
    _open("fail-2")
    response = _post_status(_status("fail-2", "failed", "2026-09-25T20:03:00Z"))
    assert response.status_code == 200
    session = _session_row()
    assert session["state"] == "failed"
    assert session["end_reason"] == "failed"
    assert session["ended_at"] is not None
    assert _of_type(EventType.TELEPHONY_CALL_FAILED)[0].payload["end_reason"] == "failed"


def test_ringing_status_does_not_publish_another_telephony_event() -> None:
    _open("ring-1")
    response = _post_status(_status("ring-1", "ringing", "2026-09-25T20:00:30Z"))
    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    session = _session_row()
    assert session["state"] == "ringing"
    assert session["answered_at"] is None
    assert session["ended_at"] is None
    assert [item.event_type for item in _published_envelopes()] == [EventType.TELEPHONY_CALL_RECEIVED]


def test_status_signature_rejection_leaves_the_session_and_publishes_nothing() -> None:
    _open("signed-1")
    response = client.post(
        "/v1/telephony/status/mock",
        json=_status("signed-1", "completed", "2026-09-25T20:05:00Z", "hangup"),
    )
    assert response.status_code == 401
    assert response.json()["error"] == "webhook_unauthorized"
    session = _session_row()
    assert session["state"] == "ringing"
    assert session["ended_at"] is None
    assert [item.event_type for item in _published_envelopes()] == [EventType.TELEPHONY_CALL_RECEIVED]
    rejected = query_all(
        "SELECT signature_valid, call_session_id FROM obs.webhook_receipt WHERE event_type = 'status'"
    )
    assert len(rejected) == 1
    assert rejected[0]["signature_valid"] is False
    assert rejected[0]["call_session_id"] is None


def test_unsigned_status_garbage_is_unauthorized_before_schema_errors() -> None:
    response = client.post(
        "/v1/telephony/status/mock",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "webhook_unauthorized"
    assert query_all("SELECT id FROM obs.webhook_receipt") == []
    assert _published_envelopes() == []


def test_signed_status_garbage_is_a_validation_error_without_a_receipt() -> None:
    response = client.post(
        "/v1/telephony/status/mock",
        content=b"not-json",
        headers={"content-type": "application/json", **SIGNED},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert query_all("SELECT id FROM obs.webhook_receipt") == []


def test_unknown_provider_call_is_not_found() -> None:
    response = _post_status(_status("missing-1", "completed", "2026-09-25T20:05:00Z", "hangup"))
    assert response.status_code == 404
    assert response.json()["error"] == "call_not_found"
    assert query_all("SELECT id FROM obs.call_session") == []
    assert _published_envelopes() == []
    receipts = query_all("SELECT call_session_id, event_type FROM obs.webhook_receipt")
    assert len(receipts) == 1
    assert receipts[0]["event_type"] == "status"
    assert receipts[0]["call_session_id"] is None


def test_backward_status_is_rejected() -> None:
    _open("back-1")
    assert _post_status(_status("back-1", "completed", "2026-09-25T20:05:00Z", "hangup")).status_code == 200
    backward = _post_status(_status("back-1", "in_progress", "2026-09-25T20:06:00Z"))
    assert backward.status_code == 409
    assert backward.json()["error"] == "state_conflict"
    session = _session_row()
    assert session["state"] == "completed"
    assert _instant(session["ended_at"]) == _instant(datetime.fromisoformat("2026-09-25T20:05:00+00:00"))
    assert _of_type(EventType.TELEPHONY_CALL_ANSWERED) == []
    assert len(_of_type(EventType.TELEPHONY_CALL_COMPLETED)) == 1


def test_redis_outage_still_sets_ended_at() -> None:
    _open("redis-1")
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"
    get_settings.cache_clear()
    response = _post_status(_status("redis-1", "completed", "2026-09-25T20:05:00Z", "hangup"))
    assert response.status_code == 200
    session = _session_row()
    assert session["state"] == "completed"
    assert session["ended_at"] is not None


def _open(provider_call_id: str) -> None:
    response = client.post(
        "/v1/telephony/voice/mock",
        json={**VOICE, "provider_call_id": provider_call_id},
        headers=SIGNED,
    )
    assert response.status_code == 200


def _status(
    provider_call_id: str,
    status: str,
    timestamp: str,
    end_reason: str | None = None,
) -> dict[str, str]:
    body = {
        "provider_call_id": provider_call_id,
        "status": status,
        "timestamp": timestamp,
    }
    if end_reason is not None:
        body["end_reason"] = end_reason
    return body


def _post_status(body: dict[str, str]):
    return client.post("/v1/telephony/status/mock", json=body, headers=SIGNED)


def _session_row() -> dict[str, object]:
    rows = query_all("SELECT id, state, answered_at, ended_at, end_reason FROM obs.call_session")
    assert len(rows) == 1
    return rows[0]


def _instant(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise AssertionError("expected a datetime")
    return value.astimezone(timezone.utc).replace(microsecond=0)


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


def _of_type(event_type: EventType) -> list[EventEnvelope]:
    return [item for item in _published_envelopes() if item.event_type is event_type]
