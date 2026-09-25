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
    """Campaigns that share an identifier, script tokens, or a short time window."""
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
        if _shares_indicator(features, member):
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


def _shares_indicator(left: CallFeatures, right: CallFeatures) -> bool:
    return bool(
        left.claimed_organizations & right.claimed_organizations
        or left.callback_identifiers & right.callback_identifiers
        or left.domains & right.domains
        or left.email_patterns & right.email_patterns
        or left.repeated_phrases & right.repeated_phrases
    )
