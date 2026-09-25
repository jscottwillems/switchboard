"""Connection-scoped observation port used by the mock voice webhook.

Method names match the voice webhook: active operator lookup, idempotent ringing
insert, and an append-only receipt. The same connection commits both writes.
Repeat `(carrier, external_call_id)` returns the stored session id and does not
change the caller number.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from switchboard_schemas.observations import CallSession

from switchboard_repositories.connection import DictConnection, connect
from switchboard_repositories.postgres_obs import (
    PostgresCallSessions,
    PostgresOperatorNumbers,
    PostgresWebhookReceipts,
)


class TelephonyObsStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[DictConnection]:
        with connect(self._database_url) as conn:
            yield conn

    def find_active_operator_id(self, conn: DictConnection, e164: str) -> UUID | None:
        return PostgresOperatorNumbers(conn).find_active_id(e164)

    def insert_ringing_session(
        self,
        conn: DictConnection,
        session: CallSession,
    ) -> tuple[UUID, bool]:
        """Return the stored id and whether this call created the row."""

        stored, created = PostgresCallSessions(conn).insert_ringing(session)
        return stored.id, created

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
        receipt = PostgresWebhookReceipts(conn).insert(
            provider=provider,
            event_type=event_type,
            payload=payload,
            signature_valid=signature_valid,
            call_session_id=call_session_id,
        )
        return receipt.id
