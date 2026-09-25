"""Small call and observation builders shared by tests."""

from datetime import datetime, timezone

from watson.models import CompletedCall
from watson.sherlock.models import CallIntelligence, Observation, ObservationKind


def make_call(
    call_id: str,
    transcript: str,
    start: str = "2026-04-02T14:00:00",
    end: str = "2026-04-02T14:03:00",
    caller_id: str | None = None,
) -> CompletedCall:
    return CompletedCall(
        call_id=call_id,
        started_at=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        ended_at=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        caller_id=caller_id,
        transcript=transcript,
    )


def make_observation(
    call_id: str,
    kind: ObservationKind,
    value: str,
    *,
    confidence: float = 0.95,
    normalized: str | None = None,
) -> Observation:
    normalized_value = value if normalized is None else normalized
    return Observation(
        observation_id=f"{call_id}:{kind.value}:{normalized_value}",
        call_id=call_id,
        kind=kind,
        value=value,
        normalized_value=normalized_value,
        source="test",
        transcript_segment_id="seg",
        start_timestamp=0.0,
        end_timestamp=1.0,
        char_start=0,
        char_end=len(value),
        confidence=confidence,
    )


def make_intelligence(
    call_id: str,
    observations: list[Observation],
) -> CallIntelligence:
    return CallIntelligence(call_id=call_id, observations=observations, inference=None)
