"""Schema validation for evidence packages and provisional inputs."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from switchboard.clerk.adapters.upstream import ProvisionalBundle, ProvisionalCallSession
from switchboard.clerk.errors import PackagingError
from switchboard.clerk.fixtures.synthetic_calls import synthetic_bundles
from switchboard.clerk.packaging import package_bundle
from switchboard.clerk.schemas.evidence import EvidencePackage, ReportedCallerMetadata
from switchboard.clerk.schemas.provenance import (
    Confidence,
    EpistemicLayer,
    FactClass,
    PackageScope,
)


UTC = timezone.utc


def _packages() -> list[EvidencePackage]:
    return [package_bundle(bundle) for bundle in synthetic_bundles()]


def test_synthetic_packages_round_trip() -> None:
    for package in _packages():
        assert package.synthetic is True
        assert package.generator == "clerk"
        assert package.upstream_input_schema == "clerk.provisional_upstream.v0"
        restored = EvidencePackage.model_validate_json(package.model_dump_json())
        assert restored == package


def test_fact_classes_stay_on_their_epistemic_layers() -> None:
    single, campaign, incident = _packages()
    call = single.calls[0]
    assert call.reported_caller_metadata.fact_class is FactClass.REPORTED_CALLER_METADATA
    assert call.reported_caller_metadata.epistemic is EpistemicLayer.RAW_OBSERVATION
    spoken = {item.identifier_id: item for item in call.spoken_identifiers}
    assert spoken["syn-spk-003"].fact_class is FactClass.SPOKEN_IDENTIFIER
    assert spoken["syn-spk-003"].value == "1-800-555-0199"
    observations = {item.observation_id: item for item in call.observations}
    assert observations["syn-obs-001"].confirmed is True
    assert observations["syn-obs-001"].fact_class is FactClass.CONFIRMED_OBSERVATION
    assert observations["syn-obs-001"].epistemic is EpistemicLayer.RAW_OBSERVATION
    assert observations["syn-obs-002"].confirmed is False
    assert observations["syn-obs-002"].fact_class is FactClass.RAW_OBSERVATION
    assert observations["syn-obs-003"].confirmed is False
    assert observations["syn-obs-003"].fact_class is FactClass.DERIVED_INTERPRETATION
    assert observations["syn-obs-003"].epistemic is EpistemicLayer.DERIVED_INTERPRETATION
    assert campaign.campaign is not None
    assert campaign.campaign.fact_class is FactClass.DERIVED_ASSOCIATION
    assert campaign.campaign.epistemic is EpistemicLayer.CAMPAIGN_ATTRIBUTION
    assert incident.incident is not None
    assert incident.incident.fact_class is FactClass.DERIVED_INTERPRETATION
    assert incident.campaign is None
    assert single.incident is None


def test_duration_mismatch_is_rejected() -> None:
    package = _packages()[0]
    data = package.model_dump()
    data["calls"][0]["duration_seconds"] = 1
    with pytest.raises(ValidationError):
        EvidencePackage.model_validate(data)


def test_extra_fields_are_rejected() -> None:
    package = _packages()[0]
    data = package.model_dump()
    data["analyst_note"] = "added outside the schema"
    with pytest.raises(ValidationError):
        EvidencePackage.model_validate(data)


def test_confirmed_flag_cannot_drift_from_fact_class() -> None:
    package = _packages()[0]
    data = package.model_dump()
    data["calls"][0]["observations"][0]["confirmed"] = False
    with pytest.raises(ValidationError):
        EvidencePackage.model_validate(data)


def test_reported_metadata_cannot_be_relabeled() -> None:
    with pytest.raises(ValidationError):
        ReportedCallerMetadata.model_validate(
            {
                "fact_class": FactClass.DERIVED_ASSOCIATION.value,
                "epistemic": EpistemicLayer.CAMPAIGN_ATTRIBUTION.value,
            }
        )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProvisionalCallSession(
            call_id="test-call",
            started_at=datetime(2026, 1, 1),
            ended_at=datetime(2026, 1, 1, 0, 1),
            duration_seconds=60,
        )


@pytest.mark.parametrize("score", [True, False, -0.1, 1.1, math.nan, math.inf, "high"])
def test_confidence_score_must_be_a_unit_interval_number(score: object) -> None:
    with pytest.raises(ValidationError):
        Confidence.model_validate({"level": "high", "score": score, "basis": "supplied"})


def test_orphan_observation_is_not_dropped() -> None:
    bundle = synthetic_bundles()[0]
    orphan = bundle.observations[0].model_copy(
        update={"observation_id": "syn-obs-orphan", "call_id": "syn-call-missing"}
    )
    bad = bundle.model_copy(update={"observations": [*bundle.observations, orphan]})
    with pytest.raises(PackagingError, match="outside the bundle"):
        package_bundle(bad)


def test_minimal_package_leaves_absent_fields_empty() -> None:
    bundle = ProvisionalBundle(
        package_id="test-pkg-empty",
        synthetic=True,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        scope=PackageScope.SINGLE_CALL,
        calls=[
            ProvisionalCallSession(
                call_id="test-call-1",
                started_at=datetime(2026, 1, 1, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
                duration_seconds=60,
            )
        ],
    )
    package = package_bundle(bundle)
    call = package.calls[0]
    assert call.reported_caller_metadata.displayed_caller_number is None
    assert call.spoken_identifiers == []
    assert call.observations == []
    assert package.campaign is None
    assert package.incident is None
    assert package.synthetic is True
