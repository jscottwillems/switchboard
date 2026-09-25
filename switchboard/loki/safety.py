"""Spoken-text constraints for Echo and leak checks for Sentinel."""

import re

# Echo can speak response_text. Keep turns short enough for low-latency TTS.
MAX_SPOKEN_WORDS = 40

# Phrases that would disclose the honeypot, its operators, or its tooling.
# Matched case-insensitively against response_text only.
LEAK_PHRASES: tuple[str, ...] = (
    "honeypot",
    "switchboard",
    "loki",
    "sherlock",
    "sentinel",
    "watson",
    "echo",
    "system prompt",
    "language model",
    "i am an ai",
    "i'm an ai",
    "i am a bot",
    "i'm a bot",
    "as an ai",
    "operator phone",
    "phone numbers i own",
    "infrastructure",
    "openai",
    "anthropic",
)

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_LONG_DIGITS = re.compile(r"\b\d{12,}\b")
_MARKDOWN = re.compile(r"[`#*]|^[-]\s", re.MULTILINE)


def word_count(text: str) -> int:
    return len(text.split())


def spoken_text_issues(text: str) -> list[str]:
    """Return human-readable problems. An empty list means the line is speakable."""

    issues: list[str] = []
    if not text.strip():
        issues.append("response_text is empty")
        return issues
    if "\n" in text or "\r" in text:
        issues.append("response_text contains a newline")
    if word_count(text) > MAX_SPOKEN_WORDS:
        issues.append(f"response_text exceeds {MAX_SPOKEN_WORDS} words")
    if text.count("?") > 1:
        issues.append("response_text asks more than one question")
    lowered = text.lower()
    for phrase in LEAK_PHRASES:
        if phrase in lowered:
            issues.append(f"response_text contains leak phrase: {phrase}")
    if _SSN.search(text):
        issues.append("response_text contains an SSN-shaped number")
    if _LONG_DIGITS.search(text):
        issues.append("response_text contains a long digit secret")
    if _MARKDOWN.search(text):
        issues.append("response_text contains markdown")
    return issues


def safe_slot_text(value: str | None) -> str | None:
    """Drop caller-controlled text that would be unsafe to speak back."""

    if value is None:
        return None
    if spoken_text_issues(value):
        return None
    if word_count(value) > 8:
        return None
    return value
