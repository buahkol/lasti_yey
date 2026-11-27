"""Tests for src.database.db_connection against the SiMonPro schema (database/init.sql).

* Integration tests need PostgreSQL (``docker compose up -d``) and use the ``*_test`` database
  selected by the root conftest; the schema is rebuilt by the ``schema_ready`` fixture.
* ``TestTransactionRecovery`` needs no database: it drives the wrapper with a fake connection.
"""

import psycopg2
import pytest

from src.database.db_connection import Database, get_db, test_connection

TEST_SKU = "TEST-DB-01"


@pytest.fixture
def db(schema_ready):
    return get_db()


@pytest.fixture
def clean_test_sku(db):
    db.execute_update("DELETE FROM produk WHERE sku = %s", (TEST_SKU,))
    yield
    db.execute_update("DELETE FROM produk WHERE sku = %s", (TEST_SKU,))


class TestDatabaseConnection:
    def test_connection_success(self, schema_ready):
        """TC-DB-01: reachable database."""
        assert test_connection() is True

    def test_runs_on_test_database(self, db):
        """TC-DB-02: tests never run on the development database."""
        name = db.execute_query("SELECT current_database() AS name")[0]["name"]
        assert name.endswith("_test")

    def test_schema_is_simonpro(self, db):
        """TC-DB-03: SiMonPro tables exist; tables of the old textile app do not."""
        tables = {r["table_name"] for r in db.execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
        assert {"pengguna", "sesi", "perangkat", "produk", "batch", "output_produksi", "inspeksi",
                "kejadian_produksi"} <= tables
        assert tables.isdisjoint({"users", "tipe_defect", "produksi_harian", "kategori_produk"})

    def test_seed_data(self, db):
        """TC-DB-04: dummy.sql seeds the Operasional account, a device and the products."""
        users = db.execute_query("SELECT username FROM pengguna")
        assert [u["username"] for u in users] == ["operasional"]
        assert db.execute_query("SELECT count(*) AS n FROM perangkat")[0]["n"] == 1
        skus = {r["sku"] for r in db.execute_query("SELECT sku FROM produk")}
        assert {"SRD-TOMAT-155G", "SRD-CABAI-155G", "SRD-TOMAT-425G", "DEMO-CAN"} <= skus

    def test_password_is_hashed(self, db):
        """TC-DB-05 (FR-02): passwords are stored as bcrypt hashes, never as plain text."""
        row = db.execute_query("SELECT password_hash FROM pengguna WHERE username = 'operasional'")[0]
        assert row["password_hash"].startswith("$2") and row["password_hash"] != "operasional123"

    def test_execute_update_and_delete(self, db, clean_test_sku):
        """TC-DB-06: insert, read back and delete a product."""
        assert db.execute_update(
            "INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
            (TEST_SKU, "Produk Uji", 1234)) == 1
        rows = db.execute_query("SELECT nama, harga_satuan FROM produk WHERE sku = %s", (TEST_SKU,))
        assert rows == [{"nama": "Produk Uji", "harga_satuan": 1234}]
        assert db.execute_update("DELETE FROM produk WHERE sku = %s", (TEST_SKU,)) == 1
        assert db.execute_query("SELECT 1 FROM produk WHERE sku = %s", (TEST_SKU,)) == []

    def test_execute_many(self, db, clean_test_sku):
        """TC-DB-07: executemany inserts all rows."""
        db.execute_many("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
                        [(TEST_SKU, "Uji A", 1)])
        assert db.execute_query("SELECT count(*) AS n FROM produk WHERE sku = %s", (TEST_SKU,))[0]["n"] == 1

    def test_context_manager_commit(self, db, clean_test_sku):
        """TC-DB-08: ``with db`` commits on success."""
        with db:
            db.execute_update("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
                              (TEST_SKU, "Ctx", 1))
        assert len(db.execute_query("SELECT 1 FROM produk WHERE sku = %s", (TEST_SKU,))) == 1

    def test_context_manager_rollback(self, db, clean_test_sku):
        """TC-DB-09: ``with db`` rolls back when the block raises."""
        with pytest.raises(RuntimeError):
            with db:
                db.execute_update("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
                                  (TEST_SKU, "Ctx", 1))
                raise RuntimeError("Force rollback")
        assert db.execute_query("SELECT 1 FROM produk WHERE sku = %s", (TEST_SKU,)) == []

    def test_bad_query_does_not_poison_connection(self, db):
        """TC-DB-10: a failed statement is rolled back; the next query works."""
        with pytest.raises(psycopg2.errors.UndefinedTable):
            db.execute_query("SELECT * FROM tabel_yang_tidak_ada")
        assert db.execute_query("SELECT 1 AS ok") == [{"ok": 1}]

    def test_constraint_violation_does_not_poison_connection(self, db, clean_test_sku):
        """TC-DB-11: a unique violation (duplicate SKU) is recoverable."""
        db.execute_update("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
                          (TEST_SKU, "Satu", 1))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute_update("INSERT INTO produk (sku, nama, harga_satuan) VALUES (%s, %s, %s)",
                              (TEST_SKU, "Dua", 2))
        assert db.execute_query("SELECT count(*) AS n FROM produk WHERE sku = %s", (TEST_SKU,))[0]["n"] == 1

    def test_singleton_behavior(self):
        """TC-DB-12: get_db() returns the same instance."""
        assert get_db() is get_db()

    def test_force_new_instance(self):
        """TC-DB-13: force_new=True creates a fresh instance."""
        db1 = get_db()
        db2 = get_db(force_new=True)
        assert db1 is not db2
        assert db2._connection is None or db2._connection.closed


# --------------------------------------------------------------------------- #
# No database needed: fake psycopg2 connection that behaves like PostgreSQL      #
# after an error ("current transaction is aborted").                             #
# --------------------------------------------------------------------------- #
class _FakeCursor:
    def __init__(self, conn):
        self.conn, self.rowcount = conn, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.conn.aborted:
            raise psycopg2.errors.InFailedSqlTransaction("current transaction is aborted")
        if "boom" in sql:
            self.conn.aborted = True
            raise psycopg2.errors.UndefinedTable("relation does not exist")
        self.rowcount = 1

    def executemany(self, sql, params):
        self.execute(sql)

    def fetchall(self):
        return [{"ok": 1}]


class _FakeConnection:
    closed = False

    def __init__(self):
        self.aborted, self.commits, self.rollbacks = False, 0, 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
        self.aborted = False

    def close(self):
        self.closed = True


class TestTransactionRecovery:
    @pytest.fixture
    def fake_db(self):
        db = Database(force_new=True)
        db._connection = _FakeConnection()
        yield db
        db._connection = None
        Database._instance = None

    @pytest.mark.parametrize("call", [
        lambda db: db.execute_query("SELECT boom"),
        lambda db: db.execute_update("UPDATE boom"),
        lambda db: db.execute_many("INSERT boom", [(1,)]),
    ])
    def test_failed_statement_is_rolled_back(self, fake_db, call):
        with pytest.raises(psycopg2.Error):
            call(fake_db)
        assert fake_db._connection.rollbacks == 1
        assert fake_db.execute_query("SELECT 1") == [{"ok": 1}]  # not "transaction is aborted"

    def test_success_commits_and_does_not_roll_back(self, fake_db):
        fake_db.execute_update("UPDATE ok")
        assert (fake_db._connection.commits, fake_db._connection.rollbacks) == (1, 0)

    def test_inside_context_the_caller_owns_the_transaction(self, fake_db):
        conn = fake_db._connection  # ``with db`` closes and drops the connection on exit
        with pytest.raises(psycopg2.Error):
            with fake_db:
                fake_db.execute_update("UPDATE boom")
        # one rollback, performed by __exit__ (not by the statement), no commit
        assert (conn.rollbacks, conn.commits) == (1, 0)
