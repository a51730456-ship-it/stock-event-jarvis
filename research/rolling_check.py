"""자르는 날을 하나 고르지 않는다 — **모든 자르는 날로 겹쳐 잰다** (2026-08-07).

**왜 이렇게까지 하나.** 지금까지 두 번 넘어졌다.
  ① 10년을 앞뒤 두 토막으로만 갈라 미국 배점을 정했다(2026-08-06).
  ② 12년을 앞뒤 두 토막으로 갈라 한국을 재다가, 해마다 다시 보니 '같이 움직이는
     무리'가 잴 수 있는 해가 3년뿐이었다(상하님 지적).
두 토막은 진 해와 이긴 해를 섞어 평균 내 버리고, 해마다 보기는 그해 표본이 적으면
흔들린다. 그래서 **3년짜리 창을 한 달씩 밀면서** 수십 번 재고, **몇 번이나 이겼는지**
를 본다. 자르는 날을 사람이 고르지 않으므로 고르는 자의성이 없다.

창끼리 겹치므로 '몇 번 중 몇 번'은 서로 독립된 시험이 아니다. 그래도 '어디서 잘라도
버티나'라는 물음에는 이것이 정확한 답이다. 같이 찍는 **가장 나빴던 창**을 꼭 보라 —
평균이 좋아도 최악이 크게 나쁘면 그 자리는 언젠가 그만큼 아프다.

쓰는 법:  python research/rolling_check.py us
          python research/rolling_check.py kr
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

WINDOW_YEARS = 3
STEP_DAYS = 21          # 한 달에 한 번씩 창을 민다
MIN_TRADES = 30         # 창 안에 자리가 이보다 적으면 그 창은 세지 않는다


def roll(returns: pd.DataFrame, mask: pd.DataFrame, pool: pd.DataFrame | None = None):
    """창을 밀며 재고, 이긴 창의 비율과 가장 나빴던 창을 돌려준다."""
    length = int(WINDOW_YEARS * 252)
    values_all = returns.where(mask).to_numpy()
    base_all = returns.to_numpy() if pool is None else returns.where(pool).to_numpy()
    active_all = mask.to_numpy().any(axis=1)
    win_edges, median_edges = [], []
    for start in range(0, len(returns) - length + 1, STEP_DAYS):
        stop = start + length
        picked = values_all[start:stop].ravel()
        picked = picked[~np.isnan(picked)]
        if picked.size < MIN_TRADES:
            continue
        base = base_all[start:stop][active_all[start:stop]].ravel()
        base = base[~np.isnan(base)]
        if base.size < MIN_TRADES:
            continue
        win_edges.append((picked > 0).mean() * 100 - (base > 0).mean() * 100)
        median_edges.append(float(np.median(picked) - np.median(base)))
    return np.array(win_edges), np.array(median_edges)


def roll_within(returns: pd.DataFrame, net: pd.DataFrame, factor: pd.DataFrame):
    """**그물 안에서** 비교한다 — 조건에 맞는 것 vs 같은 그물의 나머지.

    배점은 '아무 종목보다 나은가'가 아니라 '이미 그물에 걸린 것들 중 어느 것을
    위로 올릴까'를 정하는 값이다. 그러니 상대는 그물의 나머지여야 한다.

    2026-08-07에 이걸 틀렸다. 상대를 '그날 아무 종목이나'로 잡았더니, 시장이
    통째로 눌려 수십 종목이 한꺼번에 걸리는 날이 신호 쪽 평균을 지배했다.
    '테마가 뭉쳤나'가 아니라 '그날이 어떤 날이었나'를 재고 있었다
    (상하님 지적: "테마 동반이 전혀 상관없다는 건 믿을 수 없다").
    """
    length = int(WINDOW_YEARS * 252)
    yes = returns.where(net & factor).to_numpy()
    no = returns.where(net & ~factor).to_numpy()
    win_edges, median_edges = [], []
    for start in range(0, len(returns) - length + 1, STEP_DAYS):
        stop = start + length
        a = yes[start:stop].ravel()
        a = a[~np.isnan(a)]
        b = no[start:stop].ravel()
        b = b[~np.isnan(b)]
        if a.size < MIN_TRADES or b.size < MIN_TRADES:
            continue
        win_edges.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
        median_edges.append(float(np.median(a) - np.median(b)))
    return np.array(win_edges), np.array(median_edges)


def report(name: str, win_edges, median_edges) -> None:
    if win_edges.size == 0:
        print(f"{name:<32} 창이 없다 (자리가 너무 적음)")
        return
    share = (win_edges > 0).mean() * 100
    share_median = (median_edges > 0).mean() * 100
    print(f"{name:<32} 창 {win_edges.size:>3}개 · "
          f"승률로 이긴 창 {share:5.1f}% · 수익률로 이긴 창 {share_median:5.1f}%  |  "
          f"가운데 {np.median(win_edges):+5.1f}p · 가장 나쁜 창 {win_edges.min():+6.1f}p")


def _streak(above: pd.DataFrame) -> pd.DataFrame:
    values = above.to_numpy(dtype="int16", na_value=0)
    out = np.zeros_like(values)
    for row in range(1, values.shape[0]):
        out[row] = np.where(values[row] > 0, out[row - 1] + 1, 0)
    return pd.DataFrame(out, index=above.index, columns=above.columns)


def _together(mask: pd.DataFrame, themes_of: dict[str, set]) -> pd.DataFrame:
    columns = list(mask.columns)
    array = mask.to_numpy()
    out = np.zeros(array.shape, dtype="int16")
    for row in np.nonzero(array.any(axis=1))[0]:
        picked = np.nonzero(array[row])[0]
        codes = [columns[i] for i in picked]
        counts: dict[str, int] = {}
        for code in codes:
            for theme in themes_of.get(code, ()):
                counts[theme] = counts.get(theme, 0) + 1
        out[row, picked] = [
            max((counts[t] for t in themes_of.get(code, ()) if t in counts), default=1)
            for code in codes
        ]
    return pd.DataFrame(out, index=mask.index, columns=mask.columns)


def _common(close, high, volume):
    dates = close.index
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    turnover = close * volume
    return {
        "days_since": days_since, "from_peak": from_peak, "from_high": from_high,
        "recent11": (close / close.shift(11) - 1.0) * 100.0,
        "gain60": (close / close.shift(60) - 1.0) * 100.0,
        "turnover": turnover,
        "streak": _streak(turnover > turnover.rolling(50, min_periods=20).mean()),
        "value": turnover.rolling(50, min_periods=20).mean(),
    }


def run_us() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    metric = _common(close, high, wide["volume"][stocks])
    dates = close.index
    returns = (close.shift(-120) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (qqq_drop > -10.0)
    wide_up = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    breakout = (wide_up & (metric["days_since"] >= wait_lo)
                & (metric["days_since"] <= wait_hi)
                & (metric["from_peak"] <= drop_hi) & (metric["from_peak"] >= drop_lo))

    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    crash = deep & (metric["from_high"] <= -20.0) & (metric["from_high"] >= -50.0)

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            themes_of.setdefault(stock, set()).add(theme["name"])

    for title, signal in (("상승장", breakout), ("급락 후 반등장", crash)):
        together = _together(signal, themes_of)
        print(f"\n### 미국 {title}  (명부 {len(stocks)}종목 · 120거래일 보유)")
        report("그물 전체 (vs 아무 종목)", *roll(returns, signal))
        # 그물에 걸린 것들이 어떻게 흩어져 있나 — 조건이 너무 헐거우면 고르는 값이 아니다
        counts = together.to_numpy()[signal.to_numpy()]
        total = counts.size
        print(f"  그물에 걸린 자리 {total:,}개 중 테마 동반 "
              f"1개 {np.mean(counts <= 1) * 100:.0f}% · 2개 {np.mean(counts == 2) * 100:.0f}% · "
              f"3개↑ {np.mean(counts >= 3) * 100:.0f}% · 5개↑ {np.mean(counts >= 5) * 100:.0f}%")
        print("  ── 그물 안에서 비교 (조건 맞는 것 vs 같은 그물의 나머지) ──")
        for name, factor in (
            ("테마 동반 3개↑", together >= 3),
            ("테마 동반 5개↑", together >= 5),
            ("최근 11일 -5%↑ 빠짐", metric["recent11"] <= -5.0),
            ("최근 11일 안 올랐음(<=0)", metric["recent11"] <= 0.0),
            ("눌린 폭 10~15%" if title == "상승장" else "낙폭 -30~-50%",
             ((metric["from_peak"] <= -10.0) & (metric["from_peak"] >= -15.0))
             if title == "상승장" else
             ((metric["from_high"] <= -30.0) & (metric["from_high"] >= -50.0))),
            ("거래대금 연속 11일↑", metric["streak"] >= 11),
            ("60일 40%↑ 오름", metric["gain60"] >= 40.0),
        ):
            report(name, *roll_within(returns, signal, factor))


def run_kr() -> None:
    from kr_measure import DAILY, ROSTER, load_wide

    wide = load_wide()
    close, high = wide["close"], wide["high"]
    metric = _common(close, high, wide["volume"])
    dates = close.index
    value = metric["value"] / 1e8  # 억원

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_drop = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_drop <= -10.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)

    up_pool = value >= 50
    breakout = ((metric["days_since"] >= 1) & (metric["days_since"] <= 10)
                & (metric["from_peak"] <= -4.0) & (metric["from_peak"] >= -6.0) & up_pool)
    down_pool = value >= 10
    crash = (deep & (metric["from_high"] <= -40.0) & (metric["from_high"] >= -50.0)
             & down_pool)

    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"]
    themes_of = {code: set(entry["themes"]) for code, entry in roster.items()}

    for title, signal, pool, hold in (("상승장 (거래대금 50억↑)", breakout, up_pool, 120),
                                      ("급락 후 반등장 (거래대금 10억↑)", crash, down_pool, 60)):
        returns = (close.shift(-hold) / wide["open"].shift(-1) - 1.0) * 100.0
        together = _together(signal, themes_of)
        print(f"\n### 한국 {title} · {hold}거래일 보유")
        report("그물 전체 (vs 아무 종목)", *roll(returns, signal, pool))
        counts = together.to_numpy()[signal.to_numpy()]
        print(f"  그물에 걸린 자리 {counts.size:,}개 중 테마 동반 "
              f"1개 {np.mean(counts <= 1) * 100:.0f}% · 2개 {np.mean(counts == 2) * 100:.0f}% · "
              f"3개↑ {np.mean(counts >= 3) * 100:.0f}% · 5개↑ {np.mean(counts >= 5) * 100:.0f}%")
        print("  ── 그물 안에서 비교 (조건 맞는 것 vs 같은 그물의 나머지) ──")
        for name, factor in (
            ("거래대금 500억↑", value >= 500),
            ("테마 동반 3개↑", together >= 3),
            ("테마 동반 5개↑", together >= 5),
            ("최근 11일 -5%↑ 빠짐", metric["recent11"] <= -5.0),
            ("최근 11일 안 올랐음(<=0)", metric["recent11"] <= 0.0),
            ("60일 안 올랐음(<=0)", metric["gain60"] <= 0.0),
            ("60일 40%↑ 오름", metric["gain60"] >= 40.0),
            ("거래대금 연속 11일↑", metric["streak"] >= 11),
        ):
            report(name, *roll_within(returns, signal, factor))


if __name__ == "__main__":
    print(f"창 {WINDOW_YEARS}년 · 한 달에 한 번 밀기 · 창 안 자리 {MIN_TRADES}개 이상만 셈\n")
    {"us": run_us, "kr": run_kr}[sys.argv[1]]()
