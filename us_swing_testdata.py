# -*- coding: utf-8 -*-
"""US_SWING_V1(상승장 신고가 눌림매수) 시험용 합성 일봉 (2026-08-20).

**시험에서만 쓴다. 화면과 계산은 이 파일을 부르지 않는다.**

왜 따로 두나 — 새 그물이 여섯 겹이 됐다(나스닥 시장 Gate · RS60 · RS120 ·
종가 52주 신고가 · 신고가 뒤 1~3거래일 · 종가 눌림 3~10%). 이걸 다 만족하는
가짜 일봉은 260줄로는 못 만든다(신고가에만 직전 252줄이 필요하다). 그리고
`test_jarvis3_data`와 `test_jarvis3_page`가 **같은 자료**를 봐야 표 시험과
계산 시험이 서로 다른 것을 굳히지 않는다.
"""

from __future__ import annotations

import pandas as pd


def ohlcv(close, index, volume=100.0):
    values = [float(value) for value in close]
    volumes = (list(volume) if isinstance(volume, (list, tuple))
               else [float(volume)] * len(values))
    return pd.DataFrame(
        {"Open": values, "High": [value * 1.01 for value in values],
         "Low": [value * 0.99 for value in values], "Close": values,
         "Volume": volumes},
        index=index,
    )


def market_frame(periods: int = 400, *, market_on: bool = True) -> pd.DataFrame:
    """나스닥 일봉 — 10%보다 깊은 조정을 끝내고 이전 최고 종가를 되찾은 모양."""
    index = pd.bdate_range("2024-01-02", periods=periods)
    close = [100.0] * periods
    close[210] = 89.0                                      # 이전 최고 대비 -11%
    for position in range(211, 241):
        close[position] = 89.0 + (position - 210) * (12.0 / 30.0)
    for position in range(241, periods):
        close[position] = 101.0 + (position - 240) * 0.01  # 이전 최고를 다시 넘었다
    if not market_on:
        # 되찾지 못한 채 눌려 있는 모양 — 새 후보를 막아야 하는 자리다.
        for position in range(241, periods):
            close[position] = 85.0
    return ohlcv(close, index)


def stock_frame(index, ret60: float, ret120: float, *,
                pullback: float = 7.0, rvol: float = 2.0) -> pd.DataFrame:
    """RS60·RS120과 신고가 뒤 눌림을 지정해 만드는 종목 일봉.

    끝에서 셋째 날이 52주 신고가(anchor)이고 마지막 날이 그 종가에서
    `pullback`% 내려온 자리다 — 즉 anchor 뒤 2거래일째다.
    """
    count = len(index)
    current = 100.0
    then60, then120 = current / (1.0 + ret60), current / (1.0 + ret120)
    close = [60.0] * count

    def fill(start, end, left, right):
        span = end - start
        for position in range(start, end + 1):
            ratio = 0.0 if span == 0 else (position - start) / span
            close[position] = left + (right - left) * ratio

    fill(0, count - 121, 60.0, then120)
    fill(count - 121, count - 61, then120, then60)
    fill(count - 61, count - 4, then60, 99.0)
    anchor = current / (1.0 - pullback / 100.0)
    close[-3] = anchor
    close[-2] = anchor * 0.98
    close[-1] = current
    volume = [100.0] * count
    volume[-3] = 100.0 * rvol
    return ohlcv(close, index, volume)


def fixture(*, market_on: bool = True, loner_first: bool = False, pullback: float = 7.0):
    """RS 횡단면 30종목 조건을 채운 합성 명부.

    테마에 든 30종목과 **어느 테마에도 없는 4종목**을 함께 넣는다. 테마가 없는
    종목도 목록에 남아야 한다는 규칙(2026-08-14 상하님 지시)을 여기서 재기
    때문이다. `loner_first=True`면 테마 없는 종목이 RS 1등이 된다.
    """
    import jarvis3_data as j3

    ixic = market_frame(market_on=market_on)
    index = ixic.index[-300:]
    theme_stocks = {ticker for theme in j3.US_THEMES for ticker in theme["stocks"]}
    members = [t for t in j3.US_LARGE_CAP_UNIVERSE if t in theme_stocks][:30]
    loners = [t for t in j3.US_LARGE_CAP_UNIVERSE if t not in theme_stocks][:4]
    tickers = ([loners[0]] + members + loners[1:]) if loner_first else members + loners
    frames = {
        ticker: stock_frame(index, .60 - position * .012, 1.00 - position * .022,
                            pullback=pullback)
        for position, ticker in enumerate(tickers)
    }
    return tickers, frames, ixic


def scan(**kwargs) -> dict:
    """화면이 실제로 받는 payload 그대로 만든다 (find_breakout_pullback_stocks)."""
    from unittest.mock import patch

    import jarvis3_data as j3

    _tickers, frames, ixic = fixture(**kwargs)
    payload = dict(frames)
    payload["^IXIC"] = ixic
    with patch.object(j3, "_download_cached",
                      return_value=(payload, {"fetched_at": "x"})):
        return j3.find_breakout_pullback_stocks()
