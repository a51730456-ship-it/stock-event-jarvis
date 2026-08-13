"""3층 최종전 — 세 변수만, 지적받은 것 전부 반영해서 (2026-08-13).

## 반영한 지적 (상하님·지피티)

  ① **시총이 진짜 그날 값인지 눈으로 확인한다** — NVDA 등수가 해마다 어떻게
     움직였는지 찍어 본다. 오늘 값을 과거에 쓴 것이면 등수가 안 움직인다.
  ② **N(신호 개수)과 기준선 초과를 같이 낸다** — 몫만 보면 표본 크기를 모른다.
  ③ **같은 날·같은 테마 신호를 한 사건으로 묶어서도 본다** — 반도체 10종목이
     한날 걸린 것을 10개 증거로 세면 안 된다.
  ④ **2016~2021 / 2021~2026 둘로 갈라 본다.**
  ⑤ 칸을 더 잘게 나눈다.

## 세 변수만

  A 산업(테마) 근접도   테마 합산 시총 ÷ 그 52주 최고 · 95↑/90~95/85~90/85↓
  B 그날 시총 순위      1~25 / 26~50 / 51~100 / 101위 아래
  C 뚫기 전 60일 상승률  <20 / 20~35 / 35~50 / 50~75 / 75%↑

1층·2층 고정 — QQQ 200일선 위 · 신고가 뒤 3~10일 · 고점 −4~−15%.
**점수는 안 매긴다.** 결과를 보고 상하님이 정하신다.

쓰는 법:  python research/us_layer3_final.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")

    # ── ① 시총이 진짜 그날 값인가 — 눈으로 확인 ──────────────────────────
    print(f"\n{'=' * 100}\n### [확인] 시총 순위가 해마다 움직이나 (오늘 값을 과거에 썼으면 안 움직인다)"
          f"\n{'=' * 100}")
    checks = [t for t in ("NVDA", "AAPL", "VRT", "TSLA", "INTC") if t in cap_rank.columns]
    years = [2016, 2018, 2020, 2022, 2024, 2026]
    print(f"  {'종목':<8}" + "".join(f"{y:>9}년" for y in years))
    for ticker in checks:
        cells = ""
        for year in years:
            sel = cap_rank[ticker][[d.year == year for d in dates]].dropna()
            cells += f"{'—':>10}" if sel.empty else f"{sel.iloc[-1]:>9.0f}위"
        print(f"  {ticker:<8}{cells}")

    # ── 그물 ────────────────────────────────────────────────────────────
    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60 = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()

    theme_prox = {}
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if len(members) < 3:
            continue
        total = cap[members].sum(axis=1, min_count=2)
        theme_prox[theme["name"]] = total / total.rolling(252, min_periods=200).max() * 100
    prox_frame = pd.DataFrame(theme_prox)

    themes_of: dict[str, list] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns and theme["name"] in prox_frame.columns:
                themes_of.setdefault(stock, []).append(theme["name"])
    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    main_theme = {}
    for stock, names in themes_of.items():
        prox[stock] = prox_frame[names].max(axis=1)
        main_theme[stock] = names[0]

    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    # ── 1층 = **정배열** (2026-08-13 상하님 확정) ────────────────────────
    # 상하님 말씀 — "나스닥이 200일선 위가 아니지. 정배열이고 신고가를 향하는
    # 기준이지." 200일선 위는 10년의 76%라 거의 안 거른다.
    #
    # **실측은 정배열이 더 나쁘다고 나왔다**(승률차 -4.1p vs 200일선 위 +3.3p).
    # 그래도 바꾸지 않는다 — 상하님이 정하신 것은 실측과 달라도 안 바꾸고
    # 보고만 한다(CLAUDE.md 0-1 나). 정해 둔 날에 다시 잰다.
    q20 = qqq.rolling(20, min_periods=20).mean()
    q60 = qqq.rolling(60, min_periods=60).mean()
    q120 = qqq.rolling(120, min_periods=120).mean()
    q200 = qqq.rolling(200, min_periods=200).mean()
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    ma200 = ((qqq > q20) & (q20 > q60) & (q60 > q120) & (q120 > q200)
             & (qdrop > -5.0)).fillna(False)
    print(f"\n  1층 = 정배열(종가>20>60>120>200일선) + 고점 -5% 안 — "
          f"10년 {int(ma200.sum()):,}일 / {len(dates):,}일 "
          f"({ma200.mean() * 100:.0f}%)")
    up = pd.DataFrame(np.repeat(ma200.to_numpy()[:, None], close.shape[1], axis=1),
                      index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    # ── 신호를 한 줄씩 펴 놓는다 ─────────────────────────────────────────
    rows_idx, cols_idx = np.nonzero(net.to_numpy())
    tickers = np.array(close.columns)[cols_idx]
    frame = pd.DataFrame({
        "date": dates[rows_idx],
        "ticker": tickers,
        "theme": [main_theme.get(t, "") for t in tickers],
        "prox": prox.to_numpy()[rows_idx, cols_idx],
        "cap_rank": cap_rank.to_numpy()[rows_idx, cols_idx],
        "gain60": gain60.to_numpy()[rows_idx, cols_idx],
        **{f"r{h}": rets[h].to_numpy()[rows_idx, cols_idx] for h, _n in HOLDS},
    })
    frame["half"] = np.where(frame["date"] < pd.Timestamp("2021-08-04"),
                             "2016~2021", "2021~2026")
    frame.to_csv(ROOT / "research" / "_data" / "layer3_final_trades.csv", index=False)

    def block(title, column, bands, event_level=False):
        print(f"\n{'=' * 100}\n### {title}"
              + ("  — **같은 날·같은 테마를 한 사건으로 묶어서**" if event_level else "")
              + f"\n{'=' * 100}")
        data = frame
        if event_level:
            data = (frame.groupby(["date", "theme"], as_index=False)
                    .agg({column: "mean", **{f"r{h}": "mean" for h, _n in HOLDS}}))
        header = "".join(f"{n:>28}" for _h, n in HOLDS)
        print(f"  {'칸':<20}{'N':>7}{header}")
        print(f"  {'':<20}{'':>7}" + "".join(f"{'승률   중앙값   평균':>28}" for _h in HOLDS))
        base = {h: data[f"r{h}"].dropna() for h, _n in HOLDS}
        for lo, hi, label in bands:
            sel = data[(data[column] >= lo) & (data[column] < hi)]
            cells = ""
            for hold, _n in HOLDS:
                values = sel[f"r{hold}"].dropna()
                if values.size < 30:
                    cells += f"{'자리 부족':>28}"
                    continue
                win = (values > 0).mean() * 100
                gap = float(np.median(values)) - float(np.median(base[hold]))
                cells += (f"{win:>10.0f}번{np.median(values):>8.1f}%"
                          f"{values.mean():>8.1f}%")
            print(f"  {label:<20}{len(sel):>7,}{cells}")
        cells = ""
        for hold, _n in HOLDS:
            values = base[hold]
            cells += (f"{(values > 0).mean() * 100:>10.0f}번{np.median(values):>8.1f}%"
                      f"{values.mean():>8.1f}%")
        print(f"  {'── 그물 전체 ──':<20}{len(data):>7,}{cells}")

    def halves(title, column, bands):
        print(f"\n  ── {title} · 두 기간으로 갈라 (1년 보유) ──")
        print(f"  {'칸':<20}" + "".join(f"{h:>22}" for h in ("2016~2021", "2021~2026")))
        for lo, hi, label in bands:
            cells = ""
            for half in ("2016~2021", "2021~2026"):
                sel = frame[(frame["half"] == half) & (frame[column] >= lo)
                            & (frame[column] < hi)]["r250"].dropna()
                cells += f"{'자리 부족':>22}" if sel.size < 30 else \
                    f"{len(sel):>7,}건{(sel > 0).mean() * 100:>6.0f}번{np.median(sel):>7.1f}%"
            print(f"  {label:<20}{cells}")

    prox_bands = ((95, 999, "A 근접도 95%↑"), (90, 95, "A 90~95%"),
                  (85, 90, "A 85~90%"), (0, 85, "A 85% 미만"))
    cap_bands = ((1, 26, "B 시총 1~25위"), (26, 51, "B 26~50위"),
                 (51, 101, "B 51~100위"), (101, 9999, "B 101위 아래"))
    gain_bands = ((-999, 20, "C 60일 20% 미만"), (20, 35, "C 20~35%"),
                  (35, 50, "C 35~50%"), (50, 75, "C 50~75%"), (75, 9999, "C 75%↑"))

    for title, column, bands in (("A · 산업(테마) 근접도", "prox", prox_bands),
                                 ("B · 그날 시총 순위", "cap_rank", cap_bands),
                                 ("C · 뚫기 전 60일 상승률", "gain60", gain_bands)):
        block(title, column, bands)
        halves(title, column, bands)
        block(title, column, bands, event_level=True)

    print(f"\n  원거래 {len(frame):,}줄 저장 → research/_data/layer3_final_trades.csv")
    print("  ※ 시가총액은 **그날** 발행주식수로 만들었다(위 [확인] 표 참고).")
    print("  ※ 테마 명부·종목 명부는 오늘 것이다 — 이 편향은 남는다.")


if __name__ == "__main__":
    main()
