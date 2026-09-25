"""Webhook admission: size cap, then per-client rate limit.

Signature checks stay in the route so they remain on the raw body. This module
does not parse JSON.
"""

from __future__ import annotations

import time
from enum import Enum

from fastapi import Request

from sentinel._never import assert_never
from sentinel.limits import KeyedEventLimiter, ResourceLimits

MAX_WEBHOOK_BODY_BYTES = 1_048_576

_limiter = KeyedEventLimiter()


class WebhookEdgeDeny(Enum):
    TOO_LARGE = "too_large"
    RATE_LIMITED = "rate_limited"


def reset_webhook_edge(limits: ResourceLimits | None = None) -> None:
    """Replace the process-local limiter. Tests use this between cases."""
    global _limiter
    _limiter = KeyedEventLimiter(limits)


def admit_webhook(request: Request, raw: bytes, *, at: float | None = None) -> WebhookEdgeDeny | None:
    """Return a deny reason, or None when the body may proceed to signature verification."""
    if len(raw) > MAX_WEBHOOK_BODY_BYTES:
        return WebhookEdgeDeny.TOO_LARGE
    key = request.client.host if request.client is not None else "unknown"
    stamp = time.monotonic() if at is None else at
    decision = _limiter.allow(key, at=stamp)
    if not decision.allowed:
        return WebhookEdgeDeny.RATE_LIMITED
    return None


def status_for(deny: WebhookEdgeDeny) -> tuple[int, str, str]:
    """HTTP status, error code, and message. The body does not echo the request."""
    match deny:
        case WebhookEdgeDeny.TOO_LARGE:
            return (413, "webhook_too_large", "Webhook body exceeds the size cap.")
        case WebhookEdgeDeny.RATE_LIMITED:
            return (429, "webhook_rate_limited", "Webhook rate limit exceeded.")
    assert_never(deny)
