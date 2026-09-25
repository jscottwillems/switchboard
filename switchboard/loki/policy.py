"""Deterministic conversation policy.

This is the offline reference implementation of the LOKI state machine.
A future model adapter must return the same `TurnOutput` shape. The system
prompt describes that contract for a model; this module executes it without one.
"""

from typing import assert_never

from pydantic import BaseModel, ConfigDict, Field

from switchboard.loki.goals import (
    IDENTIFIER_GATE,
    OFFER_GATE,
    ORG_GATE,
    dialogue_gates_open,
    missing_stage,
    ordered_goals,
    remaining_goals,
)
from switchboard.loki.observe import CallerObservation, observe
from switchboard.loki.safety import safe_slot_text
from switchboard.loki.schema import ElicitedHint, TurnOutput
from switchboard.loki.states import ConversationState

MAX_CONSECUTIVE_RECOVERY = 2
MAX_STALL_TURNS = 4

_STALL_LINES = (
    "Give me a second, I need a pen. Can you repeat that number slowly?",
    "I'm walking to the other room. What's the callback or website again?",
    "Sorry, someone was at the door. What name is on the account?",
    "The line cut out for a second. Can you repeat the company name?",
)


class RecordedHint(BaseModel):
    """Breadcrumb tied to a raw turn. No confidence and no character offsets."""

    model_config = ConfigDict(extra="forbid")

    turn_index: int
    kind: str
    breadcrumb: str


class RawCallerUtterance(BaseModel):
    """Verbatim caller audio transcript. No derived fields."""

    model_config = ConfigDict(extra="forbid")

    turn_index: int
    speaker: str = "caller"
    text: str


class ConversationSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: ConversationState = ConversationState.OPENING
    goals_completed: list[str] = Field(default_factory=list)
    clarification_streak: int = 0
    recovery_streak: int = 0
    stall_turns: int = 0
    opening_empty_turns: int = 0
    raw_observations: list[RawCallerUtterance] = Field(default_factory=list)
    elicited_hints: list[RecordedHint] = Field(default_factory=list)
    turns: list[TurnOutput] = Field(default_factory=list)


class LokiPolicy:
    """Step a session forward one caller utterance at a time."""

    def start_session(self, session_id: str) -> ConversationSession:
        return ConversationSession(session_id=session_id)

    def step(self, session: ConversationSession, caller_text: str) -> TurnOutput:
        if session.state is ConversationState.TERMINATION:
            return self._already_ended(session, caller_text)

        observation = observe(caller_text)
        goals_before = list(session.goals_completed)
        goals_after = _apply_goals(goals_before, observation)
        new_state = _select_state(session, observation, goals_after)
        response = _render(new_state, observation, session)
        hints = _turn_hints(observation)
        turn = TurnOutput(
            response_text=response,
            state=new_state,
            state_transition=f"{session.state.value} -> {new_state.value}",
            goals_completed=ordered_goals(goals_after),
            goals_remaining=remaining_goals(goals_after),
            confidence=_confidence(observation, new_state, goals_before, goals_after),
            reason=_reason(observation, session.state, new_state, goals_before, goals_after),
            elicited_hints=hints,
        )
        turn_index = len(session.turns)
        session.raw_observations.append(
            RawCallerUtterance(turn_index=turn_index, text=caller_text)
        )
        session.elicited_hints.extend(_recorded(turn_index, hints))
        session.turns.append(turn)
        session.goals_completed = ordered_goals(goals_after)
        session.state = new_state
        _update_counters(session, new_state)
        return turn

    def _already_ended(self, session: ConversationSession, caller_text: str) -> TurnOutput:
        turn = TurnOutput(
            response_text="Goodbye.",
            state=ConversationState.TERMINATION,
            state_transition="TERMINATION -> TERMINATION",
            goals_completed=ordered_goals(session.goals_completed),
            goals_remaining=remaining_goals(session.goals_completed),
            confidence=0.9,
            reason="The call is already over.",
            elicited_hints=[],
        )
        turn_index = len(session.turns)
        session.raw_observations.append(
            RawCallerUtterance(turn_index=turn_index, text=caller_text)
        )
        session.turns.append(turn)
        return turn


def _apply_goals(completed: list[str], observation: CallerObservation) -> list[str]:
    done = list(completed)
    for kind, _breadcrumb in observation.hints:
        if kind not in done:
            done.append(kind)
    return done


def _select_state(
    session: ConversationSession,
    observation: CallerObservation,
    goals_after: list[str],
) -> ConversationState:
    if observation.goodbye:
        return ConversationState.TERMINATION
    if session.state is ConversationState.OPENING and observation.empty:
        if session.opening_empty_turns >= 1:
            return ConversationState.CLARIFICATION
        return ConversationState.OPENING
    if observation.adversarial:
        if session.recovery_streak >= MAX_CONSECUTIVE_RECOVERY:
            return ConversationState.TERMINATION
        return ConversationState.RECOVERY
    if dialogue_gates_open(goals_after):
        if session.stall_turns >= MAX_STALL_TURNS:
            return ConversationState.TERMINATION
        return ConversationState.STALLING
    if observation.unclear:
        if session.clarification_streak >= 1:
            return ConversationState.RECOVERY
        return ConversationState.CLARIFICATION
    return _next_discovery(goals_after)


def _next_discovery(goals_after: list[str]) -> ConversationState:
    stage = missing_stage(goals_after)
    match stage:
        case "pretext":
            return ConversationState.PURPOSE_DISCOVERY
        case "organization":
            return ConversationState.ORGANIZATION_DISCOVERY
        case "offer":
            return ConversationState.OFFER_DISCOVERY
        case "identifier":
            return ConversationState.IDENTIFIER_DISCOVERY
        case _:
            assert_never(stage)


def _update_counters(session: ConversationSession, new_state: ConversationState) -> None:
    if new_state is ConversationState.CLARIFICATION:
        session.clarification_streak += 1
        session.recovery_streak = 0
        return
    if new_state is ConversationState.RECOVERY:
        session.recovery_streak += 1
        session.clarification_streak = 0
        return
    if new_state is ConversationState.STALLING:
        session.stall_turns += 1
        session.clarification_streak = 0
        session.recovery_streak = 0
        return
    if new_state is ConversationState.OPENING:
        session.opening_empty_turns += 1
        return
    session.clarification_streak = 0
    session.recovery_streak = 0


def _render(
    state: ConversationState,
    observation: CallerObservation,
    session: ConversationSession,
) -> str:
    line = _line_for(state, observation, session)
    if (
        session.state is ConversationState.OPENING
        and state not in {ConversationState.OPENING, ConversationState.TERMINATION}
        and not line.startswith(("Hi", "Hello"))
    ):
        return f"Hi. {line}"
    return line


def _line_for(
    state: ConversationState,
    observation: CallerObservation,
    session: ConversationSession,
) -> str:
    org = safe_slot_text(observation.organization)
    match state:
        case ConversationState.OPENING:
            return "Hello?"
        case ConversationState.PURPOSE_DISCOVERY:
            return "What's this call about?"
        case ConversationState.ORGANIZATION_DISCOVERY:
            spoken = observation.spoken_purpose()
            if spoken:
                return f"About {spoken}. Who are you with?"
            return "Who are you with?"
        case ConversationState.OFFER_DISCOVERY:
            if observation.pii_request:
                return "I'm not sharing personal codes. What do you need me to do?"
            if org:
                spoken_org = org[0].upper() + org[1:]
                return f"{spoken_org}. What do you need me to do?"
            return "What do you need me to do?"
        case ConversationState.IDENTIFIER_DISCOVERY:
            if observation.pii_request:
                return (
                    "I'm not reading personal numbers or codes out loud. "
                    "What's the case number and a callback?"
                )
            return "What's the case number and a number I can call you back on?"
        case ConversationState.CLARIFICATION:
            return _clarification(session.goals_completed)
        case ConversationState.STALLING:
            index = min(session.stall_turns, len(_STALL_LINES) - 1)
            return _STALL_LINES[index]
        case ConversationState.RECOVERY:
            if observation.pii_request:
                return "I'm not giving out personal codes. Who are you with?"
            if session.recovery_streak >= 1:
                return "Let's stay on the call itself. Who do you work for?"
            return "I don't know what you mean by that. Who is this, and why are you calling?"
        case ConversationState.TERMINATION:
            if observation.goodbye:
                return "Alright. Goodbye."
            if observation.adversarial:
                return "I can't help with that. Goodbye."
            return "I've got what I need for now. Goodbye."
        case _:
            assert_never(state)


def _clarification(completed: list[str]) -> str:
    stage = missing_stage(completed)
    match stage:
        case "pretext":
            return "Sorry, I didn't catch that. What's this call about?"
        case "organization":
            return "Sorry, I didn't catch that. Who are you with?"
        case "offer":
            return "Sorry, I missed that. What do you need me to do?"
        case "identifier":
            return "Sorry, I missed that. What's the case number?"
        case _:
            assert_never(stage)


def _confidence(
    observation: CallerObservation,
    new_state: ConversationState,
    goals_before: list[str],
    goals_after: list[str],
) -> float:
    if new_state is ConversationState.TERMINATION and observation.goodbye:
        base = 0.86
    elif new_state is ConversationState.TERMINATION:
        base = 0.7
    elif new_state is ConversationState.CLARIFICATION:
        base = 0.34
    elif new_state is ConversationState.RECOVERY:
        base = 0.42
    elif new_state is ConversationState.OPENING:
        base = 0.5
    else:
        base = 0.55
        kinds = {kind for kind, _breadcrumb in observation.hints}
        if "pretext_category" in kinds:
            base += 0.1
        if kinds.intersection(ORG_GATE):
            base += 0.1
        if kinds.intersection(OFFER_GATE):
            base += 0.08
        if kinds.intersection(IDENTIFIER_GATE):
            base += 0.12
    if len(goals_after) > len(goals_before) and new_state not in {
        ConversationState.CLARIFICATION,
        ConversationState.RECOVERY,
    }:
        base += 0.05
    return round(min(0.97, base), 2)


def _reason(
    observation: CallerObservation,
    previous: ConversationState,
    new_state: ConversationState,
    goals_before: list[str],
    goals_after: list[str],
) -> str:
    parts: list[str] = []
    if observation.empty:
        parts.append("No caller speech yet.")
    if observation.greeting_only:
        parts.append("Caller greeted without a request.")
    if observation.hints:
        noted = ", ".join(kind for kind, _breadcrumb in observation.hints)
        parts.append(f"Unverified breadcrumbs for {noted}.")
    if observation.adversarial:
        parts.append("Adversarial probe; response refuses disclosure.")
    if observation.pii_request:
        parts.append("Caller requested personal secrets; response refuses.")
    if observation.unclear:
        parts.append("Utterance had no usable evidence.")
    if observation.goodbye:
        parts.append("Caller closed the call.")
    if new_state is ConversationState.STALLING:
        parts.append("Dialogue gates are open; stalling for more kinds.")
    if new_state is ConversationState.TERMINATION and not observation.goodbye:
        parts.append("Ending because the stall or recovery budget is exhausted.")
    newly = [goal for goal in goals_after if goal not in goals_before]
    if newly:
        parts.append("Newly completed goals: " + ", ".join(newly) + ".")
    parts.append(f"Transition {previous.value} -> {new_state.value}.")
    return " ".join(parts)


def _turn_hints(observation: CallerObservation) -> list[ElicitedHint]:
    return [ElicitedHint(kind=kind, breadcrumb=breadcrumb) for kind, breadcrumb in observation.hints]


def _recorded(turn_index: int, hints: list[ElicitedHint]) -> list[RecordedHint]:
    return [
        RecordedHint(turn_index=turn_index, kind=hint.kind, breadcrumb=hint.breadcrumb)
        for hint in hints
    ]
