"""Strings that must be flagged before anyone is tempted to interpolate them.

A clean scan is not permission to build SQL. Queries stay parameterized.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoisonFixture:
    id: str
    value: str
    categories: tuple[str, ...]
    notes: str = ""


DATABASE_POISONING: tuple[PoisonFixture, ...] = (
    PoisonFixture(
        id="benign_name",
        value="O'Brien",
        categories=(),
        notes="Apostrophes in names are ordinary text.",
    ),
    PoisonFixture(
        id="benign_sentence",
        value="it's a recorded line about a delivery",
        categories=(),
    ),
    PoisonFixture(
        id="or_tautology",
        value="' OR 1=1",
        categories=("sql_meta",),
    ),
    PoisonFixture(
        id="union_select",
        value="1 UNION SELECT password FROM users",
        categories=("sql_meta",),
    ),
    PoisonFixture(
        id="stacked_drop",
        value="'; DROP TABLE calls;--",
        categories=("sql_meta",),
    ),
    PoisonFixture(
        id="block_comment",
        value="admin'/*",
        categories=("sql_meta",),
    ),
    PoisonFixture(
        id="xss_script",
        value="<script>alert(1)</script>",
        categories=("xss_markup",),
    ),
    PoisonFixture(
        id="xss_handler",
        value='<img src=x onerror="alert(1)">',
        categories=("xss_markup",),
    ),
    PoisonFixture(
        id="traversal",
        value="../../etc/passwd",
        categories=("path_traversal",),
    ),
    PoisonFixture(
        id="null_byte",
        value="caller\x00id",
        categories=("null_byte", "control_char"),
    ),
    PoisonFixture(
        id="template_mustache",
        value="{{constructor.constructor('return 1')()}}",
        categories=("template",),
    ),
    PoisonFixture(
        id="template_dollar",
        value="${path}",
        categories=("template",),
    ),
    PoisonFixture(
        id="bidi",
        value="safe\u202eevil",
        categories=("bidi_spoof",),
    ),
    PoisonFixture(
        id="oversized",
        value="A" * 9000,
        categories=("oversized",),
    ),
    PoisonFixture(
        id="bell_control",
        value="hello\x07",
        categories=("control_char",),
    ),
)
