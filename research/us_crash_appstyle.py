"""급락 반등 배점 — **앱이 실제로 쓰는 방식 그대로** 잰다 (2026-08-14).

## 왜 또 짜나 — 앞 측정이 앱과 다른 값을 재고 있었다

2026-08-14에 급락 자리를 재면서 테마 평균을 **후보 종목(−20~−50% 빠진 것)만으로**
냈다. 그랬더니 "많이 빠진 테마가 좋다"가 나왔다.

그런데 **앱은 그렇게 안 한다.** `jarvis3_data._attach_theme_rank`는 테마 등수를
**명부 200종목 전체**로 매긴다(그 함수 설명에 "등수는 명부 전체로 매긴다 — 표에
걸린 종목만으로 매기면 그날 몇 종목이 걸렸느냐에 따라 등수가 출렁인다"고 적혀 있다).

같은 날 같은 테마라도 두 값이 다르다.
  · 후보만 — 이미 20~50% 빠진 종목들의 평균 낙폭
  · 명부 전체 — 안 빠진 종목까지 포함한 평균 낙폭

**앱이 쓰는 것은 명부 전체다.** 그러니 배점도 명부 전체로 재야 한다. 안 그러면
배점을 거꾸로 넣게 된다.

## 무엇을 재나

자리는 나스닥(종합·QQQ)이 **−12%·−18%·−24%에 처음 닿은 날**과 **저점 다음 날**.
테마 잣대는 전부 **명부 전체**로 낸다. 사는 것은 그 자리에서 −20~−50% 빠진 종목이다.

  ① 테마가 **덜** 빠졌나        — 지금 40점
  ② 테마 주봉 오름세(Minervini) — 지금 30점
  ③ 테마 20일선 위              — 지금 20점
  ④ **테마 30주선 위**(Weinstein) — 새 후보. 급락 중 6개월에서 유일하게 통과했다
  ⑤ 테마가 **많이** 빠졌나       — ①의 반대
  ⑥ **지금 급락 배점 그대로**(①40 + ②30 + ③20)
  ⑦ **③+④**(20일선 + 30주선)
  ⑧ **①+④**(덜 빠짐 + 30주선)

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_appstyle.py
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
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    days, armed = [], True
    for day, value in drop.items():
        if value <= step and armed:
            days.append(day); armed = False
        elif value > -1.0:
            armed = True
    return days


def turn_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
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
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    above150 = (close > sma150).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}

    # **명부 전체**로 낸 테마 값 — 앱의 _attach_theme_rank와 같은 방식이다.
    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    tb = {"drop": by_theme(from_high), "aligned": by_theme(aligned),
          "above20": by_theme(above20), "above150": by_theme(above150)}

    GAUGES = (
        ("① 테마가 덜 빠졌나 (지금 40점)", lambda b: b["drop"].rank()),
        ("② 테마 주봉 오름세 (지금 30점)", lambda b: b["aligned"].rank()),
        ("③ 테마 20일선 위 (지금 20점)", lambda b: b["above20"].rank()),
        ("④ 테마 30주선 위 (새 후보)", lambda b: b["above150"].rank()),
        ("⑤ 테마가 많이 빠졌나 (①의 반대)", lambda b: (-b["drop"]).rank()),
        ("⑥ 지금 급락 배점 그대로", lambda b: (b["drop"].rank() * 40
                                        + b["aligned"].rank() * 30
                                        + b["above20"].rank() * 20)),
        ("⑦ 20일선 + 30주선", lambda b: b["above20"].rank() + b["above150"].rank()),
        ("⑧ 덜 빠짐 + 30주선", lambda b: b["drop"].rank() + b["above150"].rank()),
        # 제안하려는 배점 그대로 — 30주선 40점 · 20일선 20점
        ("⑨ 30주선40 + 20일선20 (제안)",
         lambda b: b["above150"].rank() * 40 + b["above20"].rank() * 20),
    )

    at = {d: i for i, d in enumerate(dates)}

    def theme_return(day, hold):
        """그날 −20~−50% 빠진 종목으로 만든 테마별 실제 수익률."""
        idx = at[day]
        fh, ret = from_high.iloc[idx], rets[hold].iloc[idx]
        rows = []
        for stock in names:
            v = fh.get(stock)
            if pd.isna(v) or not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                continue
            if pd.isna(ret.get(stock)) or not belongs.get(stock):
                continue
            rows.append((belongs[stock][0], ret.get(stock)))
        if len(rows) < 20:
            return None
        frame = pd.DataFrame(rows, columns=["theme", "ret"])
        board = frame.groupby("theme").agg(ret=("ret", "mean"), n=("ret", "size"))
        board = board[board["n"] >= MIN_MEMBERS]
        return board["ret"] if len(board) >= 4 else None

    for anchor_name, finder in (("① 문턱에 닿은 날", touch_days),
                                ("② 저점 다음 날 (급락 후 반등 자리)", turn_days)):
        total = {name: {label: [0, 0, []] for _h, label in HOLDS} for name, _f in GAUGES}
        for index_name, series in (("나스닥 종합(IXIC)", ixic), ("나스닥100(QQQ)", qqq)):
            for step in STEPS:
                days = [d for d in finder(series, step) if d in at]
                for gauge_name, make in GAUGES:
                    for hold, label in HOLDS:
                        for day in days:
                            actual = theme_return(day, hold)
                            if actual is None:
                                continue
                            values = {k: v.loc[day] for k, v in tb.items()}
                            gauge = make(values).reindex(actual.index).dropna()
                            common = actual.reindex(gauge.index)
                            if len(gauge) < 4:
                                continue
                            corr = gauge.rank().corr(common.rank())
                            if pd.isna(corr):
                                continue
                            total[gauge_name][label][0] += 1 if corr > 0 else 0
                            total[gauge_name][label][1] += 1
                            total[gauge_name][label][2].append(corr)
        print("\n\n" + "=" * 92 + "\n" + anchor_name
              + " — **명부 전체로 낸 테마 값**(앱과 같은 방식)\n" + "=" * 92)
        head = "잣대".ljust(30) + "  ".join(l.rjust(17) for _h, l in HOLDS) + "     합계"
        print(head); print("─" * len(head))
        ranked = []
        for gauge_name, _make in GAUGES:
            cells, hit, tot = [], 0, 0
            for _h, label in HOLDS:
                plus, tried, corrs = total[gauge_name][label]
                hit += plus; tot += tried
                cells.append((f"{plus}/{tried} ({np.mean(corrs):+.2f})"
                              if tried else "—").rjust(17))
            share = hit / tot * 100 if tot else 0
            ranked.append((share, gauge_name))
            print(gauge_name.ljust(30) + "  ".join(cells) + f"   {hit}/{tot} {share:5.1f}%")
        print("차례 — " + " · ".join(f"{t.split()[0]} {v:.0f}%"
                                    for v, t in sorted(ranked, reverse=True)))
    print("\n**사건이 몇 번뿐이다. 숫자 하나로 배점을 정하면 안 된다.**")


if __name__ == "__main__":
    main()
