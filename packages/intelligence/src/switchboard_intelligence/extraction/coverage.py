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
    ObservationKind.SPOKEN_NUMBERS: (
        "NANP phone in the same segment without a callback cue or a spoken caller-ID cue."
    ),
    ObservationKind.SPOKEN_CLI_CLAIM: (
        "NANP phone after a spoken caller-ID cue "
        "(caller ID will show, caller ID shows, shows up as). Not carrier CLI."
    ),
    ObservationKind.DOMAINS: "Host of an http(s) URL, host of an email, or a bare domain with a known TLD.",
    ObservationKind.URLS: "http and https URLs.",
    ObservationKind.EMAIL_ADDRESSES: "Standard email addresses.",
    ObservationKind.LOAN_AMOUNTS: "Dollar amounts whose nearest cue is loan, qualify, approved, principal, or financing.",
    ObservationKind.RATES: "A percent figure in a segment that also says interest, APR, or rate.",
    ObservationKind.FEES: "Dollar amounts whose nearest cue is fee, processing, activation, or charge.",
    ObservationKind.REQUESTED_INFORMATION: "A request-target phrase in a segment that also has an ask cue.",
    ObservationKind.PAYMENT_METHODS: (
        "Payment lexicon mapped onto payment_method: gift_card, wire, crypto, "
        "remote_access, bank_verify, or other."
    ),
    ObservationKind.SCRIPT_PHRASES: "Canned pitch lexicon.",
    ObservationKind.URGENCY_LANGUAGE: "Time-pressure lexicon, not arrest, freeze, or lawsuit lines.",
    ObservationKind.TRANSFER_EVENTS: "Transfer lexicon for a live handoff.",
    ObservationKind.PRETEXT_CATEGORY: (
        "Known purpose phrase after 'the purpose of this call is'. "
        "value is that free-text purpose; pretext_category is the coarse enum."
    ),
    ObservationKind.CASE_OR_REFERENCE_IDS: (
        "Case, claim, reference, ticket, confirmation, or account numbers that contain a digit, "
        "plus a social-security last four after 'ending in' or 'last four'."
    ),
    ObservationKind.THREAT_OR_CONSEQUENCE_LANGUAGE: (
        "Arrest, account freeze or suspension, lawsuit, or failure-to-comply lexicon."
    ),
    ObservationKind.REMOTE_ACCESS_TOOLS: "Named remote-control tools such as AnyDesk or TeamViewer.",
    ObservationKind.SPOOFED_AUTHORITY_CLAIMS: (
        "The clause 'I am calling from ...', 'I am with ...', or 'I'm with ...'."
    ),
    ObservationKind.FOLLOW_UP_PROMISES: (
        "Promises to call back, send a link, email next steps, or follow up."
    ),
    ObservationKind.OPENING_SCRIPT_TEXT: (
        "Full text of each of the first three scammer turns, with opening_turn_index 0, 1, or 2."
    ),
    ObservationKind.IVR_PROMPTS: "System-speaker 'press N for …' menu prompts.",
    ObservationKind.IVR_MENU_PATH: (
        "Full system-speaker segment when it contains two or more IVR prompts, in spoken order."
    ),
    ObservationKind.TRANSFER_DESTINATION_CLAIMED: (
        "Organization, department, or phone in a segment that also has a transfer phrase."
    ),
    ObservationKind.SCRIPT_LANGUAGE: (
        "Locale from an explicit English or Spanish cue, otherwise en when the first "
        "detectable scammer turn has an English function word. Evidence is a verbatim span."
    ),
    ObservationKind.OTHER: "Badge numbers that contain a digit and do not fit case_or_reference_ids.",
}

MODEL_GAPS: tuple[str, ...] = (
    "Phone numbers spoken as words.",
    "Dollar amounts written as words.",
    "Urgency or script lines that are paraphrased outside the lexicon.",
    "Organizations that are not in the organization lexicon.",
    "Domains spoken as 'dot com' rather than a dotted host.",
    "Obfuscated or scheme-less URLs.",
    "Purpose lines that are not in the purpose lexicon.",
    "Threats paraphrased outside the threat lexicon.",
    "Remote-access tools named outside the tool lexicon.",
    "IVR menus that are not 'press N for' lines on the system speaker.",
    "Transfer destinations that are not a lexicon organization, department, or phone.",
    "Script language when no English or Spanish cue is present.",
)
