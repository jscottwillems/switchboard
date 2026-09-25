"""Normalized string comparisons used by the deterministic scorer."""

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ORG_SUFFIXES = frozenset(
    {"incorporated", "inc", "llc", "ltd", "corp", "corporation", "co", "company"}
)
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "for",
        "in",
        "on",
        "is",
        "this",
        "that",
        "it",
        "you",
        "your",
        "we",
        "our",
        "with",
        "from",
        "at",
        "be",
        "are",
        "was",
        "were",
        "have",
        "has",
        "had",
        "will",
        "not",
        "do",
        "does",
        "if",
        "please",
        "hello",
        "hi",
        "am",
        "as",
        "by",
        "they",
        "them",
        "their",
        "me",
        "my",
        "so",
        "but",
        "about",
        "into",
        "over",
        "up",
        "out",
        "just",
        "than",
        "then",
        "can",
        "could",
        "would",
        "should",
        "there",
        "here",
        "been",
        "being",
        "its",
        "which",
        "who",
        "whom",
        "what",
        "when",
        "where",
        "call",
        "calling",
        "called",
    }
)


def normalize_text(value: str) -> str:
    """Lowercase and collapse punctuation to single spaces."""
    return " ".join(_TOKEN_RE.findall(value.lower()))


def tokenize(value: str) -> frozenset[str]:
    """Content tokens: length >= 3, stopwords removed."""
    return frozenset(
        token
        for token in _TOKEN_RE.findall(value.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    )


def opening_span(transcript: str, word_count: int) -> str:
    """First `word_count` whitespace-separated words of a transcript."""
    return " ".join(transcript.split()[:word_count])


def normalize_phone(value: str) -> str:
    """Digits only, dropping a leading US country code when present."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    return digits


def to_e164(value: str) -> str:
    """US-shaped numbers become +1XXXXXXXXXX. Other digit strings keep a leading +."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if digits:
        return f"+{digits}"
    return ""


def normalize_calling_from(value: str) -> str:
    """Organization named in a spoken "calling from" span."""
    text = normalize_organization(value)
    for prefix in ("calling from the ", "calling from "):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def normalize_domain(value: str) -> str:
    """Host only: no scheme, path, query, or leading www."""
    text = value.strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    if text.startswith("www."):
        text = text[4:]
    return text


def normalize_email(value: str) -> str:
    return value.strip().lower()


def email_domain(value: str) -> str:
    normalized = normalize_email(value)
    if "@" not in normalized:
        return ""
    return normalize_domain(normalized.split("@", 1)[1])


def normalize_organization(value: str) -> str:
    """Lowercase organization name with legal suffixes removed."""
    parts = [
        part
        for part in normalize_text(value).split()
        if part not in _ORG_SUFFIXES
    ]
    return " ".join(parts)


def normalize_phrase(value: str) -> str:
    return normalize_text(value)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Token overlap in [0, 1]. Empty sets score 0 (no evidence, not a match)."""
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def overlap_coefficient(left: frozenset[str], right: frozenset[str]) -> float:
    """Share of the smaller set. Empty sets score 0."""
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def levenshtein_distance(left: str, right: str) -> int:
    """Classic edit distance. Callers should pass short normalized strings."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def levenshtein_ratio(left: str, right: str) -> float:
    """1 minus edit distance over the longer length. Empty inputs score 0."""
    if not left or not right:
        return 0.0
    distance = levenshtein_distance(left, right)
    return 1.0 - (distance / max(len(left), len(right)))


def sequence_ratio(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    """Edit-distance ratio over a short token sequence such as an IVR path."""
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    distance = _sequence_distance(left, right)
    return 1.0 - (distance / max(len(left), len(right)))


def _sequence_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, start=1):
        current = [i]
        for j, right_item in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_item != right_item)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def edit_distance_bucket(ratio: float, high: float = 0.90, mid: float = 0.80) -> float:
    """Map a raw edit ratio onto a near-copy bucket. Loose similarity stays 0."""
    if ratio >= high:
        return 1.0
    if ratio >= mid:
        return 0.85
    return 0.0


def interval_gap_seconds(
    left_start: float,
    left_end: float,
    right_start: float,
    right_end: float,
) -> float:
    """Seconds between two intervals. 0 when they overlap or touch."""
    if left_start <= right_end and right_start <= left_end:
        return 0.0
    if left_end < right_start:
        return right_start - left_end
    return left_start - right_end
