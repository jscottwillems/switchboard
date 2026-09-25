"""Small call builders shared by tests."""

from datetime import datetime, timezone

from watson.models import CompletedCall


def make_call(
    call_id: str,
    transcript: str,
    start: str = "2026-04-02T14:00:00",
    end: str = "2026-04-02T14:03:00",
    transferred: bool = False,
    ivr_path: list[str] | None = None,
    caller_id: str | None = None,
) -> CompletedCall:
    return CompletedCall(
        call_id=call_id,
        started_at=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        ended_at=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        caller_id=caller_id,
        transcript=transcript,
        transferred=transferred,
        ivr_path=list(ivr_path or []),
    )
