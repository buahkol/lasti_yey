"""Shared helpers for the test databases (used by server/tests and tests/).

The tests destroy data: the server suite drops and recreates the ``public`` schema. They must
therefore never touch the development database, so every entry point goes through
``assert_test_database`` and the database name has to end in ``_test``.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
TEST_DB_SUFFIX = "_test"
DEFAULT_TEST_DB = "simonpro_test"


def assert_test_database(name: str) -> None:
    """Refuse to run destructive tests against a database that is not a *_test database."""
    if not name.endswith(TEST_DB_SUFFIX):
        raise RuntimeError(
            f"DB_NAME='{name}' bukan database uji (nama harus berakhiran '{TEST_DB_SUFFIX}'). "
            f"Tes menghapus seluruh schema public. Gunakan DB_NAME={DEFAULT_TEST_DB}."
        )


def connect_params() -> dict:
    """Connection parameters from the same variables the application uses."""
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5433")),
        "dbname": os.environ.get("DB_NAME", DEFAULT_TEST_DB),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "secret"),
    }


def rebuild_schema(**params) -> None:
    """Drop everything in ``public`` and load database/init.sql + database/dummy.sql."""
    params = params or connect_params()
    assert_test_database(params["dbname"])
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            cur.execute((ROOT / "database" / "init.sql").read_text(encoding="utf-8"))
            cur.execute((ROOT / "database" / "dummy.sql").read_text(encoding="utf-8"))
    finally:
        conn.close()
