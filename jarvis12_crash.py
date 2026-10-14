"""자비스12 전용 — 급락 후 반등장(낙폭종목) **기준일 하루로 정한 10종목** (2026-10-14 상하님 지시).

상하님 — *"나스닥이 고점 대비 −5% 밑으로 빠진 날을 기준으로 삼는데 새로운 종목들이 추가되는 것 자체가 문제 ·
그날 결정된 종목만 계속 나오는 게 맞지 않나 · 이 상황에 대한 설명이 있어야겠다 · 그날 나온 종목이 계속 그래프에
나와야겠지 · 두 가지로 갈라져 있지 않나? 그 두 가지 중 순위 5개씩, 즉 10개"*. 고르신 것(같은 날):
문턱 −5% · 더 빠지면 가장 깊은 날로 옮김 · 다음 급락까지 보여 줌 · 기준일 다음 날 한 번 산 것으로 셈.
규칙 글은 docs/US_THEME_SPEC.md 3-3 「2026-10-14 자비스12 그물」.

**무엇이 바뀌었나 (자비스3 의 jarvis3_data.find_crash_rebound_stocks 와 견줘)**
  · 기준일 — QQQ 가 52주 고점 대비 −5% 아래로 빠진 **이번 급락**에서 가장 깊었던 날. 「이번 급락」은 QQQ 가 전고점
    (52주 최고 종가)을 되찾으면 끝나고, 그 뒤 다시 −5% 아래로 빠지면 새 급락이다. 급락이 끝나도 **다음 급락까지**
    그 급락의 10종목을 그대로 보여 준다(예전처럼 오늘 낙폭으로 날마다 새로 찾지 않는다).
  · 점수 — **기준일 장 마감까지의 주가만으로** 한 번 매긴다(배점·두 갈래 낙폭 칸은 그대로). 그래서 날마다 바뀌지
    않는다. 예전에는 갈래는 기준일로 나누고 점수는 오늘 자료로 날마다 다시 매겨, 20개 안팎이 들락날락했다.
  · 고르는 수 — 고점 대비 −20~−30% 위 5개 · −30~−50% 위 5개 = 10개.
  · 현재가·「고점 대비 지금」·「기준일 뒤」 칸은 **오늘 값**이다(고른 뒤에 오늘 값으로 바꿔 끼운다).

**얼린 jarvis3_data 는 고치지 않는다(CLAUDE.md 0-2)** — 그 안의 계산 도움 함수를 같은 인자로 부르기만 한다.
**실패해도 화면이 죽지 않는다** — 못 구하면 ok=False 와 까닭을 돌려준다.
"""
from __future__ import annotations

import threading
import time
from datetime import date

import pandas as pd

import jarvis3_data as j3

# 계산이나 돌려주는 값을 바꾸면 올린다 — 화면이 옛 모듈을 다시 읽게(CLAUDE.md 11 과 같은 까닭).
MODULE_REVISION = 2026101410

SYMBOL = j3.CRASH_MARKET_SYMBOL          # QQQ — 자비스3 과 같은 자
THRESHOLD = -5.0                          # 상하님 2026-10-14 「−5%」
PER_BAND = 5                              # 두 갈래에서 5개씩
_MEMO_SECONDS = 1800.0
_MEMO: dict = {}
_LOCK = threading.Lock()


def _dates(index) -> list:
    """일봉 표의 날짜(뉴욕 날짜)."""
    out = []
    for stamp in index:
        stamp = pd.Timestamp(stamp)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert("America/New_York")
        out.append(stamp.date())
    return out


def _upto(frame, day: date):
    """그날 장 마감까지만 남긴 표."""
    if frame is None or getattr(frame, "empty", True):
        return frame
    keep = [d <= day for d in _dates(frame.index)]
    return frame.loc[keep]


def episodes() -> dict:
    """QQQ 급락을 모두 찾는다 — [{start, reference, reference_drop, last_below, recovered_on}] (오래된 것부터).

    낙폭 = 종가 ÷ 52주 최고가(장중) − 1 — 자비스3 기준일과 같은 자. 한 급락 안에서는 더 깊은 날이 오면 기준일을
    그날로 옮긴다. 종가가 52주 최고 종가에 닿으면(전고점 회복) 그 급락은 끝난다.
    """
    daily, _meta = j3._download_cached((SYMBOL,), period="2y", interval="1d", ttl_seconds=j3.US_BATCH_TTL)
    frame = daily.get(SYMBOL)
    if frame is None or frame.empty:
        return {"ok": False, "reason": "QQQ(나스닥100) 일봉을 못 받았습니다", "episodes": []}
    close = frame["Close"].astype(float)
    high52 = frame["High"].astype(float).rolling(252, min_periods=252).max()
    close52 = close.rolling(252, min_periods=252).max()
    drop = (close / high52 - 1.0) * 100.0
    days = _dates(frame.index)
    found, current = [], None
    for place, day in enumerate(days):
        value = drop.iloc[place]
        if pd.isna(value):
            continue
        value = float(value)
        if current is not None and float(close.iloc[place]) >= float(close52.iloc[place]) - 1e-9:
            current["recovered_on"] = day.isoformat()
            found.append(current)
            current = None
        if value <= THRESHOLD:
            if current is None:
                current = {"start": day.isoformat(), "reference": day.isoformat(), "reference_drop": value,
                           "last_below": day.isoformat(), "recovered_on": None}
            else:
                if value < current["reference_drop"]:
                    current["reference"], current["reference_drop"] = day.isoformat(), value
                current["last_below"] = day.isoformat()
    if current is not None:
        found.append(current)
    last_value = drop.dropna()
    return {"ok": True, "episodes": found,
            "today_drop": float(last_value.iloc[-1]) if len(last_value) else None,
            "as_of": days[-1].isoformat() if days else "", "frame": frame}


def reference() -> dict:
    """지금 보여 줄 급락(가장 최근 급락)의 기준일. 화면 설명 칸이 쓰는 값을 같이 싣는다."""
    try:
        info = episodes()
    except Exception as exc:
        return {"ok": False, "armed": False, "reason": f"기준일을 찾지 못했습니다 ({exc})"}
    if not info.get("ok"):
        return {"ok": False, "armed": False, "reason": info.get("reason")}
    if not info["episodes"]:
        return {"ok": True, "armed": False, "today_drop": info.get("today_drop"),
                "reason": f"최근 1년 안에 QQQ(나스닥100)가 고점 대비 {abs(THRESHOLD):.0f}% 넘게 빠진 날이 없었습니다."}
    latest = dict(info["episodes"][-1])
    out = {"ok": True, "armed": True, "today_drop": info.get("today_drop"),
           "reference_date": latest["reference"], "reference_drop": latest["reference_drop"],
           "episode_start": latest["start"], "last_below": latest["last_below"],
           "recovered_on": latest["recovered_on"], "threshold": THRESHOLD, "as_of": info.get("as_of"),
           "reason": ""}
    try:
        frame = info["frame"]
        days = _dates(frame.index)
        window = [stamp for stamp, day in zip(frame.index, days)
                  if latest["start"] <= day.isoformat() <= latest["last_below"]]
        out.update(j3._ixic_reference(pd.Index(window)))       # 참고 — 같은 때 나스닥 종합이 가장 깊었던 날
    except Exception:
        pass
    return out


def _pick(daily: dict, memberships: dict, ref_day: date, per_band: int = PER_BAND) -> list:
    """기준일 장 마감까지의 주가로 점수를 매기고 두 갈래에서 per_band 개씩 고른다(점수 차례 그대로)."""
    cut = {ticker: _upto(frame, ref_day) for ticker, frame in daily.items()}
    rows, all_metrics, since_reference = [], {}, {}
    for ticker in j3.US_LARGE_CAP_UNIVERSE:
        metrics = j3._series_metrics(cut.get(ticker))
        if not metrics.get("ok"):
            continue
        all_metrics[ticker] = metrics
        then_close = j3._finite(metrics.get("current"))
        now = j3._series_metrics(daily.get(ticker))
        now_close = j3._finite(now.get("current")) if now.get("ok") else None
        if then_close and now_close:
            since_reference[ticker] = (now_close / then_close - 1.0) * 100
        from_high = metrics.get("from_high_pct")
        if from_high is None:
            continue
        for order, rule in enumerate(j3.CRASH_REBOUND_RULES):
            low, high = rule["band"]
            if low <= from_high < high:
                row = j3._universe_row(ticker, metrics, memberships)
                row["judged_from_high_pct"] = from_high
                row["reference_date"] = ref_day.isoformat()
                row["bucket"] = rule["key"]
                row["bucket_label"] = rule["label"]
                row["hold_days"] = None
                row["hold_results"] = rule["results"]
                row["sample"] = rule["sample"]
                row["volume_streak"] = j3.volume_streak_days(cut.get(ticker))
                row["recent_gain_pct"] = j3.recent_gain_pct(cut.get(ticker))
                row["deepest_from_high_pct"] = j3.deepest_drop_since_high(cut.get(ticker))
                row["_order"] = order
                rows.append(row)
                break
    # 자비스3 find_crash_rebound_stocks 와 같은 차례·같은 인자로 점수 재료를 단다(기준일 자료로).
    j3._attach_crash_volatility(rows)
    j3._attach_theme_together(rows, memberships)
    j3._attach_theme_rebound_spread(rows, memberships, since_reference)
    j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_less_drop",
                          metric_key="from_high_pct", top_n=j3.CRASH_LESS_DROP_TOP_N)
    j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_aligned",
                          top_n=j3.CRASH_SPREAD_TOP_N, derive=j3._weekly_aligned)
    j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_above20",
                          top_n=j3.CRASH_SPREAD_TOP_N, derive=j3._above_sma20)
    j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_above150",
                          top_n=j3.CRASH_ABOVE150_TOP_N, derive=j3._above_sma150)
    j3._attach_theme_rank(rows, memberships, all_metrics, prefix="theme_ret120",
                          metric_key="ret120", top_n=j3.CRASH_RET120_TOP_N)
    for row in rows:
        row["score"] = float(j3.crash_rebound_score(row)["score"])
    rows.sort(key=lambda row: (-row.get("score", 0.0),
                               int(row.get("theme_above20") or 99),
                               j3._rank_key(row)[0], j3._rank_key(row)[1],
                               row.get("_order", 9), *j3._rank_key(row)[2:]))
    counts = {rule["key"]: sum(1 for row in rows if row["bucket"] == rule["key"]) for rule in j3.CRASH_REBOUND_RULES}
    picked = []
    for rule in j3.CRASH_REBOUND_RULES:                     # −20~−30 위 5개 → −30~−50 위 5개
        picked += [row for row in rows if row["bucket"] == rule["key"]][:per_band]
    # 고른 뒤 **보이는 값만 오늘 것으로** — 점수·갈래는 기준일 값 그대로다.
    for index, row in enumerate(picked, 1):
        ticker = row["ticker"]
        full = daily.get(ticker)
        now = j3._series_metrics(full)
        then_close = j3._finite((row.get("metrics") or {}).get("current"))
        row["reference_metrics"] = row.get("metrics")
        if now.get("ok"):
            row["metrics"] = now
            row["pullback"] = j3._pullback_quality(now, len(row.get("themes") or [])) or {}
            row["now_from_high_pct"] = now.get("from_high_pct")
            current = j3._finite(now.get("current"))
            row["since_reference_pct"] = ((current / then_close - 1.0) * 100) if current and then_close else None
        high_then = j3._finite((row["reference_metrics"] or {}).get("high52"))
        high_now = j3._finite(now.get("high52")) if now.get("ok") else None
        row["high52_then"], row["high52_now"] = high_then, high_now
        row["high52_moved"] = bool(high_then and high_now and abs(high_then - high_now) > 0.01)
        # 산 날 = 기준일 다음 거래일 · 산 값 = 그날 시가(성적표·그래프와 같은 셈).
        row["buy_date"], row["buy_open"] = None, None
        try:
            days = _dates(full.index)
            after = [place for place, day in enumerate(days) if day > ref_day]
            if after:
                row["buy_date"] = days[after[0]].isoformat()
                row["buy_open"] = float(full["Open"].iloc[after[0]])
        except Exception:
            pass
        row["pullback_rank"] = index
        row.pop("_order", None)
    return picked, counts


def _universe():
    daily, meta, memberships = j3._universe_daily(False)
    return daily, meta, memberships


def crash_list(*, reuse_only: bool = False) -> dict:
    """화면 「급락 후 반등장」 목록 — j3.find_crash_rebound_stocks 와 같은 모양으로 돌려준다(그리는 쪽을 그대로 쓰게)."""
    ref = reference()
    try:
        daily, meta, memberships = j3._universe_daily(reuse_only)
    except Exception as exc:
        return {"ok": False, "error": f"미국 종목 일봉 조회 실패 ({exc})", "rows": []}
    if not daily:
        return {"ok": False, "error": meta.get("error") or "미국 종목 일봉 조회 실패", "rows": []}
    market = j3.crash_market_state()
    base = {"ok": True, "mode": "crash", "rules": j3.CRASH_REBOUND_RULES, "score_weights": j3.CRASH_SCORE_WEIGHTS,
            "market": market, "reference": ref, "j12_fixed": True,
            "score_blind": False, "score_weak": False,
            "universe_count": len(j3.US_LARGE_CAP_UNIVERSE),
            "data_count": sum(1 for t in j3.US_LARGE_CAP_UNIVERSE if t in daily),
            "result_limit": PER_BAND * len(j3.CRASH_REBOUND_RULES),
            "checked_at": meta.get("fetched_at"), "stale": bool(meta.get("stale")),
            "reused_batch": bool(meta.get("reused_superset"))}
    if not ref.get("armed"):
        return {**base, "rows": [], "bucket_counts": {}, "days_since_reference": None}
    ref_day = date.fromisoformat(ref["reference_date"])
    key = ("list", ref["reference_date"], str(ref.get("as_of")))
    with _LOCK:
        memo = _MEMO.get(key)
    if memo and time.time() - memo[0] < _MEMO_SECONDS:
        picked, counts = memo[1]
    else:
        picked, counts = _pick(daily, memberships, ref_day)
        with _LOCK:
            _MEMO[key] = (time.time(), (picked, counts))
    # 「점수가 순위를 못 가른다」 경고는 자비스3 과 같이 **오늘 나스닥 낙폭**으로 판단한다 — 그 경고 글이
    # "나스닥이 지금 ○% 빠져 있습니다"라는 오늘 문장이다.
    drop_now = (market or {}).get("drop_pct")
    return {**base, "rows": [dict(row) for row in picked], "bucket_counts": counts,
            "score_blind": j3.crash_score_is_blind(drop_now), "score_weak": j3.crash_score_is_weak(drop_now),
            "days_since_reference": j3._trading_days_since(daily, ref["reference_date"])}


def cohorts(since: str = "") -> list:
    """성적표·그래프용 — 급락마다 그 10종목을 「기준일에 목록이 나왔고 다음 날 시가에 한 번 샀다」는 줄로.

    picklist 저장 줄과 같은 모양(trade_date · list_kind · code · buy_open · name · origin)이라 성적표 셈을 그대로 쓴다.
    since — 이 날 이후 기준일만(빈 글자면 1년 안 전부).
    """
    try:
        info = episodes()
    except Exception:
        return []
    if not info.get("ok") or not info["episodes"]:
        return []
    key = ("cohorts", str(info.get("as_of")), since)
    with _LOCK:
        memo = _MEMO.get(key)
    if memo and time.time() - memo[0] < _MEMO_SECONDS:
        return [dict(row) for row in memo[1]]
    try:
        daily, _meta, memberships = j3._universe_daily(False)
    except Exception:
        return []
    out = []
    for item in info["episodes"]:
        if since and item["reference"] < since:
            continue
        picked, _counts = _pick(daily, memberships, date.fromisoformat(item["reference"]))
        for row in picked:
            if not row.get("buy_open"):
                continue
            out.append({"trade_date": item["reference"], "list_kind": "crash", "code": row["ticker"],
                        "buy_open": row["buy_open"], "name": row.get("name") or row["ticker"],
                        "origin": row.get("bucket_label") or "", "rank": row.get("pullback_rank"),
                        "episode_recovered": item.get("recovered_on") or "", "j12_fixed": True})
    with _LOCK:
        _MEMO[key] = (time.time(), out)
    return [dict(row) for row in out]
