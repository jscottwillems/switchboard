"""Postgres writes for interp.conversation_turn and interp.intelligence_finding."""

from uuid import UUID

from switchboard_schemas.enums import FindingStatus
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding

from switchboard_repositories.columns import CONVERSATION_TURN_COLUMNS, FINDING_COLUMNS
from switchboard_repositories.connection import DictConnection
from switchboard_repositories.errors import NotFound
from switchboard_repositories.mapping import conversation_turn_from_row, finding_from_row


class PostgresConversationTurns:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, turn: ConversationTurn) -> tuple[ConversationTurn, bool]:
        row = self._conn.execute(
            f"""
            INSERT INTO interp.conversation_turn (
                id,
                call_session_id,
                turn_index,
                speaker,
                text,
                transcript_segment_ids,
                strategy_id,
                confidence,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s)
            ON CONFLICT (call_session_id, turn_index) DO NOTHING
            RETURNING {CONVERSATION_TURN_COLUMNS}
            """,
            (
                turn.id,
                turn.call_session_id,
                turn.turn_index,
                turn.speaker.value,
                turn.text,
                turn.transcript_segment_ids,
                turn.strategy_id,
                turn.confidence,
                turn.created_at,
            ),
        ).fetchone()
        if row is not None:
            return conversation_turn_from_row(row), True
        existing = self._conn.execute(
            f"""
            SELECT {CONVERSATION_TURN_COLUMNS}
            FROM interp.conversation_turn
            WHERE call_session_id = %s AND turn_index = %s
            """,
            (turn.call_session_id, turn.turn_index),
        ).fetchone()
        if existing is None:
            raise RuntimeError("conversation turn conflicted but no row was stored")
        return conversation_turn_from_row(existing), False

    def get(self, turn_id: UUID) -> ConversationTurn | None:
        row = self._conn.execute(
            f"""
            SELECT {CONVERSATION_TURN_COLUMNS}
            FROM interp.conversation_turn
            WHERE id = %s
            """,
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        return conversation_turn_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[ConversationTurn]:
        rows = self._conn.execute(
            f"""
            SELECT {CONVERSATION_TURN_COLUMNS}
            FROM interp.conversation_turn
            WHERE call_session_id = %s
            ORDER BY turn_index ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [conversation_turn_from_row(row) for row in rows]


class PostgresFindings:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, finding: IntelligenceFinding) -> tuple[IntelligenceFinding, bool]:
        if finding.status is not FindingStatus.PROPOSED:
            raise ValueError("new findings start as proposed")
        row = self._conn.execute(
            f"""
            INSERT INTO interp.intelligence_finding (
                id,
                call_session_id,
                kind,
                value,
                raw_quote,
                transcript_segment_ids,
                extractor,
                extractor_version,
                confidence,
                status,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING {FINDING_COLUMNS}
            """,
            (
                finding.id,
                finding.call_session_id,
                finding.kind.value,
                finding.value,
                finding.raw_quote,
                finding.transcript_segment_ids,
                finding.extractor,
                finding.extractor_version,
                finding.confidence,
                finding.status.value,
                finding.created_at,
            ),
        ).fetchone()
        if row is not None:
            return finding_from_row(row), True
        existing = self.get(finding.id)
        if existing is None:
            raise RuntimeError("finding conflicted but no row was stored")
        return existing, False

    def get(self, finding_id: UUID) -> IntelligenceFinding | None:
        row = self._conn.execute(
            f"""
            SELECT {FINDING_COLUMNS}
            FROM interp.intelligence_finding
            WHERE id = %s
            """,
            (finding_id,),
        ).fetchone()
        if row is None:
            return None
        return finding_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[IntelligenceFinding]:
        rows = self._conn.execute(
            f"""
            SELECT {FINDING_COLUMNS}
            FROM interp.intelligence_finding
            WHERE call_session_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [finding_from_row(row) for row in rows]

    def set_status(self, finding_id: UUID, status: FindingStatus) -> IntelligenceFinding:
        """Change status only. Quote, value, and cited segments stay as inserted."""

        row = self._conn.execute(
            f"""
            UPDATE interp.intelligence_finding
            SET status = %s
            WHERE id = %s
            RETURNING {FINDING_COLUMNS}
            """,
            (status.value, finding_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"finding {finding_id} does not exist")
        return finding_from_row(row)
