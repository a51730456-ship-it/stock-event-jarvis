"""급락 — **구간을 바꾼 것**과 **최저일만 산 것** 중 무엇이 값을 했나 (2026-08-12).

왜 필요한가. 앱은 상하님 표 2와 두 군데가 다르다.
  ① 나스닥 구간   −6~−12%  →  −10~−20%
  ② 사는 날       그 구간에 있는 **아무 날**  →  그 구간의 **최저일 하나**

앞선 측정에서 둘을 한꺼번에 바꿔 놓고 "앱이 낫다"고 했다. 잘못된 비교다.
어느 쪽이 값을 했는지 갈라야 설명서를 고칠지 앱을 고칠지 정할 수 있다.

구간 다섯 × 사는 날 두 가지 × 종목 낙폭 두 칸을 다 잰다.

쓰는 법:  python research/us_crash_timing.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = (60, 120, 250)
NAMES = {60: "3개월", 120: "6개월", 250: "1년"}


def main() -> None:
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens = wide["open"][stocks]
    dates = close.index

    rets = {h: (close.shift(-h) / opens.shift(-1) - 1.0) * 100.0 for h in HOLDS}
    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    valid = close.notna() & high52.notna()

    def spread(flag):
        return pd.DataFrame(np.repeat(flag.to_numpy()[:, None], close.shape[1], axis=1),
                            index=dates, columns=close.columns)

    def cells(net):
        out = []
        for hold in HOLDS:
            values = rets[hold].where(net).stack().dropna()
            out.append((len(values), (values > 0).mean() * 100 if len(values) else np.nan,
                        values.median() if len(values) else np.nan))
        return out

    def row(label, count_text, net):
        parts = ""
        for n, win, mid in cells(net):
            parts += "    자리없음    " if not n else f"{mid:>7.1f}% ({win:>4.1f}%)"
        print(f"  {label:<34}{count_text:>15}   {parts}")

    bands = ((-12.0, -6.0, "6~12%"), (-18.0, -12.0, "12~18%"), (-24.0, -18.0, "18~24%"),
             (-30.0, -24.0, "24~30%"), (-100.0, -30.0, "30% 아래"),
             (-20.0, -10.0, "10~20% (앱)"))

    print(f"\n{'=' * 108}\n### 급락 — 구간을 바꾼 것 vs 최저일만 산 것"
          f"\n### 명부 {len(stocks)}종목 · 2016-08~2026-08 10년\n{'=' * 108}")
    print(f"  {'':<34}{'':>15}   " + "".join(f"{NAMES[h]:<16}" for h in HOLDS))

    for lo, hi, name in bands:
        inside = ((qqq_drop <= hi) & (qqq_drop >= lo)).fillna(False)
        episode = (inside & ~inside.shift(1, fill_value=False)).cumsum().where(inside)
        deepest = pd.Series(False, index=dates)
        for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
            deepest.loc[group["d"].idxmin()] = True
        events = int((inside & ~inside.shift(1, fill_value=False)).sum())
        print(f"\n  ── 나스닥 {name} · 구간 진입 {events}번 · 구간 안 {int(inside.sum())}일 ──")
        for when, flag in (("구간 안 아무 날", inside), ("**그 구간 최저일만**", deepest)):
            for s_lo, s_hi, s_name in ((-30.0, -20.0, "20~30%"), (-50.0, -30.0, "30~50%")):
                net = (spread(flag) & valid & (from_high <= s_hi)
                       & (from_high >= s_lo)).fillna(False)
                total = int(net.to_numpy().sum())
                row(f"{when} · 종목 {s_name}", f"{total:,}", net)

    print("\n  ── 견줄 것 ──")
    row("아무 날 20~50% 빠진 종목", "—",
        ((from_high <= -20) & (from_high >= -50) & valid).fillna(False))
    qqq_rets = {h: (qqq.shift(-h) / wide["open"]["QQQ"].shift(-1) - 1.0) * 100.0
                for h in HOLDS}
    parts = ""
    for h in HOLDS:
        values = qqq_rets[h].dropna()
        parts += f"{values.median():>7.1f}% ({(values > 0).mean() * 100:>4.1f}%)"
    print(f"  {'QQQ 아무 날':<34}{'—':>15}   {parts}")

    print("\n※ 칸 안은 '가운데 수익률 (승률)'. 사는 것은 신호 다음 거래일 시가.")


if __name__ == "__main__":
    main()
