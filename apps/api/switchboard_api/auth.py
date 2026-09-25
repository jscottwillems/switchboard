import hmac

from fastapi import Header

from switchboard_api.errors import ApiError
from switchboard_api.settings import get_settings


def require_internal_token(
    x_switchboard_internal_token: str | None = Header(default=None),
) -> None:
    expected = get_settings().internal_token
    presented = x_switchboard_internal_token or ""
    if not expected or not hmac.compare_digest(presented.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "Internal token was rejected.")
