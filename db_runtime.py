"""로컬 SQLite와 Turso Cloud를 같은 DB-API 형태로 연결한다.

TURSO_DATABASE_URL/TURSO_AUTH_TOKEN이 둘 다 있을 때만 원격 DB를 사용한다.
그 외에는 기존 로컬 SQLite 경로를 그대로 사용한다.
"""

import os
import sqlite3


def _setting(name):
    value = str(os.environ.get(name) or "").strip()
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name) or "").strip()
    except Exception:
        return ""


def turso_config():
    url = _setting("TURSO_DATABASE_URL")
    token = _setting("TURSO_AUTH_TOKEN")
    if url and token:
        return url, token
    return None


def is_remote_database():
    return turso_config() is not None


class CompatRow:
    """libSQL 튜플 행을 sqlite3.Row처럼 숫자/컬럼명 양쪽으로 읽게 한다."""

    def __init__(self, columns, values):
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._positions = {name: index for index, name in enumerate(self._columns)}

    def keys(self):
        return list(self._columns)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._positions[key]]
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class CursorAdapter:
    def __init__(self, cursor):
        self._cursor = cursor

    def _columns(self):
        return [item[0] for item in (self._cursor.description or ())]

    def _row(self, row):
        return None if row is None else CompatRow(self._columns(), row)

    def fetchone(self):
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        columns = self._columns()
        return [CompatRow(columns, row) for row in self._cursor.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany() if size is None else self._cursor.fetchmany(size)
        columns = self._columns()
        return [CompatRow(columns, row) for row in rows]

    def __iter__(self):
        columns = self._columns()
        while True:
            row = self._cursor.fetchone()
            if row is None:
                break
            yield CompatRow(columns, row)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class ConnectionAdapter:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, parameters=()):
        return CursorAdapter(self._connection.execute(sql, parameters))

    def executemany(self, sql, parameters):
        return CursorAdapter(self._connection.executemany(sql, parameters))

    def executescript(self, script):
        return CursorAdapter(self._connection.executescript(script))

    def __getattr__(self, name):
        return getattr(self._connection, name)


def connect(local_path):
    config = turso_config()
    if config is None:
        connection = sqlite3.connect(local_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    import libsql

    url, token = config
    connection = ConnectionAdapter(libsql.connect(database=url, auth_token=token))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
