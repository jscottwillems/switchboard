"""Build 50 synthetic scam transcripts with planted indicators.

Gold labels are the substrings this script inserts. They are not produced
by the extractor. Run from anywhere:

    python packages/intelligence/scripts/build_fixtures.py
"""

import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_transcripts.jsonl"

FAMILIES: tuple[dict[str, str], ...] = (
    {
        "slug": "irs",
        "company": "Internal Revenue Service",
        "department": "legal department",
        "domain": "irs-notice-example.com",
        "email_local": "refunds",
        "case_prefix": "IR",
        "script": "This is an important message.",
        "script_phrase": "this is an important message",
    },
    {
        "slug": "ssa",
        "company": "Social Security Administration",
        "department": "benefits department",
        "domain": "ssa-verify-example.com",
        "email_local": "benefits",
        "case_prefix": "SS",
        "script": "Your account has been compromised.",
        "script_phrase": "your account has been compromised",
    },
    {
        "slug": "microsoft",
        "company": "Microsoft",
        "department": "security department",
        "domain": "ms-support-example.com",
        "email_local": "support",
        "case_prefix": "MS",
        "script": "Press 1 to speak with a representative.",
        "script_phrase": "press 1 to speak with a representative",
    },
    {
        "slug": "warranty",
        "company": "Geek Squad",
        "department": "warranty department",
        "domain": "geeksquad-warranty-example.com",
        "email_local": "claims",
        "case_prefix": "GW",
        "script": "We are calling about your extended vehicle warranty.",
        "script_phrase": "extended vehicle warranty",
    },
    {
        "slug": "student",
        "company": "Federal Student Aid",
        "department": "loan servicing department",
        "domain": "student-aid-example.com",
        "email_local": "servicing",
        "case_prefix": "FA",
        "script": "You qualify for student loan forgiveness.",
        "script_phrase": "student loan forgiveness",
    },
    {
        "slug": "bank",
        "company": "Bank of America",
        "department": "fraud department",
        "domain": "boa-fraud-example.com",
        "email_local": "fraud",
        "case_prefix": "BA",
        "script": "You have been selected.",
        "script_phrase": "you have been selected",
    },
    {
        "slug": "medicare",
        "company": "Medicare",
        "department": "claims department",
        "domain": "medicare-claims-example.com",
        "email_local": "claims",
        "case_prefix": "MC",
        "script": "Verify your identity.",
        "script_phrase": "verify your identity",
    },
    {
        "slug": "utility",
        "company": "National Grid",
        "department": "collections department",
        "domain": "national-grid-example.com",
        "email_local": "billing",
        "case_prefix": "NG",
        "script": "A refund is waiting on this account.",
        "script_phrase": "refund is waiting",
    },
    {
        "slug": "package",
        "company": "Amazon",
        "department": "verification department",
        "domain": "amazon-delivery-example.com",
        "email_local": "delivery",
        "case_prefix": "AZ",
        "script": "Your package could not be delivered.",
        "script_phrase": "your package could not be delivered",
    },
    {
        "slug": "prize",
        "company": "Publishers Clearing House",
        "department": "awards department",
        "domain": "pch-awards-example.com",
        "email_local": "prizes",
        "case_prefix": "PH",
        "script": "You have won a prize.",
        "script_phrase": "you have won a prize",
    },
)

AGENTS = ("Helen Brooks", "Marcus Hale", "Priya Nandak", "Owen Clarke", "Lydia Cho")
PAYMENTS = ("gift card", "wire transfer", "bitcoin", "zelle", "western union")
FEES = ("$29.95", "$49.95", "$79.00", "$99.50", "$149.00")
LOANS = ("$5,000", "$8,500", "$12,500", "$15,000", "$25,000")
RATES = ("2.9%", "3.5%", "4.25%", "1.9 percent", "6%")
REQUESTS = (
    "social security number",
    "date of birth",
    "bank account number",
    "routing number",
    "credit card number",
    "one-time password",
    "driver's license number",
    "medicare number",
)
URGENCY = (
    ("act immediately", "You need to act immediately."),
    ("final notice", "This is your final notice."),
    ("within 24 hours", "Respond within 24 hours."),
    ("last chance", "This is your last chance."),
    ("legal action", "We will begin legal action."),
    ("do not tell anyone", "Do not tell anyone about this call."),
    ("right away", "Handle this right away."),
    ("limited time", "This offer is for a limited time."),
    ("expires today", "Your window expires today."),
    ("failure to comply", "Failure to comply will escalate the file."),
    ("arrest warrant", "There is an arrest warrant attached to this file."),
    ("account will be suspended", "Your account will be suspended."),
    ("urgent matter", "This is an urgent matter."),
)
TRANSFERS = (
    ("let me transfer you", "Let me transfer you to a specialist."),
    ("i am transferring you", "I am transferring you to a specialist."),
    ("transferring you now", "We are transferring you now."),
    ("connecting you to", "I am connecting you to a specialist."),
    ("please hold while i connect you", "Please hold while I connect you."),
)
DECOYS = (
    "I am 100% committed to resolving this today, and the extension is 12.",
    "Call eight hundred five five five zero one nine nine when you can.",
    "The fee is forty nine dollars if you want to move forward.",
    "You should probably hurry because this will not stay open forever.",
    "Visit our site at secure payments dot com for details.",
)
CALLBACK_AREAS = ("800", "888", "877", "866", "855")
SPOKEN_AREAS = ("202", "415", "646", "312", "503")


def main() -> None:
    rows = [_build_call(index) for index in range(50)]
    if len(rows) != 50:
        raise SystemExit(f"expected 50 calls, got {len(rows)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    OUTPUT.write_text(payload, encoding="utf-8")


def _build_call(index: int) -> dict[str, object]:
    family = FAMILIES[index // 5]
    variant = index % 5
    call_id = f"synth-{index + 1:03d}"
    agent = AGENTS[variant]
    payment = PAYMENTS[variant]
    fee = FEES[variant]
    loan = LOANS[variant]
    rate = RATES[variant]
    request = REQUESTS[index % len(REQUESTS)]
    urgency_phrase, urgency_text = URGENCY[index % len(URGENCY)]
    transfer_phrase, transfer_text = TRANSFERS[variant]
    case_id = f"{family['case_prefix']}-{44000 + index}"
    email = f"{family['email_local']}{index}@{family['domain']}"
    url = f"https://{family['domain']}/case/{case_id}"
    callback = _format_phone(variant, CALLBACK_AREAS[variant], f"{100 + index:04d}")
    spoken = _format_phone(variant, SPOKEN_AREAS[variant], f"{200 + index:04d}")
    company_text = f"I am calling from {family['company']}, {family['department']}."
    fee_text = f"The processing fee is {fee}."
    loan_text = f"You are approved for a loan of {loan}."
    rate_text = f"The interest rate is {rate}."
    payment_text = f"Payment must be sent by {payment}."
    request_text = f"Please provide your {request} before we continue."
    callback_text = f"Please call us back at {callback} to continue."
    email_text = f"Email {email} for the form."
    url_text = f"Open {url} for the form."
    bare_domain_text = f"If the link fails, type {family['domain']} into a browser."
    spoken_text = f"The desk line on file is {spoken} if the transfer drops."
    agent_text = f"My name is {agent}."
    case_text = f"Your case number {case_id} is open."
    recording_text = "This call is being recorded."
    hello_text = "Hello? Who is this?"
    decoy_text = DECOYS[variant]

    planned: list[tuple[str, str, list[tuple[str, str]]]] = [
        ("system", recording_text, [("script_phrases", _surface(recording_text, "this call is being recorded"))]),
        ("scammer", family["script"], [("script_phrases", _surface(family["script"], family["script_phrase"]))]),
        ("scammer", agent_text, [("claimed_agent", _token(agent_text, agent))]),
        (
            "scammer",
            company_text,
            [
                ("claimed_company", _token(company_text, family["company"])),
                ("claimed_department", _surface(company_text, family["department"])),
            ],
        ),
        ("scammer", urgency_text, [("urgency_language", _surface(urgency_text, urgency_phrase))]),
        ("scammer", case_text, [("other", _token(case_text, case_id))]),
        ("scammer", fee_text, [("fees", _token(fee_text, fee))]),
        ("scammer", loan_text, [("loan_amounts", _token(loan_text, loan))]),
        ("scammer", rate_text, [("rates", _token(rate_text, rate))]),
        ("scammer", payment_text, [("payment_methods", _surface(payment_text, payment))]),
        ("scammer", request_text, [("requested_information", _surface(request_text, request))]),
        ("scammer", callback_text, [("callback_numbers", _token(callback_text, callback))]),
        (
            "scammer",
            email_text,
            [
                ("email_addresses", _token(email_text, email)),
                ("domains", _token(email_text, family["domain"])),
            ],
        ),
        (
            "scammer",
            url_text,
            [
                ("urls", _token(url_text, url)),
                ("domains", _token(url_text, family["domain"])),
            ],
        ),
        ("scammer", bare_domain_text, [("domains", _token(bare_domain_text, family["domain"]))]),
        ("scammer", spoken_text, [("spoken_numbers", _token(spoken_text, spoken))]),
        ("scammer", transfer_text, [("transfer_events", _surface(transfer_text, transfer_phrase))]),
        ("target", hello_text, []),
        ("scammer", decoy_text, []),
    ]

    segments = []
    gold = []
    decoy_segment_ids = []
    cursor = 0.0
    for segment_index, (speaker, text, plants) in enumerate(planned):
        segment_id = f"{call_id}-s{segment_index:02d}"
        duration = round(2.0 + len(text) / 50, 3)
        end = round(cursor + duration, 3)
        segments.append(
            {
                "segment_id": segment_id,
                "speaker": speaker,
                "text": text,
                "start_timestamp": cursor,
                "end_timestamp": end,
            }
        )
        if not plants:
            decoy_segment_ids.append(segment_id)
        for kind, value in plants:
            gold.append({"kind": kind, "segment_id": segment_id, "value": value})
        cursor = round(end + 0.35, 3)

    signatures = [(item["kind"], item["segment_id"], item["value"]) for item in gold]
    if len(signatures) != len(set(signatures)):
        raise SystemExit(f"duplicate gold rows in {call_id}")

    return {
        "call_id": call_id,
        "family": family["slug"],
        "decoy_segment_ids": decoy_segment_ids,
        "gold": gold,
        "transcript": {"call_id": call_id, "segments": segments},
    }


def _format_phone(style: int, area: str, subscriber: str) -> str:
    exchange = "555"
    if style == 0:
        return f"({area}) {exchange}-{subscriber}"
    if style == 1:
        return f"{area}-{exchange}-{subscriber}"
    if style == 2:
        return f"{area}.{exchange}.{subscriber}"
    if style == 3:
        return f"+1 {area} {exchange} {subscriber}"
    if style == 4:
        return f"1-{area}-{exchange}-{subscriber}"
    raise ValueError(style)


def _surface(text: str, phrase: str) -> str:
    folded = text.casefold()
    needle = phrase.casefold()
    index = folded.find(needle)
    if index < 0:
        raise SystemExit(f"{phrase!r} missing from {text!r}")
    end = index + len(needle)
    if index > 0 and text[index - 1].isalnum():
        raise SystemExit(f"{phrase!r} is not bounded in {text!r}")
    if end < len(text) and text[end].isalnum():
        raise SystemExit(f"{phrase!r} is not bounded in {text!r}")
    if folded.find(needle, end) != -1:
        raise SystemExit(f"{phrase!r} repeated in {text!r}")
    return text[index:end]


def _token(text: str, token: str) -> str:
    if text.count(token) != 1:
        raise SystemExit(f"{token!r} count in {text!r} is {text.count(token)}")
    return token


if __name__ == "__main__":
    main()
