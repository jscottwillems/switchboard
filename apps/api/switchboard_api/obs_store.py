"""Minimal obs writes for the mock voice webhook.

SB-017 owns the full repository surface. These statements target the Atlas
tables in apps/api/migrations/001_init.sql and do not add a schema.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Json

from switchboard_schemas.observations import CallSession

from switchboard_api.settings import get_settings

DictConnection = Connection[dict[str, Any]]


class TelephonyObsStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[DictConnection]:
        with psycopg.connect(
            self._database_url,
            row_factory=dict_row,
            connect_timeout=3,
        ) as conn:
            yield conn

    def find_active_operator_id(self, conn: DictConnection, e164: str) -> UUID | None:
        row = conn.execute(
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

    def insert_ringing_session(self, conn: DictConnection, session: CallSession) -> tuple[UUID, bool]:
        """Insert a ringing session. Return the stored id and whether this call created it."""

        inserted = conn.execute(
            """
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
            RETURNING id
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
        if inserted is not None:
            stored_id = inserted["id"]
            if not isinstance(stored_id, UUID):
                raise TypeError("obs.call_session.id must be a uuid")
            return stored_id, True
        existing = conn.execute(
            """
            SELECT id
            FROM obs.call_session
            WHERE carrier = %s AND external_call_id = %s
            """,
            (session.carrier, session.external_call_id),
        ).fetchone()
        if existing is None:
            raise RuntimeError("call session conflicted but no row was stored")
        stored_id = existing["id"]
        if not isinstance(stored_id, UUID):
            raise TypeError("obs.call_session.id must be a uuid")
        return stored_id, False

    def insert_webhook_receipt(
        self,
        conn: DictConnection,
        *,
        provider: str,
        event_type: str,
        payload: dict[str, Any],
        signature_valid: bool | None,
        call_session_id: UUID | None,
    ) -> UUID:
        receipt_id = uuid4()
        received_at = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO obs.webhook_receipt (
                id,
                call_session_id,
                provider,
                event_type,
                payload,
                signature_valid,
                received_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                receipt_id,
                call_session_id,
                provider,
                event_type,
                Json(payload),
                signature_valid,
                received_at,
            ),
        )
        return receipt_id


def get_obs_store() -> TelephonyObsStore:
    return TelephonyObsStore(get_settings().database_url)
