"""Fields Loki should try to elicit, ranked for this schema.

Rank is investigative value during a live call: infrastructure and cash-out
first, pretext identity next, offer numbers after that, and pitch color last.
Script phrases and urgency are usually volunteered; the higher ranks are the
ones a pitch will skip unless someone asks.
"""

from switchboard_intelligence.schemas.observation import ObservationKind

ELICIT_RANK: tuple[tuple[ObservationKind, str], ...] = (
    (
        ObservationKind.CALLBACK_NUMBERS,
        "Direct callable infrastructure if the session drops.",
    ),
    (
        ObservationKind.PAYMENT_METHODS,
        "Cash-out rail that types the scam and the money path.",
    ),
    (
        ObservationKind.URLS,
        "Campaign site or payment page, often unique to a kit.",
    ),
    (
        ObservationKind.DOMAINS,
        "Spoken or partial host when they will not give a full URL.",
    ),
    (
        ObservationKind.EMAIL_ADDRESSES,
        "Contact point for documents, receipts, or follow-up.",
    ),
    (
        ObservationKind.REQUESTED_INFORMATION,
        "The data they are trying to harvest.",
    ),
    (
        ObservationKind.CLAIMED_COMPANY,
        "Who they want the target to believe is calling.",
    ),
    (
        ObservationKind.CLAIMED_DEPARTMENT,
        "The pretext desk inside that organization.",
    ),
    (
        ObservationKind.CLAIMED_AGENT,
        "The alias or persona name they are using.",
    ),
    (
        ObservationKind.FEES,
        "The amount they want paid and the advance-fee ask.",
    ),
    (
        ObservationKind.LOAN_AMOUNTS,
        "The offered or approved principal they are pitching.",
    ),
    (
        ObservationKind.RATES,
        "The interest rate or APR attached to the offer.",
    ),
    (
        ObservationKind.OTHER,
        "Case, badge, ticket, or reference identifiers for clustering.",
    ),
    (
        ObservationKind.SPOKEN_NUMBERS,
        "Any other phone number they mention.",
    ),
    (
        ObservationKind.TRANSFER_EVENTS,
        "Accept a transfer and mark the handoff to a closer.",
    ),
    (
        ObservationKind.SCRIPT_PHRASES,
        "Let the pitch play; these cluster campaigns but are rarely elicited.",
    ),
    (
        ObservationKind.URGENCY_LANGUAGE,
        "Ask how soon they need a decision so the deadline is explicit.",
    ),
)
