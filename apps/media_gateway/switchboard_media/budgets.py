"""Per-socket audio accounting. The media route calls this before discarding a frame."""

from __future__ import annotations

from sentinel.limits import CallBudget, LimitDecision, ResourceLimits, check_ws_message

_limits = ResourceLimits()


def set_limits(limits: ResourceLimits) -> None:
    global _limits
    _limits = limits


def reset_limits() -> None:
    set_limits(ResourceLimits())


def current_limits() -> ResourceLimits:
    return _limits


def new_budget() -> CallBudget:
    return CallBudget(_limits)


def admit_frame(budget: CallBudget, nbytes: int, *, at: float) -> LimitDecision:
    """Reject an oversized websocket message, then count bytes toward the call budget."""
    message = check_ws_message(nbytes, _limits)
    if not message.allowed:
        return message
    return budget.note_audio(nbytes, at=at)
