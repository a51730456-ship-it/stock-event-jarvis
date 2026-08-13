"""**그날그날의** 발행주식수를 받아 둔다 (2026-08-13).

**왜.** 그동안 시총 순위를 '오늘 주식수 × 그날 종가'로 매겼다. 오늘 주식수를
2016년에 갖다 쓴 것이라 미래정보다. 상하님·지피티 지적으로 바로잡는다.

yfinance의 `Ticker.get_shares_full(start, end)`가 과거 발행주식수를 준다.
8종목으로 미리 확인했더니 전부 받아졌다(AAPL 419개·MSFT 711개 등).

**못 받은 종목은 오늘 값으로 때우지 않는다.** 빈칸으로 두고, 그 종목은 그 기간
'시총 순위 못 잼'으로 처리한다. 때우면 다시 미래정보가 섞인다.

쓰는 법:  python research/us_shares_history.py
"""

from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "_data" / "us_shares_history.parquet"


def load() -> pd.DataFrame:
    """날짜 × 티커 발행주식수. 없으면 받아서 저장한다."""
    if OUT.exists():
        return pd.read_parquet(OUT)
    return fetch()


def fetch() -> pd.DataFrame:
    import yfinance as yf

    import jarvis3_data as j3

    tickers = sorted(set(j3.US_LARGE_CAP_UNIVERSE))
    print(f"{len(tickers)}종목의 **과거** 발행주식수를 받는다...", flush=True)
    series: dict[str, pd.Series] = {}
    missing = []
    for index, ticker in enumerate(tickers, 1):
        try:
            got = yf.Ticker(ticker).get_shares_full(start="2015-06-01",
                                                    end="2026-08-13")
        except Exception:
            got = None
        if got is None or len(got) == 0:
            missing.append(ticker)
        else:
            got = got.dropna()
            got.index = pd.to_datetime(got.index).tz_localize(None)
            series[ticker] = got[~got.index.duplicated(keep="last")]
        if index % 25 == 0:
            print(f"  {index}/{len(tickers)}...", flush=True)
        time.sleep(0.05)
    frame = pd.DataFrame(series).sort_index()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUT)
    print(f"\n받은 종목 {frame.shape[1]}개 · 못 받은 종목 {len(missing)}개")
    if missing:
        print("  못 받음: " + ", ".join(missing))
    print(f"저장 → {OUT}")
    return frame


def split_factor(close: pd.DataFrame) -> pd.DataFrame:
    """그날 **이후** 일어난 주식분할의 곱. 시총을 바로잡는 데 쓴다.

    2016년 NVDA를 예로 들면 그 뒤 4:1(2021)·10:1(2024) 분할이 있었으므로 40이다.
    """
    import pickle

    path = ROOT / "research" / "_data" / "us_splits.pkl"
    if not path.exists():
        fetch_splits()
    with path.open("rb") as handle:
        splits = pickle.load(handle)
    out = pd.DataFrame(1.0, index=close.index, columns=close.columns)
    for ticker, series in splits.items():
        if ticker not in out.columns:
            continue
        factor = pd.Series(1.0, index=close.index)
        for day, ratio in series.items():
            # **날짜를 00:00으로 맞춘다.** 야후가 주는 분할 시각은 09:30인데
            # 일봉 날짜는 00:00이라, 그냥 비교하면 '분할 당일'도 옛 배수를 한 번 더
            # 곱한다. 그러면 그날 하루만 시총이 10~25배로 튄다(54건 중 29건).
            # 시총 순위는 하루만 틀려 영향이 작지만, **테마 점수는 그 가짜 값이
            # 252일 최고로 들어가 1년 내내 남는다.** 2026-08-13에 잡았다.
            factor[close.index < pd.Timestamp(day).normalize()] *= float(ratio)
        out[ticker] = factor
    return out


def fetch_splits() -> dict:
    """분할 이력을 받아 둔다. 10년 사이 200종목 중 40개(20%)에 있었다."""
    import pickle

    import yfinance as yf

    import jarvis3_data as j3

    rows = {}
    for ticker in sorted(set(j3.US_LARGE_CAP_UNIVERSE)):
        try:
            series = yf.Ticker(ticker).splits
        except Exception:
            continue
        if series is None or len(series) == 0:
            continue
        series.index = pd.to_datetime(series.index).tz_localize(None)
        series = series[series.index >= pd.Timestamp("2016-01-01")]
        if len(series):
            rows[ticker] = series
    path = ROOT / "research" / "_data" / "us_splits.pkl"
    with path.open("wb") as handle:
        pickle.dump(rows, handle)
    return rows


def daily_market_cap(close: pd.DataFrame) -> pd.DataFrame:
    """그날의 **진짜** 시가총액.

    ## 2026-08-13에 고친 버그 — 이것 때문에 시총이 분할일에 열 배씩 튀었다

    `us_yearly.fetch()`가 주는 종가는 **분할을 반영해 조정된 값**이다(auto_adjust).
    2016년 NVDA 종가가 $2.63으로 나오는 것은 그 뒤 40배 분할을 미리 반영했기
    때문이다. 그런데 `get_shares_full`이 주는 주식수는 **그때 실제 주식수**(5.4억 주)다.

    **기준이 다른 둘을 곱했다.** 그래서 2016년 NVDA 시총이 14억 달러로 나왔다
    (실제 약 580억). 그리고 분할일 하루 만에 주식수만 열 배가 되어 시총이 튀었다
    (2024-06-10: 3,083억 → 2조 9,907억).

    **바로잡는 법** — 조정주가에는 조정된 주식수를 곱해야 한다.
    그날 주식수 × 그 뒤 분할배수 = 오늘 단위로 환산한 주식수다.

        시가총액 = 조정주가 × 그날 주식수 × 그 뒤 분할배수

    고치니 2016년 NVDA가 566억 달러(등수 126위 → 50위)로 실제와 맞아떨어졌다.

    ffill만 쓴다 — 뒤 값을 앞으로 끌어오면(bfill) 미래정보가 된다.
    """
    raw = load().reindex(columns=close.columns)

    # ── 분할배수를 **보고 날짜에서** 곱한다 ──────────────────────────────
    # 일봉에 먼저 채워 넣고 곱하면, 야후의 주식수 보고일과 분할일이 며칠 어긋난
    # 종목에서 배수가 두 번 곱해진다(AAPL 2020-08-31: 42.8억 → 171억).
    import pickle

    path = ROOT / "research" / "_data" / "us_splits.pkl"
    if not path.exists():
        fetch_splits()
    with path.open("rb") as handle:
        splits = pickle.load(handle)
    factor = pd.DataFrame(1.0, index=raw.index, columns=raw.columns)
    for ticker, series in splits.items():
        if ticker not in factor.columns:
            continue
        column = pd.Series(1.0, index=raw.index)
        for day, ratio in series.items():
            column[raw.index < pd.Timestamp(day).normalize()] *= float(ratio)
        factor[ticker] = column
    adjusted = raw * factor

    # ── 이웃과 크게 어긋나는 보고를 지운다 ───────────────────────────────
    # 위 보정으로도 분할 47건 중 15건에서 시총이 하루 만에 몇 배씩 튀었다.
    # 야후가 분할 전 보고를 이미 분할 후 주식수로 고쳐 놓은 경우가 있어서다.
    # 앞뒤 보고의 가운데값과 1.8배 넘게 어긋나는 점만 지운다 —
    # 유상증자·자사주 매입 같은 진짜 변화는 그 정도로 튀지 않는다.
    # 이렇게 하면 튀는 것이 47건 중 **1건**으로 줄어든다(2026-08-13 실측).
    for _ in range(2):
        for ticker in adjusted.columns:
            reports = adjusted[ticker].dropna()
            if len(reports) < 5:
                continue
            middle = reports.rolling(31, center=True, min_periods=3).median()
            odd = (reports / middle > 1.8) | (reports / middle < 1 / 1.8)
            if odd.any():
                adjusted.loc[reports.index[odd], ticker] = np.nan

    aligned = adjusted.reindex(close.index.union(adjusted.index)).ffill()
    return close * aligned.reindex(close.index)


if __name__ == "__main__":
    frame = fetch()
    print(frame.tail(3).iloc[:, :5])
