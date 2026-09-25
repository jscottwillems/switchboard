"""Check a stream token with the API. The token value is never logged."""

import json
import urllib.error
import urllib.request
from typing import Protocol

from pydantic import ValidationError

from switchboard_schemas.api import ValidateStreamTokenResponse

INTERNAL_TOKEN_HEADER = "X-Switchboard-Internal-Token"
VALIDATE_PATH = "/v1/internal/stream-tokens/validate"
MAX_TOKEN_CHARS = 256


class StreamTokenCheckError(Exception):
    """The validate call did not return a usable body."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _ResponseBody(Protocol):
    def read(self) -> bytes: ...

    def __enter__(self) -> "_ResponseBody": ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


class UrlOpener(Protocol):
    def __call__(self, request: urllib.request.Request, timeout: float) -> _ResponseBody: ...


class StreamTokenValidator(Protocol):
    def validate(self, token: str) -> ValidateStreamTokenResponse:
        """Return the API validation body."""


class ApiStreamTokenValidator:
    """POST /v1/internal/stream-tokens/validate with the internal auth header."""

    def __init__(
        self,
        *,
        api_base_url: str,
        internal_token: str,
        timeout_s: float,
        opener: UrlOpener | None = None,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._internal_token = internal_token
        self._timeout_s = timeout_s
        self._opener = opener or urllib.request.urlopen

    def validate(self, token: str) -> ValidateStreamTokenResponse:
        if len(token) > MAX_TOKEN_CHARS:
            return ValidateStreamTokenResponse(valid=False, call_session_id=None)
        body = json.dumps({"token": token}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._api_base_url}{VALIDATE_PATH}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                INTERNAL_TOKEN_HEADER: self._internal_token,
            },
        )
        try:
            # Keyword timeout: urlopen's second positional argument is the body.
            with self._opener(request, timeout=self._timeout_s) as response:
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise StreamTokenCheckError("validate_unavailable") from exc
        try:
            return ValidateStreamTokenResponse.model_validate_json(raw)
        except ValidationError as exc:
            raise StreamTokenCheckError("validate_unavailable") from exc
