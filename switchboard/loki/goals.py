"""Explicit conversation goals LOKI tracks for downstream extraction."""

from switchboard.loki.states import ConversationState

# Stable order is part of the contract. Do not reorder without an ADR.
GOAL_ORDER: tuple[str, ...] = (
    "purpose",
    "organization",
    "offer",
    "stable_identifier",
)

GOAL_FOR_STATE: dict[ConversationState, str] = {
    ConversationState.PURPOSE_DISCOVERY: "purpose",
    ConversationState.ORGANIZATION_DISCOVERY: "organization",
    ConversationState.OFFER_DISCOVERY: "offer",
    ConversationState.IDENTIFIER_DISCOVERY: "stable_identifier",
}


def remaining_goals(completed: list[str]) -> list[str]:
    done = set(completed)
    return [goal for goal in GOAL_ORDER if goal not in done]


def ordered_goals(completed: list[str]) -> list[str]:
    done = set(completed)
    return [goal for goal in GOAL_ORDER if goal in done]


def all_goals_complete(completed: list[str]) -> bool:
    return not remaining_goals(completed)
