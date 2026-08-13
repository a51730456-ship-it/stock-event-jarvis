"""3층 최종 측정 — **버그 셋을 다 고치고** (2026-08-13).

## 고친 버그 셋

**① 시총이 분할일에 열 배씩 튀었다.**
조정주가(분할 반영)에 실제 주식수(분할 미반영)를 곱했다. 2016년 NVDA 시총이
14억 달러로 나왔다(실제 약 580억).

**② 분할배수를 하루 늦게 걷었다.**
야후의 분할 시각이 09:30인데 일봉 날짜는 00:00이라, 분할 당일에도 옛 배수를
한 번 더 곱했다. 54건 중 29건에서 시총이 하루 10~25배로 튀었다.
**시총 순위는 하루만 틀려 영향이 작지만, 테마 점수는 그 가짜 값이 252일 최고로
들어가 1년 내내 남는다.**

**③ 야후의 주식수 보고일이 분할일과 어긋난다.**
분할 전 보고가 이미 분할 후 주식수로 고쳐져 있는 종목이 있어(AAPL 등) 배수가
두 번 곱해졌다. 이웃 보고의 가운데값과 1.8배 넘게 어긋나는 점을 지워 해결했다.
→ 분할 47건 중 튀는 것 **1건**만 남았고, NVDA 2016년말 시총이 566억 달러로
실제(약 580억)와 맞아떨어졌다.

**④ 같은 돌파를 여러 날 셌다.**
한 번 뚫은 종목이 3일·4일·…·10일에 각각 잡혀 최대 여덟 번 세어졌다.
**한 돌파는 처음 걸린 날 한 번만 센다.** 6,215줄 → 1,459건.

## 새로 넣은 것

**같은 날 후보끼리 견주기** — 한 날에 여러 종목이 뜰 때 그 항목이 붙은 종목이
나머지를 이겼는지 본다. 배점은 결국 그날 목록 안에서 순서를 정하는 것이므로
이것이 진짜 시험이다.

**표본 30건 미만은 「못 잼」으로 적는다.**

1층·2층 고정 — QQQ 정배열 + 고점 −5% 안 · 신고가 뒤 3~10일 · 고점 −4~−15%.

쓰는 법:  python research/us_layer3_v2.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

OUT = ROOT / "research" / "_data" / "layer3_v2_events.csv"


def build() -> tuple:
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

    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60 = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()
    breakout_id = order.where(is_new_high).ffill()

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
    for stock, names in themes_of.items():
        prox[stock] = prox_frame[names].max(axis=1)

    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    ma = {n: qqq.rolling(n, min_periods=n).mean() for n in (20, 60, 120, 200)}
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    gate = ((qqq > ma[20]) & (ma[20] > ma[60]) & (ma[60] > ma[120])
            & (ma[120] > ma[200]) & (qdrop > -5.0)).fillna(False)
    up = pd.DataFrame(np.repeat(gate.to_numpy()[:, None], close.shape[1], axis=1),
                      index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    ret1y = (close.shift(-250) / opens.shift(-1) - 1.0) * 100.0
    rows_idx, cols_idx = np.nonzero(net.to_numpy())
    frame = pd.DataFrame({
        "date": dates[rows_idx],
        "ticker": np.array(close.columns)[cols_idx],
        "bid": breakout_id.to_numpy()[rows_idx, cols_idx],
        "wait": days_since.to_numpy()[rows_idx, cols_idx],
        "pullback": -from_peak.to_numpy()[rows_idx, cols_idx],
        "cap": cap_rank.to_numpy()[rows_idx, cols_idx],
        "prox": prox.to_numpy()[rows_idx, cols_idx],
        "gain60": gain60.to_numpy()[rows_idx, cols_idx],
        "ret": ret1y.to_numpy()[rows_idx, cols_idx],
    })
    events = (frame.sort_values("date")
              .drop_duplicates(["ticker", "bid"], keep="first")
              .dropna(subset=["ret"]).copy())
    events["half"] = np.where(events["date"] < pd.Timestamp("2021-08-04"), "앞", "뒤")

    base = (up & close.notna()).fillna(False)
    baseline = ret1y.where(base).to_numpy().ravel()
    return events, baseline[~np.isnan(baseline)], len(frame)


def main() -> None:
    events, baseline, raw_rows = build()

    print(f"\n{'=' * 94}\n### 3층 최종 — 버그 넷 고치고\n{'=' * 94}")
    print(f"  줄 수(같은 돌파 여러 날) {raw_rows:,}줄")
    print(f"  **사건 수(한 돌파 한 번) {len(events):,}건** ← 이것으로 잰다")
    print(f"\n  기준선 아무 종목이나  100번 중 {(baseline > 0).mean() * 100:.0f}번 · "
          f"{np.median(baseline):+.1f}%")
    print(f"  목록 전체            100번 중 {(events.ret > 0).mean() * 100:.0f}번 · "
          f"{events.ret.median():+.1f}%")

    def block(title, column, bands):
        print(f"\n  ── {title} ──")
        print(f"     {'칸':<16}{'N':>6}{'이긴 횟수':>10}{'수익률':>9}{'앞':>7}{'뒤':>7}")
        for low, high_, label in bands:
            sel = events[(events[column] >= low) & (events[column] < high_)]
            if len(sel) < 30:
                print(f"     {label:<16}{len(sel):>6}   못 잼 (30건 미만)")
                continue
            cells = ""
            for half in ("앞", "뒤"):
                part = sel[sel.half == half].ret
                cells += f"{'—':>7}" if len(part) < 20 else f"{(part > 0).mean() * 100:>6.0f}번"
            print(f"     {label:<16}{len(sel):>6,}{(sel.ret > 0).mean() * 100:>9.0f}번"
                  f"{sel.ret.median():>8.1f}%{cells}")

    block("① 회사 크기", "cap", ((1, 26, "1~25위"), (26, 51, "26~50위"),
                             (51, 101, "51~100위"), (101, 9999, "101위 아래")))
    block("② 테마 상태", "prox", ((95, 999, "95%↑ 뜨거움"), (85, 95, "85~95% 쉼"),
                              (0, 85, "85% 미만 식음")))
    block("③ 뚫기 전 60일", "gain60", ((-999, 20, "20% 미만"), (20, 35, "20~35%"),
                                   (35, 50, "35~50%"), (50, 75, "50~75%"),
                                   (75, 9999, "75%↑")))
    block("④ 눌린 폭", "pullback", ((4, 6, "4~6%"), (6, 8, "6~8%"), (8, 10, "8~10%"),
                                 (10, 12, "10~12%"), (12, 16, "12~15%")))
    block("⑤ 돌파 뒤 며칠", "wait", ((3, 5, "3~4일"), (5, 7, "5~6일"),
                                (7, 9, "7~8일"), (9, 11, "9~10일")))

    print("\n  ── 같은 날 후보끼리 견주면 (한 날에 여럿 뜰 때 순서를 가르나) ──")
    tests = (
        ("시총 1~25위", events.cap <= 25),
        ("시총 51~100위", (events.cap >= 51) & (events.cap <= 100)),
        ("테마 85~95%", (events.prox >= 85) & (events.prox < 95)),
        ("60일 75%↑", events.gain60 > 75),
        ("눌린 폭 8~10%", (events.pullback >= 8) & (events.pullback < 10)),
        ("눌린 폭 12~15%", (events.pullback >= 12) & (events.pullback < 16)),
    )
    for label, mask in tests:
        table = events.assign(g=mask).groupby(["date", "g"]).ret.mean().unstack().dropna()
        if len(table) < 30:
            print(f"     {label:<16}같이 뜬 날 {len(table)}일 — 못 잼")
            continue
        gap = table[True] - table[False]
        print(f"     {label:<16}같이 뜬 날 {len(gap):>4}일 · 나머지를 이긴 날 "
              f"{100 * (gap > 0).mean():>3.0f}% · 차이 가운데 {gap.median():+.1f}%p")

    events.to_csv(OUT, index=False)
    print(f"\n  사건 {len(events):,}건 저장 → {OUT.relative_to(ROOT)}")
    print("  ※ 테마 명부는 여전히 오늘 것이다 — ②번에 이 편향이 남는다.")
    print("  ※ 명부는 오늘 살아 있는 199종목이라 망한 회사가 빠져 있다.")


if __name__ == "__main__":
    main()
