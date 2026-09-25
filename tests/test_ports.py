from uuid import uuid4

from switchboard_classification import (
    CorrelationInput,
    NullCampaignCorrelator,
    NullFindingExtractor,
)
from switchboard_conversation import FIXED_REPLY, FIXED_STRATEGY_ID, FixedResponseSelector
from switchboard_observability import safe_fields
from switchboard_schemas.hotpath import ResponseRequest
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE, MockSignatureVerifier


def test_mock_verifier_and_redaction() -> None:
    verifier = MockSignatureVerifier()
    assert verifier.verify(b"{}", {MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE})
    assert not verifier.verify(b"{}", {})
    redacted = safe_fields({"route": "voice", "stream_token": "secret", "token": "secret"})
    assert redacted == {"route": "voice"}


def test_fixed_selector_and_null_classifiers() -> None:
    decision = FixedResponseSelector().select(
        ResponseRequest(call_session_id=uuid4(), turn_index=0, latest_caller_text="hello")
    )
    assert decision.text == FIXED_REPLY
    assert decision.strategy_id == FIXED_STRATEGY_ID
    assert decision.confidence == 1.0
    assert NullFindingExtractor().extract([]) == []
    assert NullCampaignCorrelator().propose(CorrelationInput(call_session_id=uuid4())) == []
