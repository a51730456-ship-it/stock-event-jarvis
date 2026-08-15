import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import database
import db_runtime

# **libsql이 없으면 이 파일은 통째로 건너뛴다.** 이 모듈은 온라인(Turso) 전용이고,
# db_runtime도 필요할 때만 늦게 불러 쓴다(db_runtime.py의 `import libsql`은 함수
# 안에 있다). 노트북에는 안 깔려 있을 수 있는데, 그때 시험이 **깨지면** 진짜
# 고장과 구별이 안 된다(2026-08-15에 실제로 그래서 여섯 시험이 깨져 보였다).
try:
    import libsql
except ModuleNotFoundError:                     # pragma: no cover - 노트북에 없을 때
    raise unittest.SkipTest(
        "libsql이 안 깔려 있어 건너뜁니다. 온라인 DB 시험입니다 — "
        "돌려 보시려면 pip install -r requirements.txt"
    )


class _ExpiredStreamConnection:
    """서버가 이미 닫아 버린 원격 스트림 흉내. 연결 직후 PRAGMA만 받는다."""

    _ERROR = (
        'Hrana: api error: status=404 Not Found, '
        'body={"error":"stream not found: a2f80cac:5103e"}'
    )

    def __init__(self):
        self.closed = False

    def execute(self, sql, parameters=()):
        if sql.strip().upper().startswith("PRAGMA"):
            return None
        raise RuntimeError(self._ERROR)

    def close(self):
        self.closed = True


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

    def test_remote_connections_are_reused_after_close(self):
        raw = sqlite3.connect(":memory:")
        with (
            mock.patch.object(db_runtime, "_REMOTE_POOLS", {}),
            mock.patch.object(
                db_runtime,
                "turso_config",
                return_value=("libsql://example.turso.io", "token"),
            ),
            mock.patch.object(libsql, "connect", return_value=raw) as connect_mock,
        ):
            first = db_runtime.connect("ignored.db")
            first.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            first.close()

            second = db_runtime.connect("ignored.db")
            second.execute("INSERT INTO sample VALUES (1)")
            second.close()

        self.assertEqual(connect_mock.call_count, 1)
        self.assertEqual(raw.execute("SELECT COUNT(*) FROM sample").fetchone()[0], 1)
        raw.close()

    def test_remote_pool_does_not_share_a_borrowed_connection(self):
        raw_connections = [sqlite3.connect(":memory:"), sqlite3.connect(":memory:")]
        with (
            mock.patch.object(db_runtime, "_REMOTE_POOLS", {}),
            mock.patch.object(
                db_runtime,
                "turso_config",
                return_value=("libsql://example.turso.io", "token"),
            ),
            mock.patch.object(libsql, "connect", side_effect=raw_connections) as connect_mock,
        ):
            first = db_runtime.connect("ignored.db")
            second = db_runtime.connect("ignored.db")
            self.assertIsNot(first._connection, second._connection)
            first.close()
            second.close()

        self.assertEqual(connect_mock.call_count, 2)
        for connection in raw_connections:
            connection.close()

    def test_pool_replaces_a_connection_whose_remote_stream_expired(self):
        stale = _ExpiredStreamConnection()
        good = sqlite3.connect(":memory:")
        with (
            mock.patch.object(db_runtime, "_REMOTE_POOLS", {}),
            mock.patch.object(
                db_runtime,
                "turso_config",
                return_value=("libsql://example.turso.io", "token"),
            ),
            mock.patch.object(libsql, "connect", side_effect=[stale, good]) as connect_mock,
        ):
            borrowed = db_runtime.connect("ignored.db")
            borrowed.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
            borrowed.execute("INSERT INTO sample VALUES (1)")
            borrowed.close()

            # 끊긴 연결은 버려졌고, 새로 만든 연결만 풀에 남아 다시 쓰인다.
            again = db_runtime.connect("ignored.db")
            self.assertIs(again._connection, good)
            again.close()

        self.assertEqual(connect_mock.call_count, 2)
        self.assertTrue(stale.closed)
        self.assertEqual(good.execute("SELECT COUNT(*) FROM sample").fetchone()[0], 1)
        good.close()

    def test_ordinary_sql_error_keeps_the_pooled_connection(self):
        raw = sqlite3.connect(":memory:")
        with (
            mock.patch.object(db_runtime, "_REMOTE_POOLS", {}),
            mock.patch.object(
                db_runtime,
                "turso_config",
                return_value=("libsql://example.turso.io", "token"),
            ),
            mock.patch.object(libsql, "connect", return_value=raw) as connect_mock,
        ):
            borrowed = db_runtime.connect("ignored.db")
            with self.assertRaises(sqlite3.OperationalError):
                borrowed.execute("SELECT * FROM missing_table")
            borrowed.close()

            again = db_runtime.connect("ignored.db")
            self.assertIs(again._connection, raw)
            again.close()

        self.assertEqual(connect_mock.call_count, 1)
        raw.close()

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

    def test_previous_flow_snapshots_skip_weekend_rows(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            database_path = str(Path(temp_dir) / "flow_history.db")

            def connection_factory():
                return db_runtime.ConnectionAdapter(libsql.connect(database_path))

            with mock.patch.object(database, "get_connection", side_effect=connection_factory):
                database.init_db()
                database.save_kr_flow_snapshot(
                    "2026-07-24", "2026-07-24T15:00:00", {"samsung_price": 90_000}
                )
                database.save_kr_flow_snapshot(
                    "2026-07-25", "2026-07-25T12:00:00", {"samsung_price": 91_000}
                )
                database.save_kr_flow_snapshot(
                    "2026-07-27", "2026-07-27T15:00:00", {"samsung_price": 92_000}
                )
                previous = database.list_previous_kr_flow_snapshots("2026-07-28")

            self.assertEqual(previous["trade_date"], "2026-07-27")
            self.assertEqual(len(previous["rows"]), 1)
            self.assertEqual(previous["rows"][0]["samsung_price"], 92_000)


if __name__ == "__main__":
    unittest.main()
