"""Normalization and similarity primitives."""

from watson.config import ScoringConfig
from watson.textutil import (
    edit_distance_bucket,
    jaccard,
    levenshtein_ratio,
    normalize_domain,
    normalize_organization,
    normalize_phone,
    tokenize,
)


def test_phone_drops_punctuation_and_country_code() -> None:
    assert normalize_phone("(800) 555-0101") == "8005550101"
    assert normalize_phone("1-800-555-0101") == "8005550101"


def test_domain_strips_scheme_path_and_www() -> None:
    assert normalize_domain("https://www.irs-refund-help.com/claim") == "irs-refund-help.com"


def test_organization_drops_legal_suffix() -> None:
    assert normalize_organization("Acme Holdings, LLC") == "acme holdings"


def test_jaccard_treats_empty_sets_as_no_evidence() -> None:
    assert jaccard(frozenset(), frozenset({"refund"})) == 0.0
    assert jaccard(frozenset({"refund"}), frozenset({"refund"})) == 1.0


def test_tokenize_drops_stopwords_and_short_tokens() -> None:
    tokens = tokenize("Hello, this is a refund hold.")
    assert "hello" not in tokens
    assert "is" not in tokens
    assert "refund" in tokens
    assert "hold" in tokens


def test_edit_distance_buckets_only_near_copies() -> None:
    config = ScoringConfig()
    assert levenshtein_ratio("refund hold", "refund hold") == 1.0
    assert edit_distance_bucket(0.90, config) == 1.0
    assert edit_distance_bucket(0.80, config) == 0.85
    assert edit_distance_bucket(0.79, config) == 0.0
    assert levenshtein_ratio("", "refund") == 0.0
