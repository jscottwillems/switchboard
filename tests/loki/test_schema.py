"""The canonical turn object rejects drift."""

import pytest
from pydantic import ValidationError

from switchboard.loki.goals import GOAL_ORDER
from switchboard.loki.schema import ElicitedHint, TurnOutput
from switchboard.loki.states import ConversationState


def _turn(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "response_text": "What's this call about?",
        "state": ConversationState.PURPOSE_DISCOVERY,
        "state_transition": "OPENING -> PURPOSE_DISCOVERY",
        "goals_completed": [],
        "goals_remaining": list(GOAL_ORDER),
        "confidence": 0.55,
        "reason": "Caller greeted without a request.",
        "elicited_hints": [],
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
        "elicited_hints",
    ]


def test_extra_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(note="operator aside"))


def test_goals_must_follow_canonical_order() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(
            _turn(
                goals_completed=["claimed_company", "pretext_category"],
                goals_remaining=[goal for goal in GOAL_ORDER if goal not in {"claimed_company", "pretext_category"}],
            )
        )


def test_hint_rejects_an_extraction_confidence() -> None:
    with pytest.raises(ValidationError):
        ElicitedHint.model_validate(
            {"kind": "pretext_category", "breadcrumb": "tax", "confidence": 0.99}
        )


def test_unknown_transition_state_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(state_transition="OPENING -> LISTENING"))


def test_confidence_must_be_a_unit_interval() -> None:
    with pytest.raises(ValidationError):
        TurnOutput.model_validate(_turn(confidence=1.2))
