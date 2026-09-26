"""Shared operator credential for dashboard read routes.

Primary header: ``X-Switchboard-Operator-Token``.
When that header is absent or blank, ``Authorization: Bearer <token>`` is accepted.
A non-blank primary header is the credential even if ``Authorization`` is also set.

``SWITCHBOARD_OPERATOR_TOKEN`` is the shared secret. Comparison uses
``hmac.compare_digest`` on UTF-8 bytes. A missing, blank, or wrong token is
``401 operator_unauthorized``. An unset or blank secret fails closed the same
way in every environment, including ``dev``.

``SWITCHBOARD_DEV_OPERATOR_BYPASS=1`` skips this check only when
``SWITCHBOARD_ENV`` is exactly ``dev``. Any other environment ignores the flag.
The process stays up so health, carrier webhooks, and internal routes still
answer. Each gated read enforces the check.
"""

import hmac

from fastapi import Header

from switchboard_api.errors import ApiError
from switchboard_api.settings import get_settings

OPERATOR_TOKEN_HEADER = "X-Switchboard-Operator-Token"
_BEARER = "bearer"


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, separator, rest = authorization.partition(" ")
    if separator == "" or scheme.lower() != _BEARER:
        return ""
    return rest.strip()


def _presented_token(header_token: str | None, authorization: str | None) -> str:
    if header_token and header_token.strip():
        return header_token.strip()
    return _bearer_token(authorization)


def require_operator(
    x_switchboard_operator_token: str | None = Header(
        default=None,
        alias=OPERATOR_TOKEN_HEADER,
    ),
    authorization: str | None = Header(default=None),
) -> None:
    """Reject operator read routes unless the shared token matches."""

    settings = get_settings()
    if settings.env == "dev" and settings.dev_operator_bypass:
        return
    expected = settings.operator_token
    presented = _presented_token(x_switchboard_operator_token, authorization)
    if not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise ApiError(401, "operator_unauthorized", "Operator token was rejected.")
