"""Deterministic extractor behavior, including gaps left for a model."""

import pytest

from switchboard_intelligence.extraction import confidence
from switchboard_intelligence.extraction.attribute import NoCampaignCorpusAttributor
from switchboard_intelligence.extraction.coverage import DETERMINISTIC_COVERAGE, MODEL_GAPS
from switchboard_intelligence.extraction.lexicon import (
    DEPARTMENTS,
    ORGANIZATIONS,
    PAYMENT_PHRASES,
    REQUEST_TARGETS,
    SCRIPT_PHRASES,
    TRANSFER_PHRASES,
    URGENCY_PHRASES,
)
from switchboard_intelligence.extraction.model import NullModelExtractor
from switchboard_intelligence.extraction.pipeline import extract_intelligence
from switchboard_intelligence.schemas import (
    Observation,
    ObservationKind,
    SpeakerRole,
    Transcript,
    TranscriptSegment,
)
from switchboard_intelligence.schemas.attribution import (
    Attribution,
    AttributionStatus,
    AttributionSubject,
)

RULE_CONFIDENCE = {
    confidence.PHONE,
    confidence.EMAIL,
    confidence.URL,
    confidence.DOMAIN_FROM_URL,
    confidence.DOMAIN_FROM_EMAIL,
    confidence.BARE_DOMAIN,
    confidence.MONEY,
    confidence.RATE,
    confidence.LEXICON,
    confidence.COMPANY,
    confidence.AGENT,
    confidence.REQUESTED,
    confidence.OTHER_ID,
    confidence.TRANSFER,
}


def _transcript(text: str, *, speaker: SpeakerRole = SpeakerRole.SCAMMER) -> Transcript:
    return Transcript(
        call_id="unit-1",
        segments=[
            TranscriptSegment(
                segment_id="unit-1-s00",
                speaker=speaker,
                text=text,
                start_timestamp=0.0,
                end_timestamp=4.0,
            )
        ],
    )


def _only(text: str, kind: ObservationKind) -> list[Observation]:
    observations = extract_intelligence(_transcript(text)).observations
    assert observations, text
    assert {item.kind for item in observations} == {kind}
    return observations


@pytest.mark.parametrize("phrase", URGENCY_PHRASES)
def test_urgency_lexicon(phrase: str) -> None:
    found = _only(f"Note: {phrase}.", ObservationKind.URGENCY_LANGUAGE)
    assert found[0].value.casefold() == phrase.casefold()


@pytest.mark.parametrize("phrase", SCRIPT_PHRASES)
def test_script_lexicon(phrase: str) -> None:
    found = _only(f"Note: {phrase}.", ObservationKind.SCRIPT_PHRASES)
    assert found[0].value.casefold() == phrase.casefold()


@pytest.mark.parametrize("phrase", PAYMENT_PHRASES)
def test_payment_lexicon(phrase: str) -> None:
    found = _only(f"Note: {phrase}.", ObservationKind.PAYMENT_METHODS)
    assert found[0].value.casefold() == phrase.casefold()


@pytest.mark.parametrize("phrase", DEPARTMENTS)
def test_department_lexicon(phrase: str) -> None:
    found = _only(f"Note: {phrase}.", ObservationKind.CLAIMED_DEPARTMENT)
    assert found[0].value.casefold() == phrase.casefold()


@pytest.mark.parametrize("phrase", TRANSFER_PHRASES)
def test_transfer_lexicon(phrase: str) -> None:
    found = _only(f"Note: {phrase}.", ObservationKind.TRANSFER_EVENTS)
    assert found[0].value.casefold() == phrase.casefold()


@pytest.mark.parametrize("phrase", REQUEST_TARGETS)
def test_requested_information_needs_an_ask(phrase: str) -> None:
    found = _only(
        f"Please provide your {phrase} today.",
        ObservationKind.REQUESTED_INFORMATION,
    )
    assert found[0].value.casefold() == phrase.casefold()
    assert extract_intelligence(_transcript(f"We discussed {phrase} yesterday.")).observations == []


@pytest.mark.parametrize("organization", ORGANIZATIONS)
def test_claimed_company_needs_a_cue(organization: str) -> None:
    found = _only(
        f"I am calling from {organization} today.",
        ObservationKind.CLAIMED_COMPANY,
    )
    assert found[0].value == organization
    assert extract_intelligence(_transcript(f"People mention {organization} often.")).observations == []


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("My name is Helen Brooks today.", "Helen Brooks"),
        ("Officer Marcus Hale stopped by.", "Marcus Hale"),
        ("Detective Priya Nandak reviewed it.", "Priya Nandak"),
        ("Agent Owen Clarke left a message.", "Owen Clarke"),
    ],
)
def test_claimed_agent_names(text: str, value: str) -> None:
    found = _only(text, ObservationKind.CLAIMED_AGENT)
    assert found[0].value == value


@pytest.mark.parametrize(
    "phone",
    [
        "(800) 555-0100",
        "888-555-0101",
        "877.555.0102",
        "+1 866 555 0103",
        "1-855-555-0104",
    ],
)
def test_callback_and_spoken_phone_formats(phone: str) -> None:
    callback = _only(f"Please call us back at {phone} today.", ObservationKind.CALLBACK_NUMBERS)
    spoken = _only(f"The desk line on file is {phone} today.", ObservationKind.SPOKEN_NUMBERS)
    assert callback[0].normalized_value.startswith("+1")
    assert len(callback[0].normalized_value) == 12
    assert spoken[0].normalized_value == callback[0].normalized_value
    assert callback[0].value == phone


def test_email_url_and_domain_sources() -> None:
    email = extract_intelligence(
        _transcript("Email refunds@irs-notice-example.com for the form.")
    ).observations
    by_kind = {item.kind: item for item in email}
    assert by_kind[ObservationKind.EMAIL_ADDRESSES].value == "refunds@irs-notice-example.com"
    assert by_kind[ObservationKind.DOMAINS].value == "irs-notice-example.com"
    assert by_kind[ObservationKind.DOMAINS].source.endswith("#email_domain")

    url = extract_intelligence(
        _transcript("Open https://irs-notice-example.com/case/IR-44000 for the form.")
    ).observations
    by_kind = {item.kind: item for item in url}
    assert by_kind[ObservationKind.URLS].value == "https://irs-notice-example.com/case/IR-44000"
    assert by_kind[ObservationKind.DOMAINS].source.endswith("#url_domain")

    bare = _only("Type irs-notice-example.com into a browser.", ObservationKind.DOMAINS)
    assert bare[0].source.endswith("#bare_domain")


def test_fee_loan_and_rate_need_cues() -> None:
    fee = _only("The processing fee is $49.95.", ObservationKind.FEES)
    loan = _only("You are approved for a loan of $12,500.", ObservationKind.LOAN_AMOUNTS)
    rate = _only("The interest rate is 4.25%.", ObservationKind.RATES)
    assert fee[0].normalized_value == "49.95"
    assert loan[0].normalized_value == "12500.00"
    assert rate[0].normalized_value == "4.25%"
    assert extract_intelligence(_transcript("The balance shows $40 on the screen.")).observations == []
    assert extract_intelligence(_transcript("I am 100% sure about that.")).observations == []


def test_other_identifier_and_nearest_money_cue() -> None:
    other = _only("Your case number IR-44921 is open.", ObservationKind.OTHER)
    assert other[0].value == "IR-44921"
    assert other[0].normalized_value == "IR-44921"
    mixed = extract_intelligence(
        _transcript("You are approved for a loan of $12,500 after a processing fee of $49.95.")
    ).observations
    kinds = {item.value: item.kind for item in mixed}
    assert kinds["$12,500"] is ObservationKind.LOAN_AMOUNTS
    assert kinds["$49.95"] is ObservationKind.FEES


@pytest.mark.parametrize(
    "text",
    [
        "I am 100% committed to resolving this today, and the extension is 12.",
        "Call eight hundred five five five zero one nine nine when you can.",
        "The fee is forty nine dollars if you want to move forward.",
        "You should probably hurry because this will not stay open forever.",
        "Visit our site at secure payments dot com for details.",
    ],
)
def test_model_gaps_are_not_extracted(text: str) -> None:
    assert extract_intelligence(_transcript(text)).observations == []


def test_coverage_mentions_every_kind() -> None:
    assert set(DETERMINISTIC_COVERAGE) == set(ObservationKind)
    assert MODEL_GAPS


def test_extraction_is_idempotent_and_anchored() -> None:
    transcript = _transcript("Please call us back at (800) 555-0100 about the processing fee of $49.95.")
    first = extract_intelligence(transcript)
    second = extract_intelligence(transcript)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    segment = transcript.segments[0]
    for observation in first.observations:
        assert observation.confidence in RULE_CONFIDENCE
        assert segment.text[observation.char_start : observation.char_end] == observation.value
        assert segment.start_timestamp <= observation.start_timestamp <= observation.end_timestamp
        assert observation.end_timestamp <= segment.end_timestamp


def test_null_model_extractor_adds_nothing() -> None:
    transcript = _transcript("Please call us back at (800) 555-0100 today.")
    plain = extract_intelligence(transcript)
    with_null = extract_intelligence(transcript, model_extractor=NullModelExtractor())
    assert plain.model_dump() == with_null.model_dump()
    assert NullModelExtractor().extract(transcript, plain.observations) == []


def test_model_extractor_can_add_a_span() -> None:
    transcript = _transcript("Please call us back at (800) 555-0100 today.")

    class Marker:
        name = "model.test"

        def extract(self, transcript: Transcript, deterministic: list[Observation]) -> list[Observation]:
            segment = transcript.segments[0]
            start = segment.text.index("today")
            end = start + len("today")
            return [
                Observation(
                    observation_id="obs_model_today",
                    call_id=transcript.call_id,
                    kind=ObservationKind.OTHER,
                    value="today",
                    normalized_value="TODAY",
                    source="model.test",
                    transcript_segment_id=segment.segment_id,
                    start_timestamp=3.0,
                    end_timestamp=4.0,
                    char_start=start,
                    char_end=end,
                    confidence=0.55,
                )
            ]

    bundle = extract_intelligence(transcript, model_extractor=Marker())
    sources = {item.source for item in bundle.observations}
    assert "model.test" in sources
    assert any(item.source.startswith("deterministic.rules/v1#") for item in bundle.observations)


def test_default_attributor_returns_nothing() -> None:
    transcript = _transcript("I am calling from Medicare today.")
    bundle = extract_intelligence(transcript)
    assert bundle.attributions == []
    assert bundle.inferences
    assert all(item.record_type == "inference" for item in bundle.inferences)
    assert all(item.record_type == "observation" for item in bundle.observations)


def test_custom_attributor_is_invoked() -> None:
    transcript = _transcript("I am calling from Medicare today.")

    class MarkerAttributor:
        name = "attribution.test"

        def attribute(self, call_id: str, observations: list[Observation], inferences: list) -> list[Attribution]:
            return [
                Attribution(
                    attribution_id="atr_test",
                    call_id=call_id,
                    subject_type=AttributionSubject.SCRIPT_FAMILY,
                    subject_key="medicare-kit",
                    subject_label="Medicare kit",
                    supporting_observation_ids=[observations[0].observation_id],
                    supporting_inference_ids=[inferences[0].inference_id],
                    confidence=0.42,
                    status=AttributionStatus.HYPOTHESIZED,
                    rationale="Test double.",
                )
            ]

    bundle = extract_intelligence(transcript, attributor=MarkerAttributor())
    assert len(bundle.attributions) == 1
    assert bundle.attributions[0].record_type == "attribution"
    assert NoCampaignCorpusAttributor().attribute("x", [], []) == []
