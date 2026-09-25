"""Rule inferences. These are judgments, not additional transcript spans."""

from collections import defaultdict
from collections.abc import Sequence
from typing import assert_never

from switchboard_intelligence.extraction import confidence
from switchboard_intelligence.extraction.derive import derive_correlation
from switchboard_intelligence.extraction.spans import stable_id
from switchboard_intelligence.schemas.inference import Inference, InferenceKind, InferenceMethod
from switchboard_intelligence.schemas.observation import Observation, ObservationKind
from switchboard_intelligence.schemas.transcript import Transcript

_OFFER_KINDS = (
    ObservationKind.FEES,
    ObservationKind.LOAN_AMOUNTS,
    ObservationKind.RATES,
)


def infer_from_observations(
    call_id: str,
    observations: Sequence[Observation],
    transcript: Transcript | None = None,
) -> list[Inference]:
    grouped: dict[ObservationKind, list[Observation]] = defaultdict(list)
    for observation in observations:
        if observation.call_id != call_id:
            raise ValueError("observation call_id does not match the inference call")
        grouped[observation.kind].append(observation)

    built: list[Inference] = []
    _add(
        built,
        call_id,
        InferenceKind.IMPERSONATED_ORGANIZATION,
        grouped.get(ObservationKind.CLAIMED_COMPANY, []),
        confidence.IMPERSONATED_ORGANIZATION,
        "A claimed company is treated as the organization being impersonated.",
    )
    _add(
        built,
        call_id,
        InferenceKind.PAYMENT_RAIL,
        grouped.get(ObservationKind.PAYMENT_METHODS, []),
        confidence.PAYMENT_RAIL,
        "A named payment method is treated as the cash-out rail.",
    )
    _add(
        built,
        call_id,
        InferenceKind.DATA_TARGET,
        grouped.get(ObservationKind.REQUESTED_INFORMATION, []),
        confidence.DATA_TARGET,
        "Requested information is treated as the data the caller wants.",
    )
    _add(
        built,
        call_id,
        InferenceKind.PRESSURE_TACTIC,
        grouped.get(ObservationKind.URGENCY_LANGUAGE, []),
        confidence.PRESSURE_TACTIC,
        "Urgency language is treated as time pressure, separate from threats.",
    )
    _add(
        built,
        call_id,
        InferenceKind.THREATENED_CONSEQUENCE,
        grouped.get(ObservationKind.THREAT_OR_CONSEQUENCE_LANGUAGE, []),
        confidence.THREATENED_CONSEQUENCE,
        "Threat language is treated as a stated consequence, separate from urgency.",
    )
    _add(
        built,
        call_id,
        InferenceKind.CALLBACK_CHANNEL,
        grouped.get(ObservationKind.CALLBACK_NUMBERS, []),
        confidence.CALLBACK_CHANNEL,
        "A callback number is treated as a channel back to the operation.",
    )
    offer_support: list[Observation] = []
    for kind in _OFFER_KINDS:
        offer_support.extend(grouped.get(kind, []))
    _add(
        built,
        call_id,
        InferenceKind.OFFER_TERMS,
        offer_support,
        confidence.OFFER_TERMS,
        "Fees, loan amounts, and rates are treated as the offer terms.",
    )
    built.extend(derive_correlation(call_id, observations, transcript))
    return sorted(
        built,
        key=lambda item: (
            item.kind.value,
            item.normalized_value or "",
            item.source_tag.value if item.source_tag is not None else "",
            item.identifier_kind.value if item.identifier_kind is not None else "",
            item.inference_id,
        ),
    )


def _add(
    built: list[Inference],
    call_id: str,
    kind: InferenceKind,
    support: Sequence[Observation],
    score: float,
    rationale: str,
) -> None:
    if not support:
        return
    support_ids = sorted({item.observation_id for item in support})
    inference_id = stable_id("inf", f"{call_id}|{kind.value}|{'|'.join(support_ids)}")
    built.append(
        Inference(
            inference_id=inference_id,
            call_id=call_id,
            kind=kind,
            proposition=_proposition(kind, support),
            supporting_observation_ids=support_ids,
            confidence=score,
            method=InferenceMethod.RULE,
            rationale=rationale,
        )
    )


def _proposition(kind: InferenceKind, support: Sequence[Observation]) -> str:
    ordered = sorted(support, key=lambda item: (item.normalized_value, item.value))
    seen: list[str] = []
    for item in ordered:
        if item.value not in seen:
            seen.append(item.value)
    values = ", ".join(seen)
    if kind is InferenceKind.IMPERSONATED_ORGANIZATION:
        return f"Caller claims to represent {values}."
    if kind is InferenceKind.PAYMENT_RAIL:
        return f"Caller is steering payment through {values}."
    if kind is InferenceKind.DATA_TARGET:
        return f"Caller is asking for {values}."
    if kind is InferenceKind.PRESSURE_TACTIC:
        return f"Caller is applying pressure with: {values}."
    if kind is InferenceKind.THREATENED_CONSEQUENCE:
        return f"Caller threatened: {values}."
    if kind is InferenceKind.CALLBACK_CHANNEL:
        return f"Caller offered a callback channel at {values}."
    if kind is InferenceKind.OFFER_TERMS:
        return f"Offer terms mentioned: {values}."
    if kind is InferenceKind.CLAIMED_COMPANY_NORMALIZED:
        return f"Normalized claimed company from {values}."
    if kind is InferenceKind.PHONE_E164:
        return f"E.164 phone from {values}."
    if kind is InferenceKind.DOMAIN_REGISTRABLE:
        return f"Registrable domain from {values}."
    if kind is InferenceKind.EMAIL_LOCAL_DOMAIN:
        return f"Email split from {values}."
    if kind is InferenceKind.EMAIL_DOMAIN_REGISTRABLE:
        return f"Email registrable domain from {values}."
    if kind is InferenceKind.SCRIPT_PHRASE_NORMALIZED:
        return f"Normalized script phrase from {values}."
    if kind is InferenceKind.OPENING_SCRIPT_FINGERPRINT:
        return f"Opening fingerprint from {values}."
    if kind is InferenceKind.PRETEXT_CATEGORY_CANONICAL:
        return f"Canonical pretext from {values}."
    if kind is InferenceKind.IDENTIFIER_KIND:
        return f"Identifier kind from {values}."
    if kind is InferenceKind.OTHER:
        return f"Unclassified inference from {values}."
    assert_never(kind)
