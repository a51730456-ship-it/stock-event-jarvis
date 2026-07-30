"""로컬 SQLite와 Turso Cloud를 같은 DB-API 형태로 연결한다.

TURSO_DATABASE_URL/TURSO_AUTH_TOKEN이 둘 다 있을 때만 원격 DB를 사용한다.
그 외에는 기존 로컬 SQLite 경로를 그대로 사용한다.
"""

import os
import queue
import sqlite3
import threading


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


# 원격 스트림은 잠깐 쉬면 서버가 닫는다. 닫힌 스트림을 다시 쓰면
# 404 stream not found가 온다(2026-07-30 미국테마 맨 위 배너로 실제 발생:
# "Hrana: api error: status=404 ... stream not found"). 그 연결이 풀에 다시
# 들어가면 다음 새로고침에도 같은 배너가 계속 뜬다.
_STALE_STREAM_MARKS = ("stream not found", "stream expired", "baton")


def _is_stale_stream_error(error):
    text = str(error or "").lower()
    return any(mark in text for mark in _STALE_STREAM_MARKS)


class _PooledConnectionAdapter(ConnectionAdapter):
    """Return a remote connection to its pool instead of closing its socket."""

    def __init__(self, connection, pool):
        super().__init__(connection)
        self._pool = pool
        self._released = False
        self._broken = False
        # 이번 대여에서 문장 하나라도 성공했는지. 첫 문장이 스트림 만료로
        # 죽은 경우만 다시 보내야 안전하다(그 문장은 서버에 닿지도 않았다).
        self._used = False

    def _run(self, method_name, *args):
        try:
            cursor = getattr(self._connection, method_name)(*args)
        except Exception as exc:
            if not _is_stale_stream_error(exc):
                # 평범한 SQL 오류는 연결 탓이 아니다. 연결은 계속 쓴다.
                raise
            if self._used:
                self._broken = True
                raise
            # 풀에서 받은 연결이 이미 끊긴 것이다. 새 연결로 딱 한 번만
            # 다시 보낸다. 여기서 또 죽으면 그대로 올려 호출자가 알게 한다.
            self._pool.discard(self._connection)
            self._connection = self._pool.new_connection()
            try:
                cursor = getattr(self._connection, method_name)(*args)
            except Exception:
                self._broken = True
                raise
        self._used = True
        return CursorAdapter(cursor)

    def execute(self, sql, parameters=()):
        return self._run("execute", sql, parameters)

    def executemany(self, sql, parameters):
        return self._run("executemany", sql, parameters)

    def executescript(self, script):
        return self._run("executescript", script)

    def close(self):
        if self._released:
            return
        self._released = True
        if self._broken:
            self._pool.discard(self._connection)
            return
        self._pool.release(self._connection)


class _RemoteConnectionPool:
    """Small process-local pool; a borrowed connection is never shared concurrently."""

    def __init__(self, url, token):
        self._url = url
        self._token = token
        self._available = queue.LifoQueue()

    def new_connection(self):
        import libsql

        connection = libsql.connect(database=self._url, auth_token=self._token)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def acquire(self):
        try:
            connection = self._available.get_nowait()
        except queue.Empty:
            connection = self.new_connection()
        return _PooledConnectionAdapter(connection, self)

    def release(self, connection):
        self._available.put(connection)

    def discard(self, connection):
        """끊긴 연결은 풀에 돌려보내지 않는다. 닫기가 실패해도 그냥 버린다."""
        try:
            connection.close()
        except Exception:
            pass


_REMOTE_POOLS = {}
_REMOTE_POOLS_LOCK = threading.Lock()


def _remote_pool(url, token):
    key = (url, token)
    with _REMOTE_POOLS_LOCK:
        pool = _REMOTE_POOLS.get(key)
        if pool is None:
            pool = _RemoteConnectionPool(url, token)
            _REMOTE_POOLS[key] = pool
        return pool


def connect(local_path):
    config = turso_config()
    if config is None:
        connection = sqlite3.connect(local_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    url, token = config
    return _remote_pool(url, token).acquire()
