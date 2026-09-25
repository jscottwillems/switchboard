"""Span helpers shared by deterministic extraction."""

import hashlib

from switchboard_intelligence.schemas.transcript import TranscriptSegment


def word_bounded(text: str, start: int, end: int) -> bool:
    if start > 0 and text[start - 1].isalnum():
        return False
    if end < len(text) and text[end].isalnum():
        return False
    return True


def overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in spans)


def find_phrases(text: str, phrases: tuple[str, ...] | list[str]) -> list[tuple[int, int, str]]:
    """Longest-first, non-overlapping, case-insensitive phrase search."""
    occupied: list[tuple[int, int]] = []
    found: list[tuple[int, int, str]] = []
    folded = text.casefold()
    for phrase in sorted(set(phrases), key=len, reverse=True):
        needle = phrase.casefold()
        if len(needle) != len(phrase):
            raise ValueError(f"lexicon phrase is not ASCII: {phrase}")
        cursor = 0
        while True:
            index = folded.find(needle, cursor)
            if index < 0:
                break
            end = index + len(needle)
            if overlaps(index, end, occupied) or not word_bounded(text, index, end):
                cursor = index + 1
                continue
            occupied.append((index, end))
            found.append((index, end, text[index:end]))
            cursor = end
    found.sort(key=lambda item: item[0])
    return found


def span_timestamps(segment: TranscriptSegment, char_start: int, char_end: int) -> tuple[float, float]:
    """Map a character span onto call-relative seconds and clamp to the segment."""
    text_length = max(len(segment.text), 1)
    duration = segment.end_timestamp - segment.start_timestamp
    start = segment.start_timestamp + duration * (char_start / text_length)
    end = segment.start_timestamp + duration * (char_end / text_length)
    start = min(max(start, segment.start_timestamp), segment.end_timestamp)
    end = min(max(end, start), segment.end_timestamp)
    return (round(start, 3), round(end, 3))


def stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
