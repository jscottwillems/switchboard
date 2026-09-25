"""Precision and recall against the 50 synthetic transcripts.

Gold labels are the indicators the fixture builder planted. They are not
copied from extractor output. On this set the deterministic extractor is
expected to hit every planted indicator and to emit nothing else:

- precision 1.0
- recall 1.0

That is the coverage bar for obvious surface forms (see
``DETERMINISTIC_COVERAGE``). Decoy segments hold the model gaps — spoken
digits, word amounts, paraphrased urgency, and 'dot com' hosts — and must
produce no observations.
"""

from collections import Counter

from switchboard_intelligence.extraction.pipeline import extract_intelligence
from switchboard_intelligence.schemas import ObservationKind, Transcript
from switchboard_intelligence.schemas.inference import InferenceKind, PhoneSourceTag

EXPECTED_INFERENCE_KINDS = {
    InferenceKind.IMPERSONATED_ORGANIZATION,
    InferenceKind.PAYMENT_RAIL,
    InferenceKind.DATA_TARGET,
    InferenceKind.PRESSURE_TACTIC,
    InferenceKind.OFFER_TERMS,
    InferenceKind.CALLBACK_CHANNEL,
    InferenceKind.THREATENED_CONSEQUENCE,
    InferenceKind.CLAIMED_COMPANY_NORMALIZED,
    InferenceKind.PHONE_E164,
    InferenceKind.DOMAIN_REGISTRABLE,
    InferenceKind.EMAIL_LOCAL_DOMAIN,
    InferenceKind.EMAIL_DOMAIN_REGISTRABLE,
    InferenceKind.SCRIPT_PHRASE_NORMALIZED,
    InferenceKind.OPENING_SCRIPT_FINGERPRINT,
    InferenceKind.PRETEXT_CATEGORY_CANONICAL,
    InferenceKind.IDENTIFIER_KIND,
}


def test_fixture_count_and_kind_coverage(fixture_rows: list[dict[str, object]]) -> None:
    assert len(fixture_rows) == 50
    families = Counter(row["family"] for row in fixture_rows)
    assert set(families) == {
        "irs",
        "ssa",
        "microsoft",
        "warranty",
        "student",
        "bank",
        "medicare",
        "utility",
        "package",
        "prize",
    }
    assert set(families.values()) == {5}
    planted = {item["kind"] for row in fixture_rows for item in row["gold"]}
    assert planted == {kind.value for kind in ObservationKind}


def test_obvious_indicator_precision_and_recall(fixture_rows: list[dict[str, object]]) -> None:
    true_positive = 0
    predicted = 0
    gold_total = 0
    for row in fixture_rows:
        transcript = Transcript.model_validate(row["transcript"])
        bundle = extract_intelligence(transcript)
        segments = {segment.segment_id: segment for segment in transcript.segments}
        pred = Counter(
            (item.kind.value, item.transcript_segment_id, item.value) for item in bundle.observations
        )
        gold = Counter((item["kind"], item["segment_id"], item["value"]) for item in row["gold"])
        assert pred == gold, row["call_id"]
        by_signature = {
            (item.kind.value, item.transcript_segment_id, item.value): item for item in bundle.observations
        }
        for item in row["gold"]:
            observation = by_signature[(item["kind"], item["segment_id"], item["value"])]
            if "payment_method" in item:
                assert observation.payment_method is not None
                assert observation.payment_method.value == item["payment_method"]
            else:
                assert observation.payment_method is None
            if "pretext_category" in item:
                assert observation.pretext_category is not None
                assert observation.pretext_category.value == item["pretext_category"]
                assert observation.normalized_value == item["pretext_category"]
            else:
                assert observation.pretext_category is None
            if observation.kind is ObservationKind.OPENING_SCRIPT_TEXT:
                assert observation.opening_turn_index == item["opening_turn_index"]
            else:
                assert observation.opening_turn_index is None
            if observation.kind is ObservationKind.SCRIPT_LANGUAGE:
                assert observation.locale is not None
                assert observation.locale.value == item["locale"]
                assert observation.normalized_value == item["locale"]
            else:
                assert observation.locale is None
        phone_tags = {
            item.source_tag
            for item in bundle.inferences
            if item.kind is InferenceKind.PHONE_E164
        }
        assert phone_tags == {
            PhoneSourceTag.CALLBACK,
            PhoneSourceTag.SPOKEN,
            PhoneSourceTag.SPOKEN_CLI,
        }
        assert any(item.fingerprint_tokens for item in bundle.inferences)
        assert bundle.elicited_hints == []
        true_positive += sum((pred & gold).values())
        predicted += sum(pred.values())
        gold_total += sum(gold.values())
        decoys = set(row["decoy_segment_ids"])
        assert decoys
        assert all(item.transcript_segment_id not in decoys for item in bundle.observations)
        for observation in bundle.observations:
            segment = segments[observation.transcript_segment_id]
            assert segment.text[observation.char_start : observation.char_end] == observation.value
            assert segment.start_timestamp <= observation.start_timestamp <= observation.end_timestamp
            assert observation.end_timestamp <= segment.end_timestamp
            assert observation.source.startswith("deterministic.rules/v1#")
        assert {item.kind for item in bundle.inferences} == EXPECTED_INFERENCE_KINDS
        assert bundle.attributions == []
        again = extract_intelligence(transcript)
        assert again.model_dump(mode="json") == bundle.model_dump(mode="json")

    assert predicted == gold_total
    precision = true_positive / predicted
    recall = true_positive / gold_total
    assert precision == 1.0
    assert recall == 1.0
