"""Outbound URL fixtures. Allowed host for the suite is reports.example.com."""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_TEST_HOSTS = frozenset({"reports.example.com", "stt.example.com"})


@dataclass(frozen=True, slots=True)
class UrlFixture:
    id: str
    url: str
    expect_ok: bool
    notes: str = ""


OUTBOUND_URL_FIXTURES: tuple[UrlFixture, ...] = (
    UrlFixture(
        id="allowed_https",
        url="https://reports.example.com/r/1?x=1",
        expect_ok=True,
    ),
    UrlFixture(
        id="allowed_explicit_port",
        url="https://stt.example.com:443/v1/transcribe",
        expect_ok=True,
    ),
    UrlFixture(id="empty", url="", expect_ok=False),
    UrlFixture(id="http", url="http://reports.example.com/r", expect_ok=False),
    UrlFixture(
        id="userinfo",
        url="https://user:pass@reports.example.com/r",
        expect_ok=False,
    ),
    UrlFixture(
        id="metadata_ip",
        url="https://169.254.169.254/latest/meta-data",
        expect_ok=False,
        notes="IP literals are rejected before any allowlist check.",
    ),
    UrlFixture(id="loopback_v4", url="https://127.0.0.1/", expect_ok=False),
    UrlFixture(id="loopback_v6", url="https://[::1]/", expect_ok=False),
    UrlFixture(id="file_scheme", url="file:///etc/passwd", expect_ok=False),
    UrlFixture(id="javascript_scheme", url="javascript:alert(1)", expect_ok=False),
    UrlFixture(
        id="suffix_trick",
        url="https://reports.example.com.evil.example/r",
        expect_ok=False,
    ),
    UrlFixture(
        id="path_lookalike",
        url="https://evil.example/reports.example.com",
        expect_ok=False,
    ),
    UrlFixture(id="localhost", url="https://localhost/", expect_ok=False),
    UrlFixture(
        id="dot_local",
        url="https://reports.example.com.local/r",
        expect_ok=False,
    ),
    UrlFixture(
        id="obfuscated_ip",
        url="https://0x7f000001/",
        expect_ok=False,
    ),
    UrlFixture(
        id="newline",
        url="https://reports.example.com/\n",
        expect_ok=False,
    ),
    UrlFixture(id="ssh_port", url="https://reports.example.com:22/", expect_ok=False),
    UrlFixture(
        id="fragment",
        url="https://reports.example.com/r#frag",
        expect_ok=False,
    ),
    UrlFixture(
        id="backslash",
        url="https://reports.example.com\\@evil.example",
        expect_ok=False,
    ),
    UrlFixture(
        id="homoglyph_host",
        url="https://ex\u0430mple.com/",
        expect_ok=False,
        notes="The second character of the label is Cyrillic a.",
    ),
    UrlFixture(
        id="too_long",
        url="https://reports.example.com/" + ("a" * 3000),
        expect_ok=False,
    ),
    UrlFixture(id="no_host", url="https:///nohost", expect_ok=False),
    UrlFixture(
        id="leading_space",
        url=" https://reports.example.com/",
        expect_ok=False,
    ),
)
