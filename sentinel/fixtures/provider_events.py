"""Malformed and valid provider-event samples.

Labels describe the bytes. This package does not define the event schema;
ATLAS owns ``docs/EVENTS.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventFixture:
    id: str
    raw: bytes
    expect_ok: bool
    expect_failure: str | None = None
    notes: str = ""


def _json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


_VALID = {
    "id": "evt_1",
    "type": "call.started",
    "call_id": "call_1",
    "occurred_at": "2026-09-25T15:00:00Z",
    "payload": {"source": "pstn"},
}

_BASE_KEYS = {
    "id": "evt_1",
    "type": "call.started",
    "call_id": "call_1",
    "occurred_at": "2026-09-25T15:00:00Z",
}


def _with(**overrides: object) -> bytes:
    body = dict(_VALID)
    body.update(overrides)
    return _json(body)


PROVIDER_EVENT_FIXTURES: tuple[EventFixture, ...] = (
    EventFixture(id="valid", raw=_json(_VALID), expect_ok=True),
    EventFixture(id="empty", raw=b"", expect_ok=False, expect_failure="empty"),
    EventFixture(
        id="too_large",
        raw=b"{" + (b"a" * 70_000),
        expect_ok=False,
        expect_failure="too_large",
    ),
    EventFixture(id="invalid_utf8", raw=b"\xff\xfe{", expect_ok=False, expect_failure="invalid_encoding"),
    EventFixture(
        id="bom",
        raw=b"\xef\xbb\xbf" + _json(_VALID),
        expect_ok=False,
        expect_failure="invalid_encoding",
    ),
    EventFixture(id="not_json", raw=b"not-json", expect_ok=False, expect_failure="invalid_json"),
    EventFixture(id="array", raw=b"[]", expect_ok=False, expect_failure="not_object"),
    EventFixture(id="null", raw=b"null", expect_ok=False, expect_failure="not_object"),
    EventFixture(
        id="duplicate_id",
        raw=(
            b'{"id":"evt_1","id":"evt_2","type":"call.started","call_id":"call_1",'
            b'"occurred_at":"2026-09-25T15:00:00Z","payload":{}}'
        ),
        expect_ok=False,
        expect_failure="duplicate_key",
    ),
    EventFixture(
        id="missing_call_id",
        raw=_json(
            {
                "id": "evt_1",
                "type": "call.started",
                "occurred_at": "2026-09-25T15:00:00Z",
                "payload": {},
            }
        ),
        expect_ok=False,
        expect_failure="missing_field",
    ),
    EventFixture(
        id="unknown_top_level",
        raw=_with(extra=True),
        expect_ok=False,
        expect_failure="unknown_key",
    ),
    EventFixture(
        id="unknown_type",
        raw=_with(type="call.transfer"),
        expect_ok=False,
        expect_failure="unknown_type",
    ),
    EventFixture(
        id="call_id_object",
        raw=_with(call_id={"id": "nope"}),
        expect_ok=False,
        expect_failure="invalid_field",
    ),
    EventFixture(
        id="bad_date",
        raw=_with(occurred_at="2026-13-01T00:00:00Z"),
        expect_ok=False,
        expect_failure="invalid_field",
    ),
    EventFixture(
        id="payload_array",
        raw=_with(payload=["nope"]),
        expect_ok=False,
        expect_failure="invalid_field",
    ),
    EventFixture(
        id="proto_key",
        raw=_json({**_BASE_KEYS, "payload": {"__proto__": "polluted"}}),
        expect_ok=False,
        expect_failure="invalid_field",
        notes="Payload keys are lowercase snake_case. Evidence text stays in values.",
    ),
    EventFixture(
        id="deep_nesting",
        raw=_json({**_BASE_KEYS, "payload": {"a": {"b": {"c": {"d": 1}}}}}),
        expect_ok=False,
        expect_failure="nesting",
    ),
    EventFixture(
        id="oversized_string",
        raw=_json({**_BASE_KEYS, "payload": {"text": "a" * 4097}}),
        expect_ok=False,
        expect_failure="invalid_field",
    ),
    EventFixture(
        id="hostile_transcript_preserved",
        raw=_json(
            {
                "id": "evt_xss",
                "type": "transcript.final",
                "call_id": "call_1",
                "occurred_at": "2026-09-25T15:00:00Z",
                "payload": {"text": "<script>alert(1)</script>"},
            }
        ),
        expect_ok=True,
        notes="Structure is valid. Rendering and SQL still have to treat the text as data.",
    ),
)
