"""SB-017: insert and fetch per writer boundary, including Bell's observation port."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from switchboard_api.deps import open_observation_writer, open_read_models
from switchboard_api.obs_store import get_obs_store
from switchboard_api.settings import get_settings
from switchboard_events import EventBus, build_envelope
from switchboard_intelligence.deps import open_attribution_writer, open_finding_writer
from switchboard_repositories import (
    InvalidCursor,
    NotFound,
    StateConflict,
    TelephonyObsStore,
    unit_of_work,
)
from switchboard_repositories.columns import FINDING_COLUMNS
from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.enums import (
    CallState,
    CampaignStatus,
    EventType,
    FindingKind,
    FindingStatus,
    MediaStreamState,
    Producer,
    Speaker,
    TranscriptSource,
)
from switchboard_schemas.events import TelephonyCallReceived
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding
from switchboard_schemas.observations import (
    CallSession,
    MediaStream,
    OperatorNumber,
    TranscriptSegment,
)

from tests.db_support import apply_migrations, database_url as configured_database_url, truncate_records

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture
def database_url() -> Iterator[str]:
    url = configured_database_url()
    apply_migrations(url)
    truncate_records(url)
    yield url


def _session(
    external: str,
    *,
    session_id: UUID | None = None,
    caller: str = "+15551212000",
    started: datetime | None = None,
) -> CallSession:
    return CallSession(
        id=session_id or uuid4(),
        operator_number_id=DEV_OPERATOR_ID,
        external_call_id=external,
        carrier="mock",
        caller_number_e164=caller,
        called_number_e164="+15550001001",
        state=CallState.RINGING,
        started_at=started or NOW,
    )


def _stream(session_id: UUID) -> MediaStream:
    return MediaStream(
        id=uuid4(),
        call_session_id=session_id,
        external_stream_id="stream-1",
        encoding="audio/pcmu",
        sample_rate_hz=8000,
        state=MediaStreamState.CONNECTING,
        started_at=NOW,
    )


def _segment(session_id: UUID, stream_id: UUID, *, sequence: int, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        id=uuid4(),
        call_session_id=session_id,
        media_stream_id=stream_id,
        sequence=sequence,
        speaker=Speaker.CALLER,
        source=TranscriptSource.STT,
        text=text,
        start_offset_ms=0,
        end_offset_ms=100,
        is_final=True,
        stt_confidence=0.5,
        provider="mock-stt",
        created_at=NOW,
    )


def test_telephony_obs_store_keeps_sb001_session_and_receipt_behavior(database_url: str) -> None:
    store = TelephonyObsStore(database_url)
    with store.connection() as conn:
        assert store.find_active_operator_id(conn, "+15550001001") == DEV_OPERATOR_ID
        assert store.find_active_operator_id(conn, "+15559999999") is None

    first_id = uuid4()
    second_id = uuid4()
    with store.connection() as conn:
        stored_id, created = store.insert_ringing_session(
            conn,
            _session("demo-1", session_id=first_id, caller="+15551110000"),
        )
        receipt_id = store.insert_webhook_receipt(
            conn,
            provider="mock",
            event_type="voice",
            payload={"provider_call_id": "demo-1", "nested": {"ok": True}},
            signature_valid=None,
            call_session_id=stored_id,
        )
    assert created
    assert stored_id == first_id

    with store.connection() as conn:
        again_id, again_created = store.insert_ringing_session(
            conn,
            _session("demo-1", session_id=second_id, caller="+15552220000"),
        )
        rejected = store.insert_webhook_receipt(
            conn,
            provider="mock",
            event_type="voice",
            payload={"provider_call_id": "unknown"},
            signature_valid=False,
            call_session_id=None,
        )
    assert not again_created
    assert again_id == first_id

    with unit_of_work(database_url) as uow:
        stored = uow.call_sessions().get(first_id)
        assert stored is not None
        assert stored.caller_number_e164 == "+15551110000"
        assert stored.state is CallState.RINGING
        receipt = uow.webhook_receipts().get(receipt_id)
        assert receipt is not None
        assert receipt.signature_valid is None
        assert receipt.payload == {"provider_call_id": "demo-1", "nested": {"ok": True}}
        assert receipt.call_session_id == first_id
        orphan = uow.webhook_receipts().get(rejected)
        assert orphan is not None
        assert orphan.call_session_id is None
        assert uow.webhook_receipts().list_for_session(first_id)[0].id == receipt_id


def test_obs_store_rollback_drops_the_session_and_the_receipt(database_url: str) -> None:
    store = get_obs_store()
    session = _session("rollback-1")
    with pytest.raises(RuntimeError, match="boom"):
        with store.connection() as conn:
            store.insert_ringing_session(conn, session)
            store.insert_webhook_receipt(
                conn,
                provider="mock",
                event_type="voice",
                payload={"provider_call_id": "rollback-1"},
                signature_valid=True,
                call_session_id=session.id,
            )
            raise RuntimeError("boom")
    with unit_of_work(database_url) as uow:
        assert uow.call_sessions().get(session.id) is None


def test_call_state_moves_forward_and_lists_by_cursor(database_url: str) -> None:
    with open_observation_writer() as writer:
        early, _ = writer.call_sessions().insert_ringing(
            _session("early", started=NOW),
        )
        middle, _ = writer.call_sessions().insert_ringing(
            _session("middle", started=NOW + timedelta(seconds=1)),
        )
        late, _ = writer.call_sessions().insert_ringing(
            _session("late", started=NOW + timedelta(seconds=2)),
        )
        answered = writer.call_sessions().apply_state(
            late.id,
            state=CallState.IN_PROGRESS,
            answered_at=NOW + timedelta(seconds=3),
        )
        assert answered.state is CallState.IN_PROGRESS
        assert answered.answered_at == NOW + timedelta(seconds=3)
        answered_again = writer.call_sessions().apply_state(
            late.id,
            state=CallState.IN_PROGRESS,
            answered_at=NOW + timedelta(seconds=9),
        )
        assert answered_again.answered_at == answered.answered_at
        completed = writer.call_sessions().apply_state(
            late.id,
            state=CallState.COMPLETED,
            ended_at=NOW + timedelta(seconds=4),
            end_reason="hangup",
        )
        assert completed.end_reason == "hangup"
        replaced = writer.call_sessions().apply_state(
            late.id,
            state=CallState.COMPLETED,
            end_reason="remote-hangup",
        )
        assert replaced.end_reason == "remote-hangup"
        assert replaced.ended_at == completed.ended_at
        with pytest.raises(StateConflict):
            writer.call_sessions().apply_state(late.id, state=CallState.IN_PROGRESS)
        with pytest.raises(NotFound):
            writer.call_sessions().apply_state(uuid4(), state=CallState.FAILED, end_reason="missing")
        page, cursor = writer.call_sessions().list_page(limit=2)
        assert [item.id for item in page] == [late.id, middle.id]
        assert cursor is not None
        rest, next_cursor = writer.call_sessions().list_page(limit=2, cursor=cursor)
        assert [item.id for item in rest] == [early.id]
        assert next_cursor is None
        with pytest.raises(InvalidCursor):
            writer.call_sessions().list_page(limit=2, cursor="not-a-cursor")


def test_transcripts_are_immutable_and_ordered(database_url: str) -> None:
    with unit_of_work(database_url) as uow:
        session, _ = uow.call_sessions().insert_ringing(_session("transcripts"))
        stream, created_stream = uow.media_streams().insert(_stream(session.id))
        assert created_stream
        again, stream_created = uow.media_streams().insert(
            _stream(session.id).model_copy(update={"id": uuid4(), "encoding": "audio/pcm"})
        )
        assert not stream_created
        assert again.id == stream.id
        assert again.encoding == "audio/pcmu"
        streaming = uow.media_streams().apply_state(stream.id, state=MediaStreamState.STREAMING)
        assert streaming.state is MediaStreamState.STREAMING
        with pytest.raises(StateConflict):
            uow.media_streams().apply_state(stream.id, state=MediaStreamState.CONNECTING)
        first, _ = uow.transcripts().insert(
            _segment(session.id, stream.id, sequence=0, text="call me"),
        )
        second, _ = uow.transcripts().insert(
            _segment(session.id, stream.id, sequence=1, text="at five"),
        )
        duplicate, created = uow.transcripts().insert(
            _segment(session.id, stream.id, sequence=0, text="rewritten"),
        )
        assert not created
        assert duplicate.id == first.id
        assert duplicate.text == "call me"
        listed = uow.transcripts().list_for_session(session.id)
        assert [item.id for item in listed] == [first.id, second.id]
        with pytest.raises(ValueError, match="final"):
            uow.transcripts().insert(
                _segment(session.id, stream.id, sequence=2, text="partial").model_copy(
                    update={"is_final": False}
                )
            )


def test_findings_have_no_campaign_column_and_status_does_not_rewrite_the_quote(
    database_url: str,
) -> None:
    assert "campaign" not in FINDING_COLUMNS
    with psycopg.connect(database_url, row_factory=dict_row, connect_timeout=3) as conn:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'interp' AND table_name = 'intelligence_finding'
            """
        ).fetchall()
    names = {row["column_name"] for row in rows}
    assert "campaign" not in names
    assert "campaign_id" not in names

    with open_finding_writer() as writer:
        with unit_of_work(database_url) as setup:
            session, _ = setup.call_sessions().insert_ringing(_session("finding"))
        segment_id = uuid4()
        finding = IntelligenceFinding(
            id=uuid4(),
            call_session_id=session.id,
            kind=FindingKind.CALLBACK_NUMBER,
            value="+15557654321",
            raw_quote="call me at +15557654321",
            transcript_segment_ids=[segment_id],
            extractor="rule.e164",
            extractor_version="1",
            confidence=0.4,
            status=FindingStatus.PROPOSED,
            created_at=NOW,
        )
        stored, created = writer.findings().insert(finding)
        assert created
        assert "campaign_id" not in IntelligenceFinding.model_fields
        accepted = writer.findings().set_status(stored.id, FindingStatus.ACCEPTED)
        assert accepted.status is FindingStatus.ACCEPTED
        assert accepted.raw_quote == stored.raw_quote
        assert accepted.transcript_segment_ids == [segment_id]
        assert accepted.value == stored.value
        replay, replay_created = writer.findings().insert(finding)
        assert not replay_created
        assert replay.status is FindingStatus.ACCEPTED
        with pytest.raises(ValueError, match="proposed"):
            writer.findings().insert(
                finding.model_copy(update={"id": uuid4(), "status": FindingStatus.REJECTED})
            )
        listed = writer.findings().list_for_session(session.id)
        assert [item.id for item in listed] == [stored.id]


def test_turns_campaigns_and_attributions_round_trip(database_url: str) -> None:
    assert get_settings().database_url == database_url
    segment_id = uuid4()
    with open_observation_writer() as observations:
        session, _ = observations.call_sessions().insert_ringing(_session("campaign"))
        turn, created = observations.conversation_turns().insert(
            ConversationTurn(
                id=uuid4(),
                call_session_id=session.id,
                turn_index=0,
                speaker=Speaker.CALLER,
                text="hello",
                transcript_segment_ids=[segment_id],
                strategy_id=None,
                confidence=1.0,
                created_at=NOW,
            )
        )
        assert created
        duplicate, turn_created = observations.conversation_turns().insert(
            turn.model_copy(update={"id": uuid4(), "text": "changed"})
        )
        assert not turn_created
        assert duplicate.text == "hello"
    with open_finding_writer() as findings:
        finding, _ = findings.findings().insert(
            IntelligenceFinding(
                id=uuid4(),
                call_session_id=session.id,
                kind=FindingKind.OTHER,
                value="hello",
                raw_quote="hello",
                transcript_segment_ids=[segment_id],
                extractor="rule",
                extractor_version="1",
                confidence=0.2,
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
                call_session_id=session.id,
                supporting_finding_ids=[finding.id],
                method="exact-callback",
                method_version="1",
                confidence=0.3,
                rationale="shared callback number",
                created_at=NOW,
            )
        )
        closed = attributions.campaigns().set_status(campaign.id, CampaignStatus.CLOSED)
        assert closed.status is CampaignStatus.CLOSED
        assert closed.label == "cluster-a"
        assert attributions.attributions().list_for_session(session.id)[0].id == attribution.id
        assert attributions.attributions().list_for_campaign(campaign.id)[0].id == attribution.id
        page, cursor = attributions.campaigns().list_page(limit=1)
        assert page[0].id == campaign.id
        assert cursor is None


def test_publish_failure_does_not_roll_back_a_committed_session(database_url: str) -> None:
    session = _session("hot-path")
    with open_read_models() as models:
        assert models.call_sessions().get(session.id) is None
    with open_observation_writer() as writer:
        stored, created = writer.call_sessions().insert_ringing(session)
    assert created
    envelope = build_envelope(
        event_type=EventType.TELEPHONY_CALL_RECEIVED,
        producer=Producer.API,
        call_session_id=stored.id,
        payload=TelephonyCallReceived(
            external_call_id=stored.external_call_id,
            carrier="mock",
            caller_number_e164=stored.caller_number_e164,
            called_number_e164=stored.called_number_e164,
        ),
        occurred_at=NOW,
    )
    result = EventBus("redis://127.0.0.1:6399/0", socket_timeout_seconds=0.2).publish(envelope)
    assert result.failed
    with open_read_models() as models:
        kept = models.call_sessions().get(stored.id)
    assert kept is not None
    assert kept.external_call_id == "hot-path"


def test_retired_operator_number_is_not_active(database_url: str) -> None:
    retired = OperatorNumber(
        id=uuid4(),
        e164=f"+1999{uuid4().int % 10_000_000:07d}",
        label="old",
        status="retired",
        created_at=NOW,
    )
    with unit_of_work(database_url) as uow:
        stored, created = uow.operator_numbers().insert(retired)
        assert created
        assert uow.operator_numbers().find_active_id(retired.e164) is None
        assert uow.operator_numbers().get(stored.id) is not None
        again, again_created = uow.operator_numbers().insert(
            retired.model_copy(update={"id": uuid4(), "label": "renamed"})
        )
        assert not again_created
        assert again.label == "old"
