"""코스피를 '언제' 들고 있을지 — 규칙을 30년 내내 그대로 따랐으면 얼마였나 (2026-09-30, 자비스10).

사건 몇 번으로 만든 표(kospi_dip_table_20260930.py)는 한 줄에 5~25번뿐이라 흔들린다.
여기서는 규칙 하나를 매일(또는 매달) 기계적으로 따랐을 때의 **돈의 길**을 통째로 잰다.

자료
  A. 코스피 지수 1996-12 ~ 2026-09 (야후 ^KS11 · 배당 빠짐)
  B. KODEX 200 (069500.KS) 수정가 2007-01 ~ 2026-09 — **배당이 들어간** 코스피200 상품. A 가 맞는지 대조용
규칙 (판단은 그날 종가로, 사고팔기는 **다음 날** — 앞을 훔쳐보지 않는다 · 한 번 바꿀 때 0.1% 비용)
  1. 그냥 들기
  2. 200일선 — 종가가 200일 평균 위면 들고, 아래면 현금 (매일 봄)
  3. 200일선 — 달 마지막 날만 본다
  4. 200일선 ±3% — 3% 넘게 아래로 가야 팔고, 3% 넘게 위로 와야 산다 (들락날락 줄이기)
  5. 12개월 상승률 — 1년 전보다 높으면 들고, 낮으면 현금 (달 마지막 날)
현금 이자는 0 과 연 3% 두 가지로 본다.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
KOSPI = ROOT / "_data" / "kospi_yahoo_19961211_20260930.csv"
KODEX = ROOT / "_data" / "kodex200_069500.csv"
COST = 0.001


def load_close(path: pathlib.Path, col: str) -> pd.Series:
    y = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    y.columns = [c[0] for c in y.columns]
    s = y[col].dropna()
    return s[s > 0]


def signals(c: pd.Series) -> dict[str, pd.Series]:
    sma = c.rolling(200).mean()
    month_end = c.index.to_series().groupby(c.index.to_period("M")).transform("max") == c.index.to_series()
    daily = (c > sma).astype(float).where(sma.notna())
    monthly = daily.where(month_end).ffill()
    band = pd.Series(np.nan, index=c.index)
    state = np.nan
    ratio = (c / sma).to_numpy()
    out = []
    for r in ratio:
        if np.isnan(r):
            out.append(np.nan)
            continue
        if np.isnan(state):
            state = 1.0 if r > 1 else 0.0
        elif state == 1.0 and r < 0.97:
            state = 0.0
        elif state == 0.0 and r > 1.03:
            state = 1.0
        out.append(state)
    band = pd.Series(out, index=c.index)
    mom = (c > c.shift(250)).astype(float).where(c.shift(250).notna())
    mom_m = mom.where(month_end).ffill()
    return {
        "그냥 들기": pd.Series(1.0, index=c.index).where(sma.notna()),
        "200일선 (매일)": daily,
        "200일선 (달마다)": monthly,
        "200일선 ±3%": band,
        "12개월 상승률 (달마다)": mom_m,
    }


def run(c: pd.Series, pos: pd.Series, rate: float) -> pd.Series:
    ret = c.pct_change().fillna(0)
    held = pos.shift(1).fillna(0)                      # 오늘 판단 → 다음 날부터 적용
    cash = (1 + rate) ** (1 / 250) - 1
    trade = held.diff().abs().fillna(0)
    daily = np.where(held > 0, ret, cash) - trade * COST
    first = pos.first_valid_index()
    return pd.Series(daily, index=c.index).loc[first:]


def stats(r: pd.Series) -> tuple[float, float]:
    eq = (1 + r).cumprod()
    yrs = len(r) / 250
    return (eq.iloc[-1] ** (1 / yrs) - 1) * 100, (eq / eq.cummax() - 1).min() * 100


def report(name: str, c: pd.Series, spans: list[tuple[str, str, str]]) -> None:
    sig = signals(c)
    print(f"\n=== {name} · {c.index[0].date()} ~ {c.index[-1].date()} ===")
    for rate in (0.0, 0.03):
        print(f"  현금 이자 연 {rate*100:.0f}%")
        for label, pos in sig.items():
            r = run(c, pos, rate)
            cagr, mdd = stats(r)
            held = pos.loc[r.index].mean() * 100
            switches = int(pos.loc[r.index].diff().abs().sum())
            parts = []
            for tag, a, b in spans:
                part = r.loc[a:b]
                if len(part) > 250:
                    parts.append(f"{tag} {stats(part)[0]:+5.1f}%")
            now = "들기" if pos.iloc[-1] == 1 else "현금"
            print(f"    {label:<16} 해마다 {cagr:+5.1f}% · 가장 크게 빠짐 {mdd:5.0f}% · 들고 있던 날 {held:3.0f}% · "
                  f"바꾼 횟수 {switches:>3} · [{' · '.join(parts)}] · 지금 {now}")


def main() -> None:
    kospi = load_close(KOSPI, "Close")
    report("코스피 지수 (배당 빠짐)", kospi,
           [("1997~2006", "1997", "2006"), ("2007~2016", "2007", "2016"), ("2017~2026", "2017", "2026")])
    if KODEX.exists():
        kodex = load_close(KODEX, "Adj Close")
        report("KODEX 200 (배당 들어감)", kodex,
               [("2008~2016", "2008", "2016"), ("2017~2026", "2017", "2026")])


if __name__ == "__main__":
    main()
