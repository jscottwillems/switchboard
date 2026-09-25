"""Correlation features derived from observations.

Each record is an Inference with its own confidence. None of these are
transcript spans.
"""

import re
from collections import defaultdict
from collections.abc import Sequence

from switchboard_intelligence.extraction import confidence
from switchboard_intelligence.extraction.normalize import (
    normalize_company_name,
    normalize_script_phrase,
    registrable_domain,
    split_email,
)
from switchboard_intelligence.extraction.spans import stable_id
from switchboard_intelligence.schemas.inference import (
    IdentifierKind,
    Inference,
    InferenceKind,
    InferenceMethod,
    PhoneSourceTag,
)
from switchboard_intelligence.schemas.observation import Observation, ObservationKind
from switchboard_intelligence.schemas.transcript import Transcript

_PHONE_TAGS = {
    ObservationKind.CALLBACK_NUMBERS: PhoneSourceTag.CALLBACK,
    ObservationKind.SPOKEN_NUMBERS: PhoneSourceTag.SPOKEN,
    ObservationKind.SPOKEN_CLI_CLAIM: PhoneSourceTag.SPOKEN_CLI,
}

_IDENTIFIER_LABELS: tuple[tuple[IdentifierKind, re.Pattern[str]], ...] = (
    (IdentifierKind.SSN_LAST4, re.compile(r"\b(?:social security|ssn|last four)\b", re.IGNORECASE)),
    (IdentifierKind.ACCOUNT, re.compile(r"\baccount\b", re.IGNORECASE)),
    (IdentifierKind.TICKET, re.compile(r"\bticket\b", re.IGNORECASE)),
    (IdentifierKind.CONFIRMATION, re.compile(r"\bconfirmation\b", re.IGNORECASE)),
    (IdentifierKind.CLAIM, re.compile(r"\bclaim\b", re.IGNORECASE)),
    (IdentifierKind.CASE, re.compile(r"\bcase\b", re.IGNORECASE)),
    (IdentifierKind.REFERENCE, re.compile(r"\breference\b", re.IGNORECASE)),
    (IdentifierKind.BADGE, re.compile(r"\bbadge\b", re.IGNORECASE)),
)

_IDENTIFIER_OBSERVATIONS = (
    ObservationKind.CASE_OR_REFERENCE_IDS,
    ObservationKind.OTHER,
)


def derive_correlation(
    call_id: str,
    observations: Sequence[Observation],
    transcript: Transcript | None,
) -> list[Inference]:
    grouped: dict[ObservationKind, list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.kind].append(observation)

    built: list[Inference] = []
    _companies(built, call_id, grouped.get(ObservationKind.CLAIMED_COMPANY, []))
    phones: list[Observation] = []
    for kind in _PHONE_TAGS:
        phones.extend(grouped.get(kind, []))
    _phones(built, call_id, phones)
    _domains(built, call_id, grouped.get(ObservationKind.DOMAINS, []))
    _emails(built, call_id, grouped.get(ObservationKind.EMAIL_ADDRESSES, []))
    _phrases(built, call_id, grouped.get(ObservationKind.SCRIPT_PHRASES, []))
    _fingerprint(built, call_id, grouped.get(ObservationKind.OPENING_SCRIPT_TEXT, []))
    _pretext(built, call_id, grouped.get(ObservationKind.PRETEXT_CATEGORY, []))
    identifiers: list[Observation] = []
    for kind in _IDENTIFIER_OBSERVATIONS:
        identifiers.extend(grouped.get(kind, []))
    _identifiers(built, call_id, identifiers, transcript)
    return built


def _companies(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    originals: dict[str, str] = {}
    for observation in sorted(observations, key=lambda item: item.value):
        normalized = normalize_company_name(observation.value)
        if not normalized:
            continue
        grouped[normalized].append(observation)
        originals.setdefault(normalized, observation.value)
    for normalized, support in grouped.items():
        _append(
            built,
            call_id,
            InferenceKind.CLAIMED_COMPANY_NORMALIZED,
            support,
            confidence.CLAIMED_COMPANY_NORMALIZED,
            f"Normalized claimed company is {normalized}.",
            "Lowercased the claimed company and removed legal suffixes.",
            normalized_value=normalized,
            original_value=originals[normalized],
        )


def _phones(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[tuple[str, PhoneSourceTag], list[Observation]] = defaultdict(list)
    originals: dict[tuple[str, PhoneSourceTag], str] = {}
    for observation in sorted(observations, key=lambda item: item.value):
        tag = _PHONE_TAGS[observation.kind]
        key = (observation.normalized_value, tag)
        grouped[key].append(observation)
        originals.setdefault(key, observation.value)
    for (number, tag), support in grouped.items():
        _append(
            built,
            call_id,
            InferenceKind.PHONE_E164,
            support,
            confidence.PHONE_E164,
            f"Phone {number} was heard as {tag.value}.",
            "Copied the E.164 form already stored on the phone observation.",
            normalized_value=number,
            original_value=originals[(number, tag)],
            source_tag=tag,
            identity=f"{number}|{tag.value}",
        )


def _domains(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        registrable = registrable_domain(observation.normalized_value)
        if not registrable:
            continue
        grouped[registrable].append(observation)
    for registrable, support in grouped.items():
        _append(
            built,
            call_id,
            InferenceKind.DOMAIN_REGISTRABLE,
            support,
            confidence.DOMAIN_REGISTRABLE,
            f"Registrable domain is {registrable}.",
            "Reduced URL, email, and bare hosts to eTLD+1.",
            normalized_value=registrable,
        )


def _emails(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.normalized_value].append(observation)
    for address, support in grouped.items():
        local, domain = split_email(address)
        registrable = registrable_domain(domain)
        _append(
            built,
            call_id,
            InferenceKind.EMAIL_LOCAL_DOMAIN,
            support,
            confidence.EMAIL_LOCAL_DOMAIN,
            f"Email splits into {local} at {domain}.",
            "Split the email observation into local part and domain.",
            normalized_value=address,
            original_value=support[0].value,
            email_local=local,
            email_domain=domain,
        )
        _append(
            built,
            call_id,
            InferenceKind.EMAIL_DOMAIN_REGISTRABLE,
            support,
            confidence.EMAIL_DOMAIN_REGISTRABLE,
            f"Email domain registrable form is {registrable}.",
            "Reduced the email host to eTLD+1.",
            normalized_value=registrable,
            identity=f"{address}|{registrable}",
        )


def _phrases(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    originals: dict[str, str] = {}
    for observation in sorted(observations, key=lambda item: item.value):
        normalized = normalize_script_phrase(observation.value)
        if not normalized:
            continue
        grouped[normalized].append(observation)
        originals.setdefault(normalized, observation.value)
    for normalized, support in grouped.items():
        _append(
            built,
            call_id,
            InferenceKind.SCRIPT_PHRASE_NORMALIZED,
            support,
            confidence.SCRIPT_PHRASE_NORMALIZED,
            f"Normalized script phrase is {normalized}.",
            "Lowercased the script phrase and stripped punctuation.",
            normalized_value=normalized,
            original_value=originals[normalized],
        )


def _fingerprint(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    turns = sorted(
        observations,
        key=lambda item: item.opening_turn_index if item.opening_turn_index is not None else 99,
    )
    tokens: list[str] = []
    for turn in turns:
        normalized = normalize_script_phrase(turn.value)
        if normalized:
            tokens.extend(normalized.split(" "))
    if not tokens:
        return
    _append(
        built,
        call_id,
        InferenceKind.OPENING_SCRIPT_FINGERPRINT,
        turns,
        confidence.OPENING_FINGERPRINT,
        "Opening fingerprint is the ordered tokens from the first caller turns.",
        "Normalized the first caller turns in order and split them into tokens.",
        normalized_value=" ".join(tokens),
        fingerprint_tokens=tokens,
    )


def _pretext(built: list[Inference], call_id: str, observations: Sequence[Observation]) -> None:
    grouped: dict[str, list[Observation]] = defaultdict(list)
    originals: dict[str, str] = {}
    for observation in sorted(observations, key=lambda item: item.value):
        if observation.pretext_category is None:
            continue
        canonical = observation.pretext_category.value
        grouped[canonical].append(observation)
        originals.setdefault(canonical, observation.value)
    for canonical, support in grouped.items():
        _append(
            built,
            call_id,
            InferenceKind.PRETEXT_CATEGORY_CANONICAL,
            support,
            confidence.PRETEXT_CANONICAL,
            f"Canonical pretext is {canonical}.",
            "Mapped the purpose span onto the closed pretext enum.",
            normalized_value=canonical,
            original_value=originals[canonical],
        )


def _identifiers(
    built: list[Inference],
    call_id: str,
    observations: Sequence[Observation],
    transcript: Transcript | None,
) -> None:
    if transcript is None:
        return
    segments = {segment.segment_id: segment.text for segment in transcript.segments}
    for observation in observations:
        text = segments.get(observation.transcript_segment_id)
        if text is None:
            continue
        window = text[max(0, observation.char_start - 64) : observation.char_start]
        label = _identifier_label(window)
        if label is None:
            continue
        _append(
            built,
            call_id,
            InferenceKind.IDENTIFIER_KIND,
            [observation],
            confidence.IDENTIFIER_KIND,
            f"Identifier {observation.normalized_value} is a {label.value}.",
            "Read the label in the text just before the identifier span.",
            normalized_value=observation.normalized_value,
            original_value=observation.value,
            identifier_kind=label,
            identity=f"{label.value}|{observation.observation_id}",
        )


def _identifier_label(window: str) -> IdentifierKind | None:
    for label, pattern in _IDENTIFIER_LABELS:
        if pattern.search(window):
            return label
    return None


def _append(
    built: list[Inference],
    call_id: str,
    kind: InferenceKind,
    support: Sequence[Observation],
    score: float,
    proposition: str,
    rationale: str,
    *,
    normalized_value: str,
    identity: str | None = None,
    original_value: str | None = None,
    source_tag: PhoneSourceTag | None = None,
    identifier_kind: IdentifierKind | None = None,
    email_local: str | None = None,
    email_domain: str | None = None,
    fingerprint_tokens: list[str] | None = None,
) -> None:
    support_ids = sorted({item.observation_id for item in support})
    key = identity if identity is not None else normalized_value
    inference_id = stable_id("inf", f"{call_id}|{kind.value}|{key}|{'|'.join(support_ids)}")
    built.append(
        Inference(
            inference_id=inference_id,
            call_id=call_id,
            kind=kind,
            proposition=proposition,
            supporting_observation_ids=support_ids,
            confidence=score,
            method=InferenceMethod.RULE,
            rationale=rationale,
            normalized_value=normalized_value,
            original_value=original_value,
            source_tag=source_tag,
            identifier_kind=identifier_kind,
            email_local=email_local,
            email_domain=email_domain,
            fingerprint_tokens=fingerprint_tokens or [],
        )
    )
