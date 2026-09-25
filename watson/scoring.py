"""Pairwise similarity. Reasons cite finding kind and value."""

from datetime import datetime

from watson.config import ANCHOR_FEATURES, SCRIPT_FEATURES, ScoringConfig
from watson.models import LEAF_FEATURES, CallFeatures, ScoreBreakdown
from watson.textutil import interval_gap_seconds, jaccard


def score_features(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig | None = None,
) -> ScoreBreakdown:
    """Score `left` against `right`. Tier C does not change association_score."""
    active = config or ScoringConfig()
    leaves, details = _leaf_scores(left, right)
    anchor, script, structure, total = _combine(leaves, active)
    reasons = _reasons(leaves, details, anchor, script, structure, active)
    return ScoreBreakdown(
        association_score=unit_score(total),
        feature_scores={name: unit_score(leaves[name]) for name in LEAF_FEATURES},
        feature_reasons=reasons,
        matched_call_id=right.call_id,
        tier_c_score=unit_score(structure),
    )


def group_totals(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> tuple[float, float, float]:
    """Return capped anchor evidence, script evidence, and the tier-C mix."""
    anchor = _capped_sum(feature_scores, config.evidence_weights, ANCHOR_FEATURES)
    script = _capped_sum(feature_scores, config.evidence_weights, SCRIPT_FEATURES)
    structure = _weighted_sum(feature_scores, config.structure_weights)
    return anchor, script, structure


def combine_association_score(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> float:
    """Sum finding and transcript evidence, capped at 1. Structure adds 0."""
    total = sum(
        config.evidence_weights[name] * feature_scores[name] for name in config.evidence_weights
    )
    return unit_score(min(1.0, total))


def _combine(
    leaves: dict[str, float],
    config: ScoringConfig,
) -> tuple[float, float, float, float]:
    anchor, script, structure = group_totals(leaves, config)
    total = min(1.0, combine_association_score(leaves, config))
    return anchor, script, structure, total


def _leaf_scores(
    left: CallFeatures,
    right: CallFeatures,
) -> tuple[dict[str, float], dict[str, str]]:
    pairs = (
        ("callback_number", left.callback_number, right.callback_number),
        ("organization_name", left.organization_name, right.organization_name),
        ("url", left.url, right.url),
        ("payment_method", left.payment_method, right.payment_method),
        ("other", left.other, right.other),
        ("pretext", left.pretext, right.pretext),
        ("person_name", left.person_name, right.person_name),
    )
    leaves: dict[str, float] = {}
    details: dict[str, str] = {}
    for kind, left_values, right_values in pairs:
        score, detail = _shared_values(kind, left_values, right_values)
        leaves[kind] = score
        details[kind] = detail
    transcript = max(
        jaccard(left.opening_tokens, right.opening_tokens),
        jaccard(left.transcript_tokens, right.transcript_tokens),
    )
    leaves["transcript_overlap"] = transcript
    details["transcript_overlap"] = (
        f"call-store transcript token Jaccard {transcript:.2f}; not an IntelligenceFinding"
    )
    timing_score, timing_detail = _timing_similarity(
        left.started_at, left.ended_at, right.started_at, right.ended_at
    )
    leaves["timing"] = timing_score
    details["timing"] = timing_detail
    leaves["duration"] = _duration_similarity(left.duration_seconds, right.duration_seconds)
    details["duration"] = (
        f"call duration {left.duration_seconds:.0f}s versus {right.duration_seconds:.0f}s "
        "(call store started_at/ended_at, not an IntelligenceFinding)"
    )
    return leaves, details


def _shared_values(kind: str, left: frozenset[str], right: frozenset[str]) -> tuple[float, str]:
    shared = sorted(left & right)
    if not shared:
        return 0.0, ""
    return 1.0, f"{kind} {', '.join(shared)}"


def _timing_similarity(
    left_start: datetime,
    left_end: datetime,
    right_start: datetime,
    right_end: datetime,
) -> tuple[float, str]:
    gap = interval_gap_seconds(
        left_start.timestamp(),
        left_end.timestamp(),
        right_start.timestamp(),
        right_end.timestamp(),
    )
    if gap <= 0:
        return 1.0, "call started_at/ended_at intervals overlap (simultaneous); call store, not an IntelligenceFinding"
    if gap <= 120:
        return 0.8, "call started_at/ended_at within 120 seconds; call store, not an IntelligenceFinding"
    if gap <= 300:
        return 0.5, "call started_at/ended_at within 300 seconds; call store, not an IntelligenceFinding"
    if gap <= 3600:
        return 0.2, "call started_at/ended_at within 3600 seconds; call store, not an IntelligenceFinding"
    return 0.0, ""


def _duration_similarity(left: float, right: float) -> float:
    scale = max(left, right, 1.0)
    return max(0.0, 1.0 - (abs(left - right) / scale))


def _reasons(
    leaves: dict[str, float],
    details: dict[str, str],
    anchor: float,
    script: float,
    structure: float,
    config: ScoringConfig,
) -> list[str]:
    reasons = [
        (
            "Tiers: "
            f"anchors {anchor:.2f}, "
            f"script {script:.2f}. "
            f"structure {structure:.2f} is retrieval and tie-break only."
        )
    ]
    for name in LEAF_FEATURES:
        score = leaves[name]
        detail = details.get(name, "")
        cutoff = config.reason_feature_cutoff
        if name in config.structure_weights:
            cutoff = max(cutoff, 0.50)
        if score < cutoff or not detail:
            continue
        reasons.append(f"{name} score {score:.2f}: {detail}.")
    return reasons


def _capped_sum(
    values: dict[str, float],
    weights: dict[str, float],
    names: tuple[str, ...],
) -> float:
    return min(1.0, sum(weights[name] * values[name] for name in names))


def _weighted_sum(values: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[name] * values[name] for name in weights)


def unit_score(value: float) -> float:
    """Round a score to 4 decimals and reject values outside [0, 1]."""
    rounded = round(value, 4)
    if rounded < 0 or rounded > 1:
        raise ValueError(f"score {value} is outside [0, 1]")
    return rounded
