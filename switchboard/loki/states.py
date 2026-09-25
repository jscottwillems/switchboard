"""Conversation states owned by LOKI."""

from enum import Enum


class ConversationState(str, Enum):
    """Active conversational objective for one honeypot turn."""

    OPENING = "OPENING"
    PURPOSE_DISCOVERY = "PURPOSE_DISCOVERY"
    ORGANIZATION_DISCOVERY = "ORGANIZATION_DISCOVERY"
    OFFER_DISCOVERY = "OFFER_DISCOVERY"
    IDENTIFIER_DISCOVERY = "IDENTIFIER_DISCOVERY"
    CLARIFICATION = "CLARIFICATION"
    STALLING = "STALLING"
    RECOVERY = "RECOVERY"
    TERMINATION = "TERMINATION"


DISCOVERY_STATES = (
    ConversationState.PURPOSE_DISCOVERY,
    ConversationState.ORGANIZATION_DISCOVERY,
    ConversationState.OFFER_DISCOVERY,
    ConversationState.IDENTIFIER_DISCOVERY,
)
