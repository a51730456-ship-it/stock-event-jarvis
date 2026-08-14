"""급락 반등 배점을 **확정하려고** 잣대를 전부 한자리에 놓고 견준다 (2026-08-14).

상하님 지시 — "상승장 신고가 눌림매수에 적용한 테마 배점도 적용이 되는지 검토하고,
종합적으로 돌려보고 배점을 확정하자."

## 무엇을 견주나

  A  테마가 **많이 빠졌나**      — 구성종목 평균 낙폭이 깊을수록 위
  A' 테마 **근접도가 낮은가**    — 합산 시총이 1년 최고에서 멀수록 위 (상승장 70점의 **반대**)
  A'' 테마 **근접도가 높은가**   — **상승장 배점 그대로**. 급락에도 통하나
  B  테마가 **20일선 위인가**    — 지금 급락 배점 20점 · 테마 순위 배점 40점
  C  **A + B**                  — 낙폭 과대 + 반등 시작
  C' **A' + B**                 — 근접도판으로 같은 생각
  D  **지금 20개 테마 순위 점수** — 20일선 40 · 5일 오름 30 · 20일 오름 20 · 덜 빠짐 10
  E  **지금 급락 배점**          — 덜 빠짐 40 · 주봉 오름세 30 · 20일선 20

A와 A'는 **다른 자다.** A는 종목마다 52주 고점 대비 낙폭을 평균낸 것이고,
A'는 테마 **합산 시총**이 그 합의 252일 최고에서 얼마나 내려왔나다. 시총이 큰
종목이 무리를 끌면 둘이 갈린다.

## 사는 날

나스닥이 고점 대비 **−12% · −18% · −24%에 처음 닿은 날**(상하님이 나눠 사시는 자리).
지수는 **나스닥 종합(IXIC)**과 QQQ 둘 다. 표 2는 여러 번 검증하신 것이라 **베이스로
쓰고 다시 검증하지 않는다** — 이 코드는 **그 자리에서 어느 테마를 고를 것인가**만 잰다.

## 판정

자리마다 테마를 그 잣대로 줄 세우고 **실제 그 뒤 테마별 평균 수익률 순위**와 맞는지
본다. 사건이 몇 번뿐이라 **전부 합쳐 몇 번 중 몇 번 맞혔나**로 확정한다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_final.py
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
    """그 하락 사건의 **최저일 다음 거래일** — 이 갈래의 이름 그대로 '급락 **후 반등**' 자리다.

    2026-08-14 상하님 지적 — "급락장을 이야기하는 게 아니고 **급락 후 반등장**이야."
    문턱에 닿은 날은 아직 떨어지는 중이다. 돌아선 자리와 답이 다를 수 있으므로
    **둘 다** 재서 나란히 놓는다.
    """
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


def _sc(series, low, high, points):
    """jarvis3_data._scale과 같은 식(값 하나가 아니라 줄 전체에 쓴다)."""
    return np.clip((series - low) / (high - low) * points, 0.0, points)


def main() -> None:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
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
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)
    rose5 = (close > close.shift(5)).astype(float)
    rose20 = (close > close.shift(20)).astype(float)

    print("시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)
    prox_by_theme = {}
    for name, members in themes.items():
        total = cap[members].sum(axis=1, min_count=2)
        prox_by_theme[name] = total / total.rolling(252, min_periods=200).max() * 100.0
    prox_board = pd.DataFrame(prox_by_theme)

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}
    at = {d: i for i, d in enumerate(dates)}

    def board_at(idx: int, hold: int):
        fh, ab, al = from_high.iloc[idx], above20.iloc[idx], aligned.iloc[idx]
        r5, r20, ret = rose5.iloc[idx], rose20.iloc[idx], rets[hold].iloc[idx]
        rows = []
        for stock in names:
            v = fh.get(stock)
            if pd.isna(v) or not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                continue
            if pd.isna(ret.get(stock)) or not belongs.get(stock):
                continue
            rows.append((belongs[stock][0], v, ab.get(stock), al.get(stock),
                         r5.get(stock), r20.get(stock), ret.get(stock)))
        if len(rows) < 20:
            return None
        frame = pd.DataFrame(rows, columns=[
            "theme", "drop", "above", "aligned", "r5", "r20", "ret"]).dropna()
        board = frame.groupby("theme").agg(
            drop=("drop", "mean"), above=("above", "mean"),
            aligned=("aligned", "mean"), r5=("r5", "mean"), r20=("r20", "mean"),
            ret=("ret", "mean"), n=("ret", "size"))
        board = board[board["n"] >= MIN_MEMBERS]
        if len(board) < 4:
            return None
        board["prox"] = prox_board.iloc[idx].reindex(board.index)
        return board

    def gauge_of(board: pd.DataFrame, key: str):
        drop_rev = (-board["drop"]).rank()
        above = board["above"].rank()
        prox_hi = board["prox"].rank()
        prox_lo = (-board["prox"]).rank()
        if key == "A":
            return drop_rev
        if key == "A'":
            return prox_lo
        if key == "A''":
            return prox_hi
        if key == "B":
            return above
        if key == "C":
            return drop_rev + above
        if key == "C'":
            return prox_lo + above
        if key == "D":       # 지금 20개 테마 순위 점수
            return (_sc(board["above"] * 100, 25, 85, 40.0)
                    + _sc(board["r5"] * 100, 20, 80, 30.0)
                    + _sc(board["r20"] * 100, 25, 85, 20.0)
                    + _sc(board["drop"], -30.0, -2.0, 10.0))
        # E — 지금 급락 배점(덜 빠짐 40 · 주봉 30 · 20일선 20). 앱은 등수로 주지만
        # 여기서는 방향만 보면 되므로 값을 그대로 등수로 바꿔 무게만 준다.
        return (board["drop"].rank() * 40.0 + board["aligned"].rank() * 30.0
                + board["above"].rank() * 20.0)

    GAUGES = (
        ("A  많이 빠진 테마", "A"),
        ("A' 근접도 낮은 테마", "A'"),
        ("A''근접도 높은 테마 (상승장 그대로)", "A''"),
        ("B  20일선 위 테마", "B"),
        ("C  A + B", "C"),
        ("C' A' + B", "C'"),
        ("D  지금 테마 순위 점수", "D"),
        ("E  지금 급락 배점", "E"),
    )

    # **두 자리를 다 잰다**(2026-08-14 상하님 지적 — "급락장을 이야기하는 게 아니고
    # 급락 후 반등장이야"). 문턱에 닿은 날은 아직 떨어지는 중이고, 저점 다음 날이
    # 이 갈래 이름 그대로 '급락 후 반등' 자리다. 답이 다를 수 있어 나란히 놓는다.
    anchors = (("① 문턱에 닿은 날 — 아직 떨어지는 중", touch_days),
               ("② 저점 다음 날 — 급락 후 반등 자리", turn_days))
    summary = {}
    for anchor_name, finder in anchors:
        print("\n\n" + "#" * 92 + "\n" + anchor_name + "\n" + "#" * 92)
        total = {key: {label: [0, 0, []] for _h, label in HOLDS} for _n, key in GAUGES}
        summary[anchor_name] = total
        for index_name, series in (("나스닥 종합(IXIC)", ixic), ("나스닥100(QQQ)", qqq)):
            for step in STEPS:
                days = [d for d in finder(series, step) if d in at]
                if not days:
                    continue
                print(f"\n── {index_name} · {step:.0f}% — {len(days)}번 "
                      f"({', '.join(str(d.date()) for d in days)}) ──")
                head = "잣대".ljust(36) + "  ".join(l.rjust(15) for _h, l in HOLDS)
                print(head); print("─" * len(head))
                for title, key in GAUGES:
                    cells = []
                    for hold, label in HOLDS:
                        plus = tried = 0
                        corrs = []
                        for day in days:
                            board = board_at(at[day], hold)
                            if board is None:
                                continue
                            gauge = gauge_of(board, key)
                            corr = gauge.rank().corr(board["ret"].rank())
                            if pd.isna(corr):
                                continue
                            tried += 1
                            plus += 1 if corr > 0 else 0
                            corrs.append(corr)
                        if tried:
                            total[key][label][0] += plus
                            total[key][label][1] += tried
                            total[key][label][2].extend(corrs)
                        cells.append((f"{plus}/{tried} ({np.mean(corrs):+.2f})"
                                      if tried else "—").rjust(15))
                    print(title.ljust(36) + "  ".join(cells))

    for anchor_name, total in summary.items():
        print("\n\n" + "=" * 92 + "\n전부 합친 것 — " + anchor_name + "\n" + "=" * 92)
        head = "잣대".ljust(36) + "  ".join(l.rjust(17) for _h, l in HOLDS) + "     합계"
        print(head); print("─" * len(head))
        ranked = []
        for title, key in GAUGES:
            cells, hit, tot = [], 0, 0
            for _h, label in HOLDS:
                plus, tried, corrs = total[key][label]
                hit += plus; tot += tried
                cells.append((f"{plus}/{tried} ({np.mean(corrs):+.2f})"
                              if tried else "—").rjust(17))
            share = hit / tot * 100 if tot else 0
            ranked.append((share, title))
            print(title.ljust(36) + "  ".join(cells) + f"   {hit}/{tot} {share:5.1f}%")
        print("차례 — " + " · ".join(f"{t.split()[0]} {v:.0f}%"
                                    for v, t in sorted(ranked, reverse=True)))
    print("\n**사건이 몇 번뿐이다. 숫자 하나로 배점을 정하면 안 된다.**")


if __name__ == "__main__":
    main()
