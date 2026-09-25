"""Feature extraction from IntelligenceFinding rows."""

import pytest
from switchboard_schemas.enums import FindingKind, FindingStatus

from watson.config import ScoringConfig
from watson.features import admitted_findings, extract_features
from watson.models import CallFeatures
from watson.sherlock.mock import FixtureFindingProvider
from tests.helpers import make_call, make_finding


def test_caller_id_is_not_a_scoring_feature() -> None:
    assert "caller_id" not in CallFeatures.model_fields


def test_low_confidence_findings_are_dropped(config: ScoringConfig) -> None:
    call = make_call("bank-x", "Your account is on hold at First National Bank.")
    findings = [
        make_finding(
            "bank-x",
            FindingKind.ORGANIZATION_NAME,
            "first national bank",
            confidence=0.95,
            extractor="fixture",
        ),
        make_finding(
            "bank-x",
            FindingKind.ORGANIZATION_NAME,
            "internal revenue service",
            confidence=0.15,
            extractor="fixture",
        ),
    ]
    kept = admitted_findings(findings, config)
    assert [item.value for item in kept] == ["first national bank"]
    features = extract_features(
        call,
        FixtureFindingProvider({"bank-x": findings}).findings_for(call),
        config,
    )
    assert features.organization_name == frozenset({"first national bank"})


def test_rejected_findings_are_dropped(config: ScoringConfig) -> None:
    call = make_call("c1", "callback +18005550101")
    finding = make_finding(
        "c1",
        FindingKind.CALLBACK_NUMBER,
        "+18005550101",
        status=FindingStatus.REJECTED,
    )
    assert admitted_findings([finding], config) == []
    features = extract_features(call, [finding], config)
    assert features.callback_number == frozenset()


def test_callback_number_must_be_literal_e164(config: ScoringConfig) -> None:
    call = make_call("c1", "call (800) 555-0101 or +18005550101")
    findings = [
        make_finding("c1", FindingKind.CALLBACK_NUMBER, "(800) 555-0101"),
        make_finding("c1", FindingKind.CALLBACK_NUMBER, "+18005550101"),
    ]
    features = extract_features(call, findings, config)
    assert features.callback_number == frozenset({"+18005550101"})


def test_other_finding_kinds_are_kept(config: ScoringConfig) -> None:
    call = make_call("c1", "hello from the desk")
    findings = [
        make_finding("c1", FindingKind.PRETEXT, "government_refund", extractor="fixture"),
        make_finding("c1", FindingKind.URL, "https://www.irs-refund-help.com/notice", extractor="fixture"),
        make_finding("c1", FindingKind.OTHER, "irf4421", extractor="fixture"),
        make_finding("c1", FindingKind.PAYMENT_METHOD, "direct deposit", extractor="fixture"),
        make_finding("c1", FindingKind.PERSON_NAME, "Jordan", extractor="fixture"),
    ]
    features = extract_features(call, findings, config)
    assert features.pretext == frozenset({"government_refund"})
    assert features.url == frozenset({"irs-refund-help.com"})
    assert features.other == frozenset({"irf4421"})
    assert features.payment_method == frozenset({"direct deposit"})
    assert features.person_name == frozenset({"Jordan"})
