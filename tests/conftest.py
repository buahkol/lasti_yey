"""Fixtures for the desktop-side tests (tests/).

The database tests need the SiMonPro schema (database/init.sql + dummy.sql). The server suite
rebuilds it for itself; here we do the same once per session so the result no longer depends on
which suite ran first. Destructive rebuilds are only allowed on a ``*_test`` database
(see the root conftest.py).
"""

import pytest

from server.tests.dbutil import rebuild_schema


@pytest.fixture(scope="session")
def schema_ready():
    """Fresh SiMonPro schema + seed in the test database."""
    rebuild_schema()
    yield


@pytest.fixture(autouse=True)
def _fresh_singleton():
    """Never leak the process-wide Database connection (and its open transaction) between tests."""
    from src.database.db_connection import Database

    yield
    inst = Database._instance
    if inst is not None:
        inst.close()
        Database._instance = None


LEGACY_SCHEMA_REASON = (
    "Menguji fitur aplikasi tekstil lama (kategori_produk, produk dengan produk_id/satuan, "
    "produksi_harian, detail_defect) yang tidak ada di skema SiMonPro (database/init.sql) dan di luar "
    "scope PRD. Digantikan oleh halaman Produk di aplikasi desktop lewat REST API (PRD 12) dan oleh "
    "server/tests/test_api.py::test_product_crud. Hapus bersama kodenya saat migrasi desktop selesai."
)


def pytest_collection_modifyitems(config, items):
    """Skip (visibly, with a reason) tests marked ``legacy_schema``; they need tables that no longer exist."""
    skip = pytest.mark.skip(reason=LEGACY_SCHEMA_REASON)
    for item in items:
        if "legacy_schema" in item.keywords:
            item.add_marker(skip)
