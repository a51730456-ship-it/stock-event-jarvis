import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database
import db_runtime
import libsql


class DbRuntimeTests(unittest.TestCase):
    def test_local_connection_keeps_sqlite_row_contract(self):
        with mock.patch.dict(os.environ, {"TURSO_DATABASE_URL": "", "TURSO_AUTH_TOKEN": ""}, clear=False):
            connection = db_runtime.connect(":memory:")
        try:
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO sample VALUES (?, ?)", (1, "자비스"))
            row = connection.execute("SELECT id, name FROM sample").fetchone()
            self.assertEqual(row[0], 1)
            self.assertEqual(row["name"], "자비스")
            self.assertEqual(dict(row), {"id": 1, "name": "자비스"})
        finally:
            connection.close()

    def test_compat_row_supports_index_name_dict_and_unpacking(self):
        row = db_runtime.CompatRow(("id", "name"), (7, "테스트"))
        self.assertEqual(row[0], 7)
        self.assertEqual(row["name"], "테스트")
        self.assertEqual(dict(row), {"id": 7, "name": "테스트"})
        self.assertEqual(tuple(row), (7, "테스트"))

    def test_remote_requires_both_url_and_token(self):
        with mock.patch.dict(
            os.environ,
            {"TURSO_DATABASE_URL": "libsql://example.turso.io", "TURSO_AUTH_TOKEN": ""},
            clear=False,
        ):
            self.assertFalse(db_runtime.is_remote_database())
        with mock.patch.dict(
            os.environ,
            {"TURSO_DATABASE_URL": "libsql://example.turso.io", "TURSO_AUTH_TOKEN": "token"},
            clear=False,
        ):
            self.assertTrue(db_runtime.is_remote_database())

    def test_cursor_adapter_preserves_lastrowid_and_rowcount(self):
        raw = sqlite3.connect(":memory:")
        adapter = db_runtime.ConnectionAdapter(raw)
        try:
            adapter.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)")
            cursor = adapter.execute("INSERT INTO sample(name) VALUES (?)", ("A",))
            self.assertEqual(cursor.lastrowid, 1)
            self.assertEqual(cursor.rowcount, 1)
            row = adapter.execute("SELECT id, name FROM sample").fetchone()
            self.assertEqual(dict(row), {"id": 1, "name": "A"})
        finally:
            adapter.close()

    def test_database_schema_and_crud_work_through_libsql_adapter(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            database_path = str(Path(temp_dir) / "remote_like.db")

            def connection_factory():
                connection = db_runtime.ConnectionAdapter(libsql.connect(database_path))
                connection.execute("PRAGMA foreign_keys = ON")
                return connection

            with mock.patch.object(database, "get_connection", side_effect=connection_factory):
                database.init_db()
                report_id = database.save_report(
                    "KR", "[테스트] Turso 호환", "test", items=[]
                )
                reports = database.list_reports()

            self.assertEqual(report_id, 1)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]["day_conclusion"], "[테스트] Turso 호환")


if __name__ == "__main__":
    unittest.main()
