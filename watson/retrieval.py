"""High-recall candidate retrieval. The decision step still applies the threshold."""

from watson.config import ScoringConfig
from watson.models import CallFeatures
from watson.store import CampaignProfile, CampaignStore
from watson.textutil import interval_gap_seconds, jaccard


def retrieve_candidates(
    features: CallFeatures,
    store: CampaignStore,
    config: ScoringConfig | None = None,
) -> list[CampaignProfile]:
    """Campaigns that share a finding value, script tokens, or a short time window."""
    active = config or ScoringConfig()
    return [
        campaign
        for campaign in store.campaigns()
        if _is_candidate(features, campaign, active)
    ]


def _is_candidate(
    features: CallFeatures,
    campaign: CampaignProfile,
    config: ScoringConfig,
) -> bool:
    for member in campaign.members:
        if _shares_finding(features, member):
            return True
        if jaccard(features.opening_tokens, member.opening_tokens) >= config.opening_retrieval_jaccard:
            return True
        if (
            jaccard(features.transcript_tokens, member.transcript_tokens)
            >= config.transcript_retrieval_jaccard
        ):
            return True
        gap = interval_gap_seconds(
            features.started_at.timestamp(),
            features.ended_at.timestamp(),
            member.started_at.timestamp(),
            member.ended_at.timestamp(),
        )
        if gap <= config.timing_retrieval_seconds:
            return True
    return False


def _shares_finding(left: CallFeatures, right: CallFeatures) -> bool:
    return bool(
        left.callback_number & right.callback_number
        or left.organization_name & right.organization_name
        or left.url & right.url
        or left.payment_method & right.payment_method
        or left.other & right.other
        or left.pretext & right.pretext
        or left.person_name & right.person_name
    )
