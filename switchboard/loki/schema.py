"""Canonical structured turn output.

`confidence` is strategy-decision confidence only. Sherlock owns extraction
confidence. `elicited_hints` are unverified breadcrumbs, not Observations.
Only `response_text` may be spoken.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from switchboard.loki.goals import GOAL_ORDER
from switchboard.loki.states import ConversationState

CANONICAL_TURN_FIELDS: tuple[str, ...] = (
    "response_text",
    "state",
    "state_transition",
    "goals_completed",
    "goals_remaining",
    "confidence",
    "reason",
    "elicited_hints",
)


class ElicitedHint(BaseModel):
    """Unverified breadcrumb. Not a Sherlock Observation."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    breadcrumb: str = Field(min_length=1)

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in GOAL_ORDER:
            raise ValueError(f"unknown hint kind: {value}")
        return value


class TurnOutput(BaseModel):
    """One honeypot turn. Extra keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    response_text: str = Field(min_length=1)
    state: ConversationState
    state_transition: str
    goals_completed: list[str]
    goals_remaining: list[str]
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Strategy-decision confidence. Not an extraction confidence.",
    )
    reason: str = Field(min_length=1)
    elicited_hints: list[ElicitedHint] = Field(default_factory=list)

    @field_validator("goals_completed", "goals_remaining")
    @classmethod
    def _known_goals(cls, value: list[str]) -> list[str]:
        unknown = [goal for goal in value if goal not in GOAL_ORDER]
        if unknown:
            raise ValueError(f"unknown goals: {unknown}")
        return value

    @field_validator("state_transition")
    @classmethod
    def _transition_shape(cls, value: str) -> str:
        parts = value.split(" -> ")
        if len(parts) != 2:
            raise ValueError("state_transition must look like 'FROM -> TO'")
        for part in parts:
            if part not in ConversationState.__members__:
                raise ValueError(f"unknown state in transition: {part}")
        return value

    @model_validator(mode="after")
    def _transition_lands_on_state(self) -> Self:
        destination = self.state_transition.split(" -> ")[1]
        if destination != self.state.value:
            raise ValueError("state_transition destination must equal state")
        overlap = set(self.goals_completed) & set(self.goals_remaining)
        if overlap:
            raise ValueError(f"goals both complete and remaining: {sorted(overlap)}")
        ordered_complete = [goal for goal in GOAL_ORDER if goal in self.goals_completed]
        ordered_remaining = [goal for goal in GOAL_ORDER if goal in self.goals_remaining]
        if self.goals_completed != ordered_complete:
            raise ValueError("goals_completed must follow canonical goal order")
        if self.goals_remaining != ordered_remaining:
            raise ValueError("goals_remaining must follow canonical goal order")
        covered = set(self.goals_completed) | set(self.goals_remaining)
        if covered != set(GOAL_ORDER):
            raise ValueError("goals_completed and goals_remaining must partition the goal list")
        return self

    def canonical_dict(self) -> dict[str, object]:
        dumped = self.model_dump(mode="json")
        return {key: dumped[key] for key in CANONICAL_TURN_FIELDS}
