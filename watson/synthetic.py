"""Hand-authored scam-call campaigns used to measure the deterministic scorer.

The JSON file under data/synthetic is this builder's export. Tests fail if
the committed file drifts from `build_dataset()`.

Findings use `IntelligenceFinding` from `packages/schemas`. `callback_number`
values are literal E.164 strings, which is what SB-009 emits. The other
`FindingKind` values are fixture-only until ATLAS expands emission.
"""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid5

from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE
from switchboard_schemas.enums import FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding

from watson.dataset import DatasetCallRecord, ScenarioTag, SyntheticDataset, default_dataset_path
from watson.textutil import normalize_domain, normalize_organization

_DESCRIPTION = (
    "Labeled synthetic honeypot calls for WATSON. Ground-truth campaign ids "
    "are independent of the camp-NNNN ids the pipeline assigns. Each call "
    "carries IntelligenceFinding rows. callback_number is a literal E.164, "
    "the only kind Sherlock emits today. organization_name, url, "
    "payment_method, other, pretext, and person_name are included so the "
    "scorer is ready when ATLAS expands FindingKind emission. CLI/ANI, "
    "timing, and duration stay on the call record."
)

_E164_EXTRACTOR = "e164"
_E164_VERSION = "0.1.0"
_FIXTURE_EXTRACTOR = "fixture"
_FIXTURE_VERSION = "0.0.0"


def build_dataset() -> SyntheticDataset:
    """Return the canonical synthetic dataset."""
    return SyntheticDataset(version=3, description=_DESCRIPTION, calls=_calls())


def export_dataset(path: Path | None = None) -> SyntheticDataset:
    """Write the canonical dataset as JSON and return it."""
    dataset = build_dataset()
    target = path or default_dataset_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return dataset


def _calls() -> list[DatasetCallRecord]:
    repeat_caller = "+15551119999"
    irs_e164 = "+18005550101"
    irs_e164_rotated = "+18005550144"
    return [
        _campaign_call(
            "irs-1",
            "2026-04-02T14:00:00",
            "2026-04-02T14:03:30",
            "+15551110001",
            _irs_body("Jordan", irs_e164),
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            e164=irs_e164,
            host="irs-refund-help.com",
            payment="direct deposit",
            pretext="government_refund",
            pretext_quote="federal refund is on hold",
            person="Jordan",
            person_quote="Officer Jordan",
            case_value="irf4421",
            case_quote="IRF four four two one",
        ),
        _campaign_call(
            "irs-2",
            "2026-04-02T14:01:10",
            "2026-04-02T14:04:40",
            "+15551110002",
            _irs_body("Ramirez", irs_e164),
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            e164=irs_e164,
            host="irs-refund-help.com",
            payment="direct deposit",
            pretext="government_refund",
            pretext_quote="federal refund is on hold",
            person="Ramirez",
            person_quote="Officer Ramirez",
            case_value="irf4421",
            case_quote="IRF four four two one",
        ),
        _campaign_call(
            "irs-3",
            "2026-04-02T14:06:00",
            "2026-04-02T14:09:10",
            "+15551110003",
            _irs_body("Blake", irs_e164),
            "gt-irs",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Internal Revenue Service",
            e164=irs_e164,
            host="irs-refund-help.com",
            payment="direct deposit",
            pretext="government_refund",
            pretext_quote="federal refund is on hold",
            person="Blake",
            person_quote="Officer Blake",
            case_value="irf4421",
            case_quote="IRF four four two one",
        ),
        _campaign_call(
            "irs-4",
            "2026-04-02T14:20:00",
            "2026-04-02T14:23:20",
            repeat_caller,
            _irs_body("Jordan", irs_e164_rotated),
            "gt-irs",
            [
                ScenarioTag.CLEARLY_RELATED,
                ScenarioTag.REPEAT_CALLER,
                ScenarioTag.CHANGING_IDENTIFIERS,
            ],
            organization="Internal Revenue Service",
            e164=irs_e164_rotated,
            host="irs-refund-help.com",
            payment="direct deposit",
            pretext="government_refund",
            pretext_quote="federal refund is on hold",
            person="Jordan",
            person_quote="Officer Jordan",
            case_value="irf4421",
            case_quote="IRF four four two one",
        ),
        _campaign_call(
            "tech-1",
            "2026-04-02T16:00:00",
            "2026-04-02T16:08:00",
            "+15552220001",
            _tech_body("Jason"),
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Microsoft Support",
            e164="+18885550199",
            host="windows-helpdesk.net",
            payment="money order",
            pretext="tech_support",
            pretext_quote="microsoft windows license",
            person="Jason",
            person_quote="this is Jason",
            case_value="msw5509",
            case_quote="MSW five five zero nine",
        ),
        _campaign_call(
            "tech-2",
            "2026-04-02T16:02:00",
            "2026-04-02T16:09:30",
            "+15552220002",
            _tech_body("Priya"),
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED],
            organization="Microsoft Support",
            e164="+18885550199",
            host="windows-helpdesk.net",
            payment="money order",
            pretext="tech_support",
            pretext_quote="microsoft windows license",
            person="Priya",
            person_quote="this is Priya",
            case_value="msw5509",
            case_quote="MSW five five zero nine",
        ),
        _campaign_call(
            "tech-3",
            "2026-04-02T18:30:00",
            "2026-04-02T18:37:00",
            repeat_caller,
            _tech_body("Jason"),
            "gt-tech",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.REPEAT_CALLER],
            organization="Microsoft Support",
            e164="+18885550199",
            host="windows-helpdesk.net",
            payment="money order",
            pretext="tech_support",
            pretext_quote="microsoft windows license",
            person="Jason",
            person_quote="this is Jason",
            case_value="msw5509",
            case_quote="MSW five five zero nine",
        ),
        _campaign_call(
            "bank-1",
            "2026-04-03T15:00:00",
            "2026-04-03T15:03:30",
            "+15553330001",
            _bank_body("Smith"),
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            organization="First National Bank",
            e164="+18775550133",
            host="firstnational-alerts.com",
            payment="wire transfer",
            pretext="bank_fraud",
            pretext_quote="suspicious wire transfer",
            person="Smith",
            person_quote="Agent Smith",
            case_value="fnb9017",
            case_quote="FNB nine zero one seven",
            extra=_bank_decoy("bank-1", _timestamp("2026-04-03T15:03:30")),
        ),
        _campaign_call(
            "bank-2",
            "2026-04-03T15:01:20",
            "2026-04-03T15:04:40",
            "+15553330002",
            _bank_body("Lee"),
            "gt-bank",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.PARTIAL_OVERLAP],
            organization="First National Bank",
            e164="+18775550133",
            host="firstnational-alerts.com",
            payment="wire transfer",
            pretext="bank_fraud",
            pretext_quote="suspicious wire transfer",
            person="Lee",
            person_quote="Agent Lee",
            case_value="fnb9017",
            case_quote="FNB nine zero one seven",
        ),
        _campaign_call(
            "solar-1",
            "2026-04-04T11:00:00",
            "2026-04-04T11:02:30",
            "+15554440001",
            _SOLAR_BODY,
            "gt-solar",
            [ScenarioTag.PARTIAL_OVERLAP],
            organization="Sunpath Solar",
            e164="+18665550121",
            host="sunpath-solar.co",
            payment="credit card",
            pretext="solar_sales",
            pretext_quote="residential solar tax credit",
            person="Riley",
            person_quote="this is Riley",
        ),
        _campaign_call(
            "insurance-1",
            "2026-04-04T11:03:10",
            "2026-04-04T11:05:40",
            "+15554440002",
            _INSURANCE_BODY,
            "gt-insurance",
            [ScenarioTag.PARTIAL_OVERLAP],
            organization="Harbor Insurance",
            e164="+18555550166",
            host="harbor-insurance-desk.com",
            payment="invoice",
            pretext="insurance_review",
            pretext_quote="homeowners premium reduction",
            person="Quinn",
            person_quote="this is Quinn",
        ),
        _campaign_call(
            "warranty-1",
            "2026-04-05T13:00:00",
            "2026-04-05T13:04:00",
            "+15555550001",
            _warranty_body("Dana"),
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED],
            organization="National Auto Warranty",
            e164="+18445550170",
            host="national-auto-warranty.com",
            payment="debit card",
            pretext="auto_warranty",
            pretext_quote="factory warranty is expiring",
            person="Dana",
            person_quote="this is Dana",
            case_value="naw3310",
            case_quote="NAW three three one zero",
        ),
        _campaign_call(
            "warranty-2",
            "2026-04-05T13:01:00",
            "2026-04-05T13:05:00",
            "+15555550002",
            _warranty_body("Chris"),
            "gt-warranty",
            [ScenarioTag.CLEARLY_RELATED, ScenarioTag.CHANGING_IDENTIFIERS],
            organization="National Auto Warranty",
            e164="+18445550170",
            host="national-auto-warranty.com",
            payment="debit card",
            pretext="auto_warranty",
            pretext_quote="factory warranty is expiring",
            person="Chris",
            person_quote="this is Chris",
            case_value="naw3310",
            case_quote="NAW three three one zero",
        ),
        _campaign_call(
            "gift-1",
            "2026-04-06T09:00:00",
            "2026-04-06T09:02:00",
            "+15556660001",
            _GIFT_BODY,
            "gt-gift",
            [ScenarioTag.UNRELATED],
            organization="Award Claim Center",
            e164="+18335550188",
            host="award-claim-center.com",
            payment="prepaid gift card",
            pretext="gift_card",
            pretext_quote="prepaid gift card",
            person="Morgan",
            person_quote="this is Morgan",
        ),
        _campaign_call(
            "survey-1",
            "2026-04-07T10:00:00",
            "2026-04-07T10:01:30",
            "+15557770001",
            _SURVEY_BODY,
            "gt-survey",
            [ScenarioTag.UNRELATED],
            organization="City Parks",
            e164="+15550100000",
            host="cityparks.example",
            payment=None,
            pretext="community_volunteer",
            pretext_quote="volunteer tree planting",
            person="Alex",
            person_quote="this is Alex",
        ),
    ]


def _irs_body(officer: str, e164: str) -> str:
    return (
        f"Hello, this is Officer {officer} calling from the Internal Revenue Service. "
        "Your federal refund is on hold due to a filing discrepancy. "
        "Please stay on the line and do not hang up. "
        "We will connect you to the refund verification department. "
        "The discrepancy involves tax year twenty twenty four and case number IRF four four two one. "
        "To release the refund we must verify the social security number on the return. "
        "The payment method on file is direct deposit. "
        f"Write down callback number {e164}. "
        f"The notice is posted at https://irs-refund-help.com/notice."
    )


def _tech_body(name: str) -> str:
    return (
        f"Hello, this is {name} calling from Microsoft Support. "
        "We detected illegal copies of Microsoft Windows on your computer. "
        "Your microsoft windows license has been used from another country and the machine will be blocked. "
        "We need remote access to remove the virus and restore the license. "
        "Read the support session code to the technician. "
        "Your case number is MSW five five zero nine. "
        "The payment method requested is a money order. "
        "Write down callback number +18885550199. "
        "The notice is posted at https://windows-helpdesk.net/notice."
    )


def _bank_body(agent: str) -> str:
    return (
        f"Hello, this is Agent {agent} calling from First National Bank. "
        "Your account is on hold due to a suspicious wire transfer. "
        "Please stay on the line and do not hang up. "
        "We will connect you to the fraud department. "
        "A case number has been assigned, FNB nine zero one seven. "
        "The payment method involved is a wire transfer. "
        "Write down callback number +18775550133. "
        "The notice is posted at https://firstnational-alerts.com/notice."
    )


_SOLAR_BODY = (
    "Hello, this is Riley calling from Sunpath Solar. "
    "You asked about residential solar panels and the residential solar tax credit for your home. "
    "Our surveyor can schedule a roof assessment this week. "
    "The payment method discussed is a credit card. "
    "Write down callback number +18665550121. "
    "The notice is posted at https://sunpath-solar.co/notice."
)

_INSURANCE_BODY = (
    "Hello, this is Quinn calling from Harbor Insurance. "
    "You asked about a homeowners premium reduction after your policy review. "
    "Please have your current policy number ready. "
    "The payment method discussed is an invoice. "
    "Write down callback number +18555550166. "
    "The notice is posted at https://harbor-insurance-desk.com/notice."
)


def _warranty_body(name: str) -> str:
    return (
        f"Hello, this is {name} calling from National Auto Warranty. "
        "Your vehicle factory warranty is expiring and this is the final courtesy reminder. "
        "We can extend engine and transmission coverage if the vehicle qualifies. "
        "Your case number is NAW three three one zero. "
        "The payment method discussed is a debit card. "
        "Write down callback number +18445550170. "
        "The notice is posted at https://national-auto-warranty.com/notice."
    )


_GIFT_BODY = (
    "Hello, this is Morgan calling from Award Claim Center. "
    "You have been selected to receive a settlement award that must be collected with a prepaid gift card. "
    "The settlement award desk only accepts a prepaid gift card. "
    "Write down callback number +18335550188. "
    "The notice is posted at https://award-claim-center.com/notice."
)

_SURVEY_BODY = (
    "Hello, this is Alex calling from City Parks. "
    "This is a reminder about the Saturday volunteer tree planting. "
    "Bring gloves and water. There is no payment and no account to verify. "
    "The meeting point is the east gate of the park. "
    "Write down callback number +15550100000. "
    "The notice is posted at https://cityparks.example/notice."
)


def _campaign_call(
    call_id: str,
    started: str,
    ended: str,
    caller_id: str,
    transcript: str,
    campaign: str,
    tags: list[ScenarioTag],
    *,
    organization: str,
    e164: str,
    host: str,
    payment: str | None,
    pretext: str,
    pretext_quote: str,
    person: str,
    person_quote: str,
    case_value: str | None = None,
    case_quote: str | None = None,
    extra: list[IntelligenceFinding] | None = None,
) -> DatasetCallRecord:
    ended_at = _timestamp(ended)
    url = f"https://{normalize_domain(host)}/notice"
    findings = [
        _finding(
            call_id,
            FindingKind.CALLBACK_NUMBER,
            e164,
            e164,
            ended_at,
            confidence=1.0,
            extractor=_E164_EXTRACTOR,
            version=_E164_VERSION,
        ),
        _finding(
            call_id,
            FindingKind.ORGANIZATION_NAME,
            normalize_organization(organization),
            organization,
            ended_at,
        ),
        _finding(call_id, FindingKind.URL, normalize_domain(host), url, ended_at),
        _finding(call_id, FindingKind.PRETEXT, pretext, pretext_quote, ended_at),
        _finding(call_id, FindingKind.PERSON_NAME, person, person_quote, ended_at),
    ]
    if payment is not None:
        findings.append(_finding(call_id, FindingKind.PAYMENT_METHOD, payment, payment, ended_at))
    if case_value is not None and case_quote is not None:
        findings.append(_finding(call_id, FindingKind.OTHER, case_value, case_quote, ended_at))
    if extra:
        findings.extend(extra)
    for finding in findings:
        if finding.raw_quote not in transcript and finding.confidence >= 0.5:
            raise ValueError(f"{call_id} raw_quote not in transcript: {finding.raw_quote!r}")
    return DatasetCallRecord(
        call_id=call_id,
        started_at=_timestamp(started),
        ended_at=ended_at,
        caller_id=caller_id,
        transcript=transcript,
        ground_truth_campaign_id=campaign,
        scenario_tags=tags,
        findings=findings,
    )


def _bank_decoy(call_id: str, created_at: datetime) -> list[IntelligenceFinding]:
    """Low-confidence organization guess. WATSON must ignore it."""
    return [
        _finding(
            call_id,
            FindingKind.ORGANIZATION_NAME,
            "internal revenue service",
            "Internal Revenue Service",
            created_at,
            confidence=0.15,
        )
    ]


def _finding(
    call_id: str,
    kind: FindingKind,
    value: str,
    raw_quote: str,
    created_at: datetime,
    *,
    confidence: float = 0.93,
    extractor: str = _FIXTURE_EXTRACTOR,
    version: str = _FIXTURE_VERSION,
) -> IntelligenceFinding:
    return IntelligenceFinding(
        id=uuid5(SWITCHBOARD_ID_NAMESPACE, f"intelligence_finding|{call_id}|{kind.value}|{value}"),
        call_session_id=uuid5(SWITCHBOARD_ID_NAMESPACE, f"call_session|{call_id}"),
        kind=kind,
        value=value,
        raw_quote=raw_quote,
        transcript_segment_ids=[
            uuid5(SWITCHBOARD_ID_NAMESPACE, f"segment|{call_id}|{kind.value}|{value}")
        ],
        extractor=extractor,
        extractor_version=version,
        confidence=confidence,
        status=FindingStatus.PROPOSED,
        created_at=created_at,
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
