"""Twilio adapter: signatures, TwiML, media frames, and REST side effects."""

import asyncio
import base64
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from switchboard.config import Settings
from switchboard.errors import ProviderConfigurationError, ProviderError
from switchboard.main import create_app
from switchboard.media.audio import fixed_response_frame
from switchboard.models.session import CallSession, CallState
from switchboard.providers.twilio import TwilioTelephonyProvider
from switchboard.security.signatures import twilio_signature

TOKEN = "twilio-token"
URL = "http://test/webhooks/twilio/voice"
PARAMS = {"CallSid": "CA123", "From": "+15551110000", "To": "+15552220000", "CallStatus": "ringing"}


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail = False

    async def update_call(
        self,
        *,
        account_sid: str,
        auth_token: str,
        call_sid: str,
        data: dict[str, str],
    ) -> None:
        if self.fail:
            raise ProviderError("twilio call update failed: HTTPStatusError")
        self.calls.append(
            {
                "account_sid": account_sid,
                "auth_token": auth_token,
                "call_sid": call_sid,
                "data": data,
            }
        )


def test_signed_voice_webhook_returns_stream_twiml() -> None:
    settings = Settings(
        public_base_url="http://test",
        media_ws_base_url="ws://test",
        mock_webhook_secret="test-secret",
        twilio_account_sid="AC123",
        twilio_auth_token=TOKEN,
        log_level="WARNING",
    )
    transport = RecordingTransport()
    client = TestClient(create_app(settings, twilio_transport=transport))
    body = urlencode(PARAMS).encode()
    signature = twilio_signature(auth_token=TOKEN, url=URL, params=PARAMS)
    response = client.post(
        "/webhooks/twilio/voice",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded", "X-Twilio-Signature": signature},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/xml")
    assert '<Stream url="ws://test/media/stream/twilio"/>' in response.text
    call_id = _only_call_id(client)
    with client.websocket_connect("/media/stream/twilio") as socket:
        socket.send_json({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        socket.send_json(
            {
                "event": "start",
                "streamSid": "MZ123",
                "start": {
                    "streamSid": "MZ123",
                    "callSid": "CA123",
                    "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
                },
            }
        )
        socket.send_json(
            {
                "event": "media",
                "streamSid": "MZ123",
                "media": {
                    "track": "inbound",
                    "chunk": "1",
                    "timestamp": "0",
                    "payload": base64.b64encode(b"\x7f" * 8).decode("ascii"),
                },
            }
        )
        reply = socket.receive_json()
        assert reply["event"] == "media"
        assert reply["streamSid"] == "MZ123"
        assert base64.b64decode(reply["media"]["payload"]) == fixed_response_frame()
        socket.send_json({"event": "stop", "streamSid": "MZ123", "stop": {"callSid": "CA123"}})
    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["provider"] == "twilio"
    assert detail["session"]["provider_metadata"]["CallStatus"] == "ringing"
    assert "call.media.started" in [event["name"] for event in detail["events"]]
    assert detail["session"]["state"] == "completed"
    assert detail["events"][-1]["name"] == "call.completed"
    assert transport.calls[-1]["data"] == {"Status": "completed"}


def test_twilio_start_rejects_pcm16() -> None:
    settings = Settings(
        public_base_url="http://test",
        media_ws_base_url="ws://test",
        twilio_auth_token=TOKEN,
        log_level="WARNING",
    )
    client = TestClient(create_app(settings))
    body = urlencode(PARAMS).encode()
    signature = twilio_signature(auth_token=TOKEN, url=URL, params=PARAMS)
    created = client.post(
        "/webhooks/twilio/voice",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded", "X-Twilio-Signature": signature},
    )
    assert created.status_code == 200
    call_id = _only_call_id(client)
    with client.websocket_connect("/media/stream/twilio") as socket:
        socket.send_json(
            {
                "event": "start",
                "streamSid": "MZ999",
                "start": {
                    "streamSid": "MZ999",
                    "callSid": "CA123",
                    "mediaFormat": {"encoding": "audio/pcm", "sampleRate": 16000, "channels": 1},
                },
            }
        )
    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["state"] == "connected"
    assert "call.media.started" not in [event["name"] for event in detail["events"]]


def test_bad_twilio_signature_is_rejected() -> None:
    settings = Settings(
        public_base_url="http://test",
        media_ws_base_url="ws://test",
        twilio_auth_token=TOKEN,
        log_level="WARNING",
    )
    client = TestClient(create_app(settings))
    body = urlencode(PARAMS).encode()
    response = client.post(
        "/webhooks/twilio/voice",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded", "X-Twilio-Signature": "not-the-signature"},
    )
    assert response.status_code == 401


def test_forward_and_terminate_use_the_transport() -> None:
    transport = RecordingTransport()
    provider = TwilioTelephonyProvider(
        Settings(twilio_account_sid="AC123", twilio_auth_token=TOKEN, log_level="WARNING"),
        transport=transport,
    )
    session = _session()

    asyncio.run(provider.forward_call(session, "+15558675309"))
    asyncio.run(provider.terminate_call(session, "operator"))
    assert transport.calls[0]["data"] == {
        "Twiml": '<?xml version="1.0" encoding="UTF-8"?><Response><Dial>+15558675309</Dial></Response>'
    }
    assert transport.calls[1]["data"] == {"Status": "completed"}
    assert transport.calls[0]["call_sid"] == "CA123"


def test_forward_without_credentials_does_not_pretend_to_dial() -> None:
    transport = RecordingTransport()
    provider = TwilioTelephonyProvider(Settings(log_level="WARNING"), transport=transport)
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.forward_call(_session(), "+15558675309"))
    assert transport.calls == []


def test_terminate_without_credentials_is_local_only() -> None:
    transport = RecordingTransport()
    provider = TwilioTelephonyProvider(Settings(log_level="WARNING"), transport=transport)

    asyncio.run(provider.terminate_call(_session(), "caller_hangup"))
    assert transport.calls == []


def test_forward_transport_failure_marks_the_call_failed() -> None:
    transport = RecordingTransport()
    transport.fail = True
    settings = Settings(
        public_base_url="http://test",
        media_ws_base_url="ws://test",
        twilio_account_sid="AC123",
        twilio_auth_token=TOKEN,
        log_level="WARNING",
    )
    client = TestClient(create_app(settings, twilio_transport=transport))
    body = urlencode(PARAMS).encode()
    signature = twilio_signature(auth_token=TOKEN, url=URL, params=PARAMS)
    created = client.post(
        "/webhooks/twilio/voice",
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded", "X-Twilio-Signature": signature},
    )
    assert created.status_code == 200
    call_id = _only_call_id(client)
    response = client.post(f"/calls/{call_id}/forward", json={"destination": "+15558675309"})
    assert response.status_code == 502
    detail = client.get(f"/calls/{call_id}").json()
    assert detail["session"]["state"] == "failed"
    assert detail["events"][-1]["name"] == "call.failed"


def _session() -> CallSession:
    now = datetime.now(timezone.utc)
    return CallSession(
        call_id="sb_test",
        provider="twilio",
        provider_call_id="CA123",
        from_number="+15551110000",
        to_number="+15552220000",
        direction="inbound",
        state=CallState.CONNECTED,
        created_at=now,
        updated_at=now,
    )


def _only_call_id(client: TestClient) -> str:
    records = [record for record in client.app.state.container.telemetry.snapshot() if record.name == "call.received"]
    assert len(records) == 1
    assert records[0].call_id is not None
    return records[0].call_id
