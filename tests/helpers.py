"""Small call and finding builders shared by tests."""

from datetime import datetime, timezone
from uuid import uuid5

from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding

from watson.models import CompletedCall


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


def make_finding(
    call_id: str,
    kind: FindingKind,
    value: str,
    *,
    confidence: float = 1.0,
    raw_quote: str | None = None,
    status: FindingStatus = FindingStatus.PROPOSED,
    extractor: str = "e164",
    extractor_version: str = "0.1.0",
) -> IntelligenceFinding:
    quote = value if raw_quote is None else raw_quote
    return IntelligenceFinding(
        id=uuid5(SWITCHBOARD_ID_NAMESPACE, f"intelligence_finding|{call_id}|{kind.value}|{value}"),
        call_session_id=uuid5(SWITCHBOARD_ID_NAMESPACE, f"call_session|{call_id}"),
        kind=kind,
        value=value,
        raw_quote=quote,
        transcript_segment_ids=[
            uuid5(SWITCHBOARD_ID_NAMESPACE, f"segment|{call_id}|{kind.value}|{value}")
        ],
        extractor=extractor,
        extractor_version=extractor_version,
        confidence=confidence,
        status=status,
        created_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
    )
