from uuid import UUID

from fastapi import APIRouter, Query

from switchboard_schemas.api import CampaignListResponse
from switchboard_schemas.attribution import Campaign

from switchboard_api.errors import ApiError

router = APIRouter(prefix="/v1/campaigns", tags=["campaigns"])


@router.get("", response_model=CampaignListResponse)
def list_campaigns(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> CampaignListResponse:
    del limit, cursor
    return CampaignListResponse(items=[], next_cursor=None)


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: UUID) -> Campaign:
    del campaign_id
    raise ApiError(404, "campaign_not_found", "No campaign exists with that id.")
