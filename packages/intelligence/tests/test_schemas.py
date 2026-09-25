"""Schema contracts for Observation, Inference, and Attribution."""

import pytest
from pydantic import ValidationError

from switchboard_intelligence.schemas import (
    SCHEMA_VERSION,
    Attribution,
    AttributionStatus,
    AttributionSubject,
    Inference,
    InferenceKind,
    InferenceMethod,
    IntelligenceBundle,
    Observation,
    ObservationKind,
    SpeakerRole,
    Transcript,
    TranscriptSegment,
)


def _observation() -> Observation:
    return Observation(
        observation_id="obs_test",
        call_id="call-1",
        kind=ObservationKind.CALLBACK_NUMBERS,
        value="(800) 555-0100",
        normalized_value="+18005550100",
        source="deterministic.rules/v1#phone",
        transcript_segment_id="seg-1",
        start_timestamp=1.0,
        end_timestamp=2.0,
        char_start=0,
        char_end=14,
        confidence=0.97,
    )


def _inference() -> Inference:
    return Inference(
        inference_id="inf_test",
        call_id="call-1",
        kind=InferenceKind.CALLBACK_CHANNEL,
        proposition="Caller offered a callback channel at (800) 555-0100.",
        supporting_observation_ids=["obs_test"],
        confidence=0.88,
        method=InferenceMethod.RULE,
        rationale="A callback number is a channel.",
    )


def test_observation_requires_span_source_and_confidence() -> None:
    observation = _observation()
    assert observation.schema_version == SCHEMA_VERSION
    assert observation.record_type == "observation"
    dumped = observation.model_dump()
    for field in (
        "value",
        "source",
        "transcript_segment_id",
        "start_timestamp",
        "end_timestamp",
        "confidence",
    ):
        assert field in dumped
    Observation.model_validate(dumped)


@pytest.mark.parametrize(
    "missing",
    [
        "value",
        "source",
        "transcript_segment_id",
        "start_timestamp",
        "end_timestamp",
        "confidence",
    ],
)
def test_observation_rejects_missing_required_field(missing: str) -> None:
    payload = _observation().model_dump()
    payload.pop(missing)
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_observation_rejects_confidence_outside_unit_interval() -> None:
    payload = _observation().model_dump()
    payload["confidence"] = 1.2
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_records_are_not_interchangeable() -> None:
    observation = _observation()
    inference = _inference()
    attribution = Attribution(
        attribution_id="atr_test",
        call_id="call-1",
        subject_type=AttributionSubject.CAMPAIGN,
        subject_key="camp-1",
        subject_label="Example kit",
        supporting_observation_ids=["obs_test"],
        confidence=0.4,
        status=AttributionStatus.HYPOTHESIZED,
        rationale="Fixture only.",
    )
    with pytest.raises(ValidationError):
        Inference.model_validate(observation.model_dump())
    with pytest.raises(ValidationError):
        Observation.model_validate(inference.model_dump())
    with pytest.raises(ValidationError):
        Attribution.model_validate(observation.model_dump())
    assert observation.record_type != inference.record_type
    assert inference.record_type != attribution.record_type
    assert "transcript_segment_id" not in Inference.model_fields
    assert "transcript_segment_id" not in Attribution.model_fields
    assert "char_start" not in Inference.model_fields


def test_attribution_requires_support() -> None:
    with pytest.raises(ValidationError):
        Attribution(
            attribution_id="atr_test",
            call_id="call-1",
            subject_type=AttributionSubject.UNKNOWN,
            subject_key="unattributed",
            subject_label="Unattributed",
            confidence=0.1,
            status=AttributionStatus.HYPOTHESIZED,
            rationale="No evidence.",
        )


def test_transcript_adapter_rejects_duplicate_segments() -> None:
    segment = TranscriptSegment(
        segment_id="seg-1",
        speaker=SpeakerRole.SCAMMER,
        text="Hello.",
        start_timestamp=0,
        end_timestamp=1,
    )
    with pytest.raises(ValidationError):
        Transcript(call_id="call-1", segments=[segment, segment])


def test_bundle_rejects_mismatched_call_id() -> None:
    observation = _observation()
    with pytest.raises(ValidationError):
        IntelligenceBundle(call_id="other-call", observations=[observation], inferences=[], attributions=[])


def test_observation_kind_values_are_stable() -> None:
    assert [kind.value for kind in ObservationKind] == [
        "claimed_company",
        "claimed_agent",
        "claimed_department",
        "callback_numbers",
        "spoken_numbers",
        "domains",
        "urls",
        "email_addresses",
        "loan_amounts",
        "rates",
        "fees",
        "requested_information",
        "payment_methods",
        "script_phrases",
        "urgency_language",
        "transfer_events",
        "pretext_category",
        "case_or_reference_ids",
        "threat_or_consequence_language",
        "remote_access_tools",
        "spoofed_authority_claims",
        "follow_up_promises",
        "other",
    ]
