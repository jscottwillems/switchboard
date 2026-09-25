"""Fields Loki should try to elicit, in the order Loki asked for.

Goal id strings are the ObservationKind values. Loki may copy those strings
into goals_completed and goals_remaining. Loki does not emit Observations.
"""

from switchboard_intelligence.schemas.observation import ObservationKind

ELICIT_GROUPS: tuple[tuple[int, tuple[ObservationKind, ...]], ...] = (
    (1, (ObservationKind.PRETEXT_CATEGORY,)),
    (2, (ObservationKind.CLAIMED_COMPANY,)),
    (
        3,
        (
            ObservationKind.LOAN_AMOUNTS,
            ObservationKind.RATES,
            ObservationKind.FEES,
        ),
    ),
    (
        4,
        (
            ObservationKind.CALLBACK_NUMBERS,
            ObservationKind.SPOKEN_NUMBERS,
            ObservationKind.CASE_OR_REFERENCE_IDS,
            ObservationKind.SPOKEN_CLI_CLAIM,
        ),
    ),
    (
        5,
        (
            ObservationKind.CLAIMED_AGENT,
            ObservationKind.CLAIMED_DEPARTMENT,
        ),
    ),
    (
        6,
        (
            ObservationKind.DOMAINS,
            ObservationKind.URLS,
            ObservationKind.EMAIL_ADDRESSES,
        ),
    ),
    (
        7,
        (
            ObservationKind.PAYMENT_METHODS,
            ObservationKind.REMOTE_ACCESS_TOOLS,
        ),
    ),
    (8, (ObservationKind.REQUESTED_INFORMATION,)),
    (
        9,
        (
            ObservationKind.SCRIPT_PHRASES,
            ObservationKind.URGENCY_LANGUAGE,
            ObservationKind.THREAT_OR_CONSEQUENCE_LANGUAGE,
            ObservationKind.TRANSFER_EVENTS,
            ObservationKind.SPOOFED_AUTHORITY_CLAIMS,
            ObservationKind.OPENING_SCRIPT_TEXT,
            ObservationKind.IVR_PROMPTS,
            ObservationKind.IVR_MENU_PATH,
            ObservationKind.TRANSFER_DESTINATION_CLAIMED,
            ObservationKind.SCRIPT_LANGUAGE,
        ),
    ),
    (10, (ObservationKind.FOLLOW_UP_PROMISES,)),
    (11, (ObservationKind.OTHER,)),
)

ELICIT_GUIDANCE: dict[ObservationKind, str] = {
    ObservationKind.PRETEXT_CATEGORY: "Ask why they are calling and store the coarse pretext class.",
    ObservationKind.CLAIMED_COMPANY: "Who they want the target to believe is calling.",
    ObservationKind.LOAN_AMOUNTS: "The offered or approved principal they are pitching.",
    ObservationKind.RATES: "The interest rate or APR attached to the offer.",
    ObservationKind.FEES: "The amount they want paid and the advance-fee ask.",
    ObservationKind.CALLBACK_NUMBERS: "Direct number to reach the operation if the line drops.",
    ObservationKind.SPOKEN_NUMBERS: "Any other phone number they mention.",
    ObservationKind.CASE_OR_REFERENCE_IDS: "Ticket, case, claim, or confirmation identifiers.",
    ObservationKind.SPOKEN_CLI_CLAIM: "The number they say they are calling from, distinct from carrier CLI.",
    ObservationKind.CLAIMED_AGENT: "The alias or persona name they are using.",
    ObservationKind.CLAIMED_DEPARTMENT: "The pretext desk inside that organization.",
    ObservationKind.DOMAINS: "Spoken or partial host when they will not give a full URL.",
    ObservationKind.URLS: "Campaign site or payment page.",
    ObservationKind.EMAIL_ADDRESSES: "Mailbox for documents or later messages.",
    ObservationKind.PAYMENT_METHODS: "Cash-out rail, stored with the payment_method enum.",
    ObservationKind.REMOTE_ACCESS_TOOLS: "Remote-control software they want installed.",
    ObservationKind.REQUESTED_INFORMATION: "The data they are trying to harvest.",
    ObservationKind.SCRIPT_PHRASES: "Let the pitch play so campaign lines are recorded.",
    ObservationKind.URGENCY_LANGUAGE: "Time pressure that is not itself a legal or account threat.",
    ObservationKind.THREAT_OR_CONSEQUENCE_LANGUAGE: "Arrest, account freeze, or lawsuit language.",
    ObservationKind.TRANSFER_EVENTS: "A live handoff to another caller.",
    ObservationKind.SPOOFED_AUTHORITY_CLAIMS: "The spoken claim that they represent an authority.",
    ObservationKind.OPENING_SCRIPT_TEXT: "Let the first caller turns play so the opening script is captured.",
    ObservationKind.IVR_PROMPTS: "Note each menu prompt they play.",
    ObservationKind.IVR_MENU_PATH: "Keep the spoken order of those menu prompts.",
    ObservationKind.TRANSFER_DESTINATION_CLAIMED: "Ask which desk or number they are transferring to.",
    ObservationKind.SCRIPT_LANGUAGE: "Note the language of the script when it is clear.",
    ObservationKind.FOLLOW_UP_PROMISES: "A promise to call back, send a link, or follow up later.",
    ObservationKind.OTHER: "Badge numbers and identifiers that are not case or reference ids.",
}

ELICIT_RANK: tuple[tuple[ObservationKind, str], ...] = tuple(
    (kind, ELICIT_GUIDANCE[kind]) for _rank, kinds in ELICIT_GROUPS for kind in kinds
)

GOAL_IDS: tuple[str, ...] = tuple(kind.value for kind, _reason in ELICIT_RANK)

# Watson scores these shapes. Tier A is an identity key. Tier B is useful and
# noisier. Tier C is context that is weak alone. Call-layer metadata is absent
# on purpose: timing windows, simultaneous calls, duration, dialing cadence,
# true CLI/ANI, and carrier spoof flags stay on the session.
WATSON_FEATURES: tuple[tuple[str, str, str, str], ...] = (
    ("A", "Inference", "claimed_company_normalized", "Lowercase company with legal suffixes removed."),
    ("A", "Inference", "phone_e164", "E.164 number tagged callback, spoken, or spoken_cli."),
    ("A", "Inference", "domain_registrable", "eTLD+1 from domain observations."),
    ("A", "Inference", "email_domain_registrable", "eTLD+1 of an email host."),
    ("A", "Inference", "opening_script_fingerprint", "Ordered tokens from the first caller turns."),
    ("A", "Inference", "pretext_category_canonical", "Closed pretext enum."),
    ("A", "Inference", "identifier_kind", "ticket, case, claim, confirmation, reference, badge, ssn_last4, or account."),
    ("A", "Observation", "callback_numbers", "Raw callback span behind phone_e164."),
    ("A", "Observation", "spoken_cli_claim", "Spoken calling-from number, not carrier CLI."),
    ("A", "Observation", "case_or_reference_ids", "Raw identifier span behind identifier_kind."),
    ("A", "Observation", "email_addresses", "Raw mailbox behind the email inferences."),
    ("A", "Observation", "domains", "Raw host behind domain_registrable."),
    ("A", "Observation", "urls", "Raw URL whose host is also a domain observation."),
    ("B", "Inference", "script_phrase_normalized", "Lowercase punctuation-stripped phrase, original kept alongside."),
    ("B", "Inference", "email_local_domain", "Local part and domain split."),
    ("B", "Observation", "opening_script_text", "Raw text of caller turns 0, 1, and 2."),
    ("B", "Observation", "ivr_menu_path", "Spoken order of a menu in one system segment."),
    ("B", "Observation", "ivr_prompts", "Each press-N-for prompt."),
    ("B", "Observation", "transfer_destination_claimed", "Org, desk, or number named at transfer."),
    ("B", "Observation", "payment_methods", "Cash-out rail plus payment_method."),
    ("B", "Observation", "remote_access_tools", "Named remote-control tool."),
    ("B", "Observation", "script_phrases", "Raw script span behind script_phrase_normalized."),
    ("B", "Observation", "spoofed_authority_claims", "Spoken authority clause."),
    ("B", "Observation", "claimed_company", "Raw company span behind claimed_company_normalized."),
    ("C", "Observation", "script_language", "Locale when the script gives one."),
    ("C", "Observation", "urgency_language", "Time pressure."),
    ("C", "Observation", "threat_or_consequence_language", "Arrest, freeze, or lawsuit language."),
    ("C", "Observation", "claimed_agent", "Persona name."),
    ("C", "Observation", "claimed_department", "Pretext desk."),
    ("C", "Observation", "fees", "Fee amount."),
    ("C", "Observation", "loan_amounts", "Principal amount."),
    ("C", "Observation", "rates", "Interest or APR."),
    ("C", "Observation", "follow_up_promises", "Promise to call, email, or send a link."),
    ("C", "Observation", "transfer_events", "The handoff itself."),
    ("C", "Observation", "requested_information", "Data the caller asked for."),
    ("C", "Observation", "spoken_numbers", "A phone that is not a callback or a spoken CLI."),
    ("C", "Observation", "other", "Badge and leftover identifiers."),
)
