"""Call read routes. Rows come from `packages/repositories` via `open_read_models`."""

from uuid import UUID

from fastapi import APIRouter, Query

from switchboard_repositories import InvalidCursor
from switchboard_repositories.ports import ReadModels
from switchboard_schemas.api import (
    AttributionListResponse,
    CallDetailResponse,
    CallListResponse,
    CallSessionSummary,
    FindingListResponse,
    TranscriptListResponse,
)
from switchboard_schemas.observations import CallSession

from switchboard_api.deps import open_read_models
from switchboard_api.errors import ApiError

router = APIRouter(prefix="/v1/calls", tags=["calls"])

_CALL_NOT_FOUND = "No call session exists with that id."
_INVALID_REQUEST = "Request failed validation."


def _summary(session: CallSession) -> CallSessionSummary:
    return CallSessionSummary(
        id=session.id,
        state=session.state,
        caller_number_e164=session.caller_number_e164,
        called_number_e164=session.called_number_e164,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


def _require_session(models: ReadModels, call_session_id: UUID) -> CallSession:
    session = models.call_sessions().get(call_session_id)
    if session is None:
        raise ApiError(404, "call_not_found", _CALL_NOT_FOUND)
    return session


@router.get("", response_model=CallListResponse)
def list_calls(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> CallListResponse:
    """Newest `started_at` first. `limit` defaults to 50 and cannot exceed 200."""

    try:
        with open_read_models() as models:
            page, next_cursor = models.call_sessions().list_page(limit=limit, cursor=cursor)
    except InvalidCursor:
        raise ApiError(422, "invalid_request", _INVALID_REQUEST) from None
    return CallListResponse(
        items=[_summary(session) for session in page],
        next_cursor=next_cursor,
    )


@router.get("/{call_session_id}/transcript", response_model=TranscriptListResponse)
def get_transcript(call_session_id: UUID) -> TranscriptListResponse:
    with open_read_models() as models:
        _require_session(models, call_session_id)
        segments = models.transcripts().list_for_session(call_session_id)
    return TranscriptListResponse(call_session_id=call_session_id, segments=segments)


@router.get("/{call_session_id}/findings", response_model=FindingListResponse)
def get_findings(call_session_id: UUID) -> FindingListResponse:
    with open_read_models() as models:
        _require_session(models, call_session_id)
        findings = models.findings().list_for_session(call_session_id)
    return FindingListResponse(call_session_id=call_session_id, findings=findings)


@router.get("/{call_session_id}/attributions", response_model=AttributionListResponse)
def get_attributions(call_session_id: UUID) -> AttributionListResponse:
    with open_read_models() as models:
        _require_session(models, call_session_id)
        attributions = models.attributions().list_for_session(call_session_id)
    return AttributionListResponse(call_session_id=call_session_id, attributions=attributions)


@router.get("/{call_session_id}", response_model=CallDetailResponse)
def get_call(call_session_id: UUID) -> CallDetailResponse:
    with open_read_models() as models:
        session = _require_session(models, call_session_id)
        return CallDetailResponse(
            session=session,
            media_streams=models.media_streams().list_for_session(call_session_id),
            transcript=models.transcripts().list_for_session(call_session_id),
            turns=models.conversation_turns().list_for_session(call_session_id),
            findings=models.findings().list_for_session(call_session_id),
            attributions=models.attributions().list_for_session(call_session_id),
        )
