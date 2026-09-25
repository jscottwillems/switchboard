"""Webhook → session → media observation → fixed reply → hangup."""

import base64
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from switchboard.media.audio import fixed_response_frame
from switchboard.security.signatures import sign_mock_body

FIXTURE = Path("docs/fixtures/webhooks/mock_inbound.json")


def _post(client: TestClient, path: str, body: bytes, secret: str = "test-secret"):
    return client.post(
        path,
        content=body,
        headers={
            "content-type": "application/json",
            "X-Switchboard-Signature": sign_mock_body(secret, body),
        },
    )


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["slice"] == "bell-telephony"


def test_rejects_missing_and_bad_signatures(client: TestClient) -> None:
    body = b'{"from":"+15551110000","to":"+15552220000"}'
    missing = client.post("/webhooks/mock/voice", content=body, headers={"content-type": "application/json"})
    assert missing.status_code == 401
    forged = client.post(
        "/webhooks/mock/voice",
        content=body,
        headers={"content-type": "application/json", "X-Switchboard-Signature": "sha256=deadbeef"},
    )
    assert forged.status_code == 401
    names = [record.name for record in client.app.state.container.telemetry.snapshot()]
    assert "call.received" not in names


def test_unknown_provider(client: TestClient) -> None:
    body = b"{}"
    response = _post(client, "/webhooks/other/voice", body)
    assert response.status_code == 404


def test_vertical_slice_observes_audio_and_hangs_up(client: TestClient) -> None:
    body = FIXTURE.read_bytes()
    created = _post(client, "/webhooks/mock/voice", body)
    assert created.status_code == 200
    answered = created.json()
    call_id = answered["call_id"]
    assert answered["state"] == "connected"
    assert answered["media_stream_url"].endswith(f"/media/stream/mock?call_id={call_id}")

    inbound = b"\x10\x20\x30\x40"
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": call_id})
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        assert ready["protocol"] == "switchboard.media.v1"
        socket.send_json(
            {
                "type": "media",
                "sequence": 1,
                "timestamp_ms": 20,
                "encoding": "audio/x-mulaw",
                "sample_rate": 8000,
                "payload_b64": base64.b64encode(inbound).decode("ascii"),
            }
        )
        reply = socket.receive_json()
        assert reply["type"] == "media"
        assert reply["source"] == "fixed_response"
        assert reply["encoding"] == "audio/x-mulaw"
        assert reply["sample_rate"] == 8000
        assert reply["channels"] == 1
        assert base64.b64decode(reply["payload_b64"]) == fixed_response_frame()
        socket.send_json({"type": "hangup", "reason": "caller_hangup"})
        assert socket.receive_json()["type"] == "media_ended"
        completed = socket.receive_json()
        assert completed["type"] == "completed"
        assert completed["reason"] == "caller_hangup"

    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["record_type"] == "interpretation"
    assert detail["session"]["state"] == "completed"
    assert detail["session"]["packets_observed"] == 1
    assert detail["session"]["packets_sent"] == 1
    assert [event["name"] for event in detail["events"]] == [
        "call.received",
        "call.connected",
        "call.media.started",
        "call.media.ended",
        "call.completed",
    ]
    observations = detail["observations"]
    assert [item["record_type"] for item in observations] == ["observation", "observation"]
    assert observations[0]["source"] == "webhook"
    assert base64.b64decode(observations[0]["raw_b64"]) == body
    media = observations[1]
    assert media["source"] == "media"
    assert media["sha256"] == hashlib.sha256(inbound).hexdigest()
    assert media["media"]["sequence"] == 1
    assert base64.b64decode(media["raw_b64"]) == inbound

    telemetry = client.app.state.container.telemetry.snapshot()
    names = [record.name for record in telemetry]
    assert "webhook.inbound" in names
    assert "media.packet.observed" in names
    assert "media.packet.sent" in names
    assert "call.completed" in names
    assert all(record.estimated_cost_usd is None for record in telemetry)
    status = client.get(f"/calls/{call_id}/status").json()
    assert status["state"] == "completed"
    assert status["record_type"] == "interpretation"


def test_disconnect_completes_the_call(client: TestClient) -> None:
    created = _post(client, "/webhooks/mock/voice", b'{"from":"+15550001111","to":"+15552220000"}')
    call_id = created.json()["call_id"]
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": call_id})
        assert socket.receive_json()["type"] == "ready"
    detail = client.get(f"/calls/{call_id}").json()
    assert [event["name"] for event in detail["events"]][-2:] == ["call.media.ended", "call.completed"]
    assert detail["events"][-1]["data"]["reason"] == "websocket_disconnect"


def test_stop_then_forward(client: TestClient) -> None:
    created = _post(
        client,
        "/webhooks/mock/voice",
        b'{"from":"+15550002222","to":"+15552220000","provider_call_id":"mock-forward"}',
    )
    call_id = created.json()["call_id"]
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": call_id})
        assert socket.receive_json()["type"] == "ready"
        socket.send_json({"type": "stop"})
        assert socket.receive_json()["type"] == "media_ended"
        forwarded = client.post(f"/calls/{call_id}/forward", json={"destination": "+15558675309"})
        assert forwarded.status_code == 200
        assert forwarded.json()["state"] == "forwarded"
        assert forwarded.json()["forward_destination"] == "+15558675309"
    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["state"] == "completed"
    names = [event["name"] for event in detail["events"]]
    assert names == [
        "call.received",
        "call.connected",
        "call.media.started",
        "call.media.ended",
        "call.forwarded",
        "call.completed",
    ]


def test_status_failed_and_idempotent_terminate(client: TestClient) -> None:
    created = _post(
        client,
        "/webhooks/mock/voice",
        b'{"from":"+15550003333","to":"+15552220000","provider_call_id":"mock-fail"}',
    )
    call_id = created.json()["call_id"]
    status_body = b'{"provider_call_id":"mock-fail","status":"failed","reason":"busy"}'
    failed = _post(client, "/webhooks/mock/status", status_body)
    assert failed.status_code == 200
    assert failed.json()["state"] == "failed"
    names = [event["name"] for event in client.get(f"/calls/{call_id}/events").json()]
    assert names == ["call.received", "call.connected", "call.failed"]

    other = _post(client, "/webhooks/mock/voice", b'{"from":"+15550004444","to":"+15552220000"}')
    other_id = other.json()["call_id"]
    first = client.post(f"/calls/{other_id}/terminate", json={"reason": "operator"})
    second = client.post(f"/calls/{other_id}/terminate", json={"reason": "operator"})
    assert first.status_code == 200
    assert second.status_code == 200
    names = [event["name"] for event in client.get(f"/calls/{other_id}/events").json()]
    assert names == ["call.received", "call.connected", "call.completed"]


def test_duplicate_provider_call_and_bad_destination(client: TestClient) -> None:
    body = b'{"from":"+15550005555","to":"+15552220000","provider_call_id":"same"}'
    assert _post(client, "/webhooks/mock/voice", body).status_code == 200
    assert _post(client, "/webhooks/mock/voice", body).status_code == 400
    created = _post(client, "/webhooks/mock/voice", b'{"from":"+15550006666","to":"+15552220000"}')
    call_id = created.json()["call_id"]
    rejected = client.post(f"/calls/{call_id}/forward", json={"destination": "not-a-number"})
    assert rejected.status_code == 400
    missing = client.post("/calls/sb_missing/terminate", json={"reason": "operator"})
    assert missing.status_code == 404


def test_mock_rejects_pcm16_on_the_wire(client: TestClient) -> None:
    created = _post(client, "/webhooks/mock/voice", b'{"from":"+15550008888","to":"+15552220000"}')
    call_id = created.json()["call_id"]
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": call_id, "encoding": "audio/pcm", "sample_rate": 16000, "channels": 1})
        assert "mulaw" in socket.receive_json()["detail"]
        socket.send_json({"type": "start", "call_id": call_id})
        assert socket.receive_json()["type"] == "ready"
        socket.send_json(
            {
                "type": "media",
                "sequence": 1,
                "encoding": "audio/pcm",
                "sample_rate": 16000,
                "channels": 1,
                "payload_b64": base64.b64encode(b"\x00\x01" * 8).decode("ascii"),
            }
        )
        assert "mulaw" in socket.receive_json()["detail"]
    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["packets_observed"] == 0
    assert detail["session"]["media_encoding"] == "audio/x-mulaw"
    assert detail["session"]["media_sample_rate"] == 8000
    assert detail["session"]["media_channels"] == 1


def test_malformed_media_frame(client: TestClient) -> None:
    created = _post(client, "/webhooks/mock/voice", b'{"from":"+15550007777","to":"+15552220000"}')
    call_id = created.json()["call_id"]
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": "sb_missing"})
        assert socket.receive_json()["type"] == "error"
        socket.send_json({"type": "start", "call_id": call_id})
        assert socket.receive_json()["type"] == "ready"
        socket.send_text("not-json")
        assert socket.receive_json()["type"] == "error"
        socket.send_json({"type": "nope"})
        assert "unsupported" in socket.receive_json()["detail"]


def test_two_calls_do_not_share_observations(client: TestClient) -> None:
    first_audio = b"\x01\x02"
    second_audio = b"\x03\x04\x05"
    first = _run_call(client, "+15551110001", "iso-1", first_audio)
    second = _run_call(client, "+15551110002", "iso-2", second_audio)
    assert first["call_id"] != second["call_id"]
    assert first["sha256"] == hashlib.sha256(first_audio).hexdigest()
    assert second["sha256"] == hashlib.sha256(second_audio).hexdigest()
    assert first["sha256"] != second["sha256"]


def _run_call(client: TestClient, from_number: str, provider_call_id: str, audio: bytes) -> dict[str, str]:
    body = json.dumps({"from": from_number, "to": "+15552220000", "provider_call_id": provider_call_id}).encode()
    created = _post(client, "/webhooks/mock/voice", body)
    call_id = created.json()["call_id"]
    with client.websocket_connect("/media/stream/mock") as socket:
        socket.send_json({"type": "start", "call_id": call_id})
        socket.receive_json()
        socket.send_json({"type": "media", "sequence": 1, "payload_b64": base64.b64encode(audio).decode("ascii")})
        socket.receive_json()
        socket.send_json({"type": "hangup", "reason": "caller_hangup"})
        socket.receive_json()
        socket.receive_json()
    detail = client.get(f"/calls/{call_id}").json()
    media = next(item for item in detail["observations"] if item["source"] == "media")
    return {"call_id": call_id, "sha256": media["sha256"]}
