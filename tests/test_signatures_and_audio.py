"""Locked signature vectors and the fixed reply frame."""

import base64
import hashlib
import hmac
import json
from pathlib import Path

from switchboard.media.audio import FRAME_SAMPLES, fixed_response_frame
from switchboard.media.mulaw import linear_to_mulaw
from switchboard.security.signatures import sign_mock_body, twilio_signature

MOCK_BODY = b'{"ping":"pong"}'
MOCK_SECRET = "test-secret"
MOCK_HEX = "39773dd05dd0bf0e0ef64320dc5e6fd9f7631400cd8768a82c87e33362446ae0"

TWILIO_TOKEN = "twilio-token"
TWILIO_URL = "https://example.com/webhooks/twilio/voice"
TWILIO_PARAMS = {"CallSid": "CA123", "From": "+15551110000", "To": "+15552220000"}
TWILIO_SIGNATURE = "YBtSTR1xrLSLvhJxMt1I00sUJBQ="


def test_mock_signature_vector() -> None:
    expected = hmac.new(MOCK_SECRET.encode(), MOCK_BODY, hashlib.sha256).hexdigest()
    assert expected == MOCK_HEX
    assert sign_mock_body(MOCK_SECRET, MOCK_BODY) == f"sha256={MOCK_HEX}"


def test_twilio_signature_vector() -> None:
    signed = TWILIO_URL + "".join(key + TWILIO_PARAMS[key] for key in sorted(TWILIO_PARAMS))
    digest = hmac.new(TWILIO_TOKEN.encode(), signed.encode(), hashlib.sha1).digest()
    assert base64.b64encode(digest).decode() == TWILIO_SIGNATURE
    assert twilio_signature(auth_token=TWILIO_TOKEN, url=TWILIO_URL, params=TWILIO_PARAMS) == TWILIO_SIGNATURE


def test_mulaw_silence_and_tone_frame() -> None:
    assert linear_to_mulaw(0) == 0xFF
    frame = fixed_response_frame()
    assert len(frame) == FRAME_SAMPLES
    assert frame == fixed_response_frame()
    assert frame != bytes([0xFF]) * FRAME_SAMPLES


def test_fixed_reply_fixture_is_mulaw_8k_mono() -> None:
    document = json.loads(Path("docs/fixtures/audio/fixed_response_mulaw.json").read_text())
    assert document["encoding"] == "audio/x-mulaw"
    assert document["sample_rate"] == 8000
    assert document["channels"] == 1
    assert document["byte_length"] == FRAME_SAMPLES
    assert base64.b64decode(document["payload_b64"]) == fixed_response_frame()
