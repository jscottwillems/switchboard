"""Conversation goals. The strings are Sherlock Observation kind names.

LOKI uses the kind names as goal ids. It does not own typed Observations,
transcript grounding, or extraction confidence.
"""

from enum import Enum
from typing import Literal

StageName = Literal["pretext", "organization", "offer", "identifier"]


class PretextCategory(str, Enum):
    TAX = "tax"
    BANK = "bank"
    WARRANTY = "warranty"
    DEBT = "debt"
    PRIZE = "prize"
    TECH_SUPPORT = "tech_support"
    GOVERNMENT = "government"
    UTILITY = "utility"
    OTHER = "other"


class PaymentMethod(str, Enum):
    GIFT_CARD = "gift_card"
    WIRE = "wire"
    CRYPTO = "crypto"
    REMOTE_ACCESS = "remote_access"
    BANK_VERIFY = "bank_verify"
    OTHER = "other"


# Exact Sherlock Observation kind names, in Sherlock's order.
GOAL_ORDER: tuple[str, ...] = (
    "pretext_category",
    "claimed_company",
    "claimed_agent",
    "claimed_department",
    "callback_numbers",
    "spoken_numbers",
    "case_or_reference_ids",
    "domains",
    "urls",
    "email_addresses",
    "loan_amounts",
    "rates",
    "fees",
    "requested_information",
    "payment_methods",
    "remote_access_tools",
    "script_phrases",
    "urgency_language",
    "threat_or_consequence_language",
    "spoofed_authority_claims",
    "transfer_events",
    "follow_up_promises",
    "other_identifiers",
)

# A stage opens when any kind in the gate has been heard.
# claimed_agent alone does not open the organization stage.
ORG_GATE: tuple[str, ...] = (
    "claimed_company",
    "claimed_department",
    "spoofed_authority_claims",
)
OFFER_GATE: tuple[str, ...] = (
    "payment_methods",
    "requested_information",
    "remote_access_tools",
    "fees",
)
IDENTIFIER_GATE: tuple[str, ...] = (
    "callback_numbers",
    "spoken_numbers",
    "case_or_reference_ids",
    "domains",
    "urls",
    "email_addresses",
    "other_identifiers",
)


def remaining_goals(completed: list[str]) -> list[str]:
    done = set(completed)
    return [goal for goal in GOAL_ORDER if goal not in done]


def ordered_goals(completed: list[str]) -> list[str]:
    done = set(completed)
    return [goal for goal in GOAL_ORDER if goal in done]


def _gate_open(completed: set[str], gate: tuple[str, ...]) -> bool:
    return any(goal in completed for goal in gate)


def dialogue_gates_open(completed: list[str]) -> bool:
    """True when pretext, an organization kind, an ask, and an identifier are in."""

    done = set(completed)
    return (
        "pretext_category" in done
        and _gate_open(done, ORG_GATE)
        and _gate_open(done, OFFER_GATE)
        and _gate_open(done, IDENTIFIER_GATE)
    )


def missing_stage(completed: list[str]) -> StageName:
    """Which discovery question is still useful. Not a goal id."""

    done = set(completed)
    if "pretext_category" not in done:
        return "pretext"
    if not _gate_open(done, ORG_GATE):
        return "organization"
    if not _gate_open(done, OFFER_GATE):
        return "offer"
    return "identifier"
