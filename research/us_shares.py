"""미국 명부 200종목의 **발행주식수**를 받아 둔다 (2026-08-12).

**왜.** 상하님이 "빅10 · 11~50위 · 51~100위를 갈라서 검정해봐라" 하셨다.
크기로 가르려면 시가총액이 있어야 하는데 지금 캐시에는 값·거래량뿐이다.

**한계 — 이 값은 '오늘의' 발행주식수다.** 자사주 매입·증자로 해마다 조금씩
달라지지만 대형주는 연 1~3% 수준이라, 10년에 걸쳐 **등수**를 가르는 데는
값(주가)의 움직임이 압도적이다. 그래서 시총 = 그날 종가 × 오늘 주식수로 잰다.
이렇게 하면 NVDA가 2016년에는 아래 칸, 2024년에는 빅10으로 **올라가는 것**이
그대로 잡힌다. '오늘 빅10인 종목은 10년 내내 빅10'으로 두는 것보다 훨씬 낫다.

쓰는 법:  python research/us_shares.py
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "_data" / "us_shares.csv"


def load() -> pd.Series:
    """티커 → 발행주식수. 없으면 받아서 저장한다."""
    if OUT.exists():
        table = pd.read_csv(OUT)
        return table.set_index("ticker")["shares"].astype("float64")
    return fetch()


def fetch() -> pd.Series:
    import yfinance as yf

    import jarvis3_data as j3

    tickers = sorted(set(j3.US_LARGE_CAP_UNIVERSE))
    print(f"{len(tickers)}종목의 발행주식수를 받는다...", flush=True)
    rows: dict[str, float] = {}
    batch = yf.Tickers(" ".join(tickers))
    for ticker in tickers:
        try:
            info = batch.tickers[ticker].fast_info
            shares = info.get("shares")
            cap = info.get("marketCap")
            price = info.get("lastPrice")
            if not shares and cap and price:
                shares = cap / price
            if shares:
                rows[ticker] = float(shares)
        except Exception as error:  # 한두 종목 실패해도 계속 간다
            print(f"  {ticker} 실패: {error}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": list(rows), "shares": list(rows.values())}).to_csv(
        OUT, index=False)
    print(f"{len(rows)}종목 저장 → {OUT}")
    return pd.Series(rows, dtype="float64")


if __name__ == "__main__":
    series = load()
    print(series.sort_values(ascending=False).head(10))
