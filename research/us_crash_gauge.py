"""급락 반등 자리에서 **어느 테마를 고를 것인가** — 잣대를 하나씩, 그리고 합쳐서 잰다.

2026-08-14. 상하님 지시 — "그 상황에서, 즉 나스닥이 최저점을 찍고 반등하는 시점에
테마들의 기준을 보고 배점에 반영하는 것이야."

상하님 표 2(`docs/US_METHOD_TABLES.md`)는 **여러 번 검증한 것이라 그대로 베이스로
쓴다.** 여기서 다시 검증하지 않는다. 표 2가 정한 것은 이렇다.

    지수 QQQ · 나스닥 고점 대비 하락율 구간마다 매수 자리 · 종목은 20~50% 빠진 것

이 코드가 재는 것은 **그 자리에서 어느 테마를 고를 것인가** 하나뿐이다.

## 사는 날

나스닥이 고점 대비 **−12% · −18% · −24%에 처음 닿은 날**(한 하락 사건에 한 번)과,
**그 뒤 실제로 돌아선 날**(저점 다음 거래일) 둘 다 본다. 상하님은 문턱에서 나눠
사시고, 돌아선 날은 사후에만 알지만 '반등 시작 시점'이 어떤지 보려는 것이다.

## 재는 잣대

  A 테마가 **많이 빠졌나**   — 테마 평균 낙폭이 깊을수록 높은 점수
  B 테마가 **20일선 위인가** — 테마 종목 중 20일선 위 비율
  C **A + B 합**             — 둘을 각각 등수로 바꿔 더한다(같은 무게)

각 자리에서 테마를 그 잣대로 줄 세우고, **실제 그 뒤 테마별 평균 수익률 순위**와
얼마나 맞는지 본다. 사건이 몇 번뿐이라 **몇 번 중 몇 번 맞혔나**로 적는다.

시가총액을 안 만들므로 빠르다(근접도는 여기서 안 본다).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_gauge.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

STEPS = (-12.0, -18.0, -24.0)
STOCK_BAND = (-50.0, -20.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3


def touch_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """고점 대비 `step`%에 **처음 닿은 날**. 한 하락 사건에 한 번만."""
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    days, armed = [], True
    for day, value in drop.items():
        if value <= step and armed:
            days.append(day)
            armed = False
        elif value > -1.0:
            armed = True
    return days


def turn_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """그 하락 사건의 **최저일 다음 거래일** — 실제로 돌아선 자리."""
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    index = list(drop.index)
    out, start = [], None
    for i, value in enumerate(drop.to_numpy()):
        if value <= step and start is None:
            start = i
        elif start is not None and value > -1.0:
            seg = drop.iloc[start:i]
            pos = index.index(seg.idxmin())
            if pos + 1 < len(index):
                out.append(index[pos + 1])
            start = None
    if start is not None:
        seg = drop.iloc[start:]
        pos = index.index(seg.idxmin())
        if pos + 1 < len(index):
            out.append(index[pos + 1])
    return out


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][names], wide["high"][names]
    opens, qqq = wide["open"][names], wide["close"]["QQQ"].dropna()
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    # 20개 테마 실시간 순위가 쓰는 두 값(2026-08-14 상하님 — "그 배점도 같이 보겠다")
    rose5 = (close > close.shift(5)).astype(float)
    rose20 = (close > close.shift(20)).astype(float)
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}
    at = {d: i for i, d in enumerate(dates)}

    def board_at(idx: int, hold: int) -> pd.DataFrame | None:
        """그날 테마별로 (많이 빠짐 · 20일선 위 비율 · 실제 수익률)."""
        fh, ab, ret = from_high.iloc[idx], above20.iloc[idx], rets[hold].iloc[idx]
        r5, r20 = rose5.iloc[idx], rose20.iloc[idx]
        rows = []
        for stock in names:
            v = fh.get(stock)
            if pd.isna(v) or not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                continue
            if pd.isna(ret.get(stock)) or pd.isna(ab.get(stock)) or not belongs.get(stock):
                continue
            rows.append((belongs[stock][0], v, ab.get(stock),
                         r5.get(stock), r20.get(stock), ret.get(stock)))
        if len(rows) < 20:
            return None
        frame = pd.DataFrame(
            rows, columns=["theme", "drop", "above", "r5", "r20", "ret"]).dropna()
        board = frame.groupby("theme").agg(
            drop=("drop", "mean"), above=("above", "mean"),
            r5=("r5", "mean"), r20=("r20", "mean"),
            ret=("ret", "mean"), n=("ret", "size"))
        board = board[board["n"] >= MIN_MEMBERS]
        return board if len(board) >= 4 else None

    for anchor_name, finder in (("문턱에 처음 닿은 날", touch_days),
                                ("저점 다음 날(돌아선 자리)", turn_days)):
        for index_name, series in (("나스닥 종합(IXIC)", ixic), ("나스닥100(QQQ)", qqq)):
            print(f"\n{'='*76}\n{anchor_name} · {index_name}\n{'='*76}")
            for step in STEPS:
                days = [d for d in finder(series, step) if d in at]
                if not days:
                    continue
                print(f"\n── 고점 대비 {step:.0f}% — {len(days)}번 "
                      f"({', '.join(str(d.date()) for d in days)}) ──")
                head = "잣대".ljust(24) + "  ".join(l.rjust(16) for _h, l in HOLDS)
                print(head); print("─" * len(head))
                for gauge_name, key in (("A 많이 빠진 테마", "drop_rev"),
                                        ("B 20일선 위 테마", "above"),
                                        ("C 둘을 합침(A+B)", "both"),
                                        ("D 지금 테마 순위 점수", "theme_score")):
                    cells = []
                    for hold, _label in HOLDS:
                        plus = tried = 0
                        corrs = []
                        for day in days:
                            board = board_at(at[day], hold)
                            if board is None:
                                continue
                            if key == "drop_rev":
                                gauge = (-board["drop"]).rank()
                            elif key == "above":
                                gauge = board["above"].rank()
                            elif key == "both":
                                gauge = (-board["drop"]).rank() + board["above"].rank()
                            else:
                                # 20개 테마 실시간 순위가 쓰는 조건점수 그대로
                                # (20일선 위 40 · 5일 오름 30 · 20일 오름 20 · 덜 빠짐 10)
                                # jarvis3_data._scale은 값 하나짜리라 여기서는 같은
                                # 식을 벡터로 쓴다 — 잘라내는 방식까지 똑같다.
                                def _sc(series, low, high, points):
                                    return np.clip((series - low) / (high - low)
                                                   * points, 0.0, points)

                                gauge = (_sc(board["above"] * 100, 25, 85, 40.0)
                                         + _sc(board["r5"] * 100, 20, 80, 30.0)
                                         + _sc(board["r20"] * 100, 25, 85, 20.0)
                                         + _sc(board["drop"], -30.0, -2.0, 10.0))
                            corr = gauge.rank().corr(board["ret"].rank())
                            if pd.isna(corr):
                                continue
                            tried += 1
                            plus += 1 if corr > 0 else 0
                            corrs.append(corr)
                        cells.append((f"{plus}/{tried} ({np.mean(corrs):+.2f})"
                                      if tried else "—").rjust(16))
                    print(gauge_name.ljust(24) + "  ".join(cells))

    print("\n괄호 안은 순위상관 평균. +면 그 잣대가 높은 테마가 더 올랐다는 뜻이다.")
    print("**사건이 몇 번뿐이다. 숫자 하나로 배점을 정하면 안 된다.**")


if __name__ == "__main__":
    main()
