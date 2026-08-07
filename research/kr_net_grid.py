"""한국 **그물 자체**를 격자로 다시 잰다 (2026-08-07).

미국에 한 것과 같은 방법이다 — 창 2·3·4년을 한 달씩 밀며, 창 셋 모두에서
승률과 수익률 둘 다 65%를 넘어야 합격.

**두 단계로 나눈 이유.** 한국 자료는 3,000일 × 2,272종목이라 미국(2,513×198)의
스무 배가 넘는다. 조합마다 창을 전부 훑으면 며칠 걸린다. 그래서
  1단계 — 날마다 '그물에 걸린 수·이긴 수'만 미리 세 두고 누적합으로 승률을 훑는다.
          같은 답이 나오면서 수백 배 빠르다.
  2단계 — 1단계를 통과한 조합만 수익률(가운데값)까지 제대로 잰다.

쓰는 법:  python research/kr_net_grid.py up
          python research/kr_net_grid.py down
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
from kr_measure import DAILY, load_wide  # noqa: E402

WINDOWS = (2, 3, 4)
STEP = 21
MIN_SIDE = 30
MIN_WINDOWS = 20
PASS = 65.0


def day_counts(returns: np.ndarray, net: np.ndarray, pool: np.ndarray):
    """날마다 '그물에 걸린 수·이긴 수'와 '울타리 전체 수·이긴 수'를 미리 센다."""
    ok = np.isfinite(returns)
    win = ok & (returns > 0)
    net_ok = net & ok
    return {
        "net_n": net_ok.sum(axis=1).astype(np.float64),
        "net_w": (net & win).sum(axis=1).astype(np.float64),
        "base_n": (pool & ok).sum(axis=1).astype(np.float64),
        "base_w": (pool & win).sum(axis=1).astype(np.float64),
        "active": net_ok.any(axis=1),
    }


def quick_win(counts: dict) -> dict:
    """누적합으로 창마다 승률 차이를 낸다. 기준선은 **신호가 난 날만** 센다."""
    active = counts["active"]
    base_n = counts["base_n"] * active
    base_w = counts["base_w"] * active
    cumulative = {key: np.concatenate([[0.0], np.cumsum(value)])
                  for key, value in (("net_n", counts["net_n"]), ("net_w", counts["net_w"]),
                                     ("base_n", base_n), ("base_w", base_w))}
    total = len(active)
    out = {}
    for years in WINDOWS:
        length = int(years * 252)
        edges = []
        for start in range(0, total - length + 1, STEP):
            stop = start + length
            net_n = cumulative["net_n"][stop] - cumulative["net_n"][start]
            base_n = cumulative["base_n"][stop] - cumulative["base_n"][start]
            if net_n < MIN_SIDE or base_n < MIN_SIDE:
                continue
            net_w = cumulative["net_w"][stop] - cumulative["net_w"][start]
            base_w = cumulative["base_w"][stop] - cumulative["base_w"][start]
            edges.append(net_w / net_n * 100 - base_w / base_n * 100)
        out[years] = np.array(edges) if len(edges) >= MIN_WINDOWS else None
    return out


def full_median(returns: np.ndarray, net: np.ndarray, pool: np.ndarray) -> dict:
    """1단계를 통과한 조합만 — 수익률 가운데값 차이를 창마다 제대로 잰다."""
    inside = np.where(net, returns, np.nan)
    outside = np.where(pool, returns, np.nan)
    active = (net & np.isfinite(returns)).any(axis=1)
    out = {}
    for years in WINDOWS:
        length = int(years * 252)
        edges = []
        for start in range(0, len(returns) - length + 1, STEP):
            stop = start + length
            a = inside[start:stop].ravel()
            a = a[~np.isnan(a)]
            if a.size < MIN_SIDE:
                continue
            b = outside[start:stop][active[start:stop]].ravel()
            b = b[~np.isnan(b)]
            if b.size < MIN_SIDE:
                continue
            edges.append(float(np.median(a) - np.median(b)))
        out[years] = np.array(edges) if len(edges) >= MIN_WINDOWS else None
    return out


def judge(win_edges: dict, median_edges: dict | None = None) -> bool:
    if any(value is None for value in win_edges.values()):
        return False
    if any((value > 0).mean() * 100 < PASS for value in win_edges.values()):
        return False
    if median_edges is None:
        return True
    if any(value is None for value in median_edges.values()):
        return False
    return all((value > 0).mean() * 100 >= PASS for value in median_edges.values())


def report(name: str, count: int, win_edges: dict, median_edges: dict) -> str:
    cells = []
    for years in WINDOWS:
        a, b = win_edges[years], median_edges[years]
        cells.append(f"{(a > 0).mean() * 100:4.0f}/{(b > 0).mean() * 100:3.0f}%({a.size:>3})")
    mid = win_edges[WINDOWS[1]]
    return (f"  {name:<34}{count:>8,}" + "".join(cells)
            + f"  가운데{np.median(mid):+5.1f}p 최악{mid.min():+6.1f}p")


def build():
    wide = load_wide()
    close, high = wide["close"], wide["high"]
    dates = close.index
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    turnover = close * wide["volume"]
    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    return {
        "wide": wide, "close": close, "dates": dates,
        "days_since": (order - order.where(is_new_high).ffill()).to_numpy(),
        "from_peak": ((close / peak - 1.0) * 100.0).to_numpy(),
        "from_high": ((close / high.rolling(252, min_periods=60).max() - 1.0)
                      * 100.0).to_numpy(),
        "value": (turnover.rolling(50, min_periods=20).mean() / 1e8).to_numpy(),
        "kospi": kospi,
        "kospi_drop": (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0,
    }


def forward(env, hold: int) -> np.ndarray:
    return ((env["wide"]["close"].shift(-hold) / env["wide"]["open"].shift(-1) - 1.0)
            * 100.0).to_numpy()


def sweep(env, nets, holds, title):
    print(f"### {title}\n")
    print(f"창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 합격선 {PASS:.0f}% · "
          "비교 상대는 그날 같은 울타리 전체")
    print(f"  {'그물':<34}{'자리':>8}" + "".join(f"{y:>7}년    " for y in WINDOWS) + "\n")
    returns_cache = {hold: forward(env, hold) for hold in holds}
    tested = passed = 0
    rows = []
    for name, net, pool in nets:
        count = int(net.sum())
        if count < 300:
            continue
        for hold in holds:
            returns = returns_cache[hold]
            tested += 1
            win_edges = quick_win(day_counts(returns, net, pool))
            if not judge(win_edges):
                continue
            median_edges = full_median(returns, net, pool)
            if not judge(win_edges, median_edges):
                continue
            passed += 1
            rows.append((float(np.median(win_edges[WINDOWS[1]])),
                         report(f"{name}·{hold}일", count, win_edges, median_edges)))
    rows.sort(key=lambda item: -item[0])
    print(f"쟀던 조합 {tested}개 · 합격 {passed}개\n")
    for _, text in rows[:20]:
        print(text)


def run_up():
    env = build()
    nets = []
    for floor_name, floor in (("문턱없음", 0), ("10억↑", 10), ("50억↑", 50), ("500억↑", 500)):
        pool = env["value"] >= floor
        for wait_lo, wait_hi in ((1, 3), (1, 5), (1, 10), (3, 10)):
            for lo, hi in ((-6.0, -4.0), (-10.0, -4.0), (-15.0, -6.0), (-20.0, -10.0)):
                net = (pool & (env["days_since"] >= wait_lo)
                       & (env["days_since"] <= wait_hi)
                       & (env["from_peak"] <= hi) & (env["from_peak"] >= lo))
                nets.append((f"{floor_name}·{wait_lo}~{wait_hi}일·{hi:.0f}~{lo:.0f}%",
                             np.nan_to_num(net, nan=False).astype(bool), pool))
    sweep(env, nets, (60, 120, 250), "한국 상승 그물 격자")


def run_down():
    env = build()
    dates = env["dates"]
    up_day = env["kospi"] > env["kospi"].shift(1)
    nets = []
    for band in ((-15.0, -5.0), (-20.0, -10.0), (-40.0, -15.0)):
        in_band = (env["kospi_drop"] <= band[1]) & (env["kospi_drop"] >= band[0])
        episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
        table = pd.DataFrame({"e": episode, "d": env["kospi_drop"]}).dropna()
        deepest = pd.Series(False, index=dates)
        rebound = pd.Series(False, index=dates)
        for _, group in table.groupby("e"):
            deepest.loc[group["d"].idxmin()] = True
            hits = group.index[up_day.reindex(group.index).fillna(False).to_numpy()]
            if len(hits):
                rebound.loc[hits[0]] = True
        for signal_name, signal in (("깊은날", deepest), ("첫반등", rebound)):
            flag = np.repeat(signal.to_numpy()[:, None], env["close"].shape[1], axis=1)
            for floor_name, floor in (("10억↑", 10), ("50억↑", 50)):
                pool = env["value"] >= floor
                for lo, hi in ((-30.0, -20.0), (-40.0, -30.0), (-50.0, -40.0),
                               (-60.0, -40.0), (-50.0, -20.0)):
                    net = (flag & pool & (env["from_high"] <= hi)
                           & (env["from_high"] >= lo))
                    nets.append((f"코스피{band[1]:.0f}~{band[0]:.0f}·{signal_name}"
                                 f"·{floor_name}·{hi:.0f}~{lo:.0f}%",
                                 np.nan_to_num(net, nan=False).astype(bool), pool))
    sweep(env, nets, (20, 60, 120, 250), "한국 급락 후 반등 그물 격자")


if __name__ == "__main__":
    {"up": run_up, "down": run_down}[sys.argv[1]]()
