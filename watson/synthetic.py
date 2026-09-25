"""Hand-authored scam-call campaigns used to measure the deterministic scorer.

The JSON file under data/synthetic is this builder's export. Tests fail if
the committed file drifts from `build_dataset()`.
"""

from datetime import datetime, timezone
from pathlib import Path

from watson.dataset import DatasetCallRecord, ScenarioTag, SyntheticDataset, default_dataset_path
from watson.sherlock.models import (
    CorrelationInference,
    EmailSplit,
    Observation,
    ObservationKind,
    PhoneE164,
)
from watson.textutil import (
    normalize_domain,
    normalize_organization,
    normalize_phrase,
    opening_span,
    to_e164,
)

_DESCRIPTION = (
    "Labeled synthetic honeypot calls for WATSON. Ground-truth campaign ids "
    "are independent of the camp-NNNN ids the pipeline assigns. Each call "
    "carries Sherlock-shaped observations and a correlation inference: "
    "phones, case ids, domains, emails, claimed company, calling-from, "
    "opening text, fingerprint, pretext, and phrases. CLI/ANI, timing, and "
    "duration stay on the call record. The set includes near-duplicate "
    "campaigns, unrelated pretexts, partial script overlap that must not "
    "auto-merge, and one caller id reused across two campaigns while "
    "callback numbers and email local-parts rotate inside the IRS campaign."
)

_OPENING_WORDS = 70


def build_dataset() -> SyntheticDataset:
    """Return the canonical synthetic dataset."""
    return SyntheticDataset(version=2, description=_DESCRIPTION, calls=_calls())


def export_dataset(path: Path | None = None) -> SyntheticDataset:
    """Write the canonical dataset as JSON and return it."""
    dataset = build_dataset()
    target = path or default_dataset_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return dataset


def _calls() -> list[DatasetCallRecord]:
    irs_phrases = (
        "federal refund is on hold",
        "filing discrepancy",
        "refund verification department",
    )
    tech_phrases = (
        "microsoft windows license",
        "remote access",
        "support session code",
    )
    bank_phrases = ("suspicious wire transfer", "fraud department")
    solar_phrases = ("residential solar tax credit", "roof assessment")
    insurance_phrases = ("homeowners premium reduction", "policy review department")
    warranty_phrases = (
        "factory warranty is expiring",
        "engine and transmission coverage",
    )
    gift_phrases = ("prepaid gift card", "settlement award")
    survey_phrases = ("volunteer tree planting", "east gate")

    irs_callback = "(800) 555-0101"
    irs_callback_rotated = "(800) 555-0144"
    irs_domain = "https://www.irs-refund-help.com/claim"
    irs_email = "refunds@irs-refund-help.com"
    irs_email_rotated = "desk@irs-refund-help.com"
    repeat_caller = "+15551119999"

    irs_spoken = "eight hundred five five five zero one zero one"
    irs_spoken_rotated = "eight hundred five five five zero one four four"
    irs_1 = _ground(_irs_body("Jordan", irs_spoken), irs_email, irs_domain, irs_callback)
    irs_2 = _ground(_irs_body("Ramirez", irs_spoken), irs_email, irs_domain, irs_callback)
    irs_3 = _ground(_irs_body("Blake", irs_spoken), irs_email, irs_domain, irs_callback)
    irs_4 = _ground(
        _irs_body("Jordan", irs_spoken_rotated),
        irs_email_rotated,
        irs_domain,
        irs_callback_rotated,
    )
    tech_1 = _ground(_tech_body("Jason"), "license@windows-helpdesk.net", "https://windows-helpdesk.net/tool", "(888) 555-0199")
    tech_2 = _ground(_tech_body("Priya"), "license@windows-helpdesk.net", "https://windows-helpdesk.net/tool", "(888) 555-0199")
    tech_3 = _ground(_tech_body("Jason"), "license@windows-helpdesk.net", "https://windows-helpdesk.net/tool", "(888) 555-0199")
    bank_1 = _ground(
        _bank_body("Smith"),
        "fraud@firstnational-alerts.com",
        "https://www.firstnational-alerts.com/fraud",
        "(877) 555-0133",
    )
    bank_2 = _ground(
        _bank_body("Lee"),
        "fraud@firstnational-alerts.com",
        "https://www.firstnational-alerts.com/fraud",
        "(877) 555-0133",
    )
    warranty_1 = _ground(
        _warranty_body("Dana"),
        "plans@national-auto-warranty.com",
        "https://national-auto-warranty.com/plans",
        "(844) 555-0170",
    )
    warranty_2 = _ground(
        _warranty_body("Chris"),
        "coverage@national-auto-warranty.com",
        "https://national-auto-warranty.com/plans",
        "(844) 555-0170",
    )
    solar = _ground(
        _SOLAR_BODY,
        "appointments@sunpath-solar.co",
        "sunpath-solar.co",
        "(866) 555-0121",
    )
    insurance = _ground(
        _INSURANCE_BODY,
        "policy@harbor-insurance-desk.com",
        "harbor-insurance-desk.com",
        "(855) 555-0166",
    )
    gift = _ground(
        _GIFT_BODY,
        "claims@award-claim-center.com",
        "award-claim-center.com",
        "(833) 555-0188",
    )
    survey = _ground(
        _SURVEY_BODY,
        "volunteer@cityparks.example",
        "cityparks.example",
        "(555) 010-0000",
    )

    return [
        _campaign_record(
            "irs-1",
            "2026-04-02T14:00:00",
            "2026-04-02T14:03:30",
            "+15551110001",
            irs_1,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            calling_from="calling from the Internal Revenue Service",
            callback=irs_callback,
            spoken_value=irs_spoken,
            spoken_e164="+18005550101",
            domain=irs_domain,
            email=irs_email,
            phrases=irs_phrases,
            fingerprint="fp-irs-refund-v1",
            pretext="government_refund",
            transfer="refund verification department",
            case_value="IRF four four two one",
            case_normalized="irf4421",
            ivr=["greeting", "ssn_prompt", "refund_agent"],
        ),
        _campaign_record(
            "irs-2",
            "2026-04-02T14:01:10",
            "2026-04-02T14:04:40",
            "+15551110002",
            irs_2,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            calling_from="calling from the Internal Revenue Service",
            callback=irs_callback,
            spoken_value=irs_spoken,
            spoken_e164="+18005550101",
            domain=irs_domain,
            email=irs_email,
            phrases=irs_phrases,
            fingerprint="fp-irs-refund-v1",
            pretext="government_refund",
            transfer="refund verification department",
            case_value="IRF four four two one",
            case_normalized="irf4421",
            ivr=["greeting", "ssn_prompt", "refund_agent"],
        ),
        _campaign_record(
            "irs-3",
            "2026-04-02T14:06:00",
            "2026-04-02T14:09:10",
            "+15551110003",
            irs_3,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            calling_from="calling from the Internal Revenue Service",
            callback=irs_callback,
            spoken_value=irs_spoken,
            spoken_e164="+18005550101",
            domain=irs_domain,
            email=irs_email,
            phrases=irs_phrases,
            fingerprint="fp-irs-refund-v1",
            pretext="government_refund",
            transfer="refund verification department",
            case_value="IRF four four two one",
            case_normalized="irf4421",
            ivr=["greeting", "ssn_prompt", "refund_agent"],
        ),
        _campaign_record(
            "irs-4",
            "2026-04-02T14:20:00",
            "2026-04-02T14:23:20",
            repeat_caller,
            irs_4,
            "gt-irs",
            [
                ScenarioTag.CLEARLY_RELATED,
                ScenarioTag.REPEAT_CALLER,
                ScenarioTag.CHANGING_IDENTIFIERS,
            ],
            organization="Internal Revenue Service",
            calling_from="calling from the Internal Revenue Service",
            callback=irs_callback_rotated,
            spoken_value=irs_spoken_rotated,
            spoken_e164="+18005550144",
            domain=irs_domain,
            email=irs_email_rotated,
            phrases=irs_phrases,
            fingerprint="fp-irs-refund-v1",
            pretext="government_refund",
            transfer="refund verification department",
            case_value="IRF four four two one",
            case_normalized="irf4421",
            ivr=["greeting", "ssn_prompt", "refund_agent"],
        ),
        _campaign_record(
            "tech-1",
            "2026-04-02T16:00:00",
            "2026-04-02T16:08:00",
            "+15552220001",
            tech_1,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Microsoft Support",
            calling_from="calling from Microsoft Support",
            callback="(888) 555-0199",
            domain="https://windows-helpdesk.net/tool",
            email="license@windows-helpdesk.net",
            phrases=tech_phrases,
            fingerprint="fp-tech-support-v1",
            pretext="tech_support",
            transfer="license compliance desk",
            case_value="MSW five five zero nine",
            case_normalized="msw5509",
            ivr=["greeting", "license_prompt", "remote_agent"],
        ),
        _campaign_record(
            "tech-2",
            "2026-04-02T16:02:00",
            "2026-04-02T16:09:30",
            "+15552220002",
            tech_2,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Microsoft Support",
            calling_from="calling from Microsoft Support",
            callback="(888) 555-0199",
            domain="https://windows-helpdesk.net/tool",
            email="license@windows-helpdesk.net",
            phrases=tech_phrases,
            fingerprint="fp-tech-support-v1",
            pretext="tech_support",
            transfer="license compliance desk",
            case_value="MSW five five zero nine",
            case_normalized="msw5509",
            ivr=["greeting", "license_prompt", "remote_agent"],
        ),
        _campaign_record(
            "tech-3",
            "2026-04-02T18:30:00",
            "2026-04-02T18:37:00",
            repeat_caller,
            tech_3,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.REPEAT_CALLER],
            organization="Microsoft Support",
            calling_from="calling from Microsoft Support",
            callback="(888) 555-0199",
            domain="https://windows-helpdesk.net/tool",
            email="license@windows-helpdesk.net",
            phrases=tech_phrases,
            fingerprint="fp-tech-support-v1",
            pretext="tech_support",
            transfer="license compliance desk",
            case_value="MSW five five zero nine",
            case_normalized="msw5509",
            ivr=["greeting", "license_prompt", "remote_agent"],
        ),
        _campaign_record(
            "bank-1",
            "2026-04-03T15:00:00",
            "2026-04-03T15:03:30",
            "+15553330001",
            bank_1,
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            organization="First National Bank",
            calling_from="calling from First National Bank",
            callback="(877) 555-0133",
            domain="https://www.firstnational-alerts.com/fraud",
            email="fraud@firstnational-alerts.com",
            phrases=bank_phrases,
            fingerprint="fp-bank-fraud-v1",
            pretext="bank_fraud",
            transfer="fraud department",
            case_value="FNB nine zero one seven",
            case_normalized="fnb9017",
            ivr=["greeting", "account_prompt", "fraud_agent"],
            extra_observations=_bank_decoys("bank-1"),
        ),
        _campaign_record(
            "bank-2",
            "2026-04-03T15:01:20",
            "2026-04-03T15:04:40",
            "+15553330002",
            bank_2,
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            organization="First National Bank",
            calling_from="calling from First National Bank",
            callback="(877) 555-0133",
            domain="https://www.firstnational-alerts.com/fraud",
            email="fraud@firstnational-alerts.com",
            phrases=bank_phrases,
            fingerprint="fp-bank-fraud-v1",
            pretext="bank_fraud",
            transfer="fraud department",
            case_value="FNB nine zero one seven",
            case_normalized="fnb9017",
            ivr=["greeting", "account_prompt", "fraud_agent"],
        ),
        _campaign_record(
            "solar-1",
            "2026-04-04T11:00:00",
            "2026-04-04T11:02:30",
            "+15554440001",
            solar,
            "gt-solar",
            [ScenarioTag.PARTIAL_OVERLAP],
            organization="Sunpath Solar",
            calling_from="calling from Sunpath Solar",
            callback="(866) 555-0121",
            domain="sunpath-solar.co",
            email="appointments@sunpath-solar.co",
            phrases=solar_phrases,
            fingerprint="fp-solar-v1",
            pretext="solar_sales",
            transfer="scheduling desk",
            ivr=["greeting", "address_prompt", "scheduler"],
        ),
        _campaign_record(
            "insurance-1",
            "2026-04-04T11:03:10",
            "2026-04-04T11:05:40",
            "+15554440002",
            insurance,
            "gt-insurance",
            [ScenarioTag.PARTIAL_OVERLAP],
            organization="Harbor Insurance",
            calling_from="calling from Harbor Insurance",
            callback="(855) 555-0166",
            domain="harbor-insurance-desk.com",
            email="policy@harbor-insurance-desk.com",
            phrases=insurance_phrases,
            fingerprint="fp-insurance-v1",
            pretext="insurance_review",
            transfer="policy review department",
            ivr=["greeting", "policy_prompt", "agent"],
        ),
        _campaign_record(
            "warranty-1",
            "2026-04-05T13:00:00",
            "2026-04-05T13:04:00",
            "+15555550001",
            warranty_1,
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED],
            organization="National Auto Warranty",
            calling_from="calling from National Auto Warranty",
            callback="(844) 555-0170",
            domain="https://national-auto-warranty.com/plans",
            email="plans@national-auto-warranty.com",
            phrases=warranty_phrases,
            fingerprint="fp-warranty-v1",
            pretext="auto_warranty",
            transfer="coverage desk",
            case_value="NAW three three one zero",
            case_normalized="naw3310",
            ivr=["greeting", "vin_prompt", "coverage_agent"],
        ),
        _campaign_record(
            "warranty-2",
            "2026-04-05T13:01:00",
            "2026-04-05T13:05:00",
            "+15555550002",
            warranty_2,
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.CHANGING_IDENTIFIERS],
            organization="National Auto Warranty",
            calling_from="calling from National Auto Warranty",
            callback="(844) 555-0170",
            domain="https://national-auto-warranty.com/plans",
            email="coverage@national-auto-warranty.com",
            phrases=warranty_phrases,
            fingerprint="fp-warranty-v1",
            pretext="auto_warranty",
            transfer="coverage desk",
            case_value="NAW three three one zero",
            case_normalized="naw3310",
            ivr=["greeting", "vin_prompt", "coverage_agent"],
        ),
        _campaign_record(
            "gift-1",
            "2026-04-06T09:00:00",
            "2026-04-06T09:02:00",
            "+15556660001",
            gift,
            "gt-gift",
            [ScenarioTag.UNRELATED],
            organization="Award Claim Center",
            calling_from="calling from Award Claim Center",
            callback="(833) 555-0188",
            domain="award-claim-center.com",
            email="claims@award-claim-center.com",
            phrases=gift_phrases,
            fingerprint="fp-gift-v1",
            pretext="gift_card",
            transfer="settlement award desk",
            ivr=["greeting", "card_prompt", "collector"],
        ),
        _campaign_record(
            "survey-1",
            "2026-04-07T10:00:00",
            "2026-04-07T10:01:30",
            "+15557770001",
            survey,
            "gt-survey",
            [ScenarioTag.UNRELATED],
            organization="City Parks",
            calling_from="calling from City Parks",
            callback="(555) 010-0000",
            domain="cityparks.example",
            email="volunteer@cityparks.example",
            phrases=survey_phrases,
            fingerprint="fp-survey-v1",
            pretext="community_volunteer",
            ivr=["greeting", "park_prompt", "volunteer_desk"],
        ),
    ]


def _irs_body(officer: str, callback_words: str) -> str:
    return (
        f"Hello, this is Officer {officer} calling from the Internal Revenue Service. "
        "Your federal refund is on hold due to a filing discrepancy. "
        "Please stay on the line and do not hang up. "
        "We will connect you to the refund verification department. "
        "The discrepancy involves tax year twenty twenty four and case number IRF four four two one. "
        "To release the refund we must verify the social security number on the return "
        "and confirm the deposit routing number that will receive the payment. "
        "Press one if you are the taxpayer named on the return. "
        f"Have a pen ready to write the callback number {callback_words}. "
        "The refund verification department will stay with you until the hold is cleared."
    )


def _tech_body(name: str) -> str:
    return (
        f"Hello, this is {name} calling from Microsoft Support. "
        "We detected illegal copies of Microsoft Windows on your computer. "
        "Your microsoft windows license has been used from another country and the machine will be blocked. "
        "Please remain connected while we open a support session. "
        "We need remote access to remove the virus and restore the license. "
        "Download the support tool and read the support session code to the technician. "
        "Your case number is MSW five five zero nine. "
        "Do not attempt to shut the computer down. "
        "The technician will ask you to install a remote access client and confirm the product key. "
        "This call is recorded by the license compliance desk."
    )


def _bank_body(agent: str) -> str:
    return (
        f"Hello, this is Agent {agent} calling from First National Bank. "
        "Your account is on hold due to a suspicious wire transfer. "
        "Please stay on the line and do not hang up. "
        "We will connect you to the fraud department. "
        "The wire was four thousand dollars to an unrecognized merchant in another state late last night. "
        "To restore access we must verify the full account number and the last four of the debit card. "
        "A case number has been assigned, FNB nine zero one seven. "
        "Press one to speak with the fraud department. "
        "Do not discuss this alert with other people at your branch."
    )


_SOLAR_BODY = (
    "Hello, this is a customer service representative calling from Sunpath Solar. "
    "You asked about residential solar panels and the residential solar tax credit for your home. "
    "Our surveyor can schedule a roof assessment this week and explain the utility interconnection timeline. "
    "The consultation is free and does not require a deposit. "
    "We will review your electric bill usage and the roof age before quoting an installation. "
    "The scheduling desk can confirm the appointment. "
    "If you still want the appointment, have your utility account login available for the roof assessment team."
)

_INSURANCE_BODY = (
    "Hello, this is a customer service representative calling from Harbor Insurance. "
    "You asked about a homeowners premium reduction after your policy review. "
    "Our licensed agent can walk through deductibles, bundling, and the policy review department checklist. "
    "Please have your current policy number and the mortgage company name ready. "
    "We can compare coverage forms and explain whether the premium reduction applies at renewal. "
    "The review is limited to the policy forms already on file."
)


def _warranty_body(name: str) -> str:
    return (
        f"Hello, this is {name} calling from National Auto Warranty. "
        "Your vehicle factory warranty is expiring and this is the final courtesy reminder. "
        "We can extend engine and transmission coverage if the vehicle qualifies under mileage limits. "
        "The plan is administered through the dealer network and begins after the factory warranty is expiring. "
        "Your case number is NAW three three one zero. "
        "Please have the vehicle identification number and current odometer ready. "
        "A specialist at the coverage desk will confirm whether engine and transmission coverage is available in your state."
    )


_GIFT_BODY = (
    "Hello, this is Morgan calling from Award Claim Center. "
    "You have been selected to receive a settlement award that must be collected with a prepaid gift card. "
    "The settlement award desk only accepts prepaid gift cards. "
    "To process the prepaid gift card payment, purchase two cards and read the numbers slowly. "
    "A courier will not visit your house. "
    "Remain available for the next twenty minutes while the settlement award desk confirms the card balances."
)

_SURVEY_BODY = (
    "Hello, this is Alex calling from City Parks. "
    "This is a reminder about the Saturday volunteer tree planting. "
    "Bring gloves and water. There is no payment and no account to verify. "
    "The meeting point is the east gate of the park. "
    "You can decline and we will remove this reminder from the volunteer list."
)


def _ground(body: str, email: str, domain: str, callback: str) -> str:
    host = normalize_domain(domain)
    trailer = f"Email {email}. URL https://{host}/notice. Callback {callback}."
    if trailer in body:
        return body
    return body.rstrip() + " " + trailer


def _campaign_record(
    call_id: str,
    started: str,
    ended: str,
    caller_id: str,
    transcript: str,
    campaign: str,
    tags: list[ScenarioTag],
    *,
    organization: str,
    calling_from: str,
    callback: str,
    domain: str,
    email: str,
    phrases: tuple[str, ...],
    fingerprint: str,
    pretext: str,
    ivr: list[str],
    transfer: str | None = None,
    spoken_value: str | None = None,
    spoken_e164: str | None = None,
    case_value: str | None = None,
    case_normalized: str | None = None,
    extra_observations: list[Observation] | None = None,
) -> DatasetCallRecord:
    observations, inference = _indicators(
        call_id,
        transcript,
        organization=organization,
        calling_from=calling_from,
        callback=callback,
        spoken_value=spoken_value,
        spoken_e164=spoken_e164,
        domain=domain,
        email=email,
        phrases=phrases,
        fingerprint=fingerprint,
        pretext=pretext,
        transfer=transfer,
        case_value=case_value,
        case_normalized=case_normalized,
        ivr=ivr,
        extra_observations=extra_observations,
    )
    return DatasetCallRecord(
        call_id=call_id,
        started_at=_timestamp(started),
        ended_at=_timestamp(ended),
        caller_id=caller_id,
        transcript=transcript,
        ground_truth_campaign_id=campaign,
        scenario_tags=tags,
        observations=observations,
        inference=inference,
    )


def _indicators(
    call_id: str,
    transcript: str,
    *,
    organization: str,
    calling_from: str,
    callback: str,
    domain: str,
    email: str,
    phrases: tuple[str, ...],
    fingerprint: str,
    pretext: str,
    transfer: str | None,
    ivr: list[str],
    spoken_value: str | None,
    spoken_e164: str | None,
    case_value: str | None,
    case_normalized: str | None,
    extra_observations: list[Observation] | None,
) -> tuple[list[Observation], CorrelationInference]:
    host = normalize_domain(domain)
    url_value = f"https://{host}/notice"
    callback_e164 = to_e164(callback)
    local, email_domain = email.split("@", 1)
    registrable = normalize_domain(email_domain)
    opening = opening_span(transcript, _OPENING_WORDS)
    turns = _opening_turns(transcript)
    first_sentence = turns[0]
    observations = [
        _span(
            call_id,
            transcript,
            ObservationKind.CLAIMED_COMPANY,
            organization,
            normalize_organization(organization),
        ),
        _span(
            call_id,
            transcript,
            ObservationKind.CALLING_FROM,
            calling_from,
            calling_from,
        ),
        _span(
            call_id,
            transcript,
            ObservationKind.CALLBACK_NUMBERS,
            callback,
            callback_e164,
        ),
        _span(call_id, transcript, ObservationKind.URLS, url_value, host),
        _span(call_id, transcript, ObservationKind.DOMAINS, host, host),
        _span(call_id, transcript, ObservationKind.EMAIL_ADDRESSES, email, email.lower()),
        *[
            _span(
                call_id,
                transcript,
                ObservationKind.SCRIPT_PHRASES,
                phrase,
                normalize_phrase(phrase),
            )
            for phrase in phrases
        ],
        _span(
            call_id,
            transcript,
            ObservationKind.OPENING_SCRIPT_TEXT,
            opening,
            normalize_phrase(opening),
        ),
        *[
            _span(
                call_id,
                transcript,
                ObservationKind.OPENING_TURNS,
                turn,
                normalize_phrase(turn),
                observation_id=f"{call_id}:opening_turns:{index}:{normalize_phrase(turn)[:24]}",
            )
            for index, turn in enumerate(turns)
        ],
        _span(
            call_id,
            transcript,
            ObservationKind.SCRIPT_LANGUAGE,
            first_sentence,
            "en",
        ),
        _ungrounded(
            call_id,
            ObservationKind.IVR_PROMPTS,
            " > ".join(ivr),
            " > ".join(ivr),
            segment_id="ivr",
        ),
    ]
    if spoken_value and spoken_e164:
        observations.append(
            _span(
                call_id,
                transcript,
                ObservationKind.SPOKEN_NUMBERS,
                spoken_value,
                spoken_e164,
            )
        )
    if case_value and case_normalized:
        observations.append(
            _span(
                call_id,
                transcript,
                ObservationKind.OTHER,
                case_value,
                case_normalized,
            )
        )
    if transfer:
        observations.append(
            _span(
                call_id,
                transcript,
                ObservationKind.TRANSFER_DESTINATION_CLAIMED,
                transfer,
                normalize_phrase(transfer),
            )
        )
    if extra_observations:
        observations.extend(extra_observations)

    phones = [PhoneE164(phone_e164=callback_e164, source="callback")]
    if spoken_e164:
        phones.append(PhoneE164(phone_e164=spoken_e164, source="spoken"))
    kinds = ["phone", "email", "url"]
    if case_normalized:
        kinds = ["phone", "case_id", "email", "url"]
    inference = CorrelationInference(
        call_id=call_id,
        confidence=0.93,
        claimed_company_normalized=normalize_organization(organization),
        phone_e164=phones,
        domain_registrable=[host],
        email=[
            EmailSplit(
                local=local.lower(),
                domain=email_domain.lower(),
                email_domain_registrable=registrable,
            )
        ],
        email_domain_registrable=[registrable],
        script_phrase_normalized=[normalize_phrase(phrase) for phrase in phrases],
        opening_script_fingerprint=fingerprint,
        pretext_category_canonical=pretext,
        identifier_kind=kinds,
    )
    return observations, inference


def _bank_decoys(call_id: str) -> list[Observation]:
    """Ungrounded IRS guesses. Confidence is below the floor, so they do not score."""
    return [
        _ungrounded(
            call_id,
            ObservationKind.CLAIMED_COMPANY,
            "Internal Revenue Service",
            "internal revenue service",
            confidence=0.15,
            source="low-confidence guess; WATSON must ignore this",
        ),
        _ungrounded(
            call_id,
            ObservationKind.SCRIPT_PHRASES,
            "federal refund is on hold",
            "federal refund is on hold",
            confidence=0.10,
            source="low-confidence guess; WATSON must ignore this",
        ),
    ]


def _opening_turns(transcript: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(transcript):
        if char != ".":
            continue
        sentence = transcript[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1
        if len(sentences) == 2:
            break
    if len(sentences) < 2:
        raise ValueError("transcript needs two opening sentences")
    return sentences


def _span(
    call_id: str,
    transcript: str,
    kind: ObservationKind,
    value: str,
    normalized: str,
    *,
    confidence: float = 0.93,
    observation_id: str | None = None,
) -> Observation:
    start = transcript.find(value)
    if start < 0:
        raise ValueError(f"{call_id} {kind.value} value is not in the transcript: {value!r}")
    return Observation(
        observation_id=observation_id or f"{call_id}:{kind.value}:{normalized}",
        call_id=call_id,
        kind=kind,
        value=value,
        normalized_value=normalized,
        source="synthetic-fixture",
        transcript_segment_id="turn-1",
        start_timestamp=0.0,
        end_timestamp=1.0,
        char_start=start,
        char_end=start + len(value),
        confidence=confidence,
    )


def _ungrounded(
    call_id: str,
    kind: ObservationKind,
    value: str,
    normalized: str,
    *,
    confidence: float = 0.88,
    source: str = "honeypot ivr path; not a spoken transcript span",
    segment_id: str = "ivr",
) -> Observation:
    return Observation(
        observation_id=f"{call_id}:{kind.value}:{normalized}",
        call_id=call_id,
        kind=kind,
        value=value,
        normalized_value=normalized,
        source=source,
        transcript_segment_id=segment_id,
        start_timestamp=0.0,
        end_timestamp=0.0,
        char_start=0,
        char_end=0,
        confidence=confidence,
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
