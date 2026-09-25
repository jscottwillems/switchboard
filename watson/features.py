"""Turn a completed call plus Sherlock indicators into scoreable features."""

from watson.config import ScoringConfig
from watson.models import CallFeatures, CompletedCall, assert_never
from watson.sherlock.models import (
    CallIntelligence,
    CorrelationInference,
    Observation,
    ObservationKind,
)
from watson.textutil import (
    normalize_calling_from,
    normalize_domain,
    normalize_organization,
    normalize_phrase,
    normalize_text,
    opening_span,
    to_e164,
    tokenize,
)


def extract_features(
    call: CompletedCall,
    intelligence: CallIntelligence,
    config: ScoringConfig | None = None,
) -> CallFeatures:
    """Build a feature vector. Low-confidence observations and inferences are dropped."""
    active = config or ScoringConfig()
    if intelligence.call_id != call.call_id:
        raise ValueError(
            f"intelligence call_id {intelligence.call_id!r} does not match {call.call_id!r}"
        )

    admitted = admitted_observations(intelligence.observations, active)
    inference = _admitted_inference(intelligence.inference, active)
    buckets = _empty_buckets()
    for observation in admitted:
        _apply_observation(buckets, observation)

    if inference is not None:
        _apply_inference(buckets, inference)

    opening_text = buckets["opening_script_text"] or _opening_from_turns(buckets["opening_turns"])
    if not opening_text:
        opening_text = opening_span(call.transcript, active.opening_word_count)

    phones = tuple(sorted(buckets["phone_e164"]))
    emails = tuple(sorted(buckets["email_split"]))
    return CallFeatures(
        call_id=call.call_id,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        phone_e164=phones,
        case_id=frozenset(buckets["case_id"]),
        domain_registrable=frozenset(buckets["domain_registrable"]),
        email_split=emails,
        claimed_company_normalized=frozenset(buckets["claimed_company_normalized"]),
        calling_from=frozenset(buckets["calling_from"]),
        opening_script_text=normalize_text(opening_text),
        opening_tokens=tokenize(opening_text),
        opening_turns=tuple(buckets["opening_turns"]),
        transcript_tokens=tokenize(call.transcript),
        opening_script_fingerprint=buckets["opening_script_fingerprint"],
        script_phrase_normalized=frozenset(buckets["script_phrase_normalized"]),
        pretext_category_canonical=buckets["pretext_category_canonical"],
        transfer_destination_claimed=frozenset(buckets["transfer_destination_claimed"]),
        script_language=buckets["script_language"],
        ivr_prompts=tuple(buckets["ivr_prompts"]),
    )


def admitted_observations(
    observations: list[Observation],
    config: ScoringConfig,
) -> list[Observation]:
    """Observations that clear the confidence floor, in input order."""
    return [
        observation
        for observation in observations
        if observation.confidence >= config.min_observation_confidence
    ]


def _admitted_inference(
    inference: CorrelationInference | None,
    config: ScoringConfig,
) -> CorrelationInference | None:
    if inference is None or inference.confidence < config.min_observation_confidence:
        return None
    return inference


def _empty_buckets() -> dict[str, object]:
    return {
        "phone_e164": set(),
        "case_id": set(),
        "domain_registrable": set(),
        "email_split": set(),
        "claimed_company_normalized": set(),
        "calling_from": set(),
        "opening_script_text": "",
        "opening_script_confidence": -1.0,
        "opening_turns": [],
        "opening_script_fingerprint": None,
        "script_phrase_normalized": set(),
        "pretext_category_canonical": None,
        "transfer_destination_claimed": set(),
        "script_language": None,
        "ivr_prompts": [],
    }


def _apply_observation(buckets: dict[str, object], observation: Observation) -> None:
    kind = observation.kind
    normalized = observation.normalized_value
    match kind:
        case ObservationKind.CLAIMED_COMPANY:
            company = normalize_organization(normalized or observation.value)
            if company:
                buckets["claimed_company_normalized"].add(company)
        case ObservationKind.CALLING_FROM:
            company = normalize_calling_from(normalized or observation.value)
            if company:
                buckets["calling_from"].add(company)
        case ObservationKind.CALLBACK_NUMBERS | ObservationKind.SPOKEN_NUMBERS:
            phone = normalized if normalized.startswith("+") else to_e164(normalized or observation.value)
            source = "callback" if kind is ObservationKind.CALLBACK_NUMBERS else "spoken"
            if phone:
                buckets["phone_e164"].add((phone, source))
        case ObservationKind.DOMAINS | ObservationKind.URLS:
            domain = normalize_domain(normalized or observation.value)
            if domain:
                buckets["domain_registrable"].add(domain)
        case ObservationKind.EMAIL_ADDRESSES:
            split = _email_tuple(normalized or observation.value)
            if split is not None:
                buckets["email_split"].add(split)
        case ObservationKind.OTHER:
            case_id = normalize_phrase(normalized or observation.value).replace(" ", "")
            if case_id:
                buckets["case_id"].add(case_id)
        case ObservationKind.OPENING_SCRIPT_TEXT:
            if observation.confidence >= buckets["opening_script_confidence"]:
                buckets["opening_script_text"] = observation.value
                buckets["opening_script_confidence"] = observation.confidence
        case ObservationKind.OPENING_TURNS:
            buckets["opening_turns"].append(observation.value)
        case ObservationKind.SCRIPT_PHRASES:
            phrase = normalize_phrase(normalized or observation.value)
            if phrase:
                buckets["script_phrase_normalized"].add(phrase)
        case ObservationKind.IVR_PROMPTS:
            buckets["ivr_prompts"].extend(_parse_ivr(normalized or observation.value))
        case ObservationKind.TRANSFER_DESTINATION_CLAIMED:
            destination = normalize_phrase(normalized or observation.value)
            if destination:
                buckets["transfer_destination_claimed"].add(destination)
        case ObservationKind.SCRIPT_LANGUAGE:
            language = (normalized or observation.value).strip().lower()
            if language:
                buckets["script_language"] = language
        case (
            ObservationKind.CLAIMED_AGENT
            | ObservationKind.CLAIMED_DEPARTMENT
            | ObservationKind.LOAN_AMOUNTS
            | ObservationKind.RATES
            | ObservationKind.FEES
            | ObservationKind.REQUESTED_INFORMATION
            | ObservationKind.PAYMENT_METHODS
            | ObservationKind.URGENCY_LANGUAGE
            | ObservationKind.TRANSFER_EVENTS
        ):
            return
        case _:
            assert_never(kind)


def _apply_inference(buckets: dict[str, object], inference: CorrelationInference) -> None:
    if inference.claimed_company_normalized:
        buckets["claimed_company_normalized"].add(
            normalize_organization(inference.claimed_company_normalized)
        )
    for phone in inference.phone_e164:
        number = phone.phone_e164 if phone.phone_e164.startswith("+") else to_e164(phone.phone_e164)
        if number:
            buckets["phone_e164"].add((number, phone.source))
    for domain in inference.domain_registrable:
        normalized = normalize_domain(domain)
        if normalized:
            buckets["domain_registrable"].add(normalized)
    for split in inference.email:
        buckets["email_split"].add((split.local.lower(), split.domain.lower(), split.email_domain_registrable.lower()))
    for domain in inference.email_domain_registrable:
        normalized = normalize_domain(domain)
        if normalized and not any(item[2] == normalized for item in buckets["email_split"]):
            buckets["email_split"].add(("", "", normalized))
    for phrase in inference.script_phrase_normalized:
        normalized = normalize_phrase(phrase)
        if normalized:
            buckets["script_phrase_normalized"].add(normalized)
    if inference.opening_script_fingerprint:
        buckets["opening_script_fingerprint"] = inference.opening_script_fingerprint
    if inference.pretext_category_canonical:
        buckets["pretext_category_canonical"] = inference.pretext_category_canonical


def _opening_from_turns(turns: list[str]) -> str:
    return " ".join(turn.strip() for turn in turns if turn.strip())


def _email_tuple(value: str) -> tuple[str, str, str] | None:
    normalized = value.strip().lower()
    if "@" not in normalized:
        return None
    local, domain = normalized.split("@", 1)
    registrable = normalize_domain(domain)
    if not local or not registrable:
        return None
    return (local, domain, registrable)


def _parse_ivr(value: str) -> list[str]:
    raw_steps: list[str] = []
    current: list[str] = []
    separators = set(">,/|")
    for char in value:
        if char in separators:
            step = "".join(current).strip()
            if step:
                raw_steps.append(step)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        raw_steps.append(tail)
    return [normalize_text(step).replace(" ", "_") for step in raw_steps if step.strip()]
