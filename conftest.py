"""Root pytest configuration: keep every test run on the test database.

``src.database.db_connection`` reads DB_NAME once at import time and defaults to the development
database (``simonpro``). Setting the default here, before any test module is imported, makes a
bare ``pytest`` use ``simonpro_test`` instead, and the guard stops a run that was explicitly
pointed at a non-test database.
"""

import os

from server.tests.dbutil import DEFAULT_TEST_DB, assert_test_database

os.environ.setdefault("DB_NAME", DEFAULT_TEST_DB)
assert_test_database(os.environ["DB_NAME"])
