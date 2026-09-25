"""Carrier boundary. Provider payloads do not pass this package unchanged."""

from typing import Mapping, Protocol

MOCK_SIGNATURE_HEADER = "x-switchboard-mock-signature"
MOCK_SIGNATURE_VALUE = "dev"


class SignatureVerifier(Protocol):
    def verify(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        """Return True when the webhook signature is acceptable."""


class MockSignatureVerifier:
    """Dev stand-in. SENTINEL replaces this with a fail-closed provider verifier."""

    def verify(self, raw_body: bytes, headers: Mapping[str, str]) -> bool:
        del raw_body
        return headers.get(MOCK_SIGNATURE_HEADER) == MOCK_SIGNATURE_VALUE
