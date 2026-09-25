"""What the deterministic extractor covers in this milestone.

Paraphrases, spoken-digit numbers, word amounts, and organizations outside
the lexicon are left for the model extractor interface.
"""

from switchboard_intelligence.schemas.observation import ObservationKind

DETERMINISTIC_COVERAGE: dict[ObservationKind, str] = {
    ObservationKind.CLAIMED_COMPANY: (
        "Organization lexicon within 80 characters after a claim cue "
        "(calling from, on behalf of, representing, I am with, this is the)."
    ),
    ObservationKind.CLAIMED_AGENT: "Name after 'my name is', or after Agent, Officer, or Detective.",
    ObservationKind.CLAIMED_DEPARTMENT: "Department lexicon, exact phrase.",
    ObservationKind.CALLBACK_NUMBERS: (
        "NANP phone with a callback cue in the preceding window "
        "(call us back, call back, callback, call us at, dial, reach us at, our number is)."
    ),
    ObservationKind.SPOKEN_NUMBERS: "NANP phone in the same segment without a callback cue.",
    ObservationKind.DOMAINS: "Host of an http(s) URL, host of an email, or a bare domain with a known TLD.",
    ObservationKind.URLS: "http and https URLs.",
    ObservationKind.EMAIL_ADDRESSES: "Standard email addresses.",
    ObservationKind.LOAN_AMOUNTS: "Dollar amounts whose nearest cue is loan, qualify, approved, principal, or financing.",
    ObservationKind.RATES: "A percent figure in a segment that also says interest, APR, or rate.",
    ObservationKind.FEES: "Dollar amounts whose nearest cue is fee, processing, activation, or charge.",
    ObservationKind.REQUESTED_INFORMATION: "A request-target phrase in a segment that also has an ask cue.",
    ObservationKind.PAYMENT_METHODS: "Payment-rail lexicon (gift card, wire, bitcoin, Zelle, and similar).",
    ObservationKind.SCRIPT_PHRASES: "Canned pitch lexicon.",
    ObservationKind.URGENCY_LANGUAGE: "Urgency lexicon.",
    ObservationKind.TRANSFER_EVENTS: "Transfer lexicon.",
    ObservationKind.OTHER: "Case, badge, reference, ticket, or confirmation numbers that contain a digit.",
}

MODEL_GAPS: tuple[str, ...] = (
    "Phone numbers spoken as words.",
    "Dollar amounts written as words.",
    "Urgency or script lines that are paraphrased outside the lexicon.",
    "Organizations that are not in the organization lexicon.",
    "Domains spoken as 'dot com' rather than a dotted host.",
    "Obfuscated or scheme-less URLs.",
)
