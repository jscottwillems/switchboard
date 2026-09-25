"""Signature primitives used by webhook verifiers and the local simulator.

Twilio signs the public URL plus the sorted, decoded form fields with
HMAC-SHA1, then base64-encodes the digest. The mock provider signs the raw
request body with HMAC-SHA256 and prefixes the hex digest with ``sha256=``.
"""

import base64
import hashlib
import hmac
from urllib.parse import parse_qsl


def sign_mock_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def twilio_signature(*, auth_token: str, url: str, params: dict[str, str]) -> str:
    signed = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def parse_form_body(body: bytes) -> dict[str, str]:
    """Decode application/x-www-form-urlencoded. Duplicate keys keep the last value."""

    text = body.decode("utf-8")
    pairs = parse_qsl(text, keep_blank_values=True, strict_parsing=False)
    return {key: value for key, value in pairs}


def signatures_match(expected: str, presented: str) -> bool:
    return hmac.compare_digest(expected, presented)
