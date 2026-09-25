"""Process-local stream-token mock.

SB-014 replaces this with a Redis-backed, single-use, short-TTL store.
Tokens never leave this module except as return values to authorized callers.
"""

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import UUID

from switchboard_schemas.api import IssueStreamTokenResponse, ValidateStreamTokenResponse

from switchboard_api.settings import get_settings

_TTL = timedelta(seconds=60)
_tokens: dict[str, tuple[UUID, datetime]] = {}


def reset_token_store() -> None:
    _tokens.clear()


def issue_token(call_session_id: UUID) -> IssueStreamTokenResponse:
    token = token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + _TTL
    _tokens[token] = (call_session_id, expires_at)
    return IssueStreamTokenResponse(
        token=token,
        expires_at=expires_at,
        stream_url=get_settings().media_gateway_public_ws,
    )


def validate_token(token: str) -> ValidateStreamTokenResponse:
    row = _tokens.get(token)
    if row is None:
        return ValidateStreamTokenResponse(valid=False, call_session_id=None)
    call_session_id, expires_at = row
    if expires_at <= datetime.now(timezone.utc):
        return ValidateStreamTokenResponse(valid=False, call_session_id=None)
    return ValidateStreamTokenResponse(valid=True, call_session_id=call_session_id)
