"""Independent JARVIS 8 12-1 momentum screen; no network or app imports.

This reproduces the *selection* rule in research/independent_high_screen_20260922.py
for one completed US trading day. The historical study used a fixed survivor roster
and a 21-session signal schedule; a daily call here is an observation, not a new
backtest or an instruction to trade.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd


VERSION = "J8-MOMENTUM-12-1-20260923.1"
FIELDS = ("Open", "High", "Low", "Close", "Volume")
BENCHMARKS = frozenset(("QQQ", "SPY", "^IXIC"))


def _dated(frame: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Keep calendar rows intact so a missing trading session cannot disappear."""
    f = frame.copy()
    f.index = pd.to_datetime(f.index).tz_localize(None).normalize()
    f = f.loc[~f.index.duplicated(keep="last")].sort_index().loc[:day]
    return f.apply(pd.to_numeric, errors="coerce")


def select_momentum(
    frames: Mapping[str, pd.DataFrame],
    as_of: str | pd.Timestamp,
    roster: Iterable[str] | None = None,
) -> dict:
    """Select at most five stocks by 12-1 return, returning JSON-safe evidence.

    All stocks are reindexed to the *same* QQQ trading calendar. A bad or missing
    benchmark is an error, while a valid benchmark below its SMA200 is a genuine
    no-candidate market state. Future rows are discarded before any calculation.
    ``momentum`` is a decimal return; ``momentum_pct`` is its display percentage.
    """
    day = pd.Timestamp(as_of)
    if day.tzinfo is not None:
        day = day.tz_localize(None)
    day = day.normalize()
    if "QQQ" not in frames or frames["QQQ"] is None:
        raise ValueError("QQQ 기준 가격자료가 없습니다")
    if "Close" not in frames["QQQ"].columns:
        raise ValueError("QQQ 종가 열이 없습니다")

    qqq = _dated(frames["QQQ"], day)
    if day not in qqq.index or not np.isfinite(qqq.at[day, "Close"]) or qqq.at[day, "Close"] <= 0:
        raise ValueError(f"QQQ {day.date()} 완료 일봉이 없습니다")
    calendar = qqq.index[qqq["Close"].notna()]
    if len(calendar) < 253:
        raise ValueError("QQQ 거래일 이력이 253일 미만입니다")
    qqq_close = qqq["Close"].reindex(calendar).astype(float)
    if not np.isfinite(qqq_close.iloc[-200:].to_numpy()).all() or (qqq_close.iloc[-200:] <= 0).any():
        raise ValueError("QQQ 최근 200거래일 종가가 유효하지 않습니다")
    qqq_sma200 = float(qqq_close.iloc[-200:].mean())
    market_pass = bool(float(qqq_close.iloc[-1]) > qqq_sma200)

    symbols = sorted(set(roster if roster is not None else frames) - BENCHMARKS)
    eligible: list[dict] = []
    excluded: dict[str, str] = {}
    trailing_days = calendar[-253:]
    for ticker in symbols:
        raw = frames.get(ticker)
        if raw is None or not isinstance(raw, pd.DataFrame) or not set(FIELDS).issubset(raw.columns):
            excluded[ticker] = "시세 또는 필수 열 없음"
            continue
        f = _dated(raw, day).reindex(trailing_days)
        v = f.loc[:, FIELDS].to_numpy(dtype=float)
        if not np.isfinite(v).all():
            excluded[ticker] = "최근 253거래일 자료 부족 또는 결측"
            continue
        if (v <= 0).any():
            excluded[ticker] = "0 이하 OHLCV 값"
            continue

        close = f["Close"]
        epsilon = close.abs() * 1e-10
        if bool((((f["High"] + epsilon) < f["Open"]) |
                 ((f["High"] + epsilon) < close) |
                 ((f["Low"] - epsilon) > f["Open"]) |
                 ((f["Low"] - epsilon) > close)).any()):
            excluded[ticker] = "고가·저가와 시가·종가 모순"
            continue
        if bool(close.pct_change(fill_method=None).iloc[1:].abs().gt(.8).any()):
            excluded[ticker] = "최근 252개 일간 수익률 중 절댓값 80% 초과"
            continue

        momentum = float(close.iloc[-22] / close.iloc[-253] - 1)
        sma200 = float(close.iloc[-200:].mean())
        liquidity = float((close.iloc[-20:] * f["Volume"].iloc[-20:]).mean())
        if not np.isfinite((momentum, sma200, liquidity)).all():
            excluded[ticker] = "계산 결과 유효하지 않음"
            continue
        reasons = []
        if not market_pass:
            reasons.append("QQQ 200일 평균 이하")
        if not momentum > 0:
            reasons.append("12-1 상승률 0 이하")
        if not float(close.iloc[-1]) > sma200:
            reasons.append("종가가 200일 평균 이하")
        if not liquidity >= 20_000_000:
            reasons.append("거래 규모 대용치 2천만 미만")
        if reasons:
            excluded[ticker] = "; ".join(reasons)
            continue

        eligible.append({
            "ticker": ticker,
            "momentum": momentum,
            "momentum_pct": momentum * 100,
            "c_252": float(close.iloc[-253]),
            "c_21": float(close.iloc[-22]),
            "date_252": trailing_days[0].date().isoformat(),
            "date_21": trailing_days[-22].date().isoformat(),
            "price": float(close.iloc[-1]),
            "turnover_proxy": liquidity,
            "recent_month_pct": float((close.iloc[-1] / close.iloc[-22] - 1) * 100),
            "start_date": trailing_days[0].date().isoformat(),
            "start_close": float(close.iloc[-253]),
            "end_date": trailing_days[-22].date().isoformat(),
            "end_close": float(close.iloc[-22]),
            "current_close": float(close.iloc[-1]),
            "sma200": sma200,
            "liquidity_proxy": liquidity,
        })
    eligible.sort(key=lambda row: (-row["momentum"], row["ticker"]))
    result = {
        "ok": True,
        "strategy_id": "J8_MOMENTUM_12_1",
        "version": VERSION,
        "as_of": day.date().isoformat(),
        "market_ok": market_pass,
        "qqq_close": float(qqq_close.iloc[-1]),
        "qqq_sma200": qqq_sma200,
        "market": {"ticker": "QQQ", "close": float(qqq_close.iloc[-1]),
                   "sma200": qqq_sma200, "pass": market_pass},
        "total": len(symbols),
        "eligible_count": len(eligible),
        "rows": eligible,
        "top5": eligible[:5],
        "eligible": eligible,
        "selected": eligible[:5],
        "excluded": excluded,
    }
    return result


def select(
    frames: Mapping[str, pd.DataFrame],
    as_of: str | pd.Timestamp,
    tickers: Iterable[str] | None = None,
) -> dict:
    """Stable app-facing name; ``tickers`` is a roster, not an eligibility override."""
    return select_momentum(frames, as_of, tickers)
