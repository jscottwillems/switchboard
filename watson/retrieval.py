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
    """Campaigns that share an anchor, a script signal, or a short time window."""
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
    left_companies = left.claimed_company_normalized | left.calling_from
    right_companies = right.claimed_company_normalized | right.calling_from
    return bool(
        _phone_numbers(left) & _phone_numbers(right)
        or left.case_id & right.case_id
        or left.domain_registrable & right.domain_registrable
        or _email_registrable(left) & _email_registrable(right)
        or left_companies & right_companies
        or left.script_phrase_normalized & right.script_phrase_normalized
        or _same_optional(left.opening_script_fingerprint, right.opening_script_fingerprint)
        or _same_optional(left.pretext_category_canonical, right.pretext_category_canonical)
    )


def _phone_numbers(features: CallFeatures) -> set[str]:
    return {number for number, _source in features.phone_e164}


def _email_registrable(features: CallFeatures) -> set[str]:
    return {registrable for _local, _domain, registrable in features.email_split if registrable}


def _same_optional(left: str | None, right: str | None) -> bool:
    return bool(left) and left == right
