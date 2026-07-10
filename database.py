"""SQLite 연결, 스키마, CRUD, timing_class 자동 분류."""

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
