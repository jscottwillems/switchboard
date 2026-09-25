"""Canonical forms used for identity and inference text."""

import re

_PHONE_DIGITS = re.compile(r"\D")
_RATE_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WHITESPACE = re.compile(r"\s+")


def normalize_phone(raw: str) -> str:
    digits = _PHONE_DIGITS.sub("", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError(f"not a 10-digit phone: {raw}")
    return f"+1{digits}"


def normalize_email(raw: str) -> str:
    return raw.strip().casefold()


def normalize_url(raw: str) -> str:
    return raw.strip().casefold()


def normalize_domain(raw: str) -> str:
    domain = raw.strip().casefold()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def normalize_money(raw: str) -> str:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    return f"{float(cleaned):.2f}"


def normalize_rate(raw: str) -> str:
    match = _RATE_NUMBER.search(raw)
    if match is None:
        raise ValueError(f"not a rate: {raw}")
    number = float(match.group(0))
    rendered = f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{rendered}%"


def normalize_phrase(raw: str) -> str:
    return _WHITESPACE.sub(" ", raw).strip().casefold()


def normalize_agent(raw: str) -> str:
    return _WHITESPACE.sub(" ", raw).strip()


def normalize_identifier(raw: str) -> str:
    return raw.strip().upper()
