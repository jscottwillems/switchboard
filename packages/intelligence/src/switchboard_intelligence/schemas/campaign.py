"""Watson-owned campaign link. Sherlock does not fill this record in v1."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssociationReason(BaseModel):
    """One reason Watson linked a call to a campaign.

    `field` is a Sherlock observation kind or inference kind. `value` is the
    Sherlock value that supported the link.
    """

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    value: str = Field(min_length=1)


class CampaignAssociation(BaseModel):
    """Watson's correlation decision for one call and one campaign.

    Sherlock's extractor does not compute `association_score` or
    `feature_scores`. Reasons cite Sherlock field names and values.
    `feature_scores` is a sparse map of those field names to Watson's
    weights. It is not a dense embedding.
    """

    model_config = ConfigDict(extra="forbid")

    record_type: Literal["campaign_association"] = "campaign_association"
    call_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    association_score: float = Field(ge=0.0, le=1.0)
    reasons: list[AssociationReason] = Field(min_length=1)
    feature_scores: dict[str, float] = Field(default_factory=dict)
