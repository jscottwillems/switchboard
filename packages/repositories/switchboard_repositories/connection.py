"""One Postgres connection per unit of work. The connection commits on clean exit."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

DictConnection = Connection[dict[str, Any]]


@contextmanager
def connect(database_url: str) -> Iterator[DictConnection]:
    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=3,
    ) as conn:
        yield conn
