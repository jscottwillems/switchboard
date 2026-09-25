"""Derived correlation features Watson scores, separate from raw spans."""

from switchboard_intelligence.extraction.normalize import (
    normalize_company_name,
    normalize_script_phrase,
    registrable_domain,
)
from switchboard_intelligence.extraction.pipeline import extract_intelligence
from switchboard_intelligence.schemas import (
    CampaignAssociation,
    IdentifierKind,
    InferenceKind,
    ObservationKind,
    PhoneSourceTag,
    ScriptLocale,
    SpeakerRole,
    Transcript,
    TranscriptSegment,
)
from switchboard_intelligence.schemas.campaign import AssociationReason


def _call(segments: list[tuple[str, str]]) -> Transcript:
    built = []
    for index, (speaker, text) in enumerate(segments):
        built.append(
            TranscriptSegment(
                segment_id=f"corr-s{index:02d}",
                speaker=SpeakerRole(speaker),
                text=text,
                start_timestamp=float(index),
                end_timestamp=float(index) + 1.0,
            )
        )
    return Transcript(call_id="corr-1", segments=built)


def test_company_normalization_strips_legal_suffixes() -> None:
    assert normalize_company_name("Bank of America, Inc.") == "bank of america"
    assert normalize_company_name("Acme Payments, L.L.C.") == "acme payments"
    assert normalize_company_name("  Geek   Squad Corp. ") == "geek squad"
    assert normalize_company_name("Internal Revenue Service") == "internal revenue service"


def test_registrable_domain_keeps_multipart_suffixes() -> None:
    assert registrable_domain("www.mail.example.co.uk") == "example.co.uk"
    assert registrable_domain("irs-notice-example.com") == "irs-notice-example.com"
    assert registrable_domain("mail.irs-notice-example.com") == "irs-notice-example.com"


def test_script_phrase_keeps_words_and_drops_punctuation() -> None:
    assert normalize_script_phrase("This is an important message!") == "this is an important message"


def test_correlation_inferences_from_a_short_call() -> None:
    transcript = _call(
        [
            ("system", "Press 1 for claims. Press 2 for a representative."),
            ("scammer", "This is an important message."),
            ("scammer", "The purpose of this call is your tax compliance matter."),
            ("scammer", "I am calling from Bank of America, Inc. today."),
            ("scammer", "Please call us back at (800) 555-0100 today."),
            ("scammer", "The desk line on file is 202-555-0199."),
            ("scammer", "Your caller ID will show 844-555-0300 on this call."),
            ("scammer", "Email refunds@mail.irs-notice-example.com for the form."),
            ("scammer", "Your case number IR-44921 is open."),
            ("scammer", "My badge number BD-44921 is on file."),
            ("scammer", "Your social security number ending in 4321 is on the file."),
            ("scammer", "Your account number AC-10023 is open."),
            ("scammer", "Let me transfer you to the fraud department."),
        ]
    )
    bundle = extract_intelligence(transcript)
    kinds = {item.kind for item in bundle.observations}
    assert ObservationKind.IVR_PROMPTS in kinds
    assert ObservationKind.IVR_MENU_PATH in kinds
    assert ObservationKind.SPOKEN_CLI_CLAIM in kinds
    assert ObservationKind.OPENING_SCRIPT_TEXT in kinds
    assert ObservationKind.SCRIPT_LANGUAGE in kinds
    assert ObservationKind.TRANSFER_DESTINATION_CLAIMED in kinds

    by_kind = {}
    for item in bundle.inferences:
        by_kind.setdefault(item.kind, []).append(item)

    company = by_kind[InferenceKind.CLAIMED_COMPANY_NORMALIZED][0]
    assert company.normalized_value == "bank of america"
    assert company.original_value == "Bank of America, Inc."

    phones = {(item.normalized_value, item.source_tag) for item in by_kind[InferenceKind.PHONE_E164]}
    assert phones == {
        ("+18005550100", PhoneSourceTag.CALLBACK),
        ("+12025550199", PhoneSourceTag.SPOKEN),
        ("+18445550300", PhoneSourceTag.SPOKEN_CLI),
    }

    domains = {item.normalized_value for item in by_kind[InferenceKind.DOMAIN_REGISTRABLE]}
    assert "irs-notice-example.com" in domains

    email = by_kind[InferenceKind.EMAIL_LOCAL_DOMAIN][0]
    assert email.email_local == "refunds"
    assert email.email_domain == "mail.irs-notice-example.com"
    assert by_kind[InferenceKind.EMAIL_DOMAIN_REGISTRABLE][0].normalized_value == "irs-notice-example.com"

    phrases = {item.normalized_value: item.original_value for item in by_kind[InferenceKind.SCRIPT_PHRASE_NORMALIZED]}
    assert phrases["this is an important message"] == "This is an important message"

    fingerprint = by_kind[InferenceKind.OPENING_SCRIPT_FINGERPRINT][0]
    assert fingerprint.fingerprint_tokens[:5] == ["this", "is", "an", "important", "message"]

    pretext = by_kind[InferenceKind.PRETEXT_CATEGORY_CANONICAL][0]
    assert pretext.normalized_value == "tax"
    assert pretext.original_value == "your tax compliance matter"

    labels = {item.identifier_kind for item in by_kind[InferenceKind.IDENTIFIER_KIND]}
    assert labels == {
        IdentifierKind.CASE,
        IdentifierKind.BADGE,
        IdentifierKind.SSN_LAST4,
        IdentifierKind.ACCOUNT,
    }

    language = next(item for item in bundle.observations if item.kind is ObservationKind.SCRIPT_LANGUAGE)
    assert language.locale is ScriptLocale.EN
    openings = [
        item for item in bundle.observations if item.kind is ObservationKind.OPENING_SCRIPT_TEXT
    ]
    assert [item.opening_turn_index for item in openings] == [0, 1, 2]
    assert bundle.attributions == []


def test_explicit_spanish_locale_is_a_span() -> None:
    transcript = _call([("scammer", "Para español, oprima dos.")])
    observations = extract_intelligence(transcript).observations
    language = next(item for item in observations if item.kind is ObservationKind.SCRIPT_LANGUAGE)
    assert language.value.casefold() == "español"
    assert language.locale is ScriptLocale.ES


def test_campaign_association_is_watson_owned_shape() -> None:
    record = CampaignAssociation(
        call_id="corr-1",
        campaign_id="camp-tax-1",
        association_score=0.74,
        reasons=[
            AssociationReason(field="claimed_company_normalized", value="bank of america"),
            AssociationReason(field="phone_e164", value="+18005550100"),
        ],
        feature_scores={"claimed_company_normalized": 0.4, "phone_e164": 0.3},
    )
    assert record.record_type == "campaign_association"
    assert record.reasons[0].field == "claimed_company_normalized"
