"""Mock webhook credential samples. The verifier is switchboard_telephony.MockSignatureVerifier."""

from __future__ import annotations

import pytest

from sentinel.fixtures.webhook_attacks import (
    MOCK_SIGNATURE_HEADER as FIXTURE_HEADER,
    MOCK_SIGNATURE_VALUE as FIXTURE_VALUE,
    WEBHOOK_ATTACK_FIXTURES,
    WEBHOOK_REPLAY_SAMPLE,
    WebhookFixture,
)
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE, MockSignatureVerifier


def test_fixture_header_matches_the_telephony_package() -> None:
    assert FIXTURE_HEADER == MOCK_SIGNATURE_HEADER
    assert FIXTURE_VALUE == MOCK_SIGNATURE_VALUE


@pytest.mark.parametrize("fixture", WEBHOOK_ATTACK_FIXTURES, ids=lambda item: item.id)
def test_webhook_attack_fixtures(fixture: WebhookFixture) -> None:
    verifier = MockSignatureVerifier()
    assert verifier.verify(fixture.body, dict(fixture.headers)) is fixture.expect_ok


def test_static_mock_credential_verifies_twice() -> None:
    """A repeated mock header is not a replay. Dedupe is on provider_call_id."""
    verifier = MockSignatureVerifier()
    headers = dict(WEBHOOK_REPLAY_SAMPLE.headers)
    assert verifier.verify(WEBHOOK_REPLAY_SAMPLE.body, headers)
    assert verifier.verify(WEBHOOK_REPLAY_SAMPLE.body, headers)
