"""Apply Atlas migrations and read obs rows from the test database."""

import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
DEV_OPERATOR_ID = "00000000-0000-4000-8000-000000000001"
DEV_OPERATOR_E164 = "+15550001001"


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def apply_migrations() -> None:
    try:
        conn = psycopg.connect(database_url(), autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            "Voice webhook tests need Postgres at DATABASE_URL. "
            "Start the compose postgres service or a local server before pytest."
        ) from exc
    with conn:
        existing = conn.execute("SELECT to_regclass('obs.call_session')").fetchone()
        if existing is None or existing[0] is None:
            migrations = ROOT / "apps" / "api" / "migrations"
            for name in ("001_init.sql", "002_seed_dev.sql"):
                execute_script(conn, (migrations / name).read_text())
        conn.execute(
            """
            INSERT INTO ops.operator_number (id, e164, label, status)
            VALUES (%s, %s, %s, 'active')
            ON CONFLICT (e164) DO NOTHING
            """,
            (DEV_OPERATOR_ID, DEV_OPERATOR_E164, "dev-honeypot-1"),
        )


def truncate_observations() -> None:
    with psycopg.connect(database_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute(
            "TRUNCATE obs.webhook_receipt, obs.call_session, attr.campaign CASCADE"
        )


def query_all(sql: str, params: tuple[object, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=3) as conn:
        rows = conn.execute(sql, params).fetchall()
    return list(rows)


def execute(sql: str, params: tuple[object, ...] = ()) -> None:
    with psycopg.connect(database_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute(sql, params)


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
