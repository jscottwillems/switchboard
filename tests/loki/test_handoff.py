"""LOKI's outbound contracts stay split between raw text and derived slots."""

from switchboard.loki.handoff import (
    PolicyResponder,
    build_sherlock_handoff,
    build_turn_event,
)
from switchboard.loki.policy import LokiPolicy


def test_sherlock_handoff_does_not_mix_raw_text_with_derived_slots() -> None:
    policy = LokiPolicy()
    session = policy.start_session("handoff-1")
    caller = "I'm calling about a serious problem with your taxes."
    turn = policy.step(session, caller)
    handoff = build_sherlock_handoff(session)

    assert handoff.contract == "loki.sherlock.handoff.v1"
    assert handoff.raw_observations[0].text == caller
    assert set(handoff.raw_observations[0].model_dump()) == {"turn_index", "speaker", "text"}
    slot = handoff.slot_observations[0]
    assert slot.purpose == "tax issue"
    assert slot.organization is None
    assert "purpose" in handoff.goals_completed
    assert handoff.goals_remaining[0] == "organization"

    event = build_turn_event(session, 0, caller, turn)
    assert event.event == "loki.turn.completed"
    assert event.raw_caller_utterance == caller
    assert event.turn.response_text == turn.response_text
    assert event.turn.reason != caller


def test_policy_responder_matches_the_reference_policy() -> None:
    direct = LokiPolicy()
    adapted = PolicyResponder()
    left = direct.start_session("left")
    right = direct.start_session("right")
    caller = "This is Dana from Chase Bank calling about a fraudulent charge."
    assert direct.step(left, caller).response_text == adapted.respond(right, caller).response_text
