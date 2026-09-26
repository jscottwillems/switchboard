"""Campaign read routes. Rows come from `packages/repositories` via `open_read_models`.

Every route on this router requires the operator token (`require_operator`).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from switchboard_repositories import InvalidCursor
from switchboard_schemas.api import CampaignListResponse
from switchboard_schemas.attribution import Campaign

from switchboard_api.deps import open_read_models
from switchboard_api.errors import ApiError
from switchboard_api.operator_auth import require_operator

router = APIRouter(
    prefix="/v1/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(require_operator)],
)

_CAMPAIGN_NOT_FOUND = "No campaign exists with that id."
_INVALID_REQUEST = "Request failed validation."


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> CampaignListResponse:
    """Newest `created_at` first. `limit` defaults to 50 and cannot exceed 200."""

    try:
        with open_read_models() as models:
            page, next_cursor = models.campaigns().list_page(limit=limit, cursor=cursor)
    except InvalidCursor:
        raise ApiError(422, "invalid_request", _INVALID_REQUEST) from None
    return CampaignListResponse(items=page, next_cursor=next_cursor)


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: UUID) -> Campaign:
    with open_read_models() as models:
        campaign = models.campaigns().get(campaign_id)
    if campaign is None:
        raise ApiError(404, "campaign_not_found", _CAMPAIGN_NOT_FOUND)
    return campaign
