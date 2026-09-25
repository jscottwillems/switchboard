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


_LEGAL_SUFFIXES = frozenset(
    {"incorporated", "inc", "llc", "corp", "corporation", "ltd", "limited", "plc"}
)
_LLC_DOTS = re.compile(r"\bl\s*\.\s*l\s*\.\s*c\s*\.?", re.IGNORECASE)
_NON_WORD = re.compile(r"[^\w\s]")

_MULTI_PART_SUFFIXES = frozenset(
    {
        "co.uk",
        "com.au",
        "co.nz",
        "com.br",
        "com.mx",
        "org.uk",
        "net.uk",
        "ac.uk",
        "com.sg",
        "co.jp",
    }
)


def normalize_company_name(raw: str) -> str:
    """Lowercase, collapse whitespace, and drop trailing legal suffixes."""

    text = raw.casefold().replace("&", " and ")
    text = _LLC_DOTS.sub("llc", text)
    text = _NON_WORD.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    parts = text.split(" ")
    while parts and parts[-1] in _LEGAL_SUFFIXES:
        parts.pop()
    return " ".join(parts)


def normalize_script_phrase(raw: str) -> str:
    """Lowercase and strip punctuation, keeping the word order."""

    text = _NON_WORD.sub(" ", raw.casefold())
    return _WHITESPACE.sub(" ", text).strip()


def registrable_domain(host: str) -> str:
    """eTLD+1 using a small multi-part suffix list, not the full public suffix list."""

    labels = [label for label in host.strip().casefold().strip(".").split(".") if label]
    if labels and labels[0] == "www":
        labels = labels[1:]
    if len(labels) <= 2:
        return ".".join(labels)
    tail = ".".join(labels[-2:])
    if tail in _MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return tail


def split_email(raw: str) -> tuple[str, str]:
    local, domain = raw.strip().casefold().split("@", 1)
    return local, domain


def normalize_agent(raw: str) -> str:
    return _WHITESPACE.sub(" ", raw).strip()


def normalize_identifier(raw: str) -> str:
    return raw.strip().upper()
