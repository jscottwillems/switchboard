"""In-process response selection. Not an HTTP API and not a bus consumer."""

from typing import Protocol

from switchboard_schemas.hotpath import ResponseDecision, ResponseRequest

FIXED_STRATEGY_ID = "fixed.v1"
FIXED_REPLY = "Could you repeat that?"
# The fixed rule had no caller utterance. Below 1, per SB-007.
EMPTY_CALLER_TEXT_CONFIDENCE = 0.0


def _has_caller_text(text: str) -> bool:
    return bool(text.strip())


class ResponseSelector(Protocol):
    def select(self, request: ResponseRequest) -> ResponseDecision:
        """Choose the next honeypot utterance for the hot path."""


class FixedResponseSelector:
    """Fixed utterance. ``select`` does not perform I/O.

    Non-empty caller text keeps ``FIXED_REPLY`` at confidence ``1.0``.
    Empty or whitespace-only caller text keeps that same short line at
    ``EMPTY_CALLER_TEXT_CONFIDENCE``.
    """

    def select(self, request: ResponseRequest) -> ResponseDecision:
        if _has_caller_text(request.latest_caller_text):
            confidence = 1.0
        else:
            confidence = EMPTY_CALLER_TEXT_CONFIDENCE
        return ResponseDecision(
            text=FIXED_REPLY,
            strategy_id=FIXED_STRATEGY_ID,
            confidence=confidence,
        )
