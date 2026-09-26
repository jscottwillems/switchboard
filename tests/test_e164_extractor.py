"""SB-009: an E.164 in a segment becomes one proposed callback_number finding."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from switchboard_classification import E164FindingExtractor, NullFindingExtractor
from switchboard_schemas.enums import FindingKind, FindingStatus, RecordLayer, Speaker, TranscriptSource
from switchboard_schemas.observations import TranscriptSegment

NOW = datetime(2026, 9, 25, 21, 0, tzinfo=timezone.utc)
CALL_ID = uuid4()
EXTRACTOR = E164FindingExtractor()
_KAYLA_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "scam_calls" / "kayla_personal_loan.json"


def _segment(text: str, *, sequence: int = 0, is_final: bool = True) -> TranscriptSegment:
    return TranscriptSegment(
        id=uuid4(),
        call_session_id=CALL_ID,
        media_stream_id=uuid4(),
        sequence=sequence,
        speaker=Speaker.CALLER,
        source=TranscriptSource.STT,
        text=text,
        start_offset_ms=sequence * 1000,
        end_offset_ms=sequence * 1000 + 800,
        is_final=is_final,
        stt_confidence=0.91,
        provider="mock-stt",
        created_at=NOW,
    )


def _kayla_sample() -> dict[str, object]:
    loaded = json.loads(_KAYLA_FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("kayla fixture must be an object")
    return loaded


def test_e164_segment_yields_one_proposed_callback_finding() -> None:
    segment = _segment("Please call me back at +15551234567 today.")
    findings = EXTRACTOR.extract([segment])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.record_layer is RecordLayer.INTERPRETATION
    assert finding.kind is FindingKind.CALLBACK_NUMBER
    assert finding.status is FindingStatus.PROPOSED
    assert finding.value == "+15551234567"
    assert finding.raw_quote == "+15551234567"
    assert finding.raw_quote in segment.text
    assert finding.transcript_segment_ids == [segment.id]
    assert finding.call_session_id == segment.call_session_id
    assert finding.extractor == "e164"
    assert finding.extractor_version == "0.1.0"
    assert finding.confidence == 1.0
    assert finding.created_at == segment.created_at


def test_segment_without_e164_yields_nothing() -> None:
    plain = _segment("Please call me back at the office.")
    formatted = _segment("The desk line is (800) 555-0199.", sequence=1)
    assert EXTRACTOR.extract([plain]) == []
    assert EXTRACTOR.extract([formatted]) == []
    assert NullFindingExtractor().extract([_segment("Call +15551234567.")]) == []


def test_distinct_e164s_each_cite_the_segment_and_repeat_is_one() -> None:
    segment = _segment("Try +15551234567 or +15551234567 or +442071234567.")
    findings = EXTRACTOR.extract([segment])
    assert [item.value for item in findings] == ["+15551234567", "+442071234567"]
    assert all(item.transcript_segment_ids == [segment.id] for item in findings)
    assert all(item.status is FindingStatus.PROPOSED for item in findings)


def test_only_segments_that_contain_an_e164_produce_findings() -> None:
    empty = _segment("Nothing to extract.", sequence=0)
    hit = _segment("Callback +15557654321.", sequence=1)
    findings = EXTRACTOR.extract([hit, empty])
    assert len(findings) == 1
    assert findings[0].value == "+15557654321"
    assert findings[0].transcript_segment_ids == [hit.id]


def test_finding_id_is_stable_for_the_same_span() -> None:
    segment = _segment("Reach us at +15550001111.")
    first = EXTRACTOR.extract([segment])
    second = EXTRACTOR.extract([segment])
    assert first[0].id == second[0].id


def test_kayla_personal_loan_e164_in_final_segment_proposes_callback() -> None:
    """Josh's sample stays spoken text. The closing final carries its E.164."""

    sample = _kayla_sample()
    transcript = sample["transcript"]
    spoken = sample["callback_spoken"]
    e164 = sample["callback_e164"]
    assert isinstance(transcript, str)
    assert spoken == "888-269-4564"
    assert e164 == "+18882694564"
    assert sample["scenario"] == "personal_loan_callback"
    assert sample["live_carrier_call"] is False
    assert sample["press_digit"] == "2"
    assert sample["callback_pattern"] == "press_2_or_call_back"
    assert transcript.startswith("Hi, this is Kayla, senior loan specialist.")
    assert "another building option" in transcript
    assert "around.  before moving forward" in transcript
    assert "Press 2 now or call me at 888-269-4564." in transcript
    assert transcript.endswith("Call me at 888-269-4564 again, 888-269-4564.")
    assert transcript.count(spoken) == 3
    assert e164 not in transcript

    closing_at = transcript.rfind("Call me at ")
    earlier = _segment(transcript[:closing_at].rstrip(), sequence=0, is_final=True)
    final = _segment(transcript[closing_at:].replace(spoken, str(e164)), sequence=1, is_final=True)
    assert earlier.is_final is True
    assert final.is_final is True
    assert e164 not in earlier.text
    assert final.text == "Call me at +18882694564 again, +18882694564."

    findings = EXTRACTOR.extract([earlier, final])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.record_layer is RecordLayer.INTERPRETATION
    assert finding.kind is FindingKind.CALLBACK_NUMBER
    assert finding.status is FindingStatus.PROPOSED
    assert finding.value == "+18882694564"
    assert finding.raw_quote == "+18882694564"
    assert finding.raw_quote in final.text
    assert finding.transcript_segment_ids == [final.id]
    assert finding.call_session_id == final.call_session_id
    assert finding.extractor == "e164"
    assert finding.confidence == 1.0
