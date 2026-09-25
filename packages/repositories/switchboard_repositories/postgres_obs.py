"""Postgres writes for ops.operator_number and obs.*."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Json

from switchboard_schemas.enums import CallState, MediaStreamState, TranscriptSource
from switchboard_schemas.observations import (
    CallSession,
    MediaStream,
    OperatorNumber,
    TranscriptSegment,
    WebhookReceipt,
)

from switchboard_repositories.columns import (
    CALL_SESSION_COLUMNS,
    MEDIA_STREAM_COLUMNS,
    OPERATOR_NUMBER_COLUMNS,
    TRANSCRIPT_COLUMNS,
    WEBHOOK_RECEIPT_COLUMNS,
)
from switchboard_repositories.connection import DictConnection
from switchboard_repositories.cursors import decode_cursor, encode_cursor
from switchboard_repositories.errors import NotFound
from switchboard_repositories.mapping import (
    call_session_from_row,
    media_stream_from_row,
    operator_number_from_row,
    transcript_from_row,
    webhook_receipt_from_row,
)
from switchboard_repositories.states import ensure_call_transition, ensure_media_transition


class PostgresOperatorNumbers:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, number: OperatorNumber) -> tuple[OperatorNumber, bool]:
        row = self._conn.execute(
            f"""
            INSERT INTO ops.operator_number (id, e164, label, status, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (e164) DO NOTHING
            RETURNING {OPERATOR_NUMBER_COLUMNS}
            """,
            (number.id, number.e164, number.label, number.status, number.created_at),
        ).fetchone()
        if row is not None:
            return operator_number_from_row(row), True
        existing = self._conn.execute(
            f"""
            SELECT {OPERATOR_NUMBER_COLUMNS}
            FROM ops.operator_number
            WHERE e164 = %s
            """,
            (number.e164,),
        ).fetchone()
        if existing is None:
            raise RuntimeError("operator number conflicted but no row was stored")
        return operator_number_from_row(existing), False

    def get(self, operator_id: UUID) -> OperatorNumber | None:
        row = self._conn.execute(
            f"""
            SELECT {OPERATOR_NUMBER_COLUMNS}
            FROM ops.operator_number
            WHERE id = %s
            """,
            (operator_id,),
        ).fetchone()
        if row is None:
            return None
        return operator_number_from_row(row)

    def find_active_id(self, e164: str) -> UUID | None:
        row = self._conn.execute(
            """
            SELECT id
            FROM ops.operator_number
            WHERE e164 = %s AND status = 'active'
            """,
            (e164,),
        ).fetchone()
        if row is None:
            return None
        operator_id = row["id"]
        if not isinstance(operator_id, UUID):
            raise TypeError("ops.operator_number.id must be a uuid")
        return operator_id


class PostgresCallSessions:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert_ringing(self, session: CallSession) -> tuple[CallSession, bool]:
        """Insert a ringing session. A repeat (carrier, external_call_id) returns the stored row."""

        if session.state is not CallState.RINGING:
            raise ValueError("insert_ringing requires state ringing")
        row = self._conn.execute(
            f"""
            INSERT INTO obs.call_session (
                id,
                operator_number_id,
                external_call_id,
                carrier,
                caller_number_e164,
                called_number_e164,
                state,
                started_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (carrier, external_call_id) DO NOTHING
            RETURNING {CALL_SESSION_COLUMNS}
            """,
            (
                session.id,
                session.operator_number_id,
                session.external_call_id,
                session.carrier,
                session.caller_number_e164,
                session.called_number_e164,
                session.state.value,
                session.started_at,
            ),
        ).fetchone()
        if row is not None:
            return call_session_from_row(row), True
        existing = self.get_by_carrier_call(session.carrier, session.external_call_id)
        if existing is None:
            raise RuntimeError("call session conflicted but no row was stored")
        return existing, False

    def get(self, session_id: UUID) -> CallSession | None:
        row = self._conn.execute(
            f"""
            SELECT {CALL_SESSION_COLUMNS}
            FROM obs.call_session
            WHERE id = %s
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return call_session_from_row(row)

    def get_by_carrier_call(self, carrier: str, external_call_id: str) -> CallSession | None:
        row = self._conn.execute(
            f"""
            SELECT {CALL_SESSION_COLUMNS}
            FROM obs.call_session
            WHERE carrier = %s AND external_call_id = %s
            """,
            (carrier, external_call_id),
        ).fetchone()
        if row is None:
            return None
        return call_session_from_row(row)

    def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[CallSession], str | None]:
        _require_limit(limit)
        moment, row_id = _cursor_bounds(cursor)
        rows = self._conn.execute(
            f"""
            SELECT {CALL_SESSION_COLUMNS}
            FROM obs.call_session
            WHERE (
                %s::timestamptz IS NULL
                OR (started_at, id) < (%s::timestamptz, %s::uuid)
            )
            ORDER BY started_at DESC, id DESC
            LIMIT %s
            """,
            (moment, moment, row_id, limit + 1),
        ).fetchall()
        page = [call_session_from_row(row) for row in rows[:limit]]
        if len(rows) <= limit:
            return page, None
        last = page[-1]
        return page, encode_cursor(last.started_at, last.id)

    def apply_state(
        self,
        session_id: UUID,
        *,
        state: CallState,
        answered_at: datetime | None = None,
        ended_at: datetime | None = None,
        end_reason: str | None = None,
    ) -> CallSession:
        current = self.get(session_id)
        if current is None:
            raise NotFound(f"call session {session_id} does not exist")
        ensure_call_transition(current.state, state)
        answered = current.answered_at if current.answered_at is not None else answered_at
        ended = current.ended_at if current.ended_at is not None else ended_at
        reason = end_reason if end_reason is not None else current.end_reason
        if (
            state == current.state
            and answered == current.answered_at
            and ended == current.ended_at
            and reason == current.end_reason
        ):
            return current
        row = self._conn.execute(
            f"""
            UPDATE obs.call_session
            SET state = %s,
                answered_at = %s,
                ended_at = %s,
                end_reason = %s,
                updated_at = now()
            WHERE id = %s
            RETURNING {CALL_SESSION_COLUMNS}
            """,
            (state.value, answered, ended, reason, session_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"call session {session_id} does not exist")
        return call_session_from_row(row)


class PostgresWebhookReceipts:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(
        self,
        *,
        provider: str,
        event_type: str,
        payload: dict[str, Any],
        signature_valid: bool | None,
        call_session_id: UUID | None,
        receipt_id: UUID | None = None,
        received_at: datetime | None = None,
    ) -> WebhookReceipt:
        stored_id = receipt_id if receipt_id is not None else uuid4()
        received = received_at if received_at is not None else datetime.now(timezone.utc)
        row = self._conn.execute(
            f"""
            INSERT INTO obs.webhook_receipt (
                id,
                call_session_id,
                provider,
                event_type,
                payload,
                signature_valid,
                received_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING {WEBHOOK_RECEIPT_COLUMNS}
            """,
            (
                stored_id,
                call_session_id,
                provider,
                event_type,
                Json(payload),
                signature_valid,
                received,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("webhook receipt insert did not return a row")
        return webhook_receipt_from_row(row)

    def get(self, receipt_id: UUID) -> WebhookReceipt | None:
        row = self._conn.execute(
            f"""
            SELECT {WEBHOOK_RECEIPT_COLUMNS}
            FROM obs.webhook_receipt
            WHERE id = %s
            """,
            (receipt_id,),
        ).fetchone()
        if row is None:
            return None
        return webhook_receipt_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[WebhookReceipt]:
        rows = self._conn.execute(
            f"""
            SELECT {WEBHOOK_RECEIPT_COLUMNS}
            FROM obs.webhook_receipt
            WHERE call_session_id = %s
            ORDER BY received_at ASC, id ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [webhook_receipt_from_row(row) for row in rows]


class PostgresMediaStreams:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, stream: MediaStream) -> tuple[MediaStream, bool]:
        row = self._conn.execute(
            f"""
            INSERT INTO obs.media_stream (
                id,
                call_session_id,
                external_stream_id,
                protocol,
                encoding,
                sample_rate_hz,
                state,
                started_at,
                ended_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (call_session_id, external_stream_id) DO NOTHING
            RETURNING {MEDIA_STREAM_COLUMNS}
            """,
            (
                stream.id,
                stream.call_session_id,
                stream.external_stream_id,
                stream.protocol,
                stream.encoding,
                stream.sample_rate_hz,
                stream.state.value,
                stream.started_at,
                stream.ended_at,
            ),
        ).fetchone()
        if row is not None:
            return media_stream_from_row(row), True
        existing = self._conn.execute(
            f"""
            SELECT {MEDIA_STREAM_COLUMNS}
            FROM obs.media_stream
            WHERE call_session_id = %s AND external_stream_id = %s
            """,
            (stream.call_session_id, stream.external_stream_id),
        ).fetchone()
        if existing is None:
            raise RuntimeError("media stream conflicted but no row was stored")
        return media_stream_from_row(existing), False

    def get(self, stream_id: UUID) -> MediaStream | None:
        row = self._conn.execute(
            f"""
            SELECT {MEDIA_STREAM_COLUMNS}
            FROM obs.media_stream
            WHERE id = %s
            """,
            (stream_id,),
        ).fetchone()
        if row is None:
            return None
        return media_stream_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[MediaStream]:
        rows = self._conn.execute(
            f"""
            SELECT {MEDIA_STREAM_COLUMNS}
            FROM obs.media_stream
            WHERE call_session_id = %s
            ORDER BY started_at ASC, id ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [media_stream_from_row(row) for row in rows]

    def apply_state(
        self,
        stream_id: UUID,
        *,
        state: MediaStreamState,
        ended_at: datetime | None = None,
    ) -> MediaStream:
        current = self.get(stream_id)
        if current is None:
            raise NotFound(f"media stream {stream_id} does not exist")
        ensure_media_transition(current.state, state)
        ended = current.ended_at if current.ended_at is not None else ended_at
        if state == current.state and ended == current.ended_at:
            return current
        row = self._conn.execute(
            f"""
            UPDATE obs.media_stream
            SET state = %s,
                ended_at = %s
            WHERE id = %s
            RETURNING {MEDIA_STREAM_COLUMNS}
            """,
            (state.value, ended, stream_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"media stream {stream_id} does not exist")
        return media_stream_from_row(row)


class PostgresTranscripts:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, segment: TranscriptSegment) -> tuple[TranscriptSegment, bool]:
        if not segment.is_final:
            raise ValueError("transcript observations are final segments")
        if segment.source is TranscriptSource.TTS_INPUT and segment.stt_confidence is not None:
            raise ValueError("tts_input segments do not carry stt_confidence")
        row = self._conn.execute(
            f"""
            INSERT INTO obs.transcript_segment (
                id,
                call_session_id,
                media_stream_id,
                sequence,
                speaker,
                source,
                text,
                language,
                start_offset_ms,
                end_offset_ms,
                is_final,
                stt_confidence,
                provider,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (call_session_id, sequence) DO NOTHING
            RETURNING {TRANSCRIPT_COLUMNS}
            """,
            (
                segment.id,
                segment.call_session_id,
                segment.media_stream_id,
                segment.sequence,
                segment.speaker.value,
                segment.source.value,
                segment.text,
                segment.language,
                segment.start_offset_ms,
                segment.end_offset_ms,
                segment.is_final,
                segment.stt_confidence,
                segment.provider,
                segment.created_at,
            ),
        ).fetchone()
        if row is not None:
            return transcript_from_row(row), True
        existing = self._conn.execute(
            f"""
            SELECT {TRANSCRIPT_COLUMNS}
            FROM obs.transcript_segment
            WHERE call_session_id = %s AND sequence = %s
            """,
            (segment.call_session_id, segment.sequence),
        ).fetchone()
        if existing is None:
            raise RuntimeError("transcript sequence conflicted but no row was stored")
        return transcript_from_row(existing), False

    def get(self, segment_id: UUID) -> TranscriptSegment | None:
        row = self._conn.execute(
            f"""
            SELECT {TRANSCRIPT_COLUMNS}
            FROM obs.transcript_segment
            WHERE id = %s
            """,
            (segment_id,),
        ).fetchone()
        if row is None:
            return None
        return transcript_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[TranscriptSegment]:
        rows = self._conn.execute(
            f"""
            SELECT {TRANSCRIPT_COLUMNS}
            FROM obs.transcript_segment
            WHERE call_session_id = %s
            ORDER BY sequence ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [transcript_from_row(row) for row in rows]


def _require_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be at least 1")


def _cursor_bounds(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None
    return decode_cursor(cursor)
