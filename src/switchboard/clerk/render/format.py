"""Shared display formatting. Formatting does not change stored values."""

from __future__ import annotations

from datetime import datetime, timezone

from switchboard.clerk.schemas.provenance import ABSENT


def iso_z(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def score_text(score: float) -> str:
    return f"{score:.2f}"


def present(value: str | None) -> str:
    if value is None:
        return ABSENT
    return value


def join_ids(values: list[str]) -> str:
    if not values:
        return ABSENT
    return ", ".join(values)
