"""Ingest a completed call and emit an explainable campaign association."""

from watson.config import ScoringConfig
from watson.decision import Decision, decide
from watson.events import AssociationEvent, EventEmitter, InMemoryEventEmitter
from watson.features import extract_features
from watson.models import (
    CallFeatures,
    CampaignAssociation,
    CompletedCall,
    DecisionAction,
    ScoreBreakdown,
    assert_never,
)
from watson.retrieval import retrieve_candidates
from watson.scoring import score_features
from watson.sherlock.interface import FindingProvider
from watson.store import CampaignProfile, CampaignStore


class AssociationPipeline:
    """Feature extraction, retrieval, scoring, decision, and event emission."""

    def __init__(
        self,
        intelligence: FindingProvider,
        store: CampaignStore | None = None,
        emitter: EventEmitter | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        self.intelligence = intelligence
        self.store = store or CampaignStore()
        self.emitter = emitter or InMemoryEventEmitter()
        self.config = config or ScoringConfig()

    def ingest(self, call: CompletedCall) -> CampaignAssociation:
        findings = self.intelligence.findings_for(call)
        features = extract_features(call, findings, self.config)
        candidates = retrieve_candidates(features, self.store, self.config)
        scored = [_score_campaign(features, campaign, self.config) for campaign in candidates]
        decision = decide(scored, self.config)
        association = self._apply(call, features, decision)
        self.emitter.emit(
            AssociationEvent(
                event_id=f"campaign.association.decided:{call.call_id}",
                occurred_at=call.ended_at,
                association=association,
            )
        )
        return association

    def _apply(
        self,
        call: CompletedCall,
        features: CallFeatures,
        decision: Decision,
    ) -> CampaignAssociation:
        action = decision.action
        match action:
            case DecisionAction.ASSOCIATE:
                if decision.campaign_id is None or decision.matched_call_id is None:
                    raise ValueError("associate decision is missing campaign or call id")
                self.store.attach(decision.campaign_id, features)
                reasons = [_associate_reason(decision, self.config), *decision.feature_reasons]
                return _association(call, decision.campaign_id, decision, reasons, self.config)
            case DecisionAction.NEW_CAMPAIGN:
                profile = self.store.create(features)
                reasons = [
                    _new_campaign_reason(call.call_id, profile.campaign_id, decision, self.config),
                    *decision.feature_reasons,
                ]
                if not decision.feature_reasons:
                    reasons.append("No candidate feature comparison was available.")
                return _association(call, profile.campaign_id, decision, reasons, self.config)
            case _:
                assert_never(action)


def _association(
    call: CompletedCall,
    campaign_id: str,
    decision: Decision,
    reasons: list[str],
    config: ScoringConfig,
) -> CampaignAssociation:
    # On a new campaign this is the closest rejected call, when one was scored.
    matched = decision.matched_call_id
    feature_scores = dict(decision.feature_scores)
    return CampaignAssociation(
        call_id=call.call_id,
        campaign_id=campaign_id,
        association_score=decision.association_score,
        reasons=reasons,
        feature_scores=feature_scores,
        decision=decision.action,
        matched_call_id=matched,
        threshold=config.associate_threshold,
    )


def _associate_reason(decision: Decision, config: ScoringConfig) -> str:
    return (
        f"Associated with campaign {decision.campaign_id} because association_score "
        f"{decision.association_score:.2f} >= threshold {config.associate_threshold:.2f} "
        f"(closest call {decision.matched_call_id})."
    )


def _new_campaign_reason(
    call_id: str,
    campaign_id: str,
    decision: Decision,
    config: ScoringConfig,
) -> str:
    if decision.matched_call_id is None:
        return (
            f"Opened a new campaign {campaign_id} for call {call_id} "
            "because no candidate campaign was retrieved."
        )
    if decision.association_score < config.associate_threshold:
        return (
            f"Opened a new campaign {campaign_id} for call {call_id} because closest "
            f"campaign {decision.closest_campaign_id} (call {decision.matched_call_id}) "
            f"scored {decision.association_score:.2f}, below threshold "
            f"{config.associate_threshold:.2f}."
        )
    return (
        f"Opened a new campaign {campaign_id} for call {call_id} because closest "
        f"campaign {decision.closest_campaign_id} (call {decision.matched_call_id}) "
        f"scored {decision.association_score:.2f}, which cleared threshold "
        f"{config.associate_threshold:.2f}, but the evidence guard rejected it "
        f"(anchor group {decision.anchor_group:.2f}, script group "
        f"{decision.script_group:.2f})."
    )


def _score_campaign(
    features: CallFeatures,
    campaign: CampaignProfile,
    config: ScoringConfig,
) -> ScoreBreakdown:
    """Best member of a campaign.

    Ties break toward the higher tier-C score, then the smaller call id.
    """
    breakdowns = [
        score_features(features, member, config).model_copy(
            update={"campaign_id": campaign.campaign_id}
        )
        for member in campaign.members
    ]
    return min(
        breakdowns,
        key=lambda item: (
            -item.association_score,
            -item.tier_c_score,
            item.matched_call_id or "",
        ),
    )
