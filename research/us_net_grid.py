"""미국 **그물 자체**를 격자로 다시 잰다 (2026-08-07).

**왜 그물부터인가.** 지금 미국 상승장 그물은 84개 창 중 52개에서만 이겼고
가운데 +0.6p다. 사실상 아무 종목이나 산 것과 같다. 그 위에 배점을 얹는 것은
마이너스 위에 순위를 매기는 일이다. 한국에서 거래대금 500억 문턱을 찾았듯이
미국에도 그런 자리가 있는지 먼저 본다.

**비교 상대는 '그날 아무 종목이나'** — 여기서는 그물 자체를 재는 것이므로
그물 밖과 견줘야 한다(배점을 잴 때와 다르다. 그때는 그물 안끼리 견줬다).

쓰는 법:  python research/us_net_grid.py up     # 상승 그물
          python research/us_net_grid.py down   # 급락 후 반등 그물
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

WINDOWS = (2, 3, 4)
STEP_DAYS = 21
MIN_SIDE = 30
MIN_WINDOWS = 20
PASS_MARK = 65.0


def roll_vs_all(returns: pd.DataFrame, net: pd.DataFrame) -> dict:
    """그물에 걸린 것 vs 그날 명부 전체. 창 길이 셋으로 잰다."""
    inside = returns.where(net).to_numpy()
    everything = returns.to_numpy()
    active = net.to_numpy().any(axis=1)
    out = {}
    for years in WINDOWS:
        length = int(years * 252)
        wins, medians = [], []
        for start in range(0, len(returns) - length + 1, STEP_DAYS):
            stop = start + length
            a = inside[start:stop].ravel()
            a = a[~np.isnan(a)]
            if a.size < MIN_SIDE:
                continue
            b = everything[start:stop][active[start:stop]].ravel()
            b = b[~np.isnan(b)]
            if b.size < MIN_SIDE:
                continue
            wins.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
            medians.append(float(np.median(a) - np.median(b)))
        if len(wins) < MIN_WINDOWS:
            out[years] = None
            continue
        wins, medians = np.array(wins), np.array(medians)
        out[years] = {"n": wins.size, "win": float((wins > 0).mean() * 100),
                      "med": float((medians > 0).mean() * 100),
                      "mid": float(np.median(wins)), "worst": float(wins.min())}
    return out


def verdict(result: dict) -> str:
    usable = [item for item in result.values() if item]
    if len(usable) < len(WINDOWS):
        return "판정못함"
    if all(i["win"] >= PASS_MARK and i["med"] >= PASS_MARK for i in usable):
        return "○ 합격"
    return "△"


def line(name: str, count: int, result: dict) -> str:
    cells = []
    for years in WINDOWS:
        item = result[years]
        cells.append("     —      " if not item
                     else f"{item['win']:4.0f}/{item['med']:3.0f}%({item['n']:>3})")
    mid = result[WINDOWS[1]]
    tail = "" if not mid else f" 가운데{mid['mid']:+5.1f}p 최악{mid['worst']:+6.1f}p"
    return f"  {name:<30}{count:>7,}" + "".join(cells) + f" {verdict(result):<7}{tail}"


def setup():
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    dates = close.index
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    return {
        "wide": wide, "stocks": stocks, "qqq": qqq, "close": close, "high": high,
        "dates": dates,
        "days_since": order - order.where(is_new_high).ffill(),
        "from_peak": (close / peak - 1.0) * 100.0,
        "from_high": (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0,
        "qqq_drop": (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0,
        "qqq_ma200": qqq.rolling(200, min_periods=200).mean(),
        "j3": j3,
    }


def wide_flag(series: pd.Series, close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(np.repeat(series.to_numpy()[:, None], close.shape[1], axis=1),
                        index=close.index, columns=close.columns)


def header():
    print(f"창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 합격선 {PASS_MARK:.0f}% · "
          "비교 상대는 그날 명부 전체")
    print(f"  {'그물':<30}{'자리':>7}" + "".join(f"{y:>7}년     " for y in WINDOWS) + "\n")


def run_up() -> None:
    env = setup()
    close, wide = env["close"], env["wide"]
    returns_by_hold = {
        hold: (close.shift(-hold) / wide["open"][env["stocks"]].shift(-1) - 1.0) * 100.0
        for hold in (60, 120, 250)
    }
    markets = {
        "조건없음": pd.Series(True, index=env["dates"]),
        "200일선위": env["qqq"] > env["qqq_ma200"],
        "200일선위+고점-10%안": (env["qqq"] > env["qqq_ma200"]) & (env["qqq_drop"] > -10.0),
    }
    print("### 미국 상승 그물 격자 — 신고가 뒤 며칠 × 눌린 폭 × 보유 × 시장조건\n")
    header()
    rows = []
    for market_name, market in markets.items():
        flag = wide_flag(market, close)
        for wait_lo, wait_hi in ((1, 3), (1, 5), (1, 10), (3, 10)):
            for lo, hi in ((-6.0, -4.0), (-10.0, -4.0), (-15.0, -6.0), (-20.0, -10.0)):
                net = (flag & (env["days_since"] >= wait_lo) & (env["days_since"] <= wait_hi)
                       & (env["from_peak"] <= hi) & (env["from_peak"] >= lo))
                count = int(net.to_numpy().sum())
                if count < 300:
                    continue
                for hold, returns in returns_by_hold.items():
                    result = roll_vs_all(returns, net)
                    mid = result[WINDOWS[1]]
                    rows.append((mid["mid"] if mid else -99,
                                 f"{market_name[:9]}·{wait_lo}~{wait_hi}일·"
                                 f"{hi:.0f}~{lo:.0f}%·{hold}일", count, result))
    rows.sort(key=lambda item: -item[0])
    passed = [row for row in rows if verdict(row[3]) == "○ 합격"]
    print(f"쟀던 조합 {len(rows)}개 · 합격 {len(passed)}개\n")
    print("── 가장 나은 12개 " + "─" * 60)
    for _, name, count, result in rows[:12]:
        print(line(name, count, result))
    print("\n── 가장 나쁜 4개 " + "─" * 60)
    for _, name, count, result in rows[-4:]:
        print(line(name, count, result))


def run_down() -> None:
    env = setup()
    close, wide = env["close"], env["wide"]
    returns_by_hold = {
        hold: (close.shift(-hold) / wide["open"][env["stocks"]].shift(-1) - 1.0) * 100.0
        for hold in (20, 60, 120, 250)
    }
    print("### 미국 급락 후 반등 그물 격자 — 나스닥 문턱 × 신호방식 × 종목낙폭 × 보유\n")
    header()
    for band in ((-12.0, -6.0), (-20.0, -10.0), (-40.0, -15.0)):
        in_band = (env["qqq_drop"] <= band[1]) & (env["qqq_drop"] >= band[0])
        episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
        table = pd.DataFrame({"e": episode, "d": env["qqq_drop"]}).dropna()
        deepest = pd.Series(False, index=env["dates"])
        rebound = pd.Series(False, index=env["dates"])
        up_day = env["qqq"] > env["qqq"].shift(1)
        for _, group in table.groupby("e"):
            deepest.loc[group["d"].idxmin()] = True
            hits = group.index[up_day.reindex(group.index).fillna(False).to_numpy()]
            if len(hits):
                rebound.loc[hits[0]] = True
        for signal_name, signal in (("가장깊은날", deepest), ("첫반등일", rebound)):
            print(f"── 나스닥 {band[1]:.0f}~{band[0]:.0f}% · {signal_name} "
                  f"({int(signal.sum())}번) " + "─" * 40)
            flag = wide_flag(signal, close)
            for lo, hi in ((-30.0, -20.0), (-50.0, -30.0), (-60.0, -40.0), (-50.0, -20.0)):
                net = flag & (env["from_high"] <= hi) & (env["from_high"] >= lo)
                count = int(net.to_numpy().sum())
                if count < 300:
                    continue
                for hold, returns in returns_by_hold.items():
                    result = roll_vs_all(returns, net)
                    if verdict(result) == "○ 합격":
                        print(line(f"{hi:.0f}~{lo:.0f}%·{hold}일", count, result))
            print()


if __name__ == "__main__":
    {"up": run_up, "down": run_down}[sys.argv[1]]()
