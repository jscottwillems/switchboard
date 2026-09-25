"""Connection-scoped unit of work. One transaction for every repository it returns."""

from collections.abc import Iterator
from contextlib import contextmanager

from switchboard_repositories.connection import DictConnection, connect
from switchboard_repositories.postgres_attr import PostgresAttributions, PostgresCampaigns
from switchboard_repositories.postgres_interp import PostgresConversationTurns, PostgresFindings
from switchboard_repositories.postgres_obs import (
    PostgresCallSessions,
    PostgresMediaStreams,
    PostgresOperatorNumbers,
    PostgresTranscripts,
    PostgresWebhookReceipts,
)
from switchboard_repositories.ports import (
    AttributionWriter,
    FindingWriter,
    ObservationWriter,
    ReadModels,
)


class PostgresUnitOfWork:
    def __init__(self, conn: DictConnection) -> None:
        self._operator_numbers = PostgresOperatorNumbers(conn)
        self._call_sessions = PostgresCallSessions(conn)
        self._webhook_receipts = PostgresWebhookReceipts(conn)
        self._media_streams = PostgresMediaStreams(conn)
        self._transcripts = PostgresTranscripts(conn)
        self._conversation_turns = PostgresConversationTurns(conn)
        self._findings = PostgresFindings(conn)
        self._campaigns = PostgresCampaigns(conn)
        self._attributions = PostgresAttributions(conn)

    def operator_numbers(self) -> PostgresOperatorNumbers:
        return self._operator_numbers

    def call_sessions(self) -> PostgresCallSessions:
        return self._call_sessions

    def webhook_receipts(self) -> PostgresWebhookReceipts:
        return self._webhook_receipts

    def media_streams(self) -> PostgresMediaStreams:
        return self._media_streams

    def transcripts(self) -> PostgresTranscripts:
        return self._transcripts

    def conversation_turns(self) -> PostgresConversationTurns:
        return self._conversation_turns

    def findings(self) -> PostgresFindings:
        return self._findings

    def campaigns(self) -> PostgresCampaigns:
        return self._campaigns

    def attributions(self) -> PostgresAttributions:
        return self._attributions


@contextmanager
def unit_of_work(database_url: str) -> Iterator[PostgresUnitOfWork]:
    with connect(database_url) as conn:
        yield PostgresUnitOfWork(conn)


@contextmanager
def observation_writer(database_url: str) -> Iterator[ObservationWriter]:
    with unit_of_work(database_url) as uow:
        yield uow


@contextmanager
def finding_writer(database_url: str) -> Iterator[FindingWriter]:
    with unit_of_work(database_url) as uow:
        yield uow


@contextmanager
def attribution_writer(database_url: str) -> Iterator[AttributionWriter]:
    with unit_of_work(database_url) as uow:
        yield uow


@contextmanager
def read_models(database_url: str) -> Iterator[ReadModels]:
    with unit_of_work(database_url) as uow:
        yield uow
