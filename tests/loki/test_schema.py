"""The canonical turn object rejects drift."""

import pytest
from pydantic import ValidationError

from switchboard.loki.schema import TurnOutput
from switchboard.loki.states import ConversationState


def _turn(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "response_text": "What's this call about?",
        "state": ConversationState.PURPOSE_DISCOVERY,
        "state_transition": "OPENING -> PURPOSE_DISCOVERY",
        "goals_completed": [],
        "goals_remaining": ["purpose", "organization", "offer", "stable_identifier"],
        "confidence": 0.55,
        "reason": "Caller greeted without a request.",
    }
    payload.update(overrides)
    return payload


def test_round_trip_keeps_field_order() -> None:
    turn = TurnOutput.model_validate(_turn())
    assert list(turn.model_dump(mode="json")) == [
        "response_text",
        "state",
        "state_transition",
        "goals_completed",
        "goals_remaining",
        "confidence",
        "reason",
    ]


def test_extra_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(note="operator aside"))


def test_goals_must_follow_canonical_order() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(
            _turn(
                goals_completed=["offer", "purpose"],
                goals_remaining=["organization", "stable_identifier"],
            )
        )


def test_unknown_transition_state_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(state_transition="OPENING -> LISTENING"))


def test_confidence_must_be_a_unit_interval() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(confidence=1.2))
