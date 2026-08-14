"""급락 후 반등 — **나스닥이 문턱에 닿은 날**을 기준으로 테마가 얼마나 듣는지 잰다.

2026-08-14. 상하님 지시로 두 번 고쳐 짰다.

## 기준을 어떻게 잡나 — 상하님 말씀 그대로

> "이 테마 설명서에 보면 −12% 기준, 또 −몇 % 기준을 적용해서 각마다 난 저점으로
> 인식하겠다는 것이야. 처음 −12%에 각 테마 종목에 30% 내지 50% 참여하고,
> 또 −24%때 또 나머지 참여하겠다는 것이야. 물론 나스닥 종합주가 빠진 기준이야."

그러니 사는 날은 **나스닥이 고점 대비 −12%(그리고 −18%·−24%)에 처음 닿은 날**이다.
지나고 나서 찾는 저점이 아니다 — **그날 바로 알 수 있는 자리**다.
어느 문턱에서 얼마를 살지는 **상하님이 정하신다.** 이 코드는 그 자리에서
**어느 테마를 고를 것인가**만 잰다.

`docs/US_METHOD_TABLES.md`의 나눠 사기(−12%에 1/3 · −18%에 1/3 · −24%에 1/3)와
같은 자리다. 10년에 −12%는 7번, −18%는 4번, −24%는 2번 왔다.

## 앞서 두 번 틀린 것 (같은 실수 반복 금지)

  ① 2026-08-14 오전 — "나스닥이 −6% 아래인 날 **전부**"로 34,701자리를 쟀다.
     그 안에는 아직 더 떨어지는 중인 날이 대부분이라 반등 자리가 아니었다.
  ② 2026-08-14 낮 — 하락 구간의 **최저일(저점)**을 기준으로 잡았다. 저점은
     사후에만 아는 자리라 실전과 다르다. 상하님이 바로잡아 주셨다.

## 무엇을 재나

  ① **테마가 설명하는 몫** — 그 자리에서 종목 수익률이 흩어진 정도 중 테마 평균이
     설명하는 비율. "테마가 어느 정도 효과 있나"의 직접 답이다.
     **제비뽑기와 나란히 본다** — 무리가 많으면 아무렇게나 나눠도 저절로 커진다.
  ② **어떤 테마 잣대가 맞히나** — 그날 테마 값으로 순위를 매기고, 실제 그 뒤
     테마별 평균 수익률 순위와 얼마나 맞는지. 사건이 몇 번뿐이라
     **몇 번 중 몇 번 맞혔나**로 적는다.
  ③ **어떤 상황에 듣는지** — 문턱(−12 / −18 / −24)마다 따로 적는다.

지수는 **나스닥 종합(IXIC)**을 쓴다(상하님 말씀). QQQ도 같이 재서 나란히 놓는다 —
앱과 표 2는 QQQ로 만들어져 있어 견줄 필요가 있다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_bottom.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

STEPS = (-12.0, -18.0, -24.0)      # 상하님이 나눠 사시는 문턱
STOCK_BAND = (-50.0, -20.0)        # 그날 이만큼 빠진 종목을 산다(표 2의 매수 자리)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3                    # 한 자리에서 이만큼 걸려야 그 테마를 센다
FAKE_DRAWS = 200


def _explained(values: np.ndarray, groups: np.ndarray) -> float:
    """무리 평균이 설명하는 흩어짐의 몫(%). 흔히 말하는 eta 제곱이다.

    **무리가 많으면 아무렇게나 나눠도 저절로 커진다.** 늘 제비뽑기와 나란히 본다.
    """
    frame = pd.DataFrame({"r": values, "g": groups})
    total = frame["r"].var(ddof=0)
    if not total > 0:
        return float("nan")
    gap = frame.groupby("g")["r"].mean().sub(frame["r"].mean()).pow(2)
    size = frame.groupby("g")["r"].size()
    return float((gap * size).sum() / len(frame) / total * 100.0)


def touch_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """고점 대비 `step`%에 **처음 닿은 날**. 한 하락 사건에 한 번만 센다."""
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    hit = (drop <= step).to_numpy()
    days, armed = [], True
    for i, flag in enumerate(hit):
        if flag and armed:
            days.append(index_close.index[i])
            armed = False
        elif not flag and drop.iloc[i] > -1.0:
            armed = True          # 고점을 거의 되찾으면 다음 사건으로 친다
    return days


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
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > sma20).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)

    print("시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)
    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    for name, members in themes.items():
        total = cap[members].sum(axis=1, min_count=2)
        value = total / total.rolling(252, min_periods=200).max() * 100.0
        for stock in members:
            prox[stock] = value if prox[stock].isna().all() \
                else np.fmax(prox[stock], value)

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}
    at = {d: i for i, d in enumerate(dates)}

    for index_name, series in (("나스닥 종합(IXIC)", ixic), ("나스닥100(QQQ)", qqq)):
        print(f"\n\n{'='*78}\n{index_name} 기준\n{'='*78}")
        for step in STEPS:
            days = [d for d in touch_days(series, step) if d in at]
            print(f"\n── 고점 대비 {step:.0f}%에 처음 닿은 날 — 10년에 {len(days)}번 ──")
            if not days:
                continue
            head = "닿은 날        후보  " + "  ".join(
                f"{l}(진짜/제비)".rjust(18) for _h, l in HOLDS)
            print(head); print("─" * len(head))
            keep = {label: [] for _h, label in HOLDS}
            for day in days:
                idx = at[day]
                line, count = [], 0
                for hold, label in HOLDS:
                    fh, ret = from_high.iloc[idx], rets[hold].iloc[idx]
                    vals, groups = [], []
                    for stock in names:
                        v, g = fh.get(stock), ret.get(stock)
                        if pd.isna(v) or pd.isna(g) or not belongs.get(stock):
                            continue
                        if not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                            continue
                        vals.append(g); groups.append(belongs[stock][0])
                    if len(vals) < 20:
                        line.append("—".rjust(18)); continue
                    frame = pd.DataFrame({"r": vals, "g": groups})
                    frame = frame[frame.groupby("g")["r"].transform("size") >= MIN_MEMBERS]
                    if frame["g"].nunique() < 4:
                        line.append("—".rjust(18)); continue
                    real = _explained(frame["r"].to_numpy(), frame["g"].to_numpy())
                    rng = np.random.default_rng(20260814)
                    fake = float(np.median([
                        _explained(frame["r"].to_numpy(),
                                   rng.permutation(frame["g"].to_numpy()))
                        for _ in range(FAKE_DRAWS)]))
                    count = len(frame)
                    keep[label].append((real, fake))
                    line.append(f"{real:5.1f}% / {fake:4.1f}%".rjust(18))
                print(f"{day.date()}  {count:4d}  " + "  ".join(line))
            print("가운데값        " + "  ".join(
                (f"{np.median([r for r, _f in keep[l]]):5.1f}% / "
                 f"{np.median([f for _r, f in keep[l]]):4.1f}%").rjust(18)
                if keep[l] else "—".rjust(18) for _h, l in HOLDS))

            # ── 어떤 잣대가 그 자리의 테마 순위를 맞혔나 ────────────────
            gauges = {"테마가 덜 빠졌나": from_high, "테마 주봉 오름세": aligned,
                      "테마 20일선 위": above20, "테마 근접도(붙음)": prox}
            print()
            for gauge_name, table in gauges.items():
                cells = []
                for hold, _label in HOLDS:
                    plus = tried = 0
                    corrs = []
                    for day in days:
                        idx = at[day]
                        fh, ret, gau = from_high.iloc[idx], rets[hold].iloc[idx], table.iloc[idx]
                        rows = []
                        for stock in names:
                            v = fh.get(stock)
                            if pd.isna(v) or not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                                continue
                            if pd.isna(ret.get(stock)) or pd.isna(gau.get(stock)) \
                                    or not belongs.get(stock):
                                continue
                            rows.append((belongs[stock][0], gau.get(stock), ret.get(stock)))
                        if len(rows) < 20:
                            continue
                        frame = pd.DataFrame(rows, columns=["theme", "gauge", "ret"])
                        board = frame.groupby("theme").agg(
                            gauge=("gauge", "mean"), ret=("ret", "mean"), n=("ret", "size"))
                        board = board[board["n"] >= MIN_MEMBERS]
                        if len(board) < 4:
                            continue
                        corr = board["gauge"].rank().corr(board["ret"].rank())
                        if pd.isna(corr):
                            continue
                        tried += 1
                        plus += 1 if corr > 0 else 0
                        corrs.append(corr)
                    cells.append((f"{plus}/{tried} ({np.mean(corrs):+.2f})" if tried
                                  else "—").rjust(18))
                print("   " + gauge_name.ljust(18) + "  ".join(cells))

    print("\n\n괄호 안은 순위상관 평균. +면 그 잣대가 높은 테마가 더 올랐다는 뜻이다.")
    print("진짜/제비 — 제비뽑기로 아무렇게나 묶어도 나오는 몫과 나란히 본 것이다.")
    print("**사건이 몇 번뿐이다. 숫자 하나로 배점을 정하면 안 된다.**")


if __name__ == "__main__":
    main()
