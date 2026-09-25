"""Pluggable webhook authenticators.

SENTINEL owns production hardening. This module is the verification boundary:
routes call a Verifier and do not implement vendor signature math themselves.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from switchboard.errors import WebhookVerificationError
from switchboard.security.signatures import parse_form_body, signatures_match, sign_mock_body, twilio_signature


class WebhookVerifier(ABC):
    """Accept or reject a webhook before any session is created."""

    name: str

    @abstractmethod
    def verify(self, *, body: bytes, headers: Mapping[str, str], url: str) -> None:
        """Raise WebhookVerificationError when the payload is not authentic."""


class MockWebhookVerifier(WebhookVerifier):
    """Accepts HMAC-SHA256 signed test payloads.

    Header: X-Switchboard-Signature: sha256=<hex digest of the raw body>
    """

    name = "mock"

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def verify(self, *, body: bytes, headers: Mapping[str, str], url: str) -> None:
        del url  # The mock signature covers the raw body only.
        if not self._secret:
            raise WebhookVerificationError("mock webhook secret is not configured")
        presented = _header(headers, "x-switchboard-signature")
        if presented is None:
            raise WebhookVerificationError("missing X-Switchboard-Signature")
        expected = sign_mock_body(self._secret, body)
        if not signatures_match(expected, presented.strip()):
            raise WebhookVerificationError("mock webhook signature mismatch")


class TwilioWebhookVerifier(WebhookVerifier):
    """Validates X-Twilio-Signature against the configured public URL.

    ``url`` must be the exact URL configured in the Twilio console, including
    scheme and path. The auth token is required; missing configuration fails
    closed.
    """

    name = "twilio"

    def __init__(self, auth_token: str) -> None:
        self._auth_token = auth_token

    def verify(self, *, body: bytes, headers: Mapping[str, str], url: str) -> None:
        if not self._auth_token:
            raise WebhookVerificationError("twilio auth token is not configured")
        presented = _header(headers, "x-twilio-signature")
        if presented is None:
            raise WebhookVerificationError("missing X-Twilio-Signature")
        params = parse_form_body(body)
        expected = twilio_signature(auth_token=self._auth_token, url=url, params=params)
        if not signatures_match(expected, presented.strip()):
            raise WebhookVerificationError("twilio webhook signature mismatch")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None
