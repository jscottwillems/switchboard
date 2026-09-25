"""In-memory campaign profiles built as calls are ingested."""

from pydantic import BaseModel, ConfigDict, Field

from watson.models import CallFeatures


class CampaignProfile(BaseModel):
    """A campaign is the set of calls already associated with it."""

    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    members: list[CallFeatures] = Field(min_length=1)


class CampaignStore:
    """Assigns deterministic campaign ids in ingest order."""

    def __init__(self) -> None:
        self._campaigns: dict[str, CampaignProfile] = {}
        self._next_id = 1

    def campaigns(self) -> list[CampaignProfile]:
        return [self._campaigns[key] for key in sorted(self._campaigns)]

    def get(self, campaign_id: str) -> CampaignProfile:
        return self._campaigns[campaign_id]

    def create(self, features: CallFeatures) -> CampaignProfile:
        campaign_id = f"camp-{self._next_id:04d}"
        self._next_id += 1
        profile = CampaignProfile(campaign_id=campaign_id, members=[features])
        self._campaigns[campaign_id] = profile
        return profile

    def attach(self, campaign_id: str, features: CallFeatures) -> CampaignProfile:
        profile = self._campaigns[campaign_id]
        profile.members.append(features)
        return profile
