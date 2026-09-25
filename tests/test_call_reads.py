"""SB-018: call list and detail read stored rows through the repository port."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from switchboard_api.deps import open_observation_writer
from switchboard_api.main import app
from switchboard_intelligence.deps import open_attribution_writer, open_finding_writer
from switchboard_schemas.api import CallDetailResponse, CallListResponse
from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.enums import (
    CallState,
    CampaignStatus,
    FindingKind,
    FindingStatus,
    MediaStreamState,
    Speaker,
    TranscriptSource,
)
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding
from switchboard_schemas.observations import CallSession, MediaStream, TranscriptSegment
from switchboard_telephony import MOCK_SIGNATURE_HEADER, MOCK_SIGNATURE_VALUE

from tests.db_support import database_url as configured_database_url
from tests.db_support import truncate_records

client = TestClient(app)

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")

VOICE = {
    "provider_call_id": "radar-1",
    "from_e164": "+15551212000",
    "to_e164": "+15550001001",
    "timestamp": "2026-09-25T20:00:00Z",
}


@pytest.fixture
def database_url() -> Iterator[str]:
    url = configured_database_url()
    truncate_records(url)
    yield url
    truncate_records(url)


def _session(
    external: str,
    *,
    caller: str = "+15551212000",
    started: datetime | None = None,
) -> CallSession:
    return CallSession(
        id=uuid4(),
        operator_number_id=DEV_OPERATOR_ID,
        external_call_id=external,
        carrier="mock",
        caller_number_e164=caller,
        called_number_e164="+15550001001",
        state=CallState.RINGING,
        started_at=started or NOW,
    )


def test_empty_list_and_unknown_detail_stay_contract_shaped(database_url: str) -> None:
    del database_url
    listing = client.get("/v1/calls")
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "next_cursor": None}
    missing = uuid4()
    for path in (
        f"/v1/calls/{missing}",
        f"/v1/calls/{missing}/transcript",
        f"/v1/calls/{missing}/findings",
        f"/v1/calls/{missing}/attributions",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {
            "error": "call_not_found",
            "message": "No call session exists with that id.",
        }


def test_limit_bounds_and_bad_cursor_are_invalid_requests(database_url: str) -> None:
    del database_url
    for limit in (0, 201):
        response = client.get("/v1/calls", params={"limit": limit})
        assert response.status_code == 422
        assert response.json()["error"] == "invalid_request"
    rejected = client.get("/v1/calls", params={"cursor": "not-a-cursor"})
    assert rejected.status_code == 422
    body = rejected.json()
    assert body["error"] == "invalid_request"
    assert "not-a-cursor" not in body["message"]


def test_list_default_limit_is_50() -> None:
    parameters = client.app.openapi()["paths"]["/v1/calls"]["get"]["parameters"]
    limit = next(item for item in parameters if item["name"] == "limit")
    assert limit["schema"]["default"] == 50
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 200


def test_webhook_session_appears_on_the_list_and_detail(database_url: str) -> None:
    del database_url
    created = client.post(
        "/v1/telephony/voice/mock",
        json=VOICE,
        headers={MOCK_SIGNATURE_HEADER: MOCK_SIGNATURE_VALUE},
    )
    assert created.status_code == 200
    session_id = created.json()["call_session_id"]

    listing = client.get("/v1/calls")
    assert listing.status_code == 200
    page = CallListResponse.model_validate(listing.json())
    assert page.next_cursor is None
    assert len(page.items) == 1
    summary = page.items[0]
    assert str(summary.id) == session_id
    assert summary.state is CallState.RINGING
    assert summary.caller_number_e164 == "+15551212000"
    assert summary.called_number_e164 == "+15550001001"
    assert summary.started_at == datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
    assert summary.ended_at is None
    assert "external_call_id" not in listing.json()["items"][0]

    detail = client.get(f"/v1/calls/{session_id}")
    assert detail.status_code == 200
    body = CallDetailResponse.model_validate(detail.json())
    assert body.session.state is CallState.RINGING
    assert body.session.external_call_id == "radar-1"
    assert body.session.carrier == "mock"
    assert body.session.record_layer == "observation"
    assert body.media_streams == []
    assert body.transcript == []
    assert body.turns == []
    assert body.findings == []
    assert body.attributions == []


def test_list_pages_newest_first_and_detail_keeps_layers_apart(database_url: str) -> None:
    early = _session("early", caller="+15551110001", started=NOW)
    middle = _session("middle", caller="+15551110002", started=NOW + timedelta(seconds=1))
    late = _session("late", caller="+15551110003", started=NOW + timedelta(seconds=2))
    with open_observation_writer() as writer:
        stored_early, _ = writer.call_sessions().insert_ringing(early)
        stored_middle, _ = writer.call_sessions().insert_ringing(middle)
        stored_late, _ = writer.call_sessions().insert_ringing(late)
        writer.call_sessions().apply_state(
            stored_middle.id,
            state=CallState.IN_PROGRESS,
            answered_at=NOW + timedelta(seconds=3),
        )
        writer.call_sessions().apply_state(
            stored_late.id,
            state=CallState.COMPLETED,
            ended_at=NOW + timedelta(seconds=4),
            end_reason="hangup",
        )
        stream, _ = writer.media_streams().insert(
            MediaStream(
                id=uuid4(),
                call_session_id=stored_late.id,
                external_stream_id="stream-1",
                encoding="audio/pcmu",
                sample_rate_hz=8000,
                state=MediaStreamState.CLOSED,
                started_at=NOW + timedelta(seconds=2),
                ended_at=NOW + timedelta(seconds=4),
            )
        )
        segment, _ = writer.transcripts().insert(
            TranscriptSegment(
                id=uuid4(),
                call_session_id=stored_late.id,
                media_stream_id=stream.id,
                sequence=0,
                speaker=Speaker.CALLER,
                source=TranscriptSource.STT,
                text="call me at +15557654321",
                start_offset_ms=0,
                end_offset_ms=100,
                is_final=True,
                stt_confidence=0.5,
                provider="mock-stt",
                created_at=NOW,
            )
        )
        turn, _ = writer.conversation_turns().insert(
            ConversationTurn(
                id=uuid4(),
                call_session_id=stored_late.id,
                turn_index=0,
                speaker=Speaker.CALLER,
                text="call me at +15557654321",
                transcript_segment_ids=[segment.id],
                strategy_id=None,
                confidence=1.0,
                created_at=NOW,
            )
        )
    with open_finding_writer() as findings:
        finding, _ = findings.findings().insert(
            IntelligenceFinding(
                id=uuid4(),
                call_session_id=stored_late.id,
                kind=FindingKind.CALLBACK_NUMBER,
                value="+15557654321",
                raw_quote="call me at +15557654321",
                transcript_segment_ids=[segment.id],
                extractor="e164",
                extractor_version="0.1.0",
                confidence=1.0,
                status=FindingStatus.PROPOSED,
                created_at=NOW,
            )
        )
    with open_attribution_writer() as attributions:
        campaign, _ = attributions.campaigns().insert(
            Campaign(
                id=uuid4(),
                label="cluster-a",
                status=CampaignStatus.HYPOTHESIZED,
                summary=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        attribution, _ = attributions.attributions().insert(
            CampaignAttribution(
                id=uuid4(),
                campaign_id=campaign.id,
                call_session_id=stored_late.id,
                supporting_finding_ids=[finding.id],
                method="exact-callback",
                method_version="1",
                confidence=0.3,
                rationale="shared callback number",
                created_at=NOW,
            )
        )

    first = client.get("/v1/calls", params={"limit": 2})
    assert first.status_code == 200
    first_page = CallListResponse.model_validate(first.json())
    assert [item.id for item in first_page.items] == [stored_late.id, stored_middle.id]
    assert first_page.items[0].state is CallState.COMPLETED
    assert first_page.items[0].ended_at == NOW + timedelta(seconds=4)
    assert first_page.items[1].state is CallState.IN_PROGRESS
    assert first_page.items[1].ended_at is None
    assert first_page.next_cursor is not None

    second = client.get("/v1/calls", params={"limit": 2, "cursor": first_page.next_cursor})
    assert second.status_code == 200
    second_page = CallListResponse.model_validate(second.json())
    assert [item.id for item in second_page.items] == [stored_early.id]
    assert second_page.items[0].state is CallState.RINGING
    assert second_page.items[0].caller_number_e164 == "+15551110001"
    assert second_page.next_cursor is None

    omitted = client.get("/v1/calls")
    assert omitted.status_code == 200
    default_page = CallListResponse.model_validate(omitted.json())
    assert [item.id for item in default_page.items] == [
        stored_late.id,
        stored_middle.id,
        stored_early.id,
    ]
    assert default_page.next_cursor is None

    detail = client.get(f"/v1/calls/{stored_late.id}")
    assert detail.status_code == 200
    body = CallDetailResponse.model_validate(detail.json())
    assert body.session.state is CallState.COMPLETED
    assert body.session.end_reason == "hangup"
    assert body.session.answered_at is None
    assert [item.id for item in body.media_streams] == [stream.id]
    assert [item.id for item in body.transcript] == [segment.id]
    assert body.transcript[0].record_layer == "observation"
    assert body.transcript[0].text == "call me at +15557654321"
    assert [item.id for item in body.turns] == [turn.id]
    assert body.turns[0].record_layer == "interpretation"
    assert body.turns[0].confidence == 1.0
    assert [item.id for item in body.findings] == [finding.id]
    assert body.findings[0].record_layer == "interpretation"
    assert body.findings[0].kind is FindingKind.CALLBACK_NUMBER
    assert body.findings[0].transcript_segment_ids == [segment.id]
    assert [item.id for item in body.attributions] == [attribution.id]
    assert body.attributions[0].record_layer == "attribution"
    assert body.attributions[0].supporting_finding_ids == [finding.id]

    transcript = client.get(f"/v1/calls/{stored_late.id}/transcript")
    assert transcript.status_code == 200
    assert transcript.json()["call_session_id"] == str(stored_late.id)
    assert transcript.json()["segments"][0]["record_layer"] == "observation"
    findings_body = client.get(f"/v1/calls/{stored_late.id}/findings")
    assert findings_body.status_code == 200
    assert findings_body.json()["findings"][0]["record_layer"] == "interpretation"
    linked = client.get(f"/v1/calls/{stored_late.id}/attributions")
    assert linked.status_code == 200
    assert linked.json()["attributions"][0]["record_layer"] == "attribution"

    bare = client.get(f"/v1/calls/{stored_early.id}/transcript")
    assert bare.status_code == 200
    assert bare.json() == {"call_session_id": str(stored_early.id), "segments": []}
