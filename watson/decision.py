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
    script_group: float = Field(ge=0, le=1)
    identifier_group: float = Field(ge=0, le=1)
    structure_group: float = Field(ge=0, le=1)


def decide(candidates: list[ScoreBreakdown], config: ScoringConfig | None = None) -> Decision:
    """Pick the highest score, breaking ties by campaign id then matched call id."""
    active = config or ScoringConfig()
    if not candidates:
        return _empty_decision()

    best = min(
        candidates,
        key=lambda candidate: (
            -candidate.association_score,
            candidate.campaign_id or "",
            candidate.matched_call_id or "",
        ),
    )
    script, identifier, structure = group_totals(best.feature_scores, active)
    guard_passed = _evidence_guard(script, identifier, active)
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
            script_group=unit_score(script),
            identifier_group=unit_score(identifier),
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
        script_group=unit_score(script),
        identifier_group=unit_score(identifier),
        structure_group=unit_score(structure),
    )


def evidence_guard_passes(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> bool:
    script, identifier, _structure = group_totals(feature_scores, config)
    return _evidence_guard(script, identifier, config)


def _evidence_guard(script: float, identifier: float, config: ScoringConfig) -> bool:
    if script >= config.min_script_group:
        return True
    return (
        identifier >= config.min_identifier_group
        and script >= config.min_script_with_identifiers
    )


def _empty_decision() -> Decision:
    return Decision(
        action=DecisionAction.NEW_CAMPAIGN,
        association_score=0.0,
        feature_scores={name: 0.0 for name in LEAF_FEATURES},
        feature_reasons=[],
        guard_passed=False,
        script_group=0.0,
        identifier_group=0.0,
        structure_group=0.0,
    )

