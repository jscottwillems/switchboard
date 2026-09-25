from uuid import UUID

from fastapi import APIRouter, Query

from switchboard_schemas.api import (
    AttributionListResponse,
    CallDetailResponse,
    CallListResponse,
    FindingListResponse,
    TranscriptListResponse,
)

from switchboard_api.errors import ApiError

router = APIRouter(prefix="/v1/calls", tags=["calls"])


@router.get("", response_model=CallListResponse)
def list_calls(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> CallListResponse:
    del limit, cursor
    return CallListResponse(items=[], next_cursor=None)


@router.get("/{call_session_id}/transcript", response_model=TranscriptListResponse)
def get_transcript(call_session_id: UUID) -> TranscriptListResponse:
    del call_session_id
    raise ApiError(404, "call_not_found", "No call session exists with that id.")


@router.get("/{call_session_id}/findings", response_model=FindingListResponse)
def get_findings(call_session_id: UUID) -> FindingListResponse:
    del call_session_id
    raise ApiError(404, "call_not_found", "No call session exists with that id.")


@router.get("/{call_session_id}/attributions", response_model=AttributionListResponse)
def get_attributions(call_session_id: UUID) -> AttributionListResponse:
    del call_session_id
    raise ApiError(404, "call_not_found", "No call session exists with that id.")


@router.get("/{call_session_id}", response_model=CallDetailResponse)
def get_call(call_session_id: UUID) -> CallDetailResponse:
    del call_session_id
    raise ApiError(404, "call_not_found", "No call session exists with that id.")
