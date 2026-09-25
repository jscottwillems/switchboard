"""Choose the best candidate campaign or open a new one."""

from pydantic import BaseModel, ConfigDict, Field

from watson.config import ScoringConfig
from watson.models import LEAF_FEATURES, DecisionAction, ScoreBreakdown
from watson.scoring import group_totals, unit_score


class Decision(BaseModel):
    """Threshold-and-guard outcome before a new campaign id is allocated."""

    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    campaign_id: str | None = None
    closest_campaign_id: str | None = None
    association_score: float = Field(ge=0, le=1)
    feature_scores: dict[str, float]
    feature_reasons: list[str]
    matched_call_id: str | None = None
    guard_passed: bool
    anchor_group: float = Field(ge=0, le=1)
    script_group: float = Field(ge=0, le=1)
    structure_group: float = Field(ge=0, le=1)


def decide(candidates: list[ScoreBreakdown], config: ScoringConfig | None = None) -> Decision:
    """Pick the highest score, then the higher tier-C score, then the lower ids."""
    active = config or ScoringConfig()
    if not candidates:
        return _empty_decision()

    best = min(
        candidates,
        key=lambda candidate: (
            -candidate.association_score,
            -candidate.tier_c_score,
            candidate.campaign_id or "",
            candidate.matched_call_id or "",
        ),
    )
    anchor, script, structure = group_totals(best.feature_scores, active)
    guard_passed = _evidence_guard(anchor, active)
    above_threshold = best.association_score >= active.associate_threshold
    if above_threshold and guard_passed:
        if best.campaign_id is None:
            raise ValueError("an association candidate is missing campaign_id")
        return Decision(
            action=DecisionAction.ASSOCIATE,
            campaign_id=best.campaign_id,
            closest_campaign_id=best.campaign_id,
            association_score=best.association_score,
            feature_scores=dict(best.feature_scores),
            feature_reasons=list(best.feature_reasons),
            matched_call_id=best.matched_call_id,
            guard_passed=True,
            anchor_group=unit_score(anchor),
            script_group=unit_score(script),
            structure_group=unit_score(structure),
        )
    return Decision(
        action=DecisionAction.NEW_CAMPAIGN,
        campaign_id=None,
        closest_campaign_id=best.campaign_id,
        association_score=best.association_score,
        feature_scores=dict(best.feature_scores),
        feature_reasons=list(best.feature_reasons),
        matched_call_id=best.matched_call_id,
        guard_passed=guard_passed,
        anchor_group=unit_score(anchor),
        script_group=unit_score(script),
        structure_group=unit_score(structure),
    )


def evidence_guard_passes(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> bool:
    anchor, _script, _structure = group_totals(feature_scores, config)
    return _evidence_guard(anchor, config)


def _evidence_guard(anchor: float, config: ScoringConfig) -> bool:
    return anchor >= config.min_anchor_group


def _empty_decision() -> Decision:
    return Decision(
        action=DecisionAction.NEW_CAMPAIGN,
        association_score=0.0,
        feature_scores={name: 0.0 for name in LEAF_FEATURES},
        feature_reasons=[],
        guard_passed=False,
        anchor_group=0.0,
        script_group=0.0,
        structure_group=0.0,
    )
