"""playbook.py — 자비스2 테마 플레이북 판정 엔진.

기존 파일(database.py, theme_history.py, market_data.py, theme_detail.py)을
수정하지 않고 임포트해서 사용한다. 이 모듈은 참고용 판정 함수 모음이며,
DB 저장·자동매매·실시간 조회와는 무관하다.

신규 DB 테이블 2개(playbook_config, playbook_journal)는 기존 테이블을
일절 건드리지 않고 독립적으로 생성한다.
"""

from __future__ import annotations

import logging
from datetime import datetime

_log = logging.getLogger(__name__)

# ── DB 초기화 ──────────────────────────────────────────────────────────────────

_PLAYBOOK_CONFIG_DEFAULTS = {
    "near_high_pct": 10.0,       # 52주 고가 대비 이 % 이내면 "고점 근접"
    "value_mult": 3.0,           # 당일 거래대금이 20일 평균의 이 배 이상이면 "급증"
    "min_value_eok": 100.0,      # 최소 거래대금 기준 (억원)
    "max_spike_pct": 20.0,       # 최근 20일 내 이 % 이상 단일 급등 시 경보
    "entry_max_age": 3.0,        # 테마 연속강세 경과 거래일이 이 일 초과 시 추격 주의
    "leader_break_pct": 7.0,     # 대장주 최근 고점 대비 이 % 이상 하락 시 붕괴 경보
    "rank_limit": 3.0,           # 대장 후보 반환 최대 수 (find_leader)
    "volatile_days_warn": 12.0,  # 60일 ±3% 변동일수 이 이상이면 시장 경고
}


def _get_connection():
    import database
    return database.get_connection()


def _init_playbook_tables() -> None:
    """playbook_config / playbook_journal 테이블을 없으면 만든다.
    기존 DB 테이블에는 어떤 변경도 가하지 않는다.
    """
    conn = _get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS playbook_config (
                key   TEXT PRIMARY KEY,
                value REAL NOT NULL,
                note  TEXT
            );

            CREATE TABLE IF NOT EXISTS playbook_journal (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at      TEXT NOT NULL,
                theme_name       TEXT NOT NULL,
                theme_age_days   INTEGER,
                leader_name      TEXT,
                target_ticker    TEXT,
                setup            TEXT,
                entry_price      REAL,
                stop_price       REAL,
                qty              INTEGER,
                r_amount         REAL,
                alert_state      TEXT,
                alert_ignore_reason TEXT,
                tags             TEXT,
                is_dropped       INTEGER DEFAULT 0,
                result           TEXT
            );

            CREATE TABLE IF NOT EXISTS crash_log (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at           TEXT NOT NULL,
                log_date              TEXT NOT NULL,
                index_change_pct      REAL,
                causes                TEXT,
                holding_logic_broken  TEXT,
                memo                  TEXT
            );
            """
        )
        # config 기본값 삽입 (이미 있으면 무시)
        for key, value in _PLAYBOOK_CONFIG_DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO playbook_config (key, value) VALUES (?, ?)",
                (key, value),
            )
        # 마이그레이션: P1 초기 기본값에서 변경된 항목을 구 기본값 그대로인 경우에만 업데이트
        _MIGRATIONS = {
            "rank_limit": (2.0, 3.0),   # (old_default, new_default)
        }
        for key, (old_val, new_val) in _MIGRATIONS.items():
            conn.execute(
                "UPDATE playbook_config SET value=? WHERE key=? AND value=?",
                (new_val, key, old_val),
            )
        conn.commit()
    finally:
        conn.close()


def _get_config() -> dict:
    """playbook_config 테이블에서 설정값을 읽어 dict로 반환."""
    _init_playbook_tables()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM playbook_config").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


# 모듈 임포트 시 테이블 자동 생성
try:
    _init_playbook_tables()
except Exception as _e:
    _log.warning("playbook_tables init failed: %s", _e)


# ── 판정 함수 6개 ──────────────────────────────────────────────────────────────


def theme_signals(theme_name: str) -> dict:
    """테마 진입 신호 3가지를 확인한다.

    1) 구성종목 3개+ 동시 양전 여부
    2) 1등 거래대금 배수 (20일 평균 대비)
    3) 연속강세 로그 존재 여부

    반환:
    {
      "ok": True,
      "three_plus_up": bool,     # 양전 종목 3개 이상
      "up_count": int,           # 양전 종목 수
      "total_count": int,        # 조회된 전체 종목 수
      "leader_value_mult": float | None,  # 등락률 1위 종목 거래대금 배수
      "strong_streak": int | None,        # 연속강세 일수 (theme_state_log 기반)
      "error": None
    }
    """
    try:
        import theme_detail
        import theme_history
        import market_data

        cfg = _get_config()
        result = theme_detail.fetch_theme_stocks(theme_name)
        stocks = result.get("stocks", [])

        up_count = sum(1 for s in stocks if s.get("change_pct") is not None and s["change_pct"] > 0)
        three_plus_up = up_count >= 3

        # 등락률 1위 종목의 거래대금 배수
        ranked = sorted(
            [s for s in stocks if s.get("change_pct") is not None],
            key=lambda s: s["change_pct"],
            reverse=True,
        )
        leader_value_mult = None
        if ranked:
            leader_code = ranked[0]["code"]
            df = market_data.get_daily(leader_code)
            if df is not None:
                leader_value_mult = market_data.today_turnover_multiple(df)

        streak = theme_history.get_theme_elapsed_strong_days(theme_name)

        return {
            "ok": True,
            "three_plus_up": three_plus_up,
            "up_count": up_count,
            "total_count": len(stocks),
            "leader_value_mult": leader_value_mult,
            "strong_streak": streak,
            "error": None,
        }
    except Exception as e:
        _log.warning("theme_signals failed %s: %s", theme_name, e)
        return {"ok": False, "error": str(e)}


def theme_age(theme_name: str) -> int | None:
    """연속강세 시작일부터 오늘까지 경과 거래일 수.

    theme_history.get_theme_elapsed_strong_days() 결과를 그대로 반환한다.
    로그가 없거나 최근 판정이 '강함'이 아니면 None.
    """
    try:
        import theme_history
        return theme_history.get_theme_elapsed_strong_days(theme_name)
    except Exception as e:
        _log.warning("theme_age failed %s: %s", theme_name, e)
        return None


def find_leader(theme_name: str) -> dict:
    """테마 구성종목 중 대장 후보 리스트를 반환한다 (자동 확정하지 않는다).

    정렬 기준 (내림차순):
      1) 52주 고가 근접 점수: pct_from_52w_high가 -near_high_pct 이내면 1, 아니면 0
      2) 거래대금 배수 (today_turnover_multiple)

    최대 rank_limit개 반환. 선택은 사용자가 직접 한다.

    반환:
    {
      "ok": True,
      "candidates": [
        {"code": "006050", "name": "국영지앤엠",
         "pct_from_52w_high": -2.9, "near_high": True,
         "turnover_mult": 1.23, "change_pct": 5.66},
        ...
      ],
      "error": None
    }
    """
    try:
        import theme_detail
        import market_data

        cfg = _get_config()
        near_pct = cfg.get("near_high_pct", 10.0)
        rank_limit = int(cfg.get("rank_limit", 2))

        result = theme_detail.fetch_theme_stocks(theme_name)
        if not result["ok"]:
            return {"ok": False, "error": result["error"], "candidates": []}

        candidates = []
        for s in result["stocks"]:
            df = market_data.get_daily(s["code"])
            if df is None:
                continue
            pct_high = market_data.pct_from_52w_high(df)
            mult = market_data.today_turnover_multiple(df)
            near_high = pct_high is not None and pct_high >= -near_pct
            candidates.append(
                {
                    "code": s["code"],
                    "name": s["name"],
                    "pct_from_52w_high": pct_high,
                    "near_high": near_high,
                    "turnover_mult": mult,
                    "change_pct": s.get("change_pct"),
                }
            )

        def _sort_key(c):
            near = 1 if c["near_high"] else 0
            mult = c["turnover_mult"] or 0.0
            return (near, mult)

        candidates.sort(key=_sort_key, reverse=True)
        return {"ok": True, "candidates": candidates[:rank_limit], "error": None}
    except Exception as e:
        _log.warning("find_leader failed %s: %s", theme_name, e)
        return {"ok": False, "error": str(e), "candidates": []}


def max_warning(code6: str) -> dict:
    """최근 20거래일 내 일간 +20% 이상(또는 상한가) 이력 경보.

    상한가는 전일 대비 +29.9% 이상으로 근사한다.
    반환:
    {
      "ok": True,
      "warning": bool,       # 경보 발생 여부
      "max_gain_pct": float, # 최근 20일 최대 일간 상승률
      "spike_days": int,     # max_spike_pct 이상 날 수
      "error": None
    }
    """
    try:
        import market_data

        cfg = _get_config()
        spike_pct = cfg.get("max_spike_pct", 20.0)

        df = market_data.get_daily(code6)
        if df is None:
            return {"ok": False, "error": "일봉 데이터 없음", "warning": False}

        closes = df["Close"].tail(21)
        if len(closes) < 2:
            return {"ok": False, "error": "데이터 부족", "warning": False}

        rets = closes.pct_change().dropna() * 100
        rets = rets.tail(20)
        max_gain = float(rets.max())
        spike_days = int((rets >= spike_pct).sum())
        warning = spike_days > 0

        return {
            "ok": True,
            "warning": warning,
            "max_gain_pct": round(max_gain, 2),
            "spike_days": spike_days,
            "error": None,
        }
    except Exception as e:
        _log.warning("max_warning failed %s: %s", code6, e)
        return {"ok": False, "error": str(e), "warning": False}


def leader_break(code6: str) -> dict:
    """대장주 최근 고점 대비 leader_break_pct 이상 하락 여부.

    최근 고점: 최근 20거래일 최고가.
    반환:
    {
      "ok": True,
      "broken": bool,           # 붕괴 여부
      "recent_high": float,     # 최근 20일 최고가
      "current": float,         # 현재 종가
      "drop_pct": float,        # 최근 고점 대비 하락률 (음수)
      "error": None
    }
    """
    try:
        import market_data

        cfg = _get_config()
        break_pct = cfg.get("leader_break_pct", 7.0)

        df = market_data.get_daily(code6)
        if df is None:
            return {"ok": False, "error": "일봉 데이터 없음", "broken": False}

        recent_high = float(df["High"].tail(20).max())
        current = float(df["Close"].iloc[-1])
        drop_pct = (current - recent_high) / recent_high * 100

        return {
            "ok": True,
            "broken": drop_pct <= -break_pct,
            "recent_high": recent_high,
            "current": current,
            "drop_pct": round(drop_pct, 2),
            "error": None,
        }
    except Exception as e:
        _log.warning("leader_break failed %s: %s", code6, e)
        return {"ok": False, "error": str(e), "broken": False}


def market_state() -> dict:
    """최근 60거래일 코스피 수익률로 시장 국면을 판단한다.

    수익률 = (최근 종가 / 60거래일 전 종가) - 1. 음수면 '하락국면'.
    config로 기준을 나중에 조정할 수 있도록 설계했다(현재는 단순 0 기준).

    반환:
    {
      "ok": True,
      "phase": "하락국면" | "상승국면",
      "return_60d_pct": float,   # 60거래일 수익률(%)
      "volatile_days": int,      # 최근 60일 중 ±3% 이상 날 수
      "error": None
    }
    """
    try:
        import market_data

        df = market_data.get_index_daily()
        if df is None or len(df) < 61:
            return {"ok": False, "error": "지수 데이터 부족", "phase": None}

        closes = df["Close"]
        ret_60d = (float(closes.iloc[-1]) / float(closes.iloc[-61]) - 1) * 100
        phase = "하락국면" if ret_60d < 0 else "상승국면"
        volatile = market_data.volatile_days_60d(df)

        return {
            "ok": True,
            "phase": phase,
            "return_60d_pct": round(ret_60d, 2),
            "volatile_days": volatile,
            "error": None,
        }
    except Exception as e:
        _log.warning("market_state failed: %s", e)
        return {"ok": False, "error": str(e), "phase": None}


# ── DB 저장·조회 헬퍼 (자비스2 UI에서 사용) ────────────────────────────────────


def save_journal_entry(
    theme_name: str,
    theme_age_days: int | None,
    leader_name: str | None,
    target_ticker: str,
    setup: str,
    entry_price: float,
    stop_price: float,
    qty: int,
    alert_state: str | None,
    alert_ignore_reason: str | None,
    tags: str,
) -> int:
    """playbook_journal에 진입 기록을 저장하고 새 행의 id를 반환한다."""
    r_amount = abs(entry_price - stop_price) * qty
    recorded_at = datetime.now().isoformat(timespec="seconds")
    conn = _get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO playbook_journal
              (recorded_at, theme_name, theme_age_days, leader_name, target_ticker,
               setup, entry_price, stop_price, qty, r_amount,
               alert_state, alert_ignore_reason, tags, is_dropped, result)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,NULL)
            """,
            (recorded_at, theme_name, theme_age_days, leader_name, target_ticker,
             setup, entry_price, stop_price, qty, r_amount,
             alert_state, alert_ignore_reason, tags),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        _log.error("save_journal_entry failed: %s", e)
        raise
    finally:
        conn.close()


def save_dropout_entry(
    theme_name: str,
    target_ticker: str,
    tags: str,
) -> int:
    """playbook_journal에 탈락 기록을 저장하고 새 행의 id를 반환한다."""
    recorded_at = datetime.now().isoformat(timespec="seconds")
    conn = _get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO playbook_journal
              (recorded_at, theme_name, target_ticker, tags, is_dropped, result)
            VALUES (?,?,?,?,1,NULL)
            """,
            (recorded_at, theme_name, target_ticker, tags),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        _log.error("save_dropout_entry failed: %s", e)
        raise
    finally:
        conn.close()


def get_open_positions() -> list[dict]:
    """미청산(is_dropped=0, result IS NULL) 진입 기록 목록을 반환한다."""
    _init_playbook_tables()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM playbook_journal WHERE is_dropped=0 AND result IS NULL ORDER BY id DESC"
        ).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]
    except Exception as e:
        _log.warning("get_open_positions failed: %s", e)
        return []
    finally:
        conn.close()


def get_journal_recent(n: int = 30) -> list[dict]:
    """playbook_journal 최근 n건을 반환한다."""
    _init_playbook_tables()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM playbook_journal ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]
    except Exception as e:
        _log.warning("get_journal_recent failed: %s", e)
        return []
    finally:
        conn.close()


def save_crash_log(
    log_date: str,
    index_change_pct: float | None,
    causes: list[str],
    holding_logic_broken: str,
    memo: str,
) -> None:
    """crash_log에 급락일 기록을 저장한다."""
    import json as _json
    recorded_at = datetime.now().isoformat(timespec="seconds")
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO crash_log
              (recorded_at, log_date, index_change_pct, causes, holding_logic_broken, memo)
            VALUES (?,?,?,?,?,?)
            """,
            (recorded_at, log_date, index_change_pct,
             _json.dumps(causes, ensure_ascii=False), holding_logic_broken, memo),
        )
        conn.commit()
    except Exception as e:
        _log.error("save_crash_log failed: %s", e)
        raise
    finally:
        conn.close()


# ── 단독 실행 테스트 ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import io
    import sys

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    logging.basicConfig(level=logging.WARNING)

    TEST_THEME = "방산"
    TEST_LEADER_CODE = "064350"  # 현대로템 (방산 대표종목)

    print("=" * 60)
    print(f"[playbook.py 단독 실행 테스트] 테마: {TEST_THEME}")
    print(f"대상 코드: {TEST_LEADER_CODE}")
    print("=" * 60)

    print("\n[1] theme_signals")
    r1 = theme_signals(TEST_THEME)
    print(f"  양전 3개+: {r1.get('three_plus_up')} ({r1.get('up_count')}/{r1.get('total_count')})")
    print(f"  1위 거래대금 배수: {r1.get('leader_value_mult')}")
    print(f"  연속강세: {r1.get('strong_streak')}일")
    if not r1["ok"]:
        print(f"  오류: {r1.get('error')}")

    print("\n[2] theme_age")
    age = theme_age(TEST_THEME)
    print(f"  경과 거래일: {age}")

    print("\n[3] find_leader")
    r3 = find_leader(TEST_THEME)
    for i, c in enumerate(r3.get("candidates", []), 1):
        print(
            f"  후보{i}: {c['name']}({c['code']}) "
            f"52주고가대비: {c['pct_from_52w_high']}% "
            f"고점근접: {c['near_high']} "
            f"거래대금배수: {c['turnover_mult']}"
        )
    if not r3["ok"]:
        print(f"  오류: {r3.get('error')}")

    print(f"\n[4] max_warning ({TEST_LEADER_CODE})")
    r4 = max_warning(TEST_LEADER_CODE)
    print(f"  경보: {r4.get('warning')} | 최대상승: {r4.get('max_gain_pct')}% | 급등일: {r4.get('spike_days')}")
    if not r4["ok"]:
        print(f"  오류: {r4.get('error')}")

    print(f"\n[5] leader_break ({TEST_LEADER_CODE})")
    r5 = leader_break(TEST_LEADER_CODE)
    print(
        f"  붕괴: {r5.get('broken')} | 최근고점: {r5.get('recent_high')} "
        f"현재가: {r5.get('current')} 하락률: {r5.get('drop_pct')}%"
    )
    if not r5["ok"]:
        print(f"  오류: {r5.get('error')}")

    print("\n[6] market_state")
    r6 = market_state()
    print(f"  국면: {r6.get('phase')} | 60일수익률: {r6.get('return_60d_pct')}% | 변동일수: {r6.get('volatile_days')}일")
    if not r6["ok"]:
        print(f"  오류: {r6.get('error')}")

    print("\n완료:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
