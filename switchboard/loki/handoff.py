"""Interfaces LOKI expects from agents that are not in this repository."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from switchboard.loki.goals import remaining_goals
from switchboard.loki.policy import (
    ConversationSession,
    LokiPolicy,
    RawCallerUtterance,
    RecordedHint,
)
from switchboard.loki.schema import TurnOutput


class SherlockHandoff(BaseModel):
    """Provisional LOKI → Sherlock payload.

    Goal ids are Sherlock Observation kind names. `elicited_hints` are
    unverified breadcrumbs only. Sherlock owns typed Observation,
    Inference, Attribution, transcript grounding, and extraction confidence.
    LOKI turn confidence is strategy-decision confidence and is not copied here.
    """

    model_config = ConfigDict(extra="forbid")

    contract: str = "loki.sherlock.handoff.v1"
    session_id: str
    goals_completed: list[str]
    goals_remaining: list[str]
    raw_observations: list[RawCallerUtterance]
    elicited_hints: list[RecordedHint]
    note: str = (
        "raw_observations are verbatim caller turns. "
        "elicited_hints are unverified breadcrumbs, not Observations."
    )


class TurnCompletedEvent(BaseModel):
    """Event Echo, Watson, and Sentinel can subscribe to later."""

    model_config = ConfigDict(extra="forbid")

    event: str = "loki.turn.completed"
    session_id: str
    turn_index: int
    raw_caller_utterance: str
    turn: TurnOutput


class TurnResponder(Protocol):
    """Something that can play the honeypot side of a transcript.

    `LokiPolicy` is the offline implementation. A live model adapter would
    implement the same method and still return `TurnOutput`.
    """

    def respond(self, session: ConversationSession, caller_text: str) -> TurnOutput:
        """Return the next structured honeypot turn."""
        ...


class SherlockSink(Protocol):
    """Where a future orchestrator would send extracted-goal context.

    Not called by the offline harness.
    """

    def submit(self, handoff: SherlockHandoff) -> None:
        """Accept one session handoff."""
        ...


def build_sherlock_handoff(session: ConversationSession) -> SherlockHandoff:
    return SherlockHandoff(
        session_id=session.session_id,
        goals_completed=list(session.goals_completed),
        goals_remaining=remaining_goals(session.goals_completed),
        raw_observations=list(session.raw_observations),
        elicited_hints=list(session.elicited_hints),
    )


def build_turn_event(
    session: ConversationSession,
    turn_index: int,
    caller_text: str,
    turn: TurnOutput,
) -> TurnCompletedEvent:
    return TurnCompletedEvent(
        session_id=session.session_id,
        turn_index=turn_index,
        raw_caller_utterance=caller_text,
        turn=turn,
    )


class PolicyResponder:
    """Adapter that exposes `LokiPolicy.step` as `TurnResponder`."""

    def __init__(self, policy: LokiPolicy | None = None) -> None:
        self._policy = policy or LokiPolicy()

    def respond(self, session: ConversationSession, caller_text: str) -> TurnOutput:
        return self._policy.step(session, caller_text)
