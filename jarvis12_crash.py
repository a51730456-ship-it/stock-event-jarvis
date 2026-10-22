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

**2026-10-21 밤 고침 (상하님 지시 · 설명서 3-3 「2026-10-21 밤 고침」)**
  · 종목 낙폭 — 기준일 종가 ÷ **「나스닥 고점일」(그 기준일까지 QQQ 52주 장중 최고가가 난 날)의 그 종목 종가** − 1.
    1년 최고가 기준은 쓰지 않는다(상하님이 분명히 거부하심).
  · 칸 — 10~20% · 20~30% · 30~50% (J12_RULES).
  · 종목 낙폭이 나스닥 낙폭(같은 두 날 QQQ 종가)의 3배를 넘으면 「수상하게 빠짐」(suspicious). 점수는 그대로.
  · 급락 배점(기준일 자료 · 같은 동점 규칙)으로 줄 세워 **20개**를 보이고, 경고 없는 종목 중 점수 위 **10개**를
    성적표에 쓴다(모자라면 경고 종목으로 채움 · scorecard=True). 순위 9 의 급락 3개 = 그 10개의 위 3개.

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
MODULE_REVISION = 2026102202

SYMBOL = j3.CRASH_MARKET_SYMBOL          # QQQ — 자비스3 과 같은 자
THRESHOLD = -5.0                          # 상하님 2026-10-14 「−5%」
PER_BAND = 5                              # (2026-10-14 판) 두 갈래에서 5개씩 — 지금은 안 쓴다
SHOW_COUNT = 20                           # 2026-10-21 — 화면·날짜별 목록에 보이는 수
SCORECARD_COUNT = 10                      # 2026-10-21 — 성적표에 쓰는 수(경고 없는 종목 먼저)
SUSPICIOUS_TIMES = 3.0                    # 종목 낙폭이 나스닥 낙폭의 이 배를 넘으면 「수상하게 빠짐」


def _results(rows):
    return tuple({"days": days, "label": label, "win_rate": win, "median_return": gain}
                 for (days, label), (win, gain) in zip(((60, "3개월"), (120, "6개월"), (250, "1년")), rows))


# 칸마다 과거 성적 — 지난 급락 22번 가장 깊은 날 기준 · 나스닥100 96종목 · 10년 · 다음 날 시가 매수(2026-10-21 상하님께
# 보고한 측정 · 참고). 큰 급락 몇 번이 자리 수를 많이 차지한다. 「median_return」 이름은 그리는 쪽(jarvis3 모양)에 맞춘 것이다.
J12_RULES = (
    {"key": "d10", "band": (-20.0, -10.0), "label": "고점일 대비 -10~-20%",
     "results": _results(((81, 16.8), (82, 24.9), (74, 29.2))), "sample": None},
    {"key": "d20", "band": (-30.0, -20.0), "label": "고점일 대비 -20~-30%",
     "results": _results(((87, 25.0), (89, 38.7), (83, 52.1))), "sample": None},
    {"key": "d30", "band": (-50.0, -30.0), "label": "고점일 대비 -30~-50%",
     "results": _results(((91, 36.6), (92, 47.0), (92, 77.6))), "sample": None},
)
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
    for item in found:
        item.update(_peak_of(frame, item["reference"]))
    last_value = drop.dropna()
    return {"ok": True, "episodes": found,
            "today_drop": float(last_value.iloc[-1]) if len(last_value) else None,
            "as_of": days[-1].isoformat() if days else "", "frame": frame}


def _close_on(frame, day: date):
    """그날(장이 없으면 그 앞 마지막 장) 종가 — 없으면 None."""
    if frame is None or getattr(frame, "empty", True):
        return None
    places = [place for place, seen in enumerate(_dates(frame.index)) if seen <= day]
    if not places:
        return None
    try:
        value = float(frame["Close"].iloc[places[-1]])
    except Exception:
        return None
    return value if value == value and value > 0 else None


def _peak_of(frame, ref_iso: str) -> dict:
    """나스닥 고점일 — 그 기준일까지 52주(252장) 안에서 QQQ 장중 최고가가 난 날 · 그날 종가 → 기준일 종가 낙폭(%)."""
    days = _dates(frame.index)
    upto = [place for place, day in enumerate(days) if day.isoformat() <= ref_iso]
    if not upto:
        return {"peak_date": None, "nasdaq_drop": None}
    end = upto[-1]
    start = max(0, end - 251)
    highs = frame["High"].astype(float).iloc[start:end + 1].reset_index(drop=True)
    place = start + int(highs.idxmax())
    peak_close = float(frame["Close"].iloc[place])
    ref_close = float(frame["Close"].iloc[end])
    return {"peak_date": days[place].isoformat(),
            "nasdaq_drop": (ref_close / peak_close - 1.0) * 100.0 if peak_close else None}


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
           "peak_date": latest.get("peak_date"), "nasdaq_drop": latest.get("nasdaq_drop"),
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


def _pick(daily: dict, memberships: dict, ref_day: date, peak_day=None, nasdaq_drop=None,
          show: int = SHOW_COUNT) -> tuple:
    """기준일 장 마감까지의 주가로 점수를 매기고 급락 배점 차례로 show 개를 고른다(2026-10-21 상하님 지시).

    종목 낙폭 = 기준일 종가 ÷ 나스닥 고점일(peak_day)의 그 종목 종가 − 1 → 10~20 · 20~30 · 30~50% 칸.
    경고 없는 종목 중 점수 위 SCORECARD_COUNT 개에 scorecard=True(모자라면 경고 종목으로 채움).
    """
    if isinstance(peak_day, str):
        peak_day = date.fromisoformat(peak_day)
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
        peak_close = _close_on(cut.get(ticker), peak_day) if peak_day else None
        if not peak_close or not then_close:
            continue                    # 나스닥 고점일 값이 없다(그 뒤 상장 등) — 못 잰다
        from_peak = (then_close / peak_close - 1.0) * 100
        for order, rule in enumerate(J12_RULES):
            low, high = rule["band"]
            if low <= from_peak < high:
                row = j3._universe_row(ticker, metrics, memberships)
                row["judged_from_high_pct"] = from_peak
                row["peak_date"] = peak_day.isoformat()
                row["peak_close"] = peak_close
                row["nasdaq_drop_pct"] = nasdaq_drop
                row["suspicious"] = bool(nasdaq_drop is not None and nasdaq_drop < 0
                                         and abs(from_peak) > SUSPICIOUS_TIMES * abs(nasdaq_drop))
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
    # 급락 배점 차례(동점이면 위 규칙 그대로) — 순위 9 가 성적표 10종목에서 위 3개를 뽑을 때 쓴다.
    for order, row in enumerate(rows):
        row["score_order"] = order
    counts = {rule["key"]: sum(1 for row in rows if row["bucket"] == rule["key"]) for rule in J12_RULES}
    picked = rows[:show]
    # 성적표 10개 — 경고 없는 종목 중 점수 위부터, 모자라면 경고 종목으로 채운다(점수 차례).
    chosen = [row for row in picked if not row["suspicious"]][:SCORECARD_COUNT]
    if len(chosen) < SCORECARD_COUNT:
        chosen += [row for row in picked if row["suspicious"]][:SCORECARD_COUNT - len(chosen)]
    chosen_ids = {id(row) for row in chosen}
    for row in picked:
        row["scorecard"] = id(row) in chosen_ids
    # 고른 뒤 **보이는 값만 오늘 것으로** — 점수·칸은 기준일 값 그대로다.
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


def drop_story(row: dict) -> str | None:
    """세부사항 노란 글의 첫 문장 — 나스닥 고점일부터 몇 % 빠졌나(2026-10-21). 자비스12 줄이 아니면 None."""
    peak, judged, ref = row.get("peak_date"), row.get("judged_from_high_pct"), row.get("reference_date")
    if not peak or judged is None or not ref:
        return None
    text = (f"나스닥 고점일({peak}) 종가에서 기준일({ref}) 종가까지 {float(judged):.1f}% 빠졌던 종목입니다.")
    nasdaq = row.get("nasdaq_drop_pct")
    if nasdaq is not None:
        text += f" 같은 두 날 나스닥(QQQ)은 {float(nasdaq):.1f}%였습니다."
    if row.get("suspicious"):
        text += (f" 나스닥의 {SUSPICIOUS_TIMES:.0f}배 넘게 빠져 「수상하게 빠짐」으로 표시합니다 — 시장 말고 이 회사만의"
                 " 까닭(실적·사건)이 있었는지 보십시오. 점수는 그대로입니다.")
    since = row.get("since_reference_pct")
    if since is not None:
        text += f" 그 뒤 {float(since):+.1f}% {'올랐습니다' if float(since) >= 0 else '더 빠졌습니다'}."
    return text + " 칸과 점수는 오늘이 아니라 그날 낙폭으로 정합니다."


def _md(iso) -> str:
    """'2026-10-06' → '10월 6일'. 못 읽으면 그대로.

    「10/6」으로 적으면 노란 상자가 점수(66/70 꼴)로 알고 초록으로 칠했다(2026-10-21 미리보기에서 발견).
    """
    try:
        _year, month, day = str(iso).split("-")
        return f"{int(month)}월 {int(day)}일"
    except Exception:
        return str(iso or "")


def buy_reason(row: dict) -> str | None:
    """세부사항 노란 상자 글 전체 — 짧게 핵심만 (2026-10-21 상하님 「장황하다 · 일반인이 보기에 직관적으로」).

    자비스12 줄(나스닥 고점일이 실린 줄)이 아니면 None — 그러면 화면은 예전 글을 그대로 쓴다.
    「다음 거래일 시가」·「파는 시점은 규칙에 없습니다」·「손절가가 없습니다」는 화면이 굵게 칠하는 말이라 그대로 둔다.
    """
    peak, judged, ref = row.get("peak_date"), row.get("judged_from_high_pct"), row.get("reference_date")
    if not peak or judged is None or not ref:
        return None
    # 지수 이름은 QQQ 로 적는다 — 이 파트는 처음부터 QQQ 로 잰다(2026-10-22 상하님 「QQQ로 표시해야 되지 않나」).
    # 숫자마다 **누구의 숫자인지** 앞에 적는다(같은 날 「나스닥종합인지 QQQ인지 개별종목인지 명확하게」).
    # 둘 다 **종가 → 종가**다 — 「시장 상황」의 QQQ 숫자(1년 장중 최고가 대비)와 출발점이 달라 조금 다르다.
    who = str(row.get("ticker") or "").strip() or "이 종목"
    text = f"{who} 종가: QQQ 고점일({_md(peak)}) → 기준일({_md(ref)}) {float(judged):.1f}%"
    nasdaq = row.get("nasdaq_drop_pct")
    if nasdaq is not None:
        text += f" · 같은 두 날 QQQ 종가 {float(nasdaq):.1f}%"
    text += "."
    since = row.get("since_reference_pct")
    # 기준일이 마지막 장이면(산 날이 아직 없음) 「그 뒤 +0.0%」는 뜻이 없어 뺀다(2026-10-22 캡처).
    if since is not None and row.get("buy_date", "있음") is not None:
        text += f" 그 뒤 {float(since):+.1f}%."
    if row.get("suspicious"):
        text += f" ⚠ QQQ 종가 낙폭의 {SUSPICIOUS_TIMES:.0f}배 넘게 빠짐 — 회사 자체 문제일 수 있습니다."
    text += " 다음 거래일 시가에 삽니다. 파는 시점은 규칙에 없습니다. 이 규칙에는 손절가가 없습니다."
    results = row.get("hold_results") or ()
    if results:
        band = str(row.get("bucket_label") or "").replace("고점일 대비 ", "").replace("-", "")
        text += (f" 이 칸({band}) 과거 성적: "
                 + " · ".join(f"{item['label']} {item['median_return']:+.1f}%(100번 중 {item['win_rate']:.0f}번)"
                              for item in results) + ".")
    return text


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
    base = {"ok": True, "mode": "crash", "rules": J12_RULES, "score_weights": j3.CRASH_SCORE_WEIGHTS,
            "market": market, "reference": ref, "j12_fixed": True,
            "score_blind": False, "score_weak": False,
            "universe_count": len(j3.US_LARGE_CAP_UNIVERSE),
            "data_count": sum(1 for t in j3.US_LARGE_CAP_UNIVERSE if t in daily),
            "result_limit": SHOW_COUNT,
            "checked_at": meta.get("fetched_at"), "stale": bool(meta.get("stale")),
            "reused_batch": bool(meta.get("reused_superset"))}
    if not ref.get("armed"):
        return {**base, "rows": [], "bucket_counts": {}, "days_since_reference": None}
    ref_day = date.fromisoformat(ref["reference_date"])
    key = ("list", ref["reference_date"], str(ref.get("as_of")), MODULE_REVISION)
    with _LOCK:
        memo = _MEMO.get(key)
    if memo and time.time() - memo[0] < _MEMO_SECONDS:
        picked, counts = memo[1]
    else:
        picked, counts = _pick(daily, memberships, ref_day, ref.get("peak_date"), ref.get("nasdaq_drop"))
        with _LOCK:
            _MEMO[key] = (time.time(), (picked, counts))
    # 「점수가 순위를 못 가른다」 경고는 자비스3 과 같이 **오늘 나스닥 낙폭**으로 판단한다 — 그 경고 글이
    # "나스닥이 지금 ○% 빠져 있습니다"라는 오늘 문장이다.
    drop_now = (market or {}).get("drop_pct")
    return {**base, "rows": [dict(row) for row in picked], "bucket_counts": counts,
            "score_blind": j3.crash_score_is_blind(drop_now), "score_weak": j3.crash_score_is_weak(drop_now),
            "days_since_reference": j3._trading_days_since(daily, ref["reference_date"])}


def cohorts(since: str = "") -> list:
    """성적표·그래프·날짜별 목록용 — 급락마다 그 20종목을 「기준일에 목록이 나왔고 다음 날 시가에 한 번 샀다」는 줄로.
    성적표는 scorecard=True 인 10개만 센다(2026-10-21).

    picklist 저장 줄과 같은 모양(trade_date · list_kind · code · buy_open · name · origin)이라 성적표 셈을 그대로 쓴다.
    since — 이 날 이후 기준일만(빈 글자면 1년 안 전부).
    """
    try:
        info = episodes()
    except Exception:
        return []
    if not info.get("ok") or not info["episodes"]:
        return []
    key = ("cohorts", str(info.get("as_of")), since, MODULE_REVISION)
    with _LOCK:
        memo = _MEMO.get(key)
    if memo and time.time() - memo[0] < _MEMO_SECONDS:
        return [dict(row) for row in memo[1]]
    try:
        daily, _meta, memberships = j3._universe_daily(False)
    except Exception:
        return []
    out = []
    found = info["episodes"]
    for place, item in enumerate(found):
        if since and item["reference"] < since:
            continue
        # 이 10종목을 보여 주는 마지막 — 다음 급락이 시작한 날(그 전날까지 보여 줌). 없으면 지금도 보여 준다.
        shown_until = found[place + 1]["start"] if place + 1 < len(found) else ""
        picked, _counts = _pick(daily, memberships, date.fromisoformat(item["reference"]),
                                item.get("peak_date"), item.get("nasdaq_drop"))
        for row in picked:
            if not row.get("buy_open"):
                continue
            # 점수·테마·기준일 낙폭·갈래는 날짜별 목록 표가 쓴다(2026-10-15 · 자비스12 목록에 10종목으로 보여 주기).
            out.append({"trade_date": item["reference"], "list_kind": "crash", "code": row["ticker"],
                        "buy_open": row["buy_open"], "name": row.get("name") or row["ticker"],
                        "origin": row.get("bucket_label") or "", "rank": row.get("pullback_rank"),
                        "score": row.get("score"), "themes": "·".join(row.get("themes") or ()),
                        "judged_from_high_pct": row.get("judged_from_high_pct"),
                        "bucket_label": row.get("bucket_label") or "", "score_order": row.get("score_order"),
                        "episode_recovered": item.get("recovered_on") or "", "shown_until": shown_until,
                        "peak_date": row.get("peak_date"), "suspicious": bool(row.get("suspicious")),
                        "scorecard": bool(row.get("scorecard")), "j12_fixed": True})
    with _LOCK:
        _MEMO[key] = (time.time(), out)
    return [dict(row) for row in out]


def held_from(rows: list, start: date) -> list:
    """고른 기간 **첫날에 이미 들고 있던** 급락 10종목 — 그 첫날 시가에 들고 있던 것으로 다시 친 줄 (2026-10-14 상하님 지시).

    상하님 — *"9월 1일부터 지금까지 표를 보니 급락 후 반등장 종목들이 나오질 않는다 · 전고점을 뚫을 때 급락 후 종목들
    검색은 종료되지만 그 당시 종목들이 그래프에는 나오게 하는 게 맞지 않나"*. 기준일 다음 날(예: 7/30)에 산 줄은 그보다
    뒤에 시작하는 기간(예: 9/1~)에서 「산 날이 없다」로 빠졌다. 그 10종목은 다음 급락 전까지 들고 있는 종목이므로, 기간
    첫날에 아직 보여 주던 급락이면 **기간 첫 거래일에 그 목록이 나왔다고 보고 다음 거래일 시가에 산 것**으로 넣는다.
    다른 파트가 「그날 목록 → 다음 거래일 시가」로 사는 것과 **같은 날**이다 — 처음(084405a)에는 기간 첫 거래일 시가에
    사서 하루 먼저 샀고, 9/1 날짜별 목록과 같은 종목인데 수익이 달랐다(MDB −1.40% · −15.8% · 상하님 캡처 2026-10-14).
    """
    late = [row for row in rows
            if row["trade_date"] < start.isoformat() and (not row.get("shown_until") or row["shown_until"] > start.isoformat())]
    if not late:
        return []
    codes = tuple(dict.fromkeys(row["code"] for row in late))
    try:
        frames, _meta = j3._download_cached(codes, period="2y", interval="1d", ttl_seconds=j3.US_BATCH_TTL)
    except Exception:
        return []
    out = []
    for row in late:
        frame = (frames or {}).get(row["code"])
        if frame is None or getattr(frame, "empty", True):
            continue
        days = _dates(frame.index)
        # 기간 첫날을 목록 날로 보고 **그 뒤 첫 장** 시가에 산다 — 첫날이 장 날이면 다음 거래일, 주말·휴일이면 그 뒤 첫
        # 거래일(2026-10-15). 예전에는 첫날 이후 첫 장을 목록 날로 쳐서 첫날이 토요일이면 화요일에 샀다 — 그 토요일
        # 목록의 다른 파트(월요일 시가)보다 하루 늦었다.
        after = [place for place, day in enumerate(days) if day > start]
        if not after:
            continue                    # 기간 첫날 다음 장이 아직 안 열렸다 — 산 날이 없다
        try:
            buy = float(frame["Open"].iloc[after[0]])
        except Exception:
            continue
        if not buy or buy != buy:
            continue
        out.append({**row, "trade_date": start.isoformat(), "buy_open": buy,
                    "held_from": days[after[0]].isoformat()})
    return out
