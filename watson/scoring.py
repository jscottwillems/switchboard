"""Pairwise similarity. Every non-trivial leaf score can be read back as a reason."""

from datetime import datetime

from watson.config import ScoringConfig
from watson.models import LEAF_FEATURES, CallFeatures, ScoreBreakdown
from watson.textutil import (
    edit_distance_bucket,
    email_domain,
    interval_gap_seconds,
    jaccard,
    levenshtein_ratio,
    overlap_coefficient,
    sequence_ratio,
)


def score_features(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig | None = None,
) -> ScoreBreakdown:
    """Score `left` against `right`. The result is symmetric in the features used."""
    active = config or ScoringConfig()
    leaves, details = _leaf_scores(left, right, active)
    script, identifier, structure, total = _combine(leaves, active)
    reasons = _reasons(leaves, details, script, identifier, structure, active)
    return ScoreBreakdown(
        association_score=unit_score(total),
        feature_scores={name: unit_score(leaves[name]) for name in LEAF_FEATURES},
        feature_reasons=reasons,
        matched_call_id=right.call_id,
    )


def group_totals(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> tuple[float, float, float]:
    """Return script, identifier, and structure group scores from leaf scores."""
    script = _weighted_sum(feature_scores, config.script_weights)
    identifier = _weighted_sum(feature_scores, config.identifier_weights)
    structure = _weighted_sum(feature_scores, config.structure_weights)
    return script, identifier, structure


def combine_association_score(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> float:
    """Weighted group formula. Missing leaves must already be present as 0."""
    script, identifier, structure = group_totals(feature_scores, config)
    total = (
        config.group_weights["script"] * script
        + config.group_weights["identifier"] * identifier
        + config.group_weights["structure"] * structure
    )
    return unit_score(total)


def _combine(
    leaves: dict[str, float],
    config: ScoringConfig,
) -> tuple[float, float, float, float]:
    script, identifier, structure = group_totals(leaves, config)
    total = (
        config.group_weights["script"] * script
        + config.group_weights["identifier"] * identifier
        + config.group_weights["structure"] * structure
    )
    return script, identifier, structure, total


def _leaf_scores(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[dict[str, float], dict[str, str]]:
    opening_score, opening_detail = _opening_similarity(left, right, config)
    transcript_score = jaccard(left.transcript_tokens, right.transcript_tokens)
    phrase_score, phrase_detail = _phrase_similarity(left, right)
    organization_score, organization_detail = _set_similarity(
        left.claimed_organizations,
        right.claimed_organizations,
        "organization",
    )
    callback_score, callback_detail = _set_similarity(
        left.callback_identifiers,
        right.callback_identifiers,
        "callback identifier",
    )
    domain_score, domain_detail = _set_similarity(left.domains, right.domains, "domain")
    email_score, email_detail = _email_similarity(left, right, config)
    timing_score, timing_detail = _timing_similarity(
        left.started_at, left.ended_at, right.started_at, right.ended_at
    )
    duration_score = _duration_similarity(left.duration_seconds, right.duration_seconds)
    transfer_score = 1.0 if left.transferred and right.transferred else 0.0
    ivr_score, ivr_detail = _ivr_similarity(left.ivr_path, right.ivr_path)

    leaves = {
        "opening_script": opening_score,
        "transcript": transcript_score,
        "repeated_phrases": phrase_score,
        "claimed_organization": organization_score,
        "callback_identifiers": callback_score,
        "domains": domain_score,
        "email_patterns": email_score,
        "timing": timing_score,
        "duration": duration_score,
        "transfer_behavior": transfer_score,
        "ivr_structure": ivr_score,
    }
    details = {
        "opening_script": opening_detail,
        "transcript": "token Jaccard overlap",
        "repeated_phrases": phrase_detail,
        "claimed_organization": organization_detail,
        "callback_identifiers": callback_detail,
        "domains": domain_detail,
        "email_patterns": email_detail,
        "timing": timing_detail,
        "duration": (
            f"{left.duration_seconds:.0f}s versus {right.duration_seconds:.0f}s"
        ),
        "transfer_behavior": "both calls were transferred",
        "ivr_structure": ivr_detail,
    }
    return leaves, details


def _opening_similarity(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[float, str]:
    token_score = jaccard(left.opening_tokens, right.opening_tokens)
    ratio = levenshtein_ratio(left.opening_text, right.opening_text)
    bucket = edit_distance_bucket(ratio, config)
    score = max(token_score, bucket)
    detail = f"token Jaccard {token_score:.2f}; edit-distance bucket {bucket:.2f}"
    return score, detail


def _phrase_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    shared = sorted(left.repeated_phrases & right.repeated_phrases)
    score = overlap_coefficient(left.repeated_phrases, right.repeated_phrases)
    if not shared:
        return score, ""
    shown = ", ".join(f"'{phrase}'" for phrase in shared)
    return score, f"shared phrases {shown}"


def _set_similarity(
    left: frozenset[str],
    right: frozenset[str],
    label: str,
) -> tuple[float, str]:
    shared = sorted(left & right)
    score = overlap_coefficient(left, right)
    if not shared:
        return score, ""
    shown = ", ".join(shared)
    return score, f"shared {label} {shown}"


def _email_similarity(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[float, str]:
    if not left.email_patterns or not right.email_patterns:
        return 0.0, ""
    shared = sorted(left.email_patterns & right.email_patterns)
    if shared:
        return 1.0, f"shared email {', '.join(shared)}"
    left_domains = {email_domain(email) for email in left.email_patterns}
    right_domains = {email_domain(email) for email in right.email_patterns}
    shared_domains = sorted(domain for domain in left_domains & right_domains if domain)
    if shared_domains:
        shown = ", ".join(shared_domains)
        return (
            config.email_domain_score,
            f"same email domain {shown} with different local parts",
        )
    return 0.0, ""


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
        return 1.0, "call intervals overlap"
    if gap <= 120:
        return 0.8, "calls fall within a 120 second burst window"
    if gap <= 300:
        return 0.5, "calls fall within a 300 second window"
    if gap <= 3600:
        return 0.2, "calls fall within a 3600 second window"
    return 0.0, ""


def _duration_similarity(left: float, right: float) -> float:
    scale = max(left, right, 1.0)
    return max(0.0, 1.0 - (abs(left - right) / scale))


def _ivr_similarity(
    left: tuple[str, ...],
    right: tuple[str, ...],
) -> tuple[float, str]:
    if not left or not right:
        return 0.0, ""
    score = sequence_ratio(left, right)
    if left == right:
        return score, f"identical IVR path {' > '.join(left)}"
    return score, f"{' > '.join(left)} versus {' > '.join(right)}"


def _reasons(
    leaves: dict[str, float],
    details: dict[str, str],
    script: float,
    identifier: float,
    structure: float,
    config: ScoringConfig,
) -> list[str]:
    reasons = [
        (
            "Weighted groups: "
            f"script {script:.2f} (weight {config.group_weights['script']:.2f}), "
            f"identifier {identifier:.2f} (weight {config.group_weights['identifier']:.2f}), "
            f"structure {structure:.2f} (weight {config.group_weights['structure']:.2f})."
        )
    ]
    for name in LEAF_FEATURES:
        score = leaves[name]
        cutoff = config.reason_feature_cutoff
        if name in config.structure_weights:
            cutoff = max(cutoff, 0.50)
        if score < cutoff:
            continue
        detail = details.get(name, "")
        if detail:
            reasons.append(f"{name} score {score:.2f}: {detail}.")
        else:
            reasons.append(f"{name} score {score:.2f}.")
    return reasons


def _weighted_sum(values: dict[str, float], weights: dict[str, float]) -> float:
    return sum(weights[name] * values[name] for name in weights)


def unit_score(value: float) -> float:
    """Round a score to 4 decimals and reject values outside [0, 1]."""
    rounded = round(value, 4)
    if rounded < 0 or rounded > 1:
        raise ValueError(f"score {value} is outside [0, 1]")
    return rounded
