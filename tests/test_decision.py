"""Threshold and evidence-guard decisions."""

from watson.config import ScoringConfig
from watson.decision import decide
from watson.models import LEAF_FEATURES, DecisionAction, ScoreBreakdown


def _breakdown(
    campaign_id: str,
    score: float,
    call_id: str = "other",
    leaves: dict[str, float] | None = None,
) -> ScoreBreakdown:
    feature_scores = {name: 0.0 for name in LEAF_FEATURES}
    feature_scores.update(
        {
            "opening_script": 1.0,
            "transcript": 1.0,
            "repeated_phrases": 1.0,
        }
    )
    if leaves is not None:
        feature_scores = {name: 0.0 for name in LEAF_FEATURES}
        feature_scores.update(leaves)
    return ScoreBreakdown(
        association_score=score,
        feature_scores=feature_scores,
        feature_reasons=["weighted groups listed by the scorer"],
        matched_call_id=call_id,
        campaign_id=campaign_id,
    )


def test_score_below_threshold_opens_a_new_campaign() -> None:
    config = ScoringConfig()
    decision = decide([_breakdown("camp-0001", config.associate_threshold - 0.0001)], config)
    assert decision.action is DecisionAction.NEW_CAMPAIGN
    assert decision.campaign_id is None
    assert decision.closest_campaign_id == "camp-0001"


def test_score_at_threshold_associates_when_the_guard_passes() -> None:
    config = ScoringConfig()
    decision = decide([_breakdown("camp-0007", config.associate_threshold)], config)
    assert decision.action is DecisionAction.ASSOCIATE
    assert decision.campaign_id == "camp-0007"
    assert decision.guard_passed is True


def test_equal_scores_break_toward_the_lower_campaign_id() -> None:
    config = ScoringConfig()
    decision = decide(
        [
            _breakdown("camp-0002", 0.80, call_id="b"),
            _breakdown("camp-0001", 0.80, call_id="a"),
        ],
        config,
    )
    assert decision.campaign_id == "camp-0001"
    assert decision.matched_call_id == "a"


def test_guard_rejects_identifiers_without_script_when_threshold_is_lenient() -> None:
    config = ScoringConfig(associate_threshold=0.10)
    leaves = {name: 0.0 for name in LEAF_FEATURES}
    leaves.update(
        {
            "claimed_organization": 1.0,
            "callback_identifiers": 1.0,
            "domains": 1.0,
            "email_patterns": 1.0,
        }
    )
    decision = decide([_breakdown("camp-0001", 0.90, leaves=leaves)], config)
    assert decision.action is DecisionAction.NEW_CAMPAIGN
    assert decision.guard_passed is False
    assert decision.association_score == 0.90


def test_empty_candidate_list_opens_a_campaign_with_zero_scores() -> None:
    decision = decide([], ScoringConfig())
    assert decision.action is DecisionAction.NEW_CAMPAIGN
    assert decision.association_score == 0.0
    assert decision.matched_call_id is None
    assert all(value == 0.0 for value in decision.feature_scores.values())
