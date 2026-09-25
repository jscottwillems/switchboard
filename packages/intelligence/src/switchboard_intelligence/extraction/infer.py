"""Rule inferences. These are judgments, not additional transcript spans."""

from collections import defaultdict
from collections.abc import Sequence
from typing import assert_never

from switchboard_intelligence.extraction import confidence
from switchboard_intelligence.extraction.spans import stable_id
from switchboard_intelligence.schemas.inference import Inference, InferenceKind, InferenceMethod
from switchboard_intelligence.schemas.observation import Observation, ObservationKind

_OFFER_KINDS = (
    ObservationKind.FEES,
    ObservationKind.LOAN_AMOUNTS,
    ObservationKind.RATES,
)


def infer_from_observations(call_id: str, observations: Sequence[Observation]) -> list[Inference]:
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
        "Urgency language is treated as a pressure tactic.",
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
    return sorted(built, key=lambda item: item.kind.value)


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
    if kind is InferenceKind.CALLBACK_CHANNEL:
        return f"Caller offered a callback channel at {values}."
    if kind is InferenceKind.OFFER_TERMS:
        return f"Offer terms mentioned: {values}."
    if kind is InferenceKind.OTHER:
        return f"Unclassified inference from {values}."
    assert_never(kind)
