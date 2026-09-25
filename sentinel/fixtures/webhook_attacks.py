"""Forgery samples for the skeleton mock webhook credential.

The header is ``X-Switchboard-Mock-Signature: dev``. It is a local stand-in,
not an HMAC. ``MOCK_SIGNATURE_VALUE`` here must stay equal to
``switchboard_telephony.MOCK_SIGNATURE_VALUE``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

MOCK_SIGNATURE_HEADER = "x-switchboard-mock-signature"
MOCK_SIGNATURE_VALUE = "dev"
# Placeholder name kept so existing imports still resolve. This is the mock
# header value, not a signing secret.
TEST_WEBHOOK_SECRET = MOCK_SIGNATURE_VALUE
FIXTURE_BODY = b'{"provider_call_id":"demo-1"}'


@dataclass(frozen=True, slots=True)
class WebhookFixture:
    id: str
    body: bytes
    headers: Mapping[str, str]
    expect_ok: bool
    notes: str = ""


def _headers(value: str | None) -> dict[str, str]:
    if value is None:
        return {}
    return {MOCK_SIGNATURE_HEADER: value}


WEBHOOK_REPLAY_SAMPLE = WebhookFixture(
    id="replay_candidate",
    body=FIXTURE_BODY,
    headers=_headers(MOCK_SIGNATURE_VALUE),
    expect_ok=True,
    notes="The mock credential is static, so a second identical request still verifies. Dedupe belongs on provider_call_id.",
)

WEBHOOK_ATTACK_FIXTURES: tuple[WebhookFixture, ...] = (
    WebhookFixture(
        id="valid_mock",
        body=FIXTURE_BODY,
        headers=_headers(MOCK_SIGNATURE_VALUE),
        expect_ok=True,
    ),
    WebhookFixture(
        id="missing_header",
        body=FIXTURE_BODY,
        headers={},
        expect_ok=False,
    ),
    WebhookFixture(
        id="empty_value",
        body=b"{}",
        headers=_headers(""),
        expect_ok=False,
    ),
    WebhookFixture(
        id="wrong_value",
        body=b"{}",
        headers=_headers("prod"),
        expect_ok=False,
    ),
    WebhookFixture(
        id="forged_sha256_label",
        body=b"{}",
        headers=_headers("sha256=ab"),
        expect_ok=False,
        notes="A body HMAC is not this verifier's credential.",
    ),
    WebhookFixture(
        id="whitespace_value",
        body=b"{}",
        headers=_headers(" dev"),
        expect_ok=False,
    ),
    WebhookFixture(
        id="body_is_not_covered",
        body=b"not-the-same-body",
        headers=_headers(MOCK_SIGNATURE_VALUE),
        expect_ok=True,
        notes="MockSignatureVerifier ignores the body. Authenticity is the header value alone.",
    ),
)
