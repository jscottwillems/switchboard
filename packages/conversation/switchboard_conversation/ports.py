"""In-process response selection. Not an HTTP API and not a bus consumer."""

from typing import Protocol

from switchboard_schemas.hotpath import ResponseDecision, ResponseRequest

FIXED_STRATEGY_ID = "fixed.v1"
FIXED_REPLY = "Could you repeat that?"


class ResponseSelector(Protocol):
    def select(self, request: ResponseRequest) -> ResponseDecision:
        """Choose the next honeypot utterance for the hot path."""


class FixedResponseSelector:
    """Skeleton policy. Confidence is certainty of following this rule."""

    def select(self, request: ResponseRequest) -> ResponseDecision:
        del request
        return ResponseDecision(
            text=FIXED_REPLY,
            strategy_id=FIXED_STRATEGY_ID,
            confidence=1.0,
        )
