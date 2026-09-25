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
    ObservationKind.FOLLOW_UP_PROMISES: "A promise to call back, send a link, or follow up later.",
    ObservationKind.OTHER: "Badge numbers and identifiers that are not case or reference ids.",
}

ELICIT_RANK: tuple[tuple[ObservationKind, str], ...] = tuple(
    (kind, ELICIT_GUIDANCE[kind]) for _rank, kinds in ELICIT_GROUPS for kind in kinds
)

GOAL_IDS: tuple[str, ...] = tuple(kind.value for kind, _reason in ELICIT_RANK)
