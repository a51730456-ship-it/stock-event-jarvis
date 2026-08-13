"""테마 강도를 **논문식**으로 잰다 — 테마 전체가 제 고점에 얼마나 가까운가.

상하님 지시 (2026-08-13) — *"너가 논문이 맞는지, 너가 어떻게 할지 기준을 정하고,
너가 제시하는 게 맞는지 확인하고 돌려보고 이야기해봐라."*

## 무엇을 바꾸나

그전 테마 항목은 **'이 종목이 테마를 몇 개 걸쳤나'**였다. 그건 오늘 만든 테마표로
14개 종목을 지목한 것이라 미래정보다(폐기).

논문(Moskowitz·Grinblatt 1999 산업 모멘텀 · George·Hwang 2004 52주 신고가 ·
Hong·Jordan·Liu 52주 신고가의 산업 효과)이 실제로 쓴 것은 **산업 전체가 제
52주 고점에 얼마나 가까운가**다. 개별 종목 몇 개를 세는 것이 아니다.

  테마 근접도 = 그날 테마 구성종목 **합산 시가총액** ÷ 그 합산 시총의 **52주 최고**

**시가총액은 그날 발행주식수로 만든다**(`us_shares_history`). 오늘 주식수를 과거에
쓰지 않는다.

## 남는 한계 — 숨기지 않는다

**테마 명부 자체는 여전히 오늘 것이다.** 다만 '테마 2개 걸침'과는 성격이 다르다 —
그건 **고정된 14종목**을 찍는 것이고, 이것은 **날마다 오르내리는 값**이다.
종목을 고르는 게 아니라 그 무리가 지금 강한지를 잰다. 그래도 명부가 오늘 것이라
편향이 남는다. 화면·문서에 그대로 적는다.

## 재는 것

  ① 테마 근접도 네 칸        95~100% / 90~95% / 85~90% / 85% 미만
  ② 같은 테마 동시 신고가 개수  0~1 / 2~3 / 4~5 / 6개↑  (기존 '4개↑'가 맞는지)
  ③ 뚫기 전 60일 50%↑        (미래정보 없음 · 그대로)
  ④ 그날 시총 상위 50         (그날 발행주식수)

**6개월을 중심으로 본다** — 논문이 6개월 보유를 썼고, 앞선 측정에서도 20일·3개월은
계단이 안 섰다.

1층·2층은 **고정**. QQQ 200일선 위 · 신고가 뒤 3~10일 · 고점 대비 −4~−15%.

쓰는 법:  python research/us_theme_strength_hjl.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60_at_peak = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()

    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")

    # ── ① 테마 근접도 (논문식) ──────────────────────────────────────────
    theme_prox = {}
    theme_hits = {}
    recent_high = is_new_high.rolling(10, min_periods=1).max().astype(bool)
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if len(members) < 3:
            continue
        total = cap[members].sum(axis=1, min_count=2)
        theme_prox[theme["name"]] = total / total.rolling(252, min_periods=200).max() * 100
        theme_hits[theme["name"]] = recent_high[members].sum(axis=1)
    prox_frame = pd.DataFrame(theme_prox)
    hits_frame = pd.DataFrame(theme_hits)

    themes_of: dict[str, list] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns and theme["name"] in prox_frame.columns:
                themes_of.setdefault(stock, []).append(theme["name"])

    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    hits = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    for stock, names in themes_of.items():
        prox[stock] = prox_frame[names].max(axis=1)
        hits[stock] = hits_frame[names].max(axis=1)

    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    ma200 = (qqq > qqq.rolling(200, min_periods=200).mean()).fillna(False)
    up = pd.DataFrame(np.repeat(ma200.to_numpy()[:, None], close.shape[1], axis=1),
                      index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total_seats = int(net.to_numpy().sum())

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    base = (up & close.notna()).fillna(False)

    def stat(values):
        values = values[~np.isnan(values)]
        return None if values.size < 100 else ((values > 0).mean() * 100,
                                               float(np.median(values)))

    def row(name, mask, when=None):
        sel = mask if when is None else mask.loc[when]
        source = rets if when is None else {h: rets[h].loc[when] for h, _ in HOLDS}
        cells = ""
        for hold, _label in HOLDS:
            got = stat(source[hold].where(sel).to_numpy().ravel())
            cells += "       —      " if not got else f" {got[0]:>3.0f}번 {got[1]:>+6.1f}%"
        count = int(sel.to_numpy().sum())
        print(f"  {name:<28}{count:>7,}{count / max(total_seats, 1) * 100:>5.0f}%{cells}")

    print(f"\n{'=' * 106}\n### 테마 강도를 논문식으로 — 테마 **전체**가 제 고점에 얼마나 가까운가"
          f"\n### 1층 QQQ 200일선 위 · 2층 신고가 뒤 {wait_lo}~{wait_hi}일 · "
          f"고점 −{abs(drop_hi):.0f}~−{abs(drop_lo):.0f}% · 그물 {total_seats:,}자리"
          f"\n{'=' * 106}")
    print(f"  {'':<28}{'자리':>7}{'몫':>5}" + "".join(f"{n:>14}" for _h, n in HOLDS))
    print()
    row("아무 종목이나 (기준선)", base)
    row("그물 전체", net)

    print("\n  ── ① 테마 근접도 (테마 합산 시총 ÷ 그 52주 최고) ──")
    bands = ((95, 101, "95~100% 매우 강함"), (90, 95, "90~95% 강함"),
             (85, 90, "85~90% 보통"), (0, 85, "85% 미만 약함"))
    for lo, hi, label in bands:
        row(label, net & (prox >= lo) & (prox < hi))

    print("\n  ── ② 같은 테마에서 최근 10일 안에 신고가 낸 종목 수 ──")
    for lo, hi, label in ((0, 2, "0~1개"), (2, 4, "2~3개"),
                          (4, 6, "4~5개"), (6, 99, "6개 이상")):
        row(label, net & (hits >= lo) & (hits < hi))

    print("\n  ── ③ 뚫기 전 60일 상승률 ──")
    row("50%↑", net & (gain60_at_peak > 50))
    print("\n  ── ④ 그날 시가총액 ──")
    row("상위 50", net & (cap_rank <= 50) & cap.notna())

    print("\n  ── 조합 (근접도 90%↑ 기준) ──")
    strong = prox >= 90
    row("근접도 90%↑ + 60일 50%↑", net & strong & (gain60_at_peak > 50))
    row("근접도 90%↑ + 시총 상위50", net & strong & (cap_rank <= 50) & cap.notna())
    row("근접도 90%↑ + 신고가 4개↑", net & strong & (hits >= 4))

    # ── 국면별 ──────────────────────────────────────────────────────────
    epi = (ma200 & ~ma200.shift(1, fill_value=False)).cumsum().where(ma200)
    groups = [(g.index[0], g.index[-1]) for _e, g in
              pd.DataFrame({"e": epi}).dropna().groupby("e") if len(g) >= 120]
    print(f"\n  ── QQQ 상승 국면별 (6개월 보유 · 논문 기준) ──")
    print(f"  {'':<28}" + "".join(f"{a.date().strftime('%y.%m'):>14}" for a, _b in groups))
    for name, mask in (("아무 종목이나", base), ("그물 전체", net),
                       ("근접도 95%↑", net & (prox >= 95)),
                       ("근접도 90%↑", net & (prox >= 90)),
                       ("근접도 85% 미만", net & (prox < 85)),
                       ("신고가 4개↑", net & (hits >= 4)),
                       ("60일 50%↑", net & (gain60_at_peak > 50)),
                       ("시총 상위50", net & (cap_rank <= 50) & cap.notna())):
        cells = ""
        for a, b in groups:
            when = (dates >= a) & (dates <= b)
            got = stat(rets[120].loc[when].where(mask.loc[when]).to_numpy().ravel())
            cells += f"{'—':>14}" if not got else f"{got[0]:>7.0f}번{got[1]:>+6.1f}"
        print(f"  {name:<28}{cells}")

    print("\n  ※ 시가총액은 **그날** 발행주식수로 만들었다(미래정보 없음).")
    print("  ※ 다만 **테마 명부는 오늘 것**이다 — 이 한계는 남는다.")
    print("  ※ 명부는 오늘 살아 있는 199종목이라 망한 회사가 빠져 있다.")


if __name__ == "__main__":
    main()
