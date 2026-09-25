from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from switchboard_schemas.api import VoiceInstruction
from switchboard_schemas.attribution import CampaignAttribution
from switchboard_schemas.enums import (
    CallState,
    EventType,
    FindingKind,
    FindingStatus,
    Producer,
    RecordLayer,
    Speaker,
)
from switchboard_schemas.events import PAYLOAD_MODELS, EventEnvelope, validate_event
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import CallSession

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def test_event_payloads_cover_every_event_type() -> None:
    assert set(PAYLOAD_MODELS) == set(EventType)


def test_typescript_stub_names_every_event() -> None:
    text = (ROOT / "packages/schemas/ts/index.ts").read_text()
    for event_type in EventType:
        assert f'"{event_type.value}"' in text


def test_call_session_is_an_observation() -> None:
    session = CallSession(
        id=uuid4(),
        operator_number_id=None,
        external_call_id="demo-1",
        carrier="mock",
        caller_number_e164="+15551212000",
        called_number_e164="+15550001001",
        state=CallState.RINGING,
        started_at=NOW,
    )
    assert session.record_layer is RecordLayer.OBSERVATION
    restored = CallSession.model_validate(session.model_dump(mode="json"))
    assert restored.id == session.id


def test_observation_rejects_interpretation_layer() -> None:
    with pytest.raises(ValidationError):
        CallSession.model_validate(
            {
                "record_layer": RecordLayer.INTERPRETATION,
                "id": str(uuid4()),
                "operator_number_id": None,
                "external_call_id": "demo-1",
                "carrier": "mock",
                "caller_number_e164": "+15551212000",
                "called_number_e164": "+15550001001",
                "state": CallState.RINGING,
                "started_at": NOW.isoformat(),
            }
        )


def test_finding_must_cite_a_segment_and_bound_confidence() -> None:
    with pytest.raises(ValidationError):
        IntelligenceFinding(
            id=uuid4(),
            call_session_id=uuid4(),
            kind=FindingKind.CALLBACK_NUMBER,
            value="+15557654321",
            raw_quote="call me",
            transcript_segment_ids=[],
            extractor="rule",
            extractor_version="0",
            confidence=0.4,
            status=FindingStatus.PROPOSED,
            created_at=NOW,
        )
    with pytest.raises(ValidationError):
        IntelligenceFinding(
            id=uuid4(),
            call_session_id=uuid4(),
            kind=FindingKind.OTHER,
            value="x",
            raw_quote="x",
            transcript_segment_ids=[uuid4()],
            extractor="rule",
            extractor_version="0",
            confidence=1.5,
            status=FindingStatus.PROPOSED,
            created_at=NOW,
        )


def test_attribution_must_cite_a_finding() -> None:
    with pytest.raises(ValidationError):
        CampaignAttribution(
            id=uuid4(),
            campaign_id=uuid4(),
            call_session_id=uuid4(),
            supporting_finding_ids=[],
            method="exact_callback_number",
            method_version="0",
            confidence=0.2,
            rationale="no evidence",
            created_at=NOW,
        )


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        CallSession(
            id=uuid4(),
            operator_number_id=None,
            external_call_id="demo-1",
            carrier="mock",
            caller_number_e164="+15551212000",
            called_number_e164="+15550001001",
            state=CallState.RINGING,
            started_at=datetime(2026, 9, 25, 20, 0),
        )


def test_voice_instruction_stream_fields() -> None:
    with pytest.raises(ValidationError):
        VoiceInstruction(action="connect_stream")
    with pytest.raises(ValidationError):
        VoiceInstruction(action="hangup", stream_token="x" * 16)
    ok = VoiceInstruction(action="reject")
    assert ok.stream_url is None


def test_partial_and_final_speech_flags() -> None:
    payload = {
        "transcript_segment_id": str(uuid4()),
        "speaker": Speaker.CALLER,
        "text": "hello",
        "is_final": True,
        "stt_confidence": 0.5,
        "start_offset_ms": 0,
        "end_offset_ms": 400,
        "sequence": 1,
    }
    final = EventEnvelope(
        event_id=uuid4(),
        event_type=EventType.SPEECH_SEGMENT_FINAL,
        occurred_at=NOW,
        producer=Producer.MEDIA_GATEWAY,
        call_session_id=uuid4(),
        payload=payload,
    )
    validate_event(final)
    partial = final.model_copy(update={"event_type": EventType.SPEECH_SEGMENT_PARTIAL})
    with pytest.raises(ValueError):
        validate_event(partial)


def test_sql_keeps_three_schemas() -> None:
    sql = (ROOT / "apps/api/migrations/001_init.sql").read_text()
    assert "CREATE SCHEMA IF NOT EXISTS obs" in sql
    assert "CREATE SCHEMA IF NOT EXISTS interp" in sql
    assert "CREATE SCHEMA IF NOT EXISTS attr" in sql
    assert "CREATE TABLE obs.call_session" in sql
    assert "CREATE TABLE interp.intelligence_finding" in sql
    assert "CREATE TABLE attr.campaign_attribution" in sql
