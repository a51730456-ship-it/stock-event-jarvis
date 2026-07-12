"""테마 강함/보통/약함 판정을 날짜별로 쌓는 순수 관찰 로그 (읽기/기록 전용).

jarvis.sqlite3 안에 완전히 독립된 테이블(theme_state_log)을 쓴다. reports/report_items와는
FK도 없고 서로 참조하지 않는다. 점수·판정·report DB 저장 로직에는 절대 연결하지 않는다
(JARVIS_CONTEXT.md 핵심 설계 원칙 3, 뉴스·공시·시황·테마 미반영 원칙과 동일 정신).

"테마 시작일 수동 입력"을 대체하는 자동 감지용 — 오늘부터 거슬러 올라가며 연속으로
"강함"인 구간의 첫 날을 찾아 경과일수를 계산한다.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "jarvis.sqlite3"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_theme_history_table():
    """theme_state_log 테이블이 없으면 만든다. reports 테이블과는 완전히 분리된 독립 테이블."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS theme_state_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            theme_name TEXT NOT NULL,
            verdict TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            UNIQUE(log_date, theme_name)
        )
        """
    )
    conn.commit()
    conn.close()


def record_theme_states(theme_verdicts, log_date=None):
    """{테마명: 강함/보통/약함} 딕셔너리를 오늘 날짜로 기록한다.

    같은 날 같은 테마가 이미 있으면 마지막 값으로 덮어쓴다(하루 여러 번 눌러도
    중복 안 쌓임). log_date를 명시하면 그 날짜로 기록한다(테스트용).
    """
    init_theme_history_table()
    log_date = log_date or datetime.now().strftime("%Y-%m-%d")
    recorded_at = datetime.now().isoformat(timespec="seconds")
    conn = _get_connection()
    for theme_name, verdict in theme_verdicts.items():
        if not theme_name or not verdict:
            continue
        conn.execute(
            "INSERT INTO theme_state_log (log_date, theme_name, verdict, recorded_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(log_date, theme_name) DO UPDATE SET "
            "verdict=excluded.verdict, recorded_at=excluded.recorded_at",
            (log_date, theme_name, verdict, recorded_at),
        )
    conn.commit()
    conn.close()


def has_theme_log(theme_name):
    """이 테마에 대한 관찰 로그가 하나라도 있는지."""
    init_theme_history_table()
    conn = _get_connection()
    row = conn.execute(
        "SELECT 1 FROM theme_state_log WHERE theme_name=? LIMIT 1", (theme_name,)
    ).fetchone()
    conn.close()
    return row is not None


def get_theme_elapsed_strong_days(theme_name):
    """이 테마가 최근 연속으로 "강함"이었던 일수를 계산한다.

    가장 최근 기록일부터 하루씩 거슬러 올라가며(달력일 기준, 하루라도 비거나
    강함이 아니면 그 자리에서 끊음) 연속 "강함" 일수를 센다.
    반환:
    - 로그가 아예 없으면 None (호출부에서 "관찰 시작 1일차"로 표시)
    - 가장 최근 기록의 판정이 "강함"이 아니면 None (지금 강한 흐름이 아니므로 경과일수 의미 없음)
    - 그 외에는 연속 강함 일수(정수, 오늘 포함 1 이상)
    """
    init_theme_history_table()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT log_date, verdict FROM theme_state_log WHERE theme_name=? ORDER BY log_date DESC",
        (theme_name,),
    ).fetchall()
    conn.close()
    if not rows:
        return None

    by_date = {r["log_date"]: r["verdict"] for r in rows}
    latest_date_str = max(by_date.keys())
    if by_date[latest_date_str] != "강함":
        return None

    cursor_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
    streak_days = 0
    while True:
        d_str = cursor_date.strftime("%Y-%m-%d")
        if by_date.get(d_str) == "강함":
            streak_days += 1
            cursor_date -= timedelta(days=1)
        else:
            break
    return streak_days
