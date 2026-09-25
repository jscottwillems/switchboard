"""Turn a completed call plus intelligence indicators into scoreable features."""

from watson.config import ScoringConfig
from watson.models import CallFeatures, CompletedCall, assert_never
from watson.sherlock.models import CallIntelligence, IntelligenceObservation, ObservationKind
from watson.textutil import (
    normalize_domain,
    normalize_email,
    normalize_organization,
    normalize_phrase,
    normalize_phone,
    normalize_text,
    opening_span,
    tokenize,
)


def extract_features(
    call: CompletedCall,
    intelligence: CallIntelligence,
    config: ScoringConfig | None = None,
) -> CallFeatures:
    """Build a feature vector. Observations under the confidence floor are dropped."""
    active = config or ScoringConfig()
    if intelligence.call_id != call.call_id:
        raise ValueError(
            f"intelligence call_id {intelligence.call_id!r} does not match {call.call_id!r}"
        )

    organizations: set[str] = set()
    callbacks: set[str] = set()
    domains: set[str] = set()
    emails: set[str] = set()
    phrases: set[str] = set()
    opening_override: str | None = None
    opening_confidence = -1.0
    ivr_override: tuple[str, ...] | None = None

    for observation in intelligence.observations:
        if observation.confidence < active.min_observation_confidence:
            continue
        kind = observation.kind
        match kind:
            case ObservationKind.CLAIMED_ORGANIZATION:
                organizations.add(normalize_organization(observation.value))
            case ObservationKind.CALLBACK_IDENTIFIER:
                phone = normalize_phone(observation.value)
                if phone:
                    callbacks.add(phone)
            case ObservationKind.DOMAIN:
                domain = normalize_domain(observation.value)
                if domain:
                    domains.add(domain)
            case ObservationKind.EMAIL_PATTERN:
                email = normalize_email(observation.value)
                if email:
                    emails.add(email)
            case ObservationKind.REPEATED_PHRASE:
                phrase = normalize_phrase(observation.value)
                if phrase:
                    phrases.add(phrase)
            case ObservationKind.OPENING_SCRIPT:
                if observation.confidence >= opening_confidence:
                    opening_override = observation.value
                    opening_confidence = observation.confidence
            case ObservationKind.IVR_STRUCTURE:
                ivr_override = _parse_ivr(observation.value)
            case _:
                assert_never(kind)

    opening_text = opening_override or opening_span(call.transcript, active.opening_word_count)
    ivr_path = tuple(_normalize_ivr_step(step) for step in call.ivr_path if step.strip())
    if not ivr_path and ivr_override:
        ivr_path = ivr_override

    return CallFeatures(
        call_id=call.call_id,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        opening_text=normalize_text(opening_text),
        opening_tokens=tokenize(opening_text),
        transcript_tokens=tokenize(call.transcript),
        repeated_phrases=frozenset(phrases),
        claimed_organizations=frozenset(organizations),
        callback_identifiers=frozenset(callbacks),
        domains=frozenset(domains),
        email_patterns=frozenset(emails),
        transferred=call.transferred,
        ivr_path=ivr_path,
    )


def _parse_ivr(value: str) -> tuple[str, ...]:
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
    return tuple(_normalize_ivr_step(step) for step in raw_steps)


def _normalize_ivr_step(step: str) -> str:
    return normalize_text(step).replace(" ", "_")


def admitted_observations(
    observations: list[IntelligenceObservation],
    config: ScoringConfig,
) -> list[IntelligenceObservation]:
    """Observations that clear the confidence floor, in input order."""
    return [
        observation
        for observation in observations
        if observation.confidence >= config.min_observation_confidence
    ]
