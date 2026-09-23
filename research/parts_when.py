# -*- coding: utf-8 -*-
"""어느 때 어느 파트가 나았나 — **화면 없이 숫자만** 낸다 (2026-09-23 상하님 지시).

상하님 — *"파트별 성적표에 어떨 때 상위 테마가 성적이 좋았는지, 급락 후 반등장이
좋았는지, 상승장이 좋았는지 만들 수 있나?"* · *"상승장은 종목이 몇 개 나오지 않아
수익률을 왜곡할 수 있다. 이 문제도 고민해 봐야 한다."*

**이 파일은 화면을 건드리지 않는다.** CLAUDE.md 0-1 가의 첫 걸음이다 — 먼저 과거
자료로 숫자를 내고, 그 숫자를 보신 뒤에 기준을 정하고, 그다음에 설명서와 화면이다.

**어디서 자료를 가져오나**
    data/picklist/{날짜}.US.csv — 그날 화면에 뜬 목록을 **찍은 그대로** 쌓아 둔 것이다.
    (2026-08-08 부터. 나중에 알게 된 것으로 고르지 않는다 — 그날의 목록 그대로다.)
    list_kind: theme15(상위 테마 5개의 1~3위) · breakout(상승장) · crash(급락 후 반등장)
               · top7(매수심사결과 높은 순위 9)

**성적을 어떻게 재나**
    신호가 뜬 날의 **다음 거래일 시가**에 사서, **5·20·60거래일 뒤 종가**에 판다.
    파는 시점을 하나로 못박지 않는다(앱의 원칙과 같다) — 셋을 나란히 본다.

**종목 수가 다른 것을 어떻게 다루나** (상승장은 하루 1~4개, 급락은 20개)
    ① **하루에 한 표** — 그날 그 파트의 **가운데 값** 하나만 그날 성적으로 쓴다.
       20종목 난 날이 1종목 난 날보다 세게 치지 않는다.
    ② **평균 대신 가운데 값** — 한 종목이 +40% 튀어도 전체가 끌려가지 않는다.
    ③ **이긴 날 수** — 그날 파트들 중 가운데 값이 가장 높았던 파트를 센다.
       종목 수와 상관없는 숫자다.
    ④ 잰 날이 적은 칸은 숫자를 **안 믿는다** — 몇 날인지를 늘 같이 적는다.

**어떤 때로 가르나**
    그날 나스닥이 1년 최고에서 얼마나 내려와 있었나(화면 맨 위 막대가 쓰는 그 값).
      · 전고점 근처 : 0 ~ -3%
      · 조금 빠짐   : -3 ~ -10%
      · 많이 빠짐   : -10% 아래
    같은 파일로 20일선 위/아래도 함께 낸다.

돌리는 법:  python research/parts_when.py
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "picklist"
HORIZONS = (5, 20, 60)
PART_NAMES = {
    "theme15": "상위 테마 5개 (1~3위)",
    "breakout": "상승장 (신고가 눌림매수)",
    "crash": "급락 후 반등장 (낙폭종목)",
    "top7": "매수심사결과 높은 순위 9",
}
BUCKETS = (
    ("전고점 근처 (0~-3%)", -3.0, 0.0),
    ("조금 빠짐 (-3~-10%)", -10.0, -3.0),
    ("많이 빠짐 (-10% 아래)", -100.0, -10.0),
)
MIN_DAYS = 10          # 이보다 적으면 숫자를 안 믿는다


def load_lists() -> dict:
    """날짜 → 파트 → 종목 목록."""
    out: dict = defaultdict(lambda: defaultdict(list))
    for path in sorted(ARCHIVE.glob("*.US.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                day = (row.get("trade_date") or "").strip()
                kind = (row.get("list_kind") or "").strip()
                code = (row.get("code") or "").strip().upper()
                if day and kind in PART_NAMES and code:
                    out[day][kind].append(code)
    return out


def price_frames(tickers) -> dict:
    """종목마다 일봉. 한 번에 묶어 받는다."""
    tickers = sorted(set(tickers))
    frames = {}
    step = 40
    for start in range(0, len(tickers), step):
        chunk = tickers[start:start + step]
        data = yf.download(chunk, period="1y", interval="1d", group_by="ticker",
                           progress=False, auto_adjust=False, threads=True)
        for ticker in chunk:
            try:
                frame = data[ticker] if len(chunk) > 1 else data
                frame = frame.dropna(subset=["Open", "Close"])
                if not frame.empty:
                    frames[ticker] = frame
            except Exception:
                continue
    return frames


def forward_return(frame, day: str, horizon: int):
    """그 다음 거래일 시가에 사서 horizon 거래일 뒤 종가에 판 값(%). 못 재면 None."""
    try:
        index = frame.index
        after = index[index > pd.Timestamp(day)]
        if len(after) < horizon + 1:
            return None
        buy = float(frame.loc[after[0], "Open"])
        sell = float(frame.loc[after[horizon], "Close"])
        if not buy:
            return None
        return (sell / buy - 1.0) * 100.0
    except Exception:
        return None


def nasdaq_state() -> pd.DataFrame:
    """날짜마다 '1년 최고 대비 몇 %'와 '20일선 위인가'."""
    frame = yf.download("^IXIC", period="2y", interval="1d", progress=False, auto_adjust=False)
    close = frame["Close"].dropna()
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    high = close.rolling(252, min_periods=60).max()
    sma20 = close.rolling(20, min_periods=20).mean()
    return pd.DataFrame({
        "drawdown": (close / high - 1.0) * 100.0,
        "above20": close > sma20,
    })


def bucket_of(drop):
    for name, low, high in BUCKETS:
        if low < drop <= high:
            return name
    return BUCKETS[-1][0] if drop is not None and drop <= -10 else None


def main() -> int:
    lists = load_lists()
    if not lists:
        print("저장해 둔 목록이 없습니다.")
        return 1
    days = sorted(lists)
    print(f"저장된 미국 목록 {len(days)}일 · {days[0]} ~ {days[-1]}")
    tickers = {code for day in lists.values() for codes in day.values() for code in codes}
    print(f"종목 {len(tickers)}개 일봉을 받습니다…")
    frames = price_frames(tickers)
    print(f"  받은 종목 {len(frames)}개")
    market = nasdaq_state()

    # 날짜 → 파트 → 기간 → 그날의 가운데 값
    daily: dict = defaultdict(lambda: defaultdict(dict))
    counts: dict = defaultdict(dict)
    for day, parts in lists.items():
        for part, codes in parts.items():
            counts[day][part] = len(codes)
            for horizon in HORIZONS:
                values = [forward_return(frames[c], day, horizon) for c in codes if c in frames]
                values = [v for v in values if v is not None]
                if values:
                    daily[day][part][horizon] = statistics.median(values)

    # 그날의 시장 상태
    state = {}
    for day in days:
        try:
            row = market.loc[:pd.Timestamp(day)].iloc[-1]
            state[day] = (float(row["drawdown"]), bool(row["above20"]))
        except Exception:
            state[day] = (None, None)

    for horizon in HORIZONS:
        print(f"\n════ {horizon}거래일 뒤에 팔았다면 ════")
        rows = [day for day in days if any(horizon in daily[day][p] for p in PART_NAMES)]
        print(f"  잴 수 있는 날 {len(rows)}일")
        if not rows:
            print("  아직 그만큼 시간이 안 지났습니다.")
            continue
        # ① 파트별 전체
        print(f"  {'파트':26s} {'잰 날':>5s} {'가운데 값':>9s} {'이긴 날':>7s} {'하루 종목 수':>11s}")
        wins = defaultdict(int)
        for day in rows:
            best, best_value = None, None
            for part in PART_NAMES:
                value = daily[day][part].get(horizon)
                if value is not None and (best_value is None or value > best_value):
                    best, best_value = part, value
            if best:
                wins[best] += 1
        for part, name in PART_NAMES.items():
            values = [daily[day][part][horizon] for day in rows if horizon in daily[day][part]]
            sizes = [counts[day].get(part, 0) for day in rows if horizon in daily[day][part]]
            if not values:
                print(f"  {name:26s} {'0':>5s} {'—':>9s} {'—':>7s} {'—':>11s}")
                continue
            middle = statistics.median(values)
            size_text = f"{statistics.median(sizes):.0f}개"
            mark = "" if len(values) >= MIN_DAYS else "  ← 아직 모자람"
            print(f"  {name:26s} {len(values):5d} {middle:+8.1f}% {wins[part]:6d}번 {size_text:>11s}{mark}")
        # ② 때별
        for bucket_name, _low, _high in BUCKETS:
            bucket_days = [day for day in rows
                           if state.get(day, (None, None))[0] is not None
                           and bucket_of(state[day][0]) == bucket_name]
            if not bucket_days:
                continue
            print(f"\n  · {bucket_name} — {len(bucket_days)}일")
            for part, name in PART_NAMES.items():
                values = [daily[day][part][horizon] for day in bucket_days if horizon in daily[day][part]]
                if not values:
                    print(f"      {name:26s} {'—':>9s}   (0일)")
                    continue
                mark = "" if len(values) >= MIN_DAYS else "  ← 아직 모자람"
                print(f"      {name:26s} {statistics.median(values):+8.1f}%   ({len(values)}일){mark}")
        # ③ 20일선 위/아래
        for label, want in (("나스닥이 20일선 위", True), ("나스닥이 20일선 아래", False)):
            sub = [day for day in rows if state.get(day, (None, None))[1] is want]
            if not sub:
                continue
            print(f"\n  · {label} — {len(sub)}일")
            for part, name in PART_NAMES.items():
                values = [daily[day][part][horizon] for day in sub if horizon in daily[day][part]]
                if not values:
                    print(f"      {name:26s} {'—':>9s}   (0일)")
                    continue
                mark = "" if len(values) >= MIN_DAYS else "  ← 아직 모자람"
                print(f"      {name:26s} {statistics.median(values):+8.1f}%   ({len(values)}일){mark}")
    print("\n※ 가운데 값 = 그날 그 파트 종목들의 가운데 수익률을, 날짜별로 다시 가운데 낸 값.")
    print(f"※ 잰 날이 {MIN_DAYS}일보다 적으면 숫자를 믿지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
