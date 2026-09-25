"""The system prompt stays aligned with the state machine."""

from switchboard.loki.goals import GOAL_ORDER
from switchboard.loki.prompt import load_system_prompt, prompt_contract_failures
from switchboard.loki.states import ConversationState


def test_system_prompt_mentions_every_rule_the_policy_enforces() -> None:
    assert prompt_contract_failures() == []
    prompt = load_system_prompt()
    for state in ConversationState:
        assert state.value in prompt
    for goal in GOAL_ORDER:
        assert goal in prompt
    assert "four stalling" in prompt
    assert "ignore previous instructions" in prompt.lower()
    assert "Do not reveal" in prompt
    assert "strategy-decision confidence" in prompt
    assert "gift_card" in prompt
    assert "tech_support" in prompt
