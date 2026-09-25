"""Pairwise scores for related, partial, and unrelated calls."""

import pytest

from watson.config import ScoringConfig
from watson.dataset import prepare
from watson.features import extract_features
from watson.models import LEAF_FEATURES
from watson.scoring import combine_association_score, score_features
from watson.synthetic import SyntheticDataset


def _features(dataset: SyntheticDataset, config: ScoringConfig):
    runnable = prepare(dataset)
    provider = runnable.provider()
    return {
        call.call_id: extract_features(call, provider.findings_for(call), config)
        for call in runnable.calls()
    }


def test_feature_scores_match_the_weighted_formula(
    dataset: SyntheticDataset,
    config: ScoringConfig,
) -> None:
    features = _features(dataset, config)
    breakdown = score_features(features["irs-1"], features["irs-4"], config)
    assert set(breakdown.feature_scores) == set(LEAF_FEATURES)
    assert breakdown.association_score == pytest.approx(
        combine_association_score(breakdown.feature_scores, config),
        abs=0.001,
    )
    assert breakdown.feature_scores["callback_number"] == 0.0
    assert breakdown.feature_scores["organization_name"] == 1.0
    assert breakdown.feature_scores["other"] == 1.0
    reasons = " ".join(breakdown.feature_reasons)
    assert "organization_name internal revenue service" in reasons
    assert "other irf4421" in reasons


def test_partial_overlap_stays_low_and_near_copies_do_not_use_loose_edits(
    dataset: SyntheticDataset,
    config: ScoringConfig,
) -> None:
    features = _features(dataset, config)
    partial = score_features(features["irs-1"], features["bank-1"], config)
    related = score_features(features["irs-1"], features["irs-2"], config)
    unrelated = score_features(features["gift-1"], features["survey-1"], config)
    assert related.association_score >= config.associate_threshold
    assert partial.association_score < config.associate_threshold
    assert partial.association_score < 0.45
    assert unrelated.association_score < partial.association_score
    assert partial.feature_scores["organization_name"] == 0.0
    assert partial.feature_scores["callback_number"] == 0.0
    assert partial.feature_scores["transcript_overlap"] > 0.0
    assert "not an IntelligenceFinding" in " ".join(partial.feature_reasons)


def test_repeat_caller_with_a_different_pretext_scores_low(
    dataset: SyntheticDataset,
    config: ScoringConfig,
) -> None:
    features = _features(dataset, config)
    breakdown = score_features(features["irs-4"], features["tech-3"], config)
    assert breakdown.association_score < config.associate_threshold
    assert "caller" not in " ".join(breakdown.feature_reasons)
