"""미국 배점을 **한 가지 방법으로** 끝까지 검증한다 (2026-08-07).

상하님 지적 — "매번 기준이 자꾸 왔다갔다해서 못 믿겠다."  맞는 말이다.
이 파일은 방법을 먼저 못박고, 그 방법으로 모든 후보·모든 문턱을 다 잰다.

**못박는 규칙 (이후 바꾸지 않는다)**
  ① 비교 상대는 **같은 그물 안의 나머지**다.
     배점은 '아무 종목보다 나은가'가 아니라 '그물에 걸린 것 중 어느 것을 위로
     올릴까'를 정한다. 상대를 '그날 아무 종목이나'로 잡으면, 수십 종목이 한꺼번에
     걸리는 폭락일이 신호 쪽 평균을 지배해 '그날이 어떤 날이었나'를 재게 된다.
  ② 창 길이를 **2년·3년·4년 셋 다** 잰다. 하나에서만 통하면 쓰지 않는다.
  ③ **승률과 수익률 둘 다** 본다. 한쪽만 좋으면 쓰지 않는다.
  ④ 문턱을 눈대중으로 고르지 않는다. **여러 문턱을 다 재고** 어디서 값이 생기는지 본다.
  ⑤ 두 무리 각각 30건 미만인 창은 버린다. 남은 창이 20개 미만이면 판정하지 않는다.

**합격선** — 창 길이 셋 **모두**에서 승률로 이긴 창과 수익률로 이긴 창이 **둘 다 65% 이상**.

쓰는 법:  python research/us_verify.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

WINDOWS = (2, 3, 4)     # 창 길이(년)
STEP_DAYS = 21          # 한 달에 한 번 민다
MIN_SIDE = 30           # 창 안에서 두 무리 각각 이만큼은 있어야 그 창을 센다
MIN_WINDOWS = 20        # 창이 이보다 적으면 판정하지 않는다
PASS_MARK = 65.0        # 이긴 창 비율 합격선(%)


def score(returns: pd.DataFrame, net: pd.DataFrame, factor: pd.DataFrame) -> dict:
    """그물 안에서 '조건 맞는 것 vs 나머지'를 창 길이 셋으로 잰다."""
    yes = returns.where(net & factor).to_numpy()
    no = returns.where(net & ~factor).to_numpy()
    out: dict[int, dict] = {}
    for years in WINDOWS:
        length = int(years * 252)
        wins, medians = [], []
        for start in range(0, len(returns) - length + 1, STEP_DAYS):
            stop = start + length
            a = yes[start:stop].ravel()
            a = a[~np.isnan(a)]
            b = no[start:stop].ravel()
            b = b[~np.isnan(b)]
            if a.size < MIN_SIDE or b.size < MIN_SIDE:
                continue
            wins.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
            medians.append(float(np.median(a) - np.median(b)))
        if len(wins) < MIN_WINDOWS:
            out[years] = None
            continue
        wins, medians = np.array(wins), np.array(medians)
        out[years] = {
            "n": wins.size,
            "win_share": float((wins > 0).mean() * 100),
            "median_share": float((medians > 0).mean() * 100),
            "win_mid": float(np.median(wins)),
            "win_worst": float(wins.min()),
        }
    return out


def verdict(result: dict) -> str:
    usable = [item for item in result.values() if item]
    if len(usable) < len(WINDOWS):
        return "판정 못 함"
    if all(item["win_share"] >= PASS_MARK and item["median_share"] >= PASS_MARK
           for item in usable):
        return "○ 합격"
    if all(item["win_share"] <= 100 - PASS_MARK and item["median_share"] <= 100 - PASS_MARK
           for item in usable):
        return "✗ 거꾸로"
    return "△ 안 됨"


def show(name: str, share: float, result: dict) -> None:
    cells = []
    for years in WINDOWS:
        item = result[years]
        cells.append("       —      " if not item else
                     f"{item['win_share']:5.0f}/{item['median_share']:3.0f}%({item['n']:>3})")
    mid = result[WINDOWS[1]]
    tail = ("" if not mid else
            f"  가운데 {mid['win_mid']:+5.1f}p · 최악 {mid['win_worst']:+6.1f}p")
    print(f"  {name:<26}{share:>5.0f}%" + "".join(cells) + f"  {verdict(result):<9}{tail}")


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    dates = close.index
    returns = (close.shift(-120) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    turnover = close * wide["volume"][stocks]
    value = turnover.rolling(50, min_periods=20).mean()
    streak_src = (turnover > value).to_numpy(dtype="int16", na_value=0)
    streak_out = np.zeros_like(streak_src)
    for row in range(1, streak_src.shape[0]):
        streak_out[row] = np.where(streak_src[row] > 0, streak_out[row - 1] + 1, 0)
    streak = pd.DataFrame(streak_out, index=dates, columns=close.columns)
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    prev = close.shift(1)
    true_range = pd.concat([(high - wide["low"][stocks]).stack(),
                            (high - prev).abs().stack(),
                            (wide["low"][stocks] - prev).abs().stack()],
                           axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0

    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (qqq_drop > -10.0)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    breakout = (up_wide & (days_since >= wait_lo) & (days_since <= wait_hi)
                & (from_peak <= drop_hi) & (from_peak >= drop_lo))

    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    crash = deep & (from_high <= -20.0) & (from_high >= -50.0)

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            themes_of.setdefault(stock, set()).add(theme["name"])
    no_theme = [s for s in stocks if s not in themes_of]
    print(f"명부 {len(stocks)}종목 중 **어느 테마에도 안 속한 종목 {len(no_theme)}개** — "
          "이들은 테마 동반이 늘 1개로 잡혀 자동으로 깎인다.\n")

    def together_of(mask: pd.DataFrame) -> pd.DataFrame:
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

    print(f"창 길이 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 한 달에 한 번 밀기 · "
          f"두 무리 각 {MIN_SIDE}건 이상 · 합격선 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'\n")

    for title, net in (("상승장", breakout), ("급락 후 반등장", crash)):
        together = together_of(net)
        in_net = net.to_numpy()
        total = int(in_net.sum())
        print(f"\n{'=' * 108}\n### 미국 {title} — 그물에 걸린 자리 {total:,}개\n{'=' * 108}")
        print(f"  {'후보':<26}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
        candidates = [
            ("테마 동반 2개↑", together >= 2),
            ("테마 동반 3개↑", together >= 3),
            ("테마 동반 4개↑", together >= 4),
            ("테마 동반 5개↑", together >= 5),
            ("테마 동반 6개↑", together >= 6),
            ("최근 11일 -10%↑ 빠짐", recent11 <= -10.0),
            ("최근 11일 -5%↑ 빠짐", recent11 <= -5.0),
            ("최근 11일 -3%↑ 빠짐", recent11 <= -3.0),
            ("최근 11일 안 올랐음", recent11 <= 0.0),
            ("60일 안 올랐음", gain60 <= 0.0),
            ("60일 15% 미만 오름", gain60 <= 15.0),
            ("60일 40%↑ 오름", gain60 >= 40.0),
            ("거래대금 연속 4일↑", streak >= 4),
            ("거래대금 연속 11일↑", streak >= 11),
            ("변동성 3% 미만", atr <= 3.0),
            ("변동성 5% 미만", atr <= 5.0),
            ("변동성 6%↑", atr >= 6.0),
        ]
        if title == "상승장":
            candidates += [("눌린 폭 4~6%", (from_peak <= -4.0) & (from_peak >= -6.0)),
                           ("눌린 폭 6~10%", (from_peak <= -6.0) & (from_peak >= -10.0)),
                           ("눌린 폭 10~15%", (from_peak <= -10.0) & (from_peak >= -15.0))]
        else:
            candidates += [("낙폭 -20~-30%", (from_high <= -20.0) & (from_high >= -30.0)),
                           ("낙폭 -30~-40%", (from_high <= -30.0) & (from_high >= -40.0)),
                           ("낙폭 -40~-50%", (from_high <= -40.0) & (from_high >= -50.0))]
        candidates.append(("거래대금 상위 절반",
                           value.rank(axis=1, pct=True, ascending=True) >= 0.5))
        for name, factor in candidates:
            share = float(factor.to_numpy()[in_net].mean() * 100)
            show(name, share, score(returns, net, factor))


if __name__ == "__main__":
    main()
