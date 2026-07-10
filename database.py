"""SQLite 연결, 스키마, CRUD, timing_class 자동 분류."""

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "jarvis.sqlite3"

MARKET_SCOPE_CHOICES = ["KR", "US", "MIXED"]
TIMING_CLASS_CHOICES = ["장전", "장중", "장후", "혼합", "장마감"]
ITEM_MARKET_CHOICES = ["KR", "US", "OTHER"]
VERDICT_CHOICES = ["추천 후보", "감시", "확인 필요", "보류(선반영)", "제외"]
BRIEFING_STAGE_CHOICES = [
    "08:30 개장 전 예측",
    "09:30~10:30 기관 수급 조짐",
    "09:40 현재 장초반 수급 조짐",
    "13:00~13:30 기관 수급 반전 최종판단",
    "13:10 오후 지속/반전 판단",
    "13시 이후 늦은 확정 신호",
    "장중 스냅샷 기반 판단",
    "미국장 마감 후 스윙 판단",
    "오늘 주가 확인 기반 국내장 판단",
    "기타",
]
SIGNAL_TYPE_CHOICES = ["선행 신호", "재확인 신호", "늦은 신호", "가짜 신호", "미분류"]
TRADE_MODE_CHOICES = ["공통", "단타", "스윙"]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                saved_at TEXT NOT NULL,
                market_scope TEXT NOT NULL,
                timing_class TEXT NOT NULL,
                day_conclusion TEXT NOT NULL,
                raw_briefing TEXT NOT NULL,
                briefing_stage TEXT
            );

            CREATE TABLE IF NOT EXISTS report_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                event_title TEXT,
                ticker TEXT,
                stock_name TEXT,
                market TEXT,
                item_timing_class TEXT,
                stock_market_basis_a TEXT,
                stock_market_basis_b TEXT,
                stock_market_basis_c TEXT,
                betting_basis_ga TEXT,
                betting_basis_na TEXT,
                betting_basis_da TEXT,
                stock_market_judgment TEXT,
                betting_market_judgment TEXT,
                verdict TEXT NOT NULL,
                signal_type TEXT,
                trade_mode TEXT DEFAULT '공통',
                FOREIGN KEY (report_id) REFERENCES reports(id)
            );

            CREATE TABLE IF NOT EXISTS rejected_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rejected_at TEXT,
                market TEXT,
                ticker TEXT,
                stock_name TEXT,
                trade_mode TEXT,
                reject_reason TEXT,
                assumed_entry_price REAL,
                note TEXT,
                source_report_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (source_report_id) REFERENCES reports(id)
            );

            -- 2단계 성과검증(판단 잔차 채굴) 준비용 자식 테이블. 이번 단계는 스키마만
            -- 만든다 — 성과 계산/가격 조회/UI/performance.py 연결은 이후 별도 작업이다.
            -- report_items 한 행에 대해 여러 거래일(horizon_sessions)과 두 가지 성과 기준
            -- (entry_basis: judgment=저장 당시 판단 적중률용, actual=실제 매수 체결가 기준
            -- 실매매 성과용)을 각각 별도 행으로 저장할 수 있게 설계했다. entry_price_used는
            -- 계산 당시 실제로 사용한 기준가격 스냅샷이며, report_items.entry_price/
            -- actual_entry_price가 나중에 바뀌어도 과거 계산 결과가 흔들리지 않도록 한다.
            CREATE TABLE IF NOT EXISTS report_item_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_item_id INTEGER NOT NULL,
                horizon_sessions INTEGER NOT NULL,
                entry_basis TEXT NOT NULL,
                entry_price_used REAL,
                target_date TEXT,
                close_price REAL,
                high_price REAL,
                low_price REAL,
                return_pct REAL,
                benchmark_symbol TEXT,
                benchmark_return_pct REAL,
                excess_return_pct REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                evaluated_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(report_item_id, horizon_sessions, entry_basis),

                CHECK(horizon_sessions > 0),
                CHECK(entry_basis IN ('judgment', 'actual')),
                CHECK(status IN ('pending', 'evaluated', 'unavailable', 'error')),

                FOREIGN KEY(report_item_id)
                    REFERENCES report_items(id)
                    ON DELETE CASCADE
            );
            """
        )
        conn.commit()
        _migrate_add_columns(conn)
    finally:
        conn.close()


def _migrate_add_columns(conn):
    """기존 DB(구버전 스키마)에 briefing_stage/signal_type 컬럼을 ALTER TABLE로 추가한다.

    기존 행은 삭제/재생성하지 않고, 새로 추가된 컬럼만 채운다
    (reports.briefing_stage -> '기타', report_items.signal_type -> '미분류').
    이미 컬럼이 있는 DB(신규 생성 DB 포함)에는 아무 영향을 주지 않는다.
    """
    report_cols = {row["name"] for row in conn.execute("PRAGMA table_info(reports)")}
    if "briefing_stage" not in report_cols:
        conn.execute("ALTER TABLE reports ADD COLUMN briefing_stage TEXT")
        conn.execute("UPDATE reports SET briefing_stage = '기타' WHERE briefing_stage IS NULL")

    item_cols = {row["name"] for row in conn.execute("PRAGMA table_info(report_items)")}
    if "signal_type" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN signal_type TEXT")
        conn.execute("UPDATE report_items SET signal_type = '미분류' WHERE signal_type IS NULL")

    if "trade_mode" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN trade_mode TEXT DEFAULT '공통'")
        conn.execute("UPDATE report_items SET trade_mode = '공통' WHERE trade_mode IS NULL")

    # 판단 설명(점수/근거/매수 확정) 표시 기능용 추가 컬럼. 기존 행은 건드리지 않고
    # (NULL로 남겨 "정보 없음"으로 표시), 새로 저장되는 행부터 save_report()가 값을 채운다.
    if "score" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN score REAL")
    if "score_reason" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN score_reason TEXT")
    if "top_candidate_reason" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN top_candidate_reason TEXT")
    if "penalty_reason" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN penalty_reason TEXT")
    # buy_confirmed는 저장 당시 시스템 판단용 legacy 필드다. 사후 실제 행동 기록은
    # actual_action(아래 별도 컬럼)을 쓰며, 둘은 동기화하지 않는다.
    if "buy_confirmed" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN buy_confirmed TEXT")
    if "buy_confirm_condition" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN buy_confirm_condition TEXT")

    # v1.1 리스크 엔진 / 청산 계획 / 경고형 확정 차단용 추가 컬럼. 기존 행은 NULL로 남기고
    # ("정보 없음"으로 표시), 새로 저장되는 행부터 save_report()가 값을 채운다.
    for col in (
        "entry_price", "stop_loss_price", "planned_stop_price", "target_price",
        "expected_holding_days", "five_day_change_pct",
    ):
        if col not in item_cols:
            conn.execute(f"ALTER TABLE report_items ADD COLUMN {col} REAL")
    for col in ("plan_followed", "violation_reason", "disclosure_type", "news_status", "judged_at"):
        if col not in item_cols:
            conn.execute(f"ALTER TABLE report_items ADD COLUMN {col} TEXT")

    # v1.2A 결과 검증층: 청산 결과 기록용 추가 컬럼. 기존 행은 NULL로 남기고, UI/저장 로직은
    # 이번 단계에서 만들지 않는다(컬럼 추가만).
    if "actual_exit_price" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN actual_exit_price REAL")
    if "result_r" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN result_r REAL")
    for col in ("actual_exit_date", "exit_reason", "verification_status"):
        if col not in item_cols:
            conn.execute(f"ALTER TABLE report_items ADD COLUMN {col} TEXT")

    # v1.2B 필터 무시 매매 로그용 추가 컬럼. 기존 행은 NULL로 남기고, UI/저장 로직은
    # 이번 단계에서 만들지 않는다(컬럼 추가만). violation_reason(청산 계획 위반 사유)과는
    # 별개 개념이라 재사용하지 않고 새 컬럼으로 분리한다.
    for col in ("filter_ignored", "filter_ignore_reason", "filter_ignore_memo"):
        if col not in item_cols:
            conn.execute(f"ALTER TABLE report_items ADD COLUMN {col} TEXT")

    # 플레이북 태그용 추가 컬럼. 이 매매가 어떤 전략/셋업이었는지 기록하는 순수 전략 태그
    # 전용이며(예: US_EARNINGS_SWING, KR_BUYBACK_SWING, LEADER_LAGGARD_DAYTRADE), 필터 무시
    # 사유/감정매매/뉴스충동/복구매매/손절지연/수주공시추격금지 같은 경고·실수 개념은 여기
    # 넣지 않는다(그건 filter_ignore_reason 영역). UI/저장 로직은 이번 단계에서 만들지 않는다
    # (컬럼 추가만).
    if "playbook_tags" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN playbook_tags TEXT")

    # 테마 태그용 추가 컬럼(1차: 스키마만). 종목별로 어떤 시장 테마(예: 반도체/HBM, 전력기기/전력망)와
    # 연결되는지 콤마구분 코드 문자열로 기록할 예정이며, playbook_tags와 동일하게 저장 시점이
    # 아니라 저장 결과 확인 화면에서 report_items.id 기준 사후 UPDATE로 채운다. 기존 행은 NULL로
    # 남기고, UI/저장 로직은 이번 단계에서 만들지 않는다(컬럼 추가만).
    if "theme_tags" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN theme_tags TEXT")

    # 실제 행동 기록용 추가 컬럼(1차: 스키마만). 저장된 판단(추천 후보/감시 등)과 별개로,
    # 상하님이 실제로 "매수"/"보류"/"제외" 중 무엇을 했는지 남긴다. 단순 매수 여부 Boolean이
    # 아니라 3가지로 나누는 이유는, 나중에 판단 잔차 채굴에서 매수했는데 실패한 경우/보류했는데
    # 상승한 경우/제외했는데 상승한 경우/매수하지 않아 손실을 피한 경우를 구분해서 비교하기
    # 위함이다. buy_confirmed(매수 확정 여부, "확정"/"미확정")와는 별개 개념이라 재사용하지
    # 않고 새 컬럼으로 분리한다. 기존 행은 NULL로 남기고, UI/저장 로직은 이번 단계에서 만들지
    # 않는다(컬럼 추가만).
    if "actual_action" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN actual_action TEXT")

    # 실제 매수 체결 평균가격용 추가 컬럼(1차: 스키마만). 상하님이 실제로 매수한 평균 체결가를
    # 남기며, 저장 당시 시스템이 제시한 entry_price(계획/참고용 진입가)와는 다른 사후 실제
    # 행동 데이터다. actual_action='매수' 여부와 자동 연동하지 않는다. 기존 행은 NULL로 남기고,
    # UI/저장 로직은 이번 단계에서 만들지 않는다(컬럼 추가만).
    if "actual_entry_price" not in item_cols:
        conn.execute("ALTER TABLE report_items ADD COLUMN actual_entry_price REAL")

    conn.commit()


def classify_timing_class(saved_at: datetime) -> str:
    """saved_at 시:분을 기준으로 장전/장중/장후/혼합을 자동 분류한다.

    00:00~05:59 혼합 (미국장 운영 시간대), 06:00~08:59 장전,
    09:00~15:29 장중, 15:30~23:59 장후.
    """
    minutes = saved_at.hour * 60 + saved_at.minute
    if minutes < 6 * 60:
        return "혼합"
    if minutes < 9 * 60:
        return "장전"
    if minutes < 15 * 60 + 30:
        return "장중"
    return "장후"


def save_report(
    market_scope, day_conclusion, raw_briefing, items=None, saved_at=None, briefing_stage=None, timing_class=None
):
    """report 1건 + report_items N건(N>=0)을 저장하고 report_id를 반환한다.

    timing_class를 명시적으로 넘기지 않으면(기존 동작 그대로) saved_at 기준 자동 분류를 쓴다.
    명시적으로 넘기면(예: 미국장 마감 후 스윙 자동 기록) 그 값을 그대로 저장한다.
    """
    if market_scope not in MARKET_SCOPE_CHOICES:
        raise ValueError(f"market_scope must be one of {MARKET_SCOPE_CHOICES}, got {market_scope!r}")

    briefing_stage = briefing_stage or "기타"
    if briefing_stage not in BRIEFING_STAGE_CHOICES:
        raise ValueError(f"briefing_stage must be one of {BRIEFING_STAGE_CHOICES}, got {briefing_stage!r}")

    saved_at = saved_at or datetime.now()
    if timing_class is None:
        timing_class = classify_timing_class(saved_at)
    elif timing_class not in TIMING_CLASS_CHOICES:
        raise ValueError(f"timing_class must be one of {TIMING_CLASS_CHOICES}, got {timing_class!r}")
    items = items or []

    for item in items:
        if item.get("verdict") not in VERDICT_CHOICES:
            raise ValueError(f"verdict must be one of {VERDICT_CHOICES}, got {item.get('verdict')!r}")
        signal_type = item.get("signal_type") or "미분류"
        if signal_type not in SIGNAL_TYPE_CHOICES:
            raise ValueError(f"signal_type must be one of {SIGNAL_TYPE_CHOICES}, got {signal_type!r}")
        trade_mode = item.get("trade_mode") or "공통"
        if trade_mode not in TRADE_MODE_CHOICES:
            raise ValueError(f"trade_mode must be one of {TRADE_MODE_CHOICES}, got {trade_mode!r}")

    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO reports (saved_at, market_scope, timing_class, day_conclusion, raw_briefing, briefing_stage) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                saved_at.isoformat(timespec="seconds"),
                market_scope,
                timing_class,
                day_conclusion,
                raw_briefing,
                briefing_stage,
            ),
        )
        report_id = cur.lastrowid

        for item in items:
            conn.execute(
                """
                INSERT INTO report_items (
                    report_id, event_title, ticker, stock_name, market, item_timing_class,
                    stock_market_basis_a, stock_market_basis_b, stock_market_basis_c,
                    betting_basis_ga, betting_basis_na, betting_basis_da,
                    stock_market_judgment, betting_market_judgment, verdict, signal_type, trade_mode,
                    score, score_reason, top_candidate_reason, penalty_reason,
                    buy_confirmed, buy_confirm_condition,
                    entry_price, stop_loss_price, planned_stop_price, target_price,
                    expected_holding_days, five_day_change_pct,
                    plan_followed, violation_reason, disclosure_type, news_status, judged_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    item.get("event_title"),
                    item.get("ticker"),
                    item.get("stock_name"),
                    item.get("market"),
                    item.get("item_timing_class"),
                    item.get("stock_market_basis_a"),
                    item.get("stock_market_basis_b"),
                    item.get("stock_market_basis_c"),
                    item.get("betting_basis_ga"),
                    item.get("betting_basis_na"),
                    item.get("betting_basis_da"),
                    item.get("stock_market_judgment"),
                    item.get("betting_market_judgment"),
                    item.get("verdict"),
                    item.get("signal_type") or "미분류",
                    item.get("trade_mode") or "공통",
                    item.get("score"),
                    item.get("score_reason") or None,
                    item.get("top_candidate_reason") or None,
                    item.get("penalty_reason") or None,
                    item.get("buy_confirmed") or "미확정",
                    item.get("buy_confirm_condition") or "확인 필요",
                    item.get("entry_price"),
                    item.get("stop_loss_price"),
                    item.get("planned_stop_price"),
                    item.get("target_price"),
                    item.get("expected_holding_days"),
                    item.get("five_day_change_pct"),
                    item.get("plan_followed"),
                    item.get("violation_reason"),
                    item.get("disclosure_type"),
                    item.get("news_status"),
                    item.get("judged_at"),
                ),
            )
        conn.commit()
        return report_id
    finally:
        conn.close()


def list_reports():
    """모든 report를 최신순으로 반환."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM reports ORDER BY saved_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_report():
    """가장 최근 report 1건. 없으면 None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reports ORDER BY saved_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_report(report_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_report_items(report_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM report_items WHERE report_id = ? ORDER BY id", (report_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_report_item_theme_tags(report_item_id, theme_tags):
    """report_items.id 기준 사후 UPDATE 전용(새 report/report_item 생성 없음).

    theme_tags는 문자열 리스트를 받는다. 앞뒤 공백 제거 + 중복 제거 후 JSON 배열 문자열로
    저장한다(한글이 깨지지 않도록 ensure_ascii=False). 빈 리스트를 넘기면 태그 전부 해제로
    보고 NULL을 저장한다. report_items.id 외 다른 컬럼/다른 행은 건드리지 않는다.
    존재하지 않는 id를 넘기면 아무 행도 갱신되지 않으므로 False를 반환한다(조용한 성공 아님).
    """
    cleaned = []
    seen = set()
    for tag in theme_tags or []:
        tag = (tag or "").strip()
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    value = json.dumps(cleaned, ensure_ascii=False) if cleaned else None

    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE report_items SET theme_tags = ? WHERE id = ?", (value, report_item_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def parse_theme_tags(value):
    """report_items.theme_tags(TEXT, JSON 배열 문자열)를 리스트로 안전하게 변환한다.

    NULL/빈 문자열 -> 빈 리스트. JSON 파싱에 실패하거나 리스트가 아닌 값이 저장돼 있어도
    예외를 던지지 않고 빈 리스트로 처리한다(화면 렌더링이 중단되지 않도록).
    """
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(v).strip() for v in parsed if str(v).strip()]


ACTUAL_ACTION_CHOICES = ("매수", "보류", "제외")


def update_report_item_actual_action(report_item_id, action):
    """report_items.id 기준 사후 UPDATE 전용(새 report/report_item 생성 없음).

    action은 None(미기록) 또는 "매수"/"보류"/"제외" 중 하나만 허용한다. 그 외 값은
    ValueError를 던진다(저장하지 않음). report_items.id 외 다른 컬럼/다른 행은 건드리지
    않는다. buy_confirmed는 저장 당시 시스템 판단용 legacy 필드이고 actual_action은
    사용자의 사후 실제 행동 기록이라 서로 동기화하지 않는다(이 함수는 buy_confirmed를
    절대 건드리지 않는다). 존재하지 않는 id를 넘기면 아무 행도 갱신되지 않으므로 False를
    반환한다(조용한 성공 아님).

    실제 체결가(actual_entry_price)가 이미 채워진 행을 '매수'가 아닌 값으로 바꾸려 하면
    ValueError를 던지고 저장을 거부한다(모순 방지). actual_entry_price를 자동으로 지우지
    않으며, 먼저 체결가를 비운 뒤 다시 시도해야 한다는 안내는 호출자(UI) 쪽에서 보여준다.
    """
    if action is not None and action not in ACTUAL_ACTION_CHOICES:
        raise ValueError(f"action must be None or one of {ACTUAL_ACTION_CHOICES}, got {action!r}")

    conn = get_connection()
    try:
        if action != "매수":
            row = conn.execute(
                "SELECT actual_entry_price FROM report_items WHERE id = ?", (report_item_id,)
            ).fetchone()
            if row is not None and row["actual_entry_price"] is not None:
                raise ValueError(
                    "실제 체결가가 입력된 상태에서는 '매수'가 아닌 값으로 바꿀 수 없습니다. "
                    "먼저 실제 체결가를 비운 뒤 다시 시도하세요."
                )
        cur = conn.execute(
            "UPDATE report_items SET actual_action = ? WHERE id = ?", (action, report_item_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_report_item_actual_entry_price(report_item_id, price):
    """report_items.id 기준 사후 UPDATE 전용(새 report/report_item 생성 없음).

    price는 None(미기록, DB에는 NULL) 또는 0보다 큰 유한 숫자(int/float)만 허용한다.
    bool은 숫자로 인정하지 않고, NaN/Infinity/0 이하 값은 ValueError를 던진다(저장 안 함).
    대상 행의 actual_action이 '매수'가 아니면 양수 가격 저장은 거부하지만(ValueError),
    None(NULL) 저장은 행동값과 무관하게 항상 허용한다(체결가를 비우는 동작은 막지 않음).
    entry_price/buy_confirmed 등 다른 컬럼은 절대 건드리지 않는다. 존재하지 않는 id를
    넘기면 아무 행도 갱신되지 않으므로 False를 반환한다.
    """
    if price is not None:
        if isinstance(price, bool):
            raise ValueError("price must not be a bool")
        if not isinstance(price, (int, float)):
            raise ValueError(f"price must be None or a number, got {price!r}")
        price = float(price)
        if not math.isfinite(price):
            raise ValueError("price must be a finite number (NaN/Infinity not allowed)")
        if price <= 0:
            raise ValueError("price must be greater than 0")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT actual_action FROM report_items WHERE id = ?", (report_item_id,)
        ).fetchone()
        if row is None:
            return False
        if price is not None and row["actual_action"] != "매수":
            raise ValueError("실제 행동이 '매수'인 종목만 실제 체결가를 저장할 수 있습니다.")
        cur = conn.execute(
            "UPDATE report_items SET actual_entry_price = ? WHERE id = ?", (price, report_item_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def normalize_actual_action(value):
    """report_items.actual_action(TEXT)을 화면 표시용 값으로 안전하게 변환한다.

    NULL/빈 문자열/허용되지 않은 값 -> "미기록". "매수"/"보류"/"제외"는 그대로 반환한다.
    비정상 값이 있어도 예외를 던지지 않고 "미기록"으로 표시만 하며, DB에 자동으로
    덮어쓰지 않는다(읽기 전용 정규화).
    """
    if value in ACTUAL_ACTION_CHOICES:
        return value
    return "미기록"


def get_report_items_grouped_by_verdict(report_id):
    """해당 report의 report_items를 판정 5종별로 그룹화해서 반환."""
    grouped = {verdict: [] for verdict in VERDICT_CHOICES}
    for item in get_report_items(report_id):
        grouped.setdefault(item["verdict"], []).append(item)
    return grouped


def search_reports(
    date_from=None,
    date_to=None,
    market_scopes=None,
    timing_classes=None,
    verdicts=None,
    day_conclusion_keyword=None,
    raw_briefing_keyword=None,
    briefing_stages=None,
    signal_types=None,
):
    """보관함 필터/검색용 조회. 모든 인자는 선택적이며, 비어있으면(None/빈 값) 해당 조건은 적용하지 않는다.

    - date_from/date_to: "YYYY-MM-DD" 문자열, saved_at 기준 범위(포함)
    - market_scopes/timing_classes/verdicts/briefing_stages/signal_types: 값 목록(list). 여러 개 선택 시 OR로 매칭.
    - verdicts/signal_types는 report_items에 있는 값이라 EXISTS 서브쿼리로 필터링한다
      (해당 조건을 만족하는 종목이 하나라도 있으면 포함 — verdict와 signal_type은 같은 종목
      항목일 필요 없이 서로 독립적으로 존재 여부만 확인한다).
    - day_conclusion_keyword/raw_briefing_keyword: 부분 일치(LIKE) 검색.
    - 모든 조건은 AND로 결합. 반환은 reports 컬럼만 포함하며 최신순.
    """
    where_clauses = []
    params = []

    if date_from:
        where_clauses.append("saved_at >= ?")
        params.append(f"{date_from}T00:00:00")
    if date_to:
        where_clauses.append("saved_at <= ?")
        params.append(f"{date_to}T23:59:59")
    if market_scopes:
        placeholders = ",".join("?" for _ in market_scopes)
        where_clauses.append(f"market_scope IN ({placeholders})")
        params.extend(market_scopes)
    if timing_classes:
        placeholders = ",".join("?" for _ in timing_classes)
        where_clauses.append(f"timing_class IN ({placeholders})")
        params.extend(timing_classes)
    if briefing_stages:
        placeholders = ",".join("?" for _ in briefing_stages)
        where_clauses.append(f"briefing_stage IN ({placeholders})")
        params.extend(briefing_stages)
    if day_conclusion_keyword:
        where_clauses.append("day_conclusion LIKE ?")
        params.append(f"%{day_conclusion_keyword}%")
    if raw_briefing_keyword:
        where_clauses.append("raw_briefing LIKE ?")
        params.append(f"%{raw_briefing_keyword}%")
    if verdicts:
        placeholders = ",".join("?" for _ in verdicts)
        where_clauses.append(
            f"EXISTS (SELECT 1 FROM report_items ri WHERE ri.report_id = reports.id AND ri.verdict IN ({placeholders}))"
        )
        params.extend(verdicts)
    if signal_types:
        placeholders = ",".join("?" for _ in signal_types)
        where_clauses.append(
            f"EXISTS (SELECT 1 FROM report_items ri WHERE ri.report_id = reports.id AND ri.signal_type IN ({placeholders}))"
        )
        params.extend(signal_types)

    query = "SELECT * FROM reports"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY saved_at DESC, id DESC"

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---- report_item_outcomes 저장/조회 헬퍼 (2단계 성과검증 스키마 전용) ----
# 이번 단계는 저장/조회 함수만 추가한다. performance.py 연결, 가격 자동조회, UI,
# 판단 적중률/실매매 수익률 계산은 전부 이후 별도 작업이다. 이 함수들을 호출해도
# 운영 DB에 실제 outcome 행이 생기지는 않는다(호출하는 곳이 아직 없음).

OUTCOME_ENTRY_BASIS_CHOICES = ("judgment", "actual")
OUTCOME_STATUS_CHOICES = ("pending", "evaluated", "unavailable", "error")


def _validate_outcome_price(value, name):
    """가격류 필드(entry_price_used/close_price/high_price/low_price) 검증.

    None 허용. bool/NaN/Infinity 거부. 값이 있으면 0보다 커야 한다.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must not be a bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number (NaN/Infinity not allowed)")
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


def _validate_outcome_pct(value, name):
    """수익률류 필드(return_pct/benchmark_return_pct/excess_return_pct) 검증.

    None 허용. bool/NaN/Infinity 거부. 음수는 허용한다(하락도 정상 값이므로).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must not be a bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number (NaN/Infinity not allowed)")
    return value


def upsert_report_item_outcome(
    report_item_id,
    horizon_sessions,
    entry_basis,
    entry_price_used=None,
    target_date=None,
    close_price=None,
    high_price=None,
    low_price=None,
    return_pct=None,
    benchmark_symbol=None,
    benchmark_return_pct=None,
    excess_return_pct=None,
    status="pending",
    evaluated_at=None,
):
    """report_item_outcomes를 UNIQUE(report_item_id, horizon_sessions, entry_basis)
    기준으로 UPSERT한다(새 report/report_item은 생성하지 않음).

    같은 키로 다시 호출하면 INSERT가 아니라 UPDATE로 처리되며, 이때 id와 created_at은
    바뀌지 않고 updated_at만 CURRENT_TIMESTAMP로 갱신된다. 잘못된 입력은 DB에 쓰기 전에
    ValueError를 던진다(가격류는 0 이하/bool/NaN/Infinity 거부, 수익률류는 bool/NaN/
    Infinity만 거부하고 음수는 허용). report_item_id가 존재하지 않는 report_items.id면
    ValueError를 던진다. status='evaluated'면 entry_price_used/target_date/close_price/
    return_pct가 전부 채워져 있어야 한다(high_price/low_price는 선택). 성공 시 저장된
    report_item_outcomes.id를 반환한다. 다른 report_item_outcomes 행이나 report_items
    행은 건드리지 않는다.
    """
    if isinstance(horizon_sessions, bool) or not isinstance(horizon_sessions, int):
        raise ValueError(
            f"horizon_sessions must be a positive int (not bool), got {horizon_sessions!r}"
        )
    if horizon_sessions <= 0:
        raise ValueError("horizon_sessions must be greater than 0")

    if entry_basis not in OUTCOME_ENTRY_BASIS_CHOICES:
        raise ValueError(
            f"entry_basis must be one of {OUTCOME_ENTRY_BASIS_CHOICES}, got {entry_basis!r}"
        )

    if status not in OUTCOME_STATUS_CHOICES:
        raise ValueError(f"status must be one of {OUTCOME_STATUS_CHOICES}, got {status!r}")

    for _name, _value in (("target_date", target_date), ("evaluated_at", evaluated_at)):
        if _value is not None and not isinstance(_value, str):
            raise ValueError(f"{_name} must be a string or None, got {_value!r}")
    if benchmark_symbol is not None and not isinstance(benchmark_symbol, str):
        raise ValueError(f"benchmark_symbol must be a string or None, got {benchmark_symbol!r}")

    entry_price_used = _validate_outcome_price(entry_price_used, "entry_price_used")
    close_price = _validate_outcome_price(close_price, "close_price")
    high_price = _validate_outcome_price(high_price, "high_price")
    low_price = _validate_outcome_price(low_price, "low_price")
    return_pct = _validate_outcome_pct(return_pct, "return_pct")
    benchmark_return_pct = _validate_outcome_pct(benchmark_return_pct, "benchmark_return_pct")
    excess_return_pct = _validate_outcome_pct(excess_return_pct, "excess_return_pct")

    if status == "evaluated":
        missing = [
            _name
            for _name, _value in (
                ("entry_price_used", entry_price_used),
                ("target_date", target_date),
                ("close_price", close_price),
                ("return_pct", return_pct),
            )
            if _value is None
        ]
        if missing:
            raise ValueError(f"status='evaluated' requires non-null: {', '.join(missing)}")

    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT id FROM report_items WHERE id = ?", (report_item_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"report_item_id {report_item_id!r} does not exist")

        conn.execute(
            """
            INSERT INTO report_item_outcomes (
                report_item_id, horizon_sessions, entry_basis, entry_price_used,
                target_date, close_price, high_price, low_price, return_pct,
                benchmark_symbol, benchmark_return_pct, excess_return_pct,
                status, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_item_id, horizon_sessions, entry_basis) DO UPDATE SET
                entry_price_used = excluded.entry_price_used,
                target_date = excluded.target_date,
                close_price = excluded.close_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                return_pct = excluded.return_pct,
                benchmark_symbol = excluded.benchmark_symbol,
                benchmark_return_pct = excluded.benchmark_return_pct,
                excess_return_pct = excluded.excess_return_pct,
                status = excluded.status,
                evaluated_at = excluded.evaluated_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                report_item_id, horizon_sessions, entry_basis, entry_price_used,
                target_date, close_price, high_price, low_price, return_pct,
                benchmark_symbol, benchmark_return_pct, excess_return_pct,
                status, evaluated_at,
            ),
        )
        conn.commit()
        saved = conn.execute(
            "SELECT id FROM report_item_outcomes "
            "WHERE report_item_id = ? AND horizon_sessions = ? AND entry_basis = ?",
            (report_item_id, horizon_sessions, entry_basis),
        ).fetchone()
        return saved["id"]
    finally:
        conn.close()


def get_report_item_outcomes(report_item_id):
    """report_item_id 하나의 성과 행 전체를 반환한다.

    정렬: horizon_sessions 오름차순, 같은 horizon 안에서는 entry_basis가 judgment 먼저,
    actual 다음. 행이 없거나 report_item_id 자체가 존재하지 않아도 예외 없이 빈 리스트를
    반환한다(get_report_items()와 동일한 조회 전용 패턴). 원본 DB 값은 읽기만 한다.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM report_item_outcomes
            WHERE report_item_id = ?
            ORDER BY horizon_sessions ASC,
                     CASE entry_basis WHEN 'judgment' THEN 0 WHEN 'actual' THEN 1 ELSE 2 END
            """,
            (report_item_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report_outcomes(report_id):
    """report_id 하나에 대해 reports -> report_items -> report_item_outcomes를
    INNER JOIN해서 이미 저장된 성과 행만 반환한다.

    outcome이 없는 report_item은 결과에 포함되지 않으며(INNER JOIN), 이 함수는 조회만
    하고 새 pending 행을 만들지 않는다. 정렬: report_item_id, horizon_sessions,
    entry_basis(judgment 먼저) 순.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                r.id AS report_id,
                ri.id AS report_item_id,
                ri.stock_name AS item_name,
                ri.ticker AS ticker,
                ri.market AS market,
                ri.actual_action AS actual_action,
                ri.actual_entry_price AS actual_entry_price,
                ri.theme_tags AS theme_tags,
                rio.horizon_sessions AS horizon_sessions,
                rio.entry_basis AS entry_basis,
                rio.entry_price_used AS entry_price_used,
                rio.target_date AS target_date,
                rio.close_price AS close_price,
                rio.high_price AS high_price,
                rio.low_price AS low_price,
                rio.return_pct AS return_pct,
                rio.benchmark_symbol AS benchmark_symbol,
                rio.benchmark_return_pct AS benchmark_return_pct,
                rio.excess_return_pct AS excess_return_pct,
                rio.status AS status,
                rio.evaluated_at AS evaluated_at
            FROM reports r
            JOIN report_items ri ON ri.report_id = r.id
            JOIN report_item_outcomes rio ON rio.report_item_id = ri.id
            WHERE r.id = ?
            ORDER BY ri.id ASC, rio.horizon_sessions ASC,
                     CASE rio.entry_basis WHEN 'judgment' THEN 0 WHEN 'actual' THEN 1 ELSE 2 END
            """,
            (report_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
