"""PostgreSQL access with a thread-safe connection pool.

FastAPI runs plain ``def`` endpoints in a threadpool, so each request borrows
one connection, runs inside one transaction, and returns it to the pool.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .config import Settings

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._pool: ThreadedConnectionPool | None = None

    def open(self) -> None:
        s = self._settings
        self._pool = ThreadedConnectionPool(
            1,
            s.db_pool_max,
            host=s.db_host,
            port=s.db_port,
            dbname=s.db_name,
            user=s.db_user,
            password=s.db_password,
            options=f"-c timezone={s.timezone}",
            cursor_factory=RealDictCursor,
        )
        logger.info("Database pool opened (%s:%s/%s)", s.db_host, s.db_port, s.db_name)

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def connection(self) -> Iterator[PgConnection]:
        """Borrow a connection; commit on success, roll back on error."""
        if self._pool is None:
            raise RuntimeError("Database pool is not open")
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)


def is_unique_violation(exc: Exception) -> bool:
    return isinstance(exc, psycopg2.errors.UniqueViolation)
