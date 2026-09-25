"""Turn a completed call plus Sherlock findings into scoreable features."""

import re

from switchboard_schemas.enums import FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding

from watson.config import ScoringConfig
from watson.models import CallFeatures, CompletedCall, assert_never
from watson.textutil import (
    normalize_domain,
    normalize_organization,
    normalize_phrase,
    opening_span,
    tokenize,
)

# Literal E.164. Formatted NANP text is not a callback finding.
_E164 = re.compile(r"^\+[1-9]\d{1,14}$")


def extract_features(
    call: CompletedCall,
    findings: list[IntelligenceFinding],
    config: ScoringConfig | None = None,
) -> CallFeatures:
    """Build a feature vector from admitted findings and the call record."""
    active = config or ScoringConfig()
    admitted = admitted_findings(findings, active)
    buckets = _empty_buckets()
    for finding in admitted:
        _apply_finding(buckets, finding)

    opening = opening_span(call.transcript, active.opening_word_count)
    return CallFeatures(
        call_id=call.call_id,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        callback_number=frozenset(buckets["callback_number"]),
        organization_name=frozenset(buckets["organization_name"]),
        url=frozenset(buckets["url"]),
        payment_method=frozenset(buckets["payment_method"]),
        other=frozenset(buckets["other"]),
        pretext=frozenset(buckets["pretext"]),
        person_name=frozenset(buckets["person_name"]),
        opening_text=opening,
        opening_tokens=tokenize(opening),
        transcript_tokens=tokenize(call.transcript),
    )


def admitted_findings(
    findings: list[IntelligenceFinding],
    config: ScoringConfig,
) -> list[IntelligenceFinding]:
    """Proposed or accepted findings that clear the confidence floor."""
    kept: list[IntelligenceFinding] = []
    for finding in findings:
        if finding.confidence < config.min_observation_confidence:
            continue
        if not _status_counts(finding.status):
            continue
        kept.append(finding)
    return kept


def _status_counts(status: FindingStatus) -> bool:
    match status:
        case FindingStatus.PROPOSED | FindingStatus.ACCEPTED:
            return True
        case FindingStatus.REJECTED:
            return False
        case _:
            assert_never(status)


def _empty_buckets() -> dict[str, set[str]]:
    return {
        "callback_number": set(),
        "organization_name": set(),
        "url": set(),
        "payment_method": set(),
        "other": set(),
        "pretext": set(),
        "person_name": set(),
    }


def _apply_finding(buckets: dict[str, set[str]], finding: IntelligenceFinding) -> None:
    kind = finding.kind
    match kind:
        case FindingKind.CALLBACK_NUMBER:
            if _E164.fullmatch(finding.value):
                buckets["callback_number"].add(finding.value)
        case FindingKind.ORGANIZATION_NAME:
            name = normalize_organization(finding.value)
            if name:
                buckets["organization_name"].add(name)
        case FindingKind.URL:
            host = normalize_domain(finding.value)
            if host:
                buckets["url"].add(host)
        case FindingKind.PAYMENT_METHOD:
            method = normalize_phrase(finding.value)
            if method:
                buckets["payment_method"].add(method)
        case FindingKind.OTHER:
            token = normalize_phrase(finding.value).replace(" ", "")
            if token:
                buckets["other"].add(token)
        case FindingKind.PRETEXT:
            label = finding.value.strip()
            if label:
                buckets["pretext"].add(label)
        case FindingKind.PERSON_NAME:
            name = finding.value.strip()
            if name:
                buckets["person_name"].add(name)
        case _:
            assert_never(kind)
