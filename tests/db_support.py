"""Apply Atlas migrations for repository tests. No schema beyond 001_init.sql."""

import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "apps" / "api" / "migrations"
DEV_OPERATOR_ID = "00000000-0000-4000-8000-000000000001"
DEV_OPERATOR_E164 = "+15550001001"


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def apply_migrations(url: str | None = None) -> None:
    target = url if url is not None else database_url()
    try:
        conn = psycopg.connect(target, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            "Repository tests need Postgres at DATABASE_URL. "
            "Start the compose postgres service or a local server before pytest."
        ) from exc
    with conn:
        existing = conn.execute("SELECT to_regclass('obs.call_session')").fetchone()
        if existing is None or existing[0] is None:
            for name in ("001_init.sql", "002_seed_dev.sql"):
                execute_script(conn, (MIGRATIONS / name).read_text())
        conn.execute(
            """
            INSERT INTO ops.operator_number (id, e164, label, status)
            VALUES (%s, %s, %s, 'active')
            ON CONFLICT (e164) DO NOTHING
            """,
            (DEV_OPERATOR_ID, DEV_OPERATOR_E164, "dev-honeypot-1"),
        )


def truncate_records(url: str | None = None) -> None:
    target = url if url is not None else database_url()
    with psycopg.connect(target, autocommit=True, connect_timeout=3) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                attr.campaign_attribution,
                attr.campaign,
                interp.intelligence_finding,
                interp.conversation_turn,
                obs.transcript_segment,
                obs.media_stream,
                obs.webhook_receipt,
                obs.call_session
            RESTART IDENTITY CASCADE
            """
        )


def execute_script(conn: psycopg.Connection, sql: str) -> None:
    for statement in _statements(sql):
        conn.execute(statement)


def _statements(sql: str) -> list[str]:
    statements: list[str] = []
    for chunk in sql.split(";"):
        lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements
