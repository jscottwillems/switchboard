"""Hand-authored scam-call campaigns used to measure the deterministic scorer.

The JSON file under data/synthetic is this builder's export. Tests fail if
the committed file drifts from `build_dataset()`.
"""

from datetime import datetime, timezone
from pathlib import Path

from watson.config import ScoringConfig
from watson.dataset import DatasetCallRecord, ScenarioTag, SyntheticDataset, default_dataset_path
from watson.sherlock.models import IntelligenceObservation, ObservationKind
from watson.textutil import opening_span

_DESCRIPTION = (
    "Labeled synthetic honeypot calls for WATSON. Ground-truth campaign ids "
    "are independent of the camp-NNNN ids the pipeline assigns. The set "
    "includes near-duplicate campaigns, unrelated pretexts, partial script "
    "overlap that must not auto-merge, and one caller id reused across two "
    "campaigns while callback numbers rotate inside the IRS campaign."
)


def build_dataset() -> SyntheticDataset:
    """Return the canonical synthetic dataset."""
    return SyntheticDataset(version=1, description=_DESCRIPTION, calls=_calls())


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

    irs_ivr = ["greeting", "ssn_prompt", "refund_agent"]
    tech_ivr = ["greeting", "license_prompt", "remote_agent"]
    bank_ivr = ["greeting", "account_prompt", "fraud_agent"]
    solar_ivr = ["greeting", "address_prompt", "scheduler"]
    insurance_ivr = ["greeting", "policy_prompt", "agent"]
    warranty_ivr = ["greeting", "vin_prompt", "coverage_agent"]
    gift_ivr = ["greeting", "card_prompt", "collector"]
    survey_ivr = ["greeting", "park_prompt", "volunteer_desk"]

    irs_callback = "(800) 555-0101"
    irs_callback_rotated = "(800) 555-0144"
    irs_domain = "https://www.irs-refund-help.com/claim"
    irs_email = "refunds@irs-refund-help.com"
    irs_email_rotated = "desk@irs-refund-help.com"
    repeat_caller = "+15551119999"

    irs_1 = _irs_transcript("Jordan", "eight hundred five five five zero one zero one")
    irs_2 = _irs_transcript("Ramirez", "eight hundred five five five zero one zero one")
    irs_3 = _irs_transcript("Blake", "eight hundred five five five zero one zero one")
    irs_4 = _irs_transcript("Jordan", "eight hundred five five five zero one four four")
    tech_1 = _tech_transcript("Jason")
    tech_2 = _tech_transcript("Priya")
    tech_3 = _tech_transcript("Jason")
    bank_1 = _bank_transcript("Smith")
    bank_2 = _bank_transcript("Lee")
    warranty_1 = _warranty_transcript("Dana")
    warranty_2 = _warranty_transcript("Chris")

    return [
        _record(
            "irs-1",
            "2026-04-02T14:00:00",
            "2026-04-02T14:03:30",
            "+15551110001",
            irs_1,
            True,
            irs_ivr,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "Internal Revenue Service",
                irs_callback,
                irs_domain,
                irs_email,
                irs_phrases,
                irs_1,
                irs_ivr,
            ),
        ),
        _record(
            "irs-2",
            "2026-04-02T14:01:10",
            "2026-04-02T14:04:40",
            "+15551110002",
            irs_2,
            True,
            irs_ivr,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "Internal Revenue Service",
                irs_callback,
                irs_domain,
                irs_email,
                irs_phrases,
                irs_2,
                irs_ivr,
            ),
        ),
        _record(
            "irs-3",
            "2026-04-02T14:06:00",
            "2026-04-02T14:09:10",
            "+15551110003",
            irs_3,
            False,
            irs_ivr,
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "Internal Revenue Service",
                irs_callback,
                irs_domain,
                irs_email,
                irs_phrases,
                irs_3,
                irs_ivr,
            ),
        ),
        _record(
            "irs-4",
            "2026-04-02T14:20:00",
            "2026-04-02T14:23:20",
            repeat_caller,
            irs_4,
            True,
            irs_ivr,
            "gt-irs",
            [
                ScenarioTag.CLEARLY_RELATED,
                ScenarioTag.REPEAT_CALLER,
                ScenarioTag.CHANGING_IDENTIFIERS,
            ],
            _indicators(
                "Internal Revenue Service",
                irs_callback_rotated,
                irs_domain,
                irs_email_rotated,
                irs_phrases,
                irs_4,
                irs_ivr,
            ),
        ),
        _record(
            "tech-1",
            "2026-04-02T16:00:00",
            "2026-04-02T16:08:00",
            "+15552220001",
            tech_1,
            True,
            tech_ivr,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "Microsoft Support",
                "(888) 555-0199",
                "https://windows-helpdesk.net/tool",
                "license@windows-helpdesk.net",
                tech_phrases,
                tech_1,
                tech_ivr,
            ),
        ),
        _record(
            "tech-2",
            "2026-04-02T16:02:00",
            "2026-04-02T16:09:30",
            "+15552220002",
            tech_2,
            True,
            tech_ivr,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "Microsoft Support",
                "(888) 555-0199",
                "https://windows-helpdesk.net/tool",
                "license@windows-helpdesk.net",
                tech_phrases,
                tech_2,
                tech_ivr,
            ),
        ),
        _record(
            "tech-3",
            "2026-04-02T18:30:00",
            "2026-04-02T18:37:00",
            repeat_caller,
            tech_3,
            False,
            tech_ivr,
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.REPEAT_CALLER],
            _indicators(
                "Microsoft Support",
                "(888) 555-0199",
                "https://windows-helpdesk.net/tool",
                "license@windows-helpdesk.net",
                tech_phrases,
                tech_3,
                tech_ivr,
            ),
        ),
        _record(
            "bank-1",
            "2026-04-03T15:00:00",
            "2026-04-03T15:03:30",
            "+15553330001",
            bank_1,
            False,
            bank_ivr,
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            _indicators(
                "First National Bank",
                "(877) 555-0133",
                "https://www.firstnational-alerts.com/fraud",
                "fraud@firstnational-alerts.com",
                bank_phrases,
                bank_1,
                bank_ivr,
                extra=[
                    _indicator(
                        ObservationKind.CLAIMED_ORGANIZATION,
                        "Internal Revenue Service",
                        0.15,
                        "low-confidence guess; WATSON must ignore this",
                    ),
                    _indicator(
                        ObservationKind.REPEATED_PHRASE,
                        "federal refund is on hold",
                        0.10,
                        "low-confidence guess; WATSON must ignore this",
                    ),
                ],
            ),
        ),
        _record(
            "bank-2",
            "2026-04-03T15:01:20",
            "2026-04-03T15:04:40",
            "+15553330002",
            bank_2,
            False,
            bank_ivr,
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            _indicators(
                "First National Bank",
                "(877) 555-0133",
                "https://www.firstnational-alerts.com/fraud",
                "fraud@firstnational-alerts.com",
                bank_phrases,
                bank_2,
                bank_ivr,
            ),
        ),
        _record(
            "solar-1",
            "2026-04-04T11:00:00",
            "2026-04-04T11:02:30",
            "+15554440001",
            _SOLAR_TRANSCRIPT,
            False,
            solar_ivr,
            "gt-solar",
            [ScenarioTag.PARTIAL_OVERLAP],
            _indicators(
                "Sunpath Solar",
                "(866) 555-0121",
                "sunpath-solar.co",
                "appointments@sunpath-solar.co",
                solar_phrases,
                _SOLAR_TRANSCRIPT,
                solar_ivr,
            ),
        ),
        _record(
            "insurance-1",
            "2026-04-04T11:03:10",
            "2026-04-04T11:05:40",
            "+15554440002",
            _INSURANCE_TRANSCRIPT,
            False,
            insurance_ivr,
            "gt-insurance",
            [ScenarioTag.PARTIAL_OVERLAP],
            _indicators(
                "Harbor Insurance",
                "(855) 555-0166",
                "harbor-insurance-desk.com",
                "policy@harbor-insurance-desk.com",
                insurance_phrases,
                _INSURANCE_TRANSCRIPT,
                insurance_ivr,
            ),
        ),
        _record(
            "warranty-1",
            "2026-04-05T13:00:00",
            "2026-04-05T13:04:00",
            "+15555550001",
            warranty_1,
            True,
            warranty_ivr,
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED],
            _indicators(
                "National Auto Warranty",
                "(844) 555-0170",
                "https://national-auto-warranty.com/plans",
                "plans@national-auto-warranty.com",
                warranty_phrases,
                warranty_1,
                warranty_ivr,
            ),
        ),
        _record(
            "warranty-2",
            "2026-04-05T13:01:00",
            "2026-04-05T13:05:00",
            "+15555550002",
            warranty_2,
            True,
            warranty_ivr,
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.CHANGING_IDENTIFIERS],
            _indicators(
                "National Auto Warranty",
                "(844) 555-0170",
                "https://national-auto-warranty.com/plans",
                "coverage@national-auto-warranty.com",
                warranty_phrases,
                warranty_2,
                warranty_ivr,
            ),
        ),
        _record(
            "gift-1",
            "2026-04-06T09:00:00",
            "2026-04-06T09:02:00",
            "+15556660001",
            _GIFT_TRANSCRIPT,
            False,
            gift_ivr,
            "gt-gift",
            [ScenarioTag.UNRELATED],
            _indicators(
                "Award Claim Center",
                "(833) 555-0188",
                "award-claim-center.com",
                "claims@award-claim-center.com",
                gift_phrases,
                _GIFT_TRANSCRIPT,
                gift_ivr,
            ),
        ),
        _record(
            "survey-1",
            "2026-04-07T10:00:00",
            "2026-04-07T10:01:30",
            "+15557770001",
            _SURVEY_TRANSCRIPT,
            False,
            survey_ivr,
            "gt-survey",
            [ScenarioTag.UNRELATED],
            _indicators(
                "City Parks",
                "(555) 010-0000",
                "cityparks.example",
                "volunteer@cityparks.example",
                survey_phrases,
                _SURVEY_TRANSCRIPT,
                survey_ivr,
            ),
        ),
    ]


def _irs_transcript(officer: str, callback_words: str) -> str:
    return (
        f"Hello, this is Officer {officer} with the Internal Revenue Service. "
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


def _tech_transcript(name: str) -> str:
    return (
        f"Hello, this is {name} from Microsoft Support. "
        "We detected illegal copies of Microsoft Windows on your computer. "
        "Your microsoft windows license has been used from another country and the machine will be blocked. "
        "Please remain connected while we open a support session. "
        "We need remote access to remove the virus and restore the license. "
        "Download the support tool from the website we provide and read the support session code to the technician. "
        "Do not attempt to shut the computer down. "
        "The technician will ask you to install a remote access client and confirm the product key. "
        "This call is recorded by the license compliance desk."
    )


def _bank_transcript(agent: str) -> str:
    return (
        f"Hello, this is Agent {agent} with First National Bank. "
        "Your account is on hold due to a suspicious wire transfer. "
        "Please stay on the line and do not hang up. "
        "We will connect you to the fraud department. "
        "The wire was four thousand dollars to an unrecognized merchant in another state late last night. "
        "To restore access we must verify the full account number and the last four of the debit card. "
        "A case number has been assigned, FNB nine zero one seven. "
        "Press one to speak with the fraud department. "
        "Do not discuss this alert with other people at your branch."
    )


_SOLAR_TRANSCRIPT = (
    "Hello, this is a customer service representative calling about your recent inquiry. "
    "You asked about residential solar panels and the residential solar tax credit for your home. "
    "Our surveyor can schedule a roof assessment this week and explain the utility interconnection timeline. "
    "The consultation is free and does not require a deposit. "
    "We will review your electric bill usage and the roof age before quoting an installation. "
    "If you still want the appointment, have your utility account login available for the roof assessment team."
)

_INSURANCE_TRANSCRIPT = (
    "Hello, this is a customer service representative calling about your recent inquiry. "
    "You asked about a homeowners premium reduction after your policy review. "
    "Our licensed agent can walk through deductibles, bundling, and the policy review department checklist. "
    "Please have your current policy number and the mortgage company name ready. "
    "We can compare coverage forms and explain whether the premium reduction applies at renewal. "
    "The review is limited to the policy forms already on file."
)

def _warranty_transcript(name: str) -> str:
    return (
        f"Hello, this is {name} from National Auto Warranty. "
        "Your vehicle factory warranty is expiring and this is the final courtesy reminder. "
        "We can extend engine and transmission coverage if the vehicle qualifies under mileage limits. "
        "The plan is administered through the dealer network and begins after the factory warranty is expiring. "
        "Please have the vehicle identification number and current odometer ready. "
        "A specialist will confirm whether engine and transmission coverage is available in your state."
    )


_GIFT_TRANSCRIPT = (
    "Hello, this is Morgan from Award Claim Center. "
    "You have been selected to receive a settlement award that must be collected with a prepaid gift card. "
    "The settlement award desk only accepts prepaid gift cards. "
    "To process the prepaid gift card payment, purchase two cards and read the numbers slowly. "
    "A courier will not visit your house. "
    "Remain available for the next twenty minutes while the settlement award desk confirms the card balances."
)

_SURVEY_TRANSCRIPT = (
    "Hello, this is Alex from City Parks. "
    "This is a reminder about the Saturday volunteer tree planting. "
    "Bring gloves and water. There is no payment and no account to verify. "
    "The meeting point is the east gate of the park. "
    "You can decline and we will remove this reminder from the volunteer list."
)


def _record(
    call_id: str,
    started: str,
    ended: str,
    caller_id: str,
    transcript: str,
    transferred: bool,
    ivr_path: list[str],
    campaign: str,
    tags: list[ScenarioTag],
    observations: list[IntelligenceObservation],
) -> DatasetCallRecord:
    return DatasetCallRecord(
        call_id=call_id,
        started_at=_timestamp(started),
        ended_at=_timestamp(ended),
        caller_id=caller_id,
        transcript=transcript,
        transferred=transferred,
        ivr_path=ivr_path,
        ground_truth_campaign_id=campaign,
        scenario_tags=tags,
        observations=observations,
    )


def _indicators(
    organization: str,
    callback: str,
    domain: str,
    email: str,
    phrases: tuple[str, ...],
    transcript: str,
    ivr_path: list[str],
    extra: list[IntelligenceObservation] | None = None,
) -> list[IntelligenceObservation]:
    opening_words = ScoringConfig().opening_word_count
    observations = [
        _indicator(ObservationKind.CLAIMED_ORGANIZATION, organization, evidence=organization),
        _indicator(ObservationKind.CALLBACK_IDENTIFIER, callback, evidence=callback),
        _indicator(ObservationKind.DOMAIN, domain, evidence=domain),
        _indicator(ObservationKind.EMAIL_PATTERN, email, evidence=email),
        *[
            _indicator(ObservationKind.REPEATED_PHRASE, phrase, evidence=phrase)
            for phrase in phrases
        ],
        _indicator(
            ObservationKind.OPENING_SCRIPT,
            opening_span(transcript, opening_words),
            0.90,
            "pitch span supplied by the fixture, standing in for SHERLOCK",
        ),
        _indicator(
            ObservationKind.IVR_STRUCTURE,
            " > ".join(ivr_path),
            0.88,
            "structured IVR path",
        ),
    ]
    if extra:
        observations.extend(extra)
    return observations


def _indicator(
    kind: ObservationKind,
    value: str,
    confidence: float = 0.93,
    evidence: str | None = None,
) -> IntelligenceObservation:
    return IntelligenceObservation(
        kind=kind,
        value=value,
        confidence=confidence,
        evidence=evidence,
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
