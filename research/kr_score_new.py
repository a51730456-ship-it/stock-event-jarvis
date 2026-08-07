"""**새 그물** 위에서 한국 배점을 다시 잰다 (2026-08-07).

옛 배점은 옛 그물에서 잰 것이라 통째로 무효다. 그물이 바뀌면 그 안에 걸리는
종목이 달라지고, 어느 항목이 값을 하는지도 달라진다.

**새 그물** (research/kr_net_grid.py 격자에서 고른 것)
  상승장       거래대금 50억↑ · 신고가 뒤 3~10일 · 고점 대비 -4~-6% · 250거래일
               (321개 창 중 전부 이김 · 가운데 +8.7p · 최악 +0.0p)
  급락 후 반등  코스피 -15% 아래 국면의 가장 깊은 날 · 거래대금 50억↑
               · 종목 -40~-60% · 20거래일 (306개 창 전부 이김 · 가운데 +9.1p)

**비교 상대는 같은 그물 안의 나머지** — 배점은 그물에 걸린 것 중 순위를 매기는
값이기 때문이다. 창 2·3·4년, 승률과 수익률 둘 다 65% 이상이라야 합격.

쓰는 법:  python research/kr_score_new.py
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
from kr_measure import DAILY, ROSTER, load_wide  # noqa: E402
from us_verify import MIN_SIDE, PASS_MARK, WINDOWS, score, show  # noqa: E402


def main() -> None:
    wide = load_wide()
    close, high = wide["close"], wide["high"]
    dates = close.index
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    turnover = close * wide["volume"]
    value = turnover.rolling(50, min_periods=20).mean() / 1e8          # 억원
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    prev = close.shift(1)
    true_range = pd.concat([(high - wide["low"]).stack(), (high - prev).abs().stack(),
                            (wide["low"] - prev).abs().stack()],
                           axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    flow = (turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean())

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_drop = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_drop <= -15.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)

    pool = value >= 50
    up_net = (pool & (days_since >= 3) & (days_since <= 10)
              & (from_peak <= -4.0) & (from_peak >= -6.0))
    down_net = deep & pool & (from_high <= -40.0) & (from_high >= -60.0)

    # ── 테마 ────────────────────────────────────────────────────────────
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"]
    themes_of = {code: set(entry["themes"]) for code, entry in roster.items()
                 if code in close.columns}
    members: dict[str, list[str]] = {}
    for code, names in themes_of.items():
        for name in names:
            members.setdefault(name, []).append(code)
    members = {name: codes for name, codes in members.items() if len(codes) >= 3}
    has_theme = pd.DataFrame(
        np.repeat(np.array([[c in themes_of for c in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    print(f"명부 {close.shape[1]:,}종목 중 테마 있는 것 {len(themes_of):,}개 · "
          f"3종목 이상인 테마 {len(members):,}개\n")

    def theme_frame(source: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({name: source[codes].mean(axis=1)
                             for name, codes in members.items()})

    def spread_top(values: pd.DataFrame, share: float) -> pd.DataFrame:
        """테마를 줄 세워 **상위 몇 %** 안에 드는 테마에 속하면 True."""
        ranks = values.rank(axis=1, pct=True, ascending=False)
        winners = ranks <= share
        out = {code: (winners[[n for n in themes_of.get(code, ()) if n in winners.columns]]
                      .any(axis=1)
                      if any(n in winners.columns for n in themes_of.get(code, ()))
                      else pd.Series(False, index=values.index))
               for code in close.columns}
        return pd.DataFrame(out, index=values.index).fillna(False)

    theme_ret20 = theme_frame(close.pct_change(20) * 100)
    theme_ret60 = theme_frame(close.pct_change(60) * 100)
    theme_flow = theme_frame(flow)
    theme_drop = theme_frame(from_high)

    def together(mask: pd.DataFrame) -> pd.DataFrame:
        columns = list(mask.columns)
        array = mask.to_numpy()
        out = np.zeros(array.shape, dtype="int16")
        for row in np.nonzero(array.any(axis=1))[0]:
            picked = np.nonzero(array[row])[0]
            codes = [columns[i] for i in picked]
            tally: dict[str, int] = {}
            for code in codes:
                for name in themes_of.get(code, ()):
                    tally[name] = tally.get(name, 0) + 1
            out[row, picked] = [
                max((tally[n] for n in themes_of.get(code, ()) if n in tally), default=0)
                for code in codes
            ]
        return pd.DataFrame(out, index=mask.index, columns=mask.columns)

    print(f"창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"합격선 {PASS_MARK:.0f}% · 비교 상대는 **같은 그물 안의 나머지**")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'\n")

    for title, raw_net, hold in (("상승장", up_net, 250),
                                 ("급락 후 반등장", down_net, 20)):
        net = (raw_net & has_theme).fillna(False)
        returns = (close.shift(-hold) / wide["open"].shift(-1) - 1.0) * 100.0
        in_net = net.to_numpy()
        pair = together(net)
        print(f"\n{'=' * 110}\n### 한국 {title} — 테마 있는 종목 {int(in_net.sum()):,}자리"
              f" · {hold}거래일 보유\n{'=' * 110}")
        print(f"  {'후보':<28}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
        candidates = [
            ("거래대금 500억↑", value >= 500),
            ("거래대금 1,000억↑", value >= 1000),
            ("거래대금 상위 20%", value.rank(axis=1, pct=True) >= 0.8),
            ("최근 11일 -5%↑ 빠짐", recent11 <= -5.0),
            ("최근 11일 안 올랐음", recent11 <= 0.0),
            ("최근 11일 +5%↑ 오름", recent11 >= 5.0),
            ("60일 안 올랐음", gain60 <= 0.0),
            ("60일 40%↑ 오름", gain60 >= 40.0),
            ("변동성 4% 미만", atr <= 4.0),
            ("변동성 6%↑", atr >= 6.0),
            ("테마 동반 3개↑", pair >= 3),
            ("테마 동반 5개↑", pair >= 5),
            ("테마 20일 상위 5%", spread_top(theme_ret20, 0.05)),
            ("테마 20일 상위 20%", spread_top(theme_ret20, 0.20)),
            ("테마 60일 상위 20%", spread_top(theme_ret60, 0.20)),
            ("테마 거래대금 늘었나 상위 20%", spread_top(theme_flow, 0.20)),
            ("테마 덜 빠졌나 상위 20%", spread_top(theme_drop, 0.20)),
        ]
        for name, factor in candidates:
            factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
            factor = factor.astype(bool)
            got = float(factor.to_numpy()[in_net].mean() * 100)
            show(name, got, score(returns, net, factor))


if __name__ == "__main__":
    main()
