"""Other agents import the corpora from either package path."""

from __future__ import annotations

import json

import sentinel.fixtures as package_fixtures
import tests.fixtures.adversarial as test_fixtures


def test_reexport_matches_the_package() -> None:
    for name in (
        "PROMPT_INJECTION_CORPUS",
        "PROVIDER_EVENT_FIXTURES",
        "WEBHOOK_ATTACK_FIXTURES",
        "WEBHOOK_REPLAY_SAMPLE",
        "MALICIOUS_TRANSCRIPTS",
        "OUTBOUND_URL_FIXTURES",
        "DATABASE_POISONING",
        "MODEL_OUTPUT_FIXTURES",
        "TEST_WEBHOOK_SECRET",
    ):
        assert getattr(test_fixtures, name) is getattr(package_fixtures, name)


def test_fixture_ids_are_unique() -> None:
    groups = (
        package_fixtures.PROMPT_INJECTION_CORPUS,
        package_fixtures.PROVIDER_EVENT_FIXTURES,
        package_fixtures.WEBHOOK_ATTACK_FIXTURES,
        package_fixtures.MALICIOUS_TRANSCRIPTS,
        package_fixtures.OUTBOUND_URL_FIXTURES,
        package_fixtures.DATABASE_POISONING,
        package_fixtures.MODEL_OUTPUT_FIXTURES,
    )
    for group in groups:
        ids = [item.id for item in group]
        assert ids
        assert len(ids) == len(set(ids))


def test_labeled_text_corpora_have_text_and_consistent_flags() -> None:
    for item in package_fixtures.PROMPT_INJECTION_CORPUS:
        assert item.text
        assert item.expect_flagged is bool(item.categories)
    for item in package_fixtures.MALICIOUS_TRANSCRIPTS:
        assert item.text
    for item in package_fixtures.DATABASE_POISONING:
        assert item.value
    for item in package_fixtures.OUTBOUND_URL_FIXTURES:
        assert item.id
        if item.expect_ok:
            assert item.url.startswith("https://")
    for item in package_fixtures.MODEL_OUTPUT_FIXTURES:
        assert item.expect_reason
        if item.expect_reason == "ok":
            assert item.raw.startswith("{")


def test_provider_event_labels_match_the_bytes() -> None:
    for item in package_fixtures.PROVIDER_EVENT_FIXTURES:
        assert (item.expect_failure is None) is item.expect_ok
        if item.expect_ok:
            parsed = json.loads(item.raw)
            assert isinstance(parsed, dict)
        else:
            assert item.expect_failure


def test_webhook_secret_placeholder_is_not_empty() -> None:
    assert package_fixtures.TEST_WEBHOOK_SECRET == "dev"
