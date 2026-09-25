"""Pairwise similarity. Reasons cite Observation and Inference field names."""

from datetime import datetime

from watson.config import ScoringConfig
from watson.models import LEAF_FEATURES, CallFeatures, ScoreBreakdown
from watson.textutil import (
    edit_distance_bucket,
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
    """Score `left` against `right`. Tier C does not change association_score."""
    active = config or ScoringConfig()
    leaves, details = _leaf_scores(left, right, active)
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
    """Return anchor, script, and structure group scores from leaf scores."""
    anchor = _weighted_sum(feature_scores, config.anchor_weights)
    script = _weighted_sum(feature_scores, config.script_weights)
    structure = _weighted_sum(feature_scores, config.structure_weights)
    return anchor, script, structure


def combine_association_score(
    feature_scores: dict[str, float],
    config: ScoringConfig,
) -> float:
    """Tier A and tier B only. Structure's group weight is 0."""
    anchor, script, structure = group_totals(feature_scores, config)
    total = (
        config.group_weights["anchor"] * anchor
        + config.group_weights["script"] * script
        + config.group_weights["structure"] * structure
    )
    return unit_score(total)


def _combine(
    leaves: dict[str, float],
    config: ScoringConfig,
) -> tuple[float, float, float, float]:
    anchor, script, structure = group_totals(leaves, config)
    total = (
        config.group_weights["anchor"] * anchor
        + config.group_weights["script"] * script
        + config.group_weights["structure"] * structure
    )
    return anchor, script, structure, total


def _leaf_scores(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[dict[str, float], dict[str, str]]:
    phone_score, phone_detail = _phone_similarity(left, right)
    case_score, case_detail = _case_similarity(left, right)
    domain_score, domain_detail = _domain_similarity(left, right)
    email_score, email_detail = _email_similarity(left, right, config)
    company_score, company_detail = _company_similarity(left, right)
    opening_score, opening_detail = _opening_similarity(left, right, config)
    fingerprint_score, fingerprint_detail = _fingerprint_similarity(left, right)
    phrase_score, phrase_detail = _phrase_similarity(left, right)
    pretext_score, pretext_detail = _pretext_similarity(left, right)
    transfer_score, transfer_detail = _transfer_similarity(left, right)
    language_score, language_detail = _language_similarity(left, right, config)
    timing_score, timing_detail = _timing_similarity(
        left.started_at, left.ended_at, right.started_at, right.ended_at
    )
    duration_score = _duration_similarity(left.duration_seconds, right.duration_seconds)
    ivr_score, ivr_detail = _ivr_similarity(left.ivr_prompts, right.ivr_prompts)
    leaves = {
        "phone_e164": phone_score,
        "case_id": case_score,
        "domain_registrable": domain_score,
        "email_domain_registrable": email_score,
        "claimed_company_normalized": company_score,
        "opening_script_text": opening_score,
        "opening_script_fingerprint": fingerprint_score,
        "script_phrase_normalized": phrase_score,
        "pretext_category_canonical": pretext_score,
        "transfer_destination_claimed": transfer_score,
        "script_language": language_score,
        "timing": timing_score,
        "duration": duration_score,
        "ivr_prompts": ivr_score,
    }
    details = {
        "phone_e164": phone_detail,
        "case_id": case_detail,
        "domain_registrable": domain_detail,
        "email_domain_registrable": email_detail,
        "claimed_company_normalized": company_detail,
        "opening_script_text": opening_detail,
        "opening_script_fingerprint": fingerprint_detail,
        "script_phrase_normalized": phrase_detail,
        "pretext_category_canonical": pretext_detail,
        "transfer_destination_claimed": transfer_detail,
        "script_language": language_detail,
        "timing": timing_detail,
        "duration": (
            f"call duration {left.duration_seconds:.0f}s versus {right.duration_seconds:.0f}s "
            "(call store started_at/ended_at, not an Observation)"
        ),
        "ivr_prompts": ivr_detail,
    }
    return leaves, details


def _phone_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    left_numbers = {number for number, _source in left.phone_e164}
    right_numbers = {number for number, _source in right.phone_e164}
    shared = sorted(left_numbers & right_numbers)
    if not shared:
        return 0.0, ""
    parts = []
    for number in shared:
        sources = sorted(
            {
                source
                for phone, source in (*left.phone_e164, *right.phone_e164)
                if phone == number
            }
        )
        parts.append(f"phone_e164 {number} source={','.join(sources)}")
    return 1.0, "; ".join(parts)


def _case_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    shared = sorted(left.case_id & right.case_id)
    if not shared:
        return 0.0, ""
    shown = ", ".join(shared)
    return 1.0, f"observation other {shown}; identifier_kind=case_id"


def _domain_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    shared = sorted(left.domain_registrable & right.domain_registrable)
    if not shared:
        return 0.0, ""
    return 1.0, f"domain_registrable {', '.join(shared)}"


def _email_similarity(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[float, str]:
    if not left.email_split or not right.email_split:
        return 0.0, ""
    left_exact = {(local, domain) for local, domain, _registrable in left.email_split if local}
    right_exact = {(local, domain) for local, domain, _registrable in right.email_split if local}
    shared_exact = sorted(left_exact & right_exact)
    if shared_exact:
        local, domain = shared_exact[0]
        registrable = next(
            item[2] for item in left.email_split if item[0] == local and item[1] == domain
        )
        return (
            1.0,
            f"local {local} domain {domain}; email_domain_registrable {registrable}",
        )
    left_registrable = {item[2] for item in left.email_split if item[2]}
    right_registrable = {item[2] for item in right.email_split if item[2]}
    shared_domains = sorted(left_registrable & right_registrable)
    if shared_domains:
        return (
            config.email_domain_score,
            f"email_domain_registrable {', '.join(shared_domains)}; local parts differ",
        )
    return 0.0, ""


def _company_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    left_names = left.claimed_company_normalized | left.calling_from
    right_names = right.claimed_company_normalized | right.calling_from
    shared = sorted(left_names & right_names)
    if not shared:
        return 0.0, ""
    parts = []
    for name in shared:
        fields = []
        if name in left.claimed_company_normalized or name in right.claimed_company_normalized:
            fields.append("claimed_company_normalized")
        if name in left.calling_from or name in right.calling_from:
            fields.append("calling_from")
        parts.append(f"{' and '.join(fields)} {name}")
    return 1.0, "; ".join(parts)


def _opening_similarity(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[float, str]:
    token_score = jaccard(left.opening_tokens, right.opening_tokens)
    ratio = levenshtein_ratio(left.opening_script_text, right.opening_script_text)
    bucket = edit_distance_bucket(ratio, config)
    score = max(token_score, bucket)
    detail = f"opening_script_text token Jaccard {token_score:.2f}; edit-distance bucket {bucket:.2f}"
    if left.opening_turns and right.opening_turns:
        detail += f"; opening_turns {len(left.opening_turns)} and {len(right.opening_turns)}"
    return score, detail


def _fingerprint_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    if not left.opening_script_fingerprint or not right.opening_script_fingerprint:
        return 0.0, ""
    if left.opening_script_fingerprint != right.opening_script_fingerprint:
        return 0.0, ""
    return 1.0, f"opening_script_fingerprint {left.opening_script_fingerprint}"


def _phrase_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    shared = sorted(left.script_phrase_normalized & right.script_phrase_normalized)
    score = overlap_coefficient(left.script_phrase_normalized, right.script_phrase_normalized)
    if not shared:
        return score, ""
    shown = ", ".join(f"'{phrase}'" for phrase in shared)
    return score, f"script_phrase_normalized {shown}"


def _pretext_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    if not left.pretext_category_canonical or not right.pretext_category_canonical:
        return 0.0, ""
    if left.pretext_category_canonical != right.pretext_category_canonical:
        return 0.0, ""
    return 1.0, f"pretext_category_canonical {left.pretext_category_canonical}"


def _transfer_similarity(left: CallFeatures, right: CallFeatures) -> tuple[float, str]:
    shared = sorted(left.transfer_destination_claimed & right.transfer_destination_claimed)
    if not shared:
        return 0.0, ""
    return 1.0, f"transfer_destination_claimed {', '.join(shared)}"


def _language_similarity(
    left: CallFeatures,
    right: CallFeatures,
    config: ScoringConfig,
) -> tuple[float, str]:
    if not left.script_language or not right.script_language:
        return 0.0, ""
    if left.script_language != right.script_language:
        return 0.0, ""
    if left.script_language == config.nondistinctive_script_language:
        return 0.0, f"script_language {left.script_language} is shared and is not campaign evidence"
    return 1.0, f"script_language {left.script_language}"


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
        return 1.0, "call started_at/ended_at intervals overlap (simultaneous); call store, not an Observation"
    if gap <= 120:
        return 0.8, "call started_at/ended_at within 120 seconds; call store, not an Observation"
    if gap <= 300:
        return 0.5, "call started_at/ended_at within 300 seconds; call store, not an Observation"
    if gap <= 3600:
        return 0.2, "call started_at/ended_at within 3600 seconds; call store, not an Observation"
    return 0.0, ""


def _duration_similarity(left: float, right: float) -> float:
    scale = max(left, right, 1.0)
    return max(0.0, 1.0 - (abs(left - right) / scale))


def _ivr_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[float, str]:
    if not left or not right:
        return 0.0, ""
    score = sequence_ratio(left, right)
    if left == right:
        return score, f"ivr_prompts {' > '.join(left)}"
    return score, f"ivr_prompts {' > '.join(left)} versus {' > '.join(right)}"


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
            f"anchors {anchor:.2f} (weight {config.group_weights['anchor']:.2f}), "
            f"script {script:.2f} (weight {config.group_weights['script']:.2f}). "
            f"structure {structure:.2f} is retrieval and tie-break only "
            f"(association weight {config.group_weights['structure']:.2f})."
        )
    ]
    for name in LEAF_FEATURES:
        score = leaves[name]
        detail = details.get(name, "")
        if name == "script_language" and detail:
            reasons.append(f"script_language score {score:.2f}: {detail}.")
            continue
        cutoff = config.reason_feature_cutoff
        if name in config.structure_weights:
            cutoff = max(cutoff, 0.50)
        if score < cutoff:
            continue
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
