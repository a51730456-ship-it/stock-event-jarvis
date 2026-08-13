"""3층을 **버그 둘을 고치고** 다시 잰다 (2026-08-13).

## 고친 것 둘

**① 시가총액이 분할일에 열 배씩 튀었다.**
조정주가(분할 반영)에 실제 주식수(분할 미반영)를 곱했다. 2016년 NVDA 시총이
14억 달러로 나왔다(실제 약 580억). `us_shares_history.daily_market_cap`에서
**그 뒤 분할배수를 곱해** 바로잡았다. 10년 사이 200종목 중 **40개(20%)**가 영향받았다.

**② 같은 돌파를 여러 날 셌다.**
한 번 전고점을 뚫은 종목이 3일·4일·…·10일에 각각 신호로 잡혀 **최대 여덟 번**
세어졌다. 6,215줄이 실제로는 한 번의 사건 1,700개쯤이다.
**한 돌파는 처음 걸린 날 한 번만 센다.**

두 번째 것은 특히 중요하다 — 같은 사건을 여덟 번 세면 "10년에 6,215번 확인했다"는
말이 거짓이 된다. 실제로는 그 8분의 1만큼만 확인한 것이다.

1층·2층은 고정 — QQQ 정배열 + 고점 −5% 안 · 신고가 뒤 3~10일 · 고점 −4~−15%.

쓰는 법:  python research/us_layer3_fixed.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))


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

    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60 = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()
    # 어느 돌파에서 나온 신호인지 — 같은 돌파를 한 번만 세려고 표를 붙인다.
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
    ret6m = (close.shift(-120) / opens.shift(-1) - 1.0) * 100.0

    rows_idx, cols_idx = np.nonzero(net.to_numpy())
    frame = pd.DataFrame({
        "date": dates[rows_idx],
        "ticker": np.array(close.columns)[cols_idx],
        "bid": breakout_id.to_numpy()[rows_idx, cols_idx],
        "wait": days_since.to_numpy()[rows_idx, cols_idx],
        "drop": -from_peak.to_numpy()[rows_idx, cols_idx],
        "cap_rank": cap_rank.to_numpy()[rows_idx, cols_idx],
        "prox": prox.to_numpy()[rows_idx, cols_idx],
        "gain60": gain60.to_numpy()[rows_idx, cols_idx],
        "r1y": ret1y.to_numpy()[rows_idx, cols_idx],
        "r6m": ret6m.to_numpy()[rows_idx, cols_idx],
    })
    # **한 돌파는 한 번만** — 그 돌파에서 처음 걸린 날만 남긴다.
    once = frame.sort_values("date").drop_duplicates(["ticker", "bid"], keep="first")
    once = once.copy()
    once["half"] = np.where(once["date"] < pd.Timestamp("2021-08-04"), "앞", "뒤")

    base = (up & close.notna()).fillna(False)
    bv = ret1y.where(base).to_numpy().ravel(); bv = bv[~np.isnan(bv)]

    print(f"\n{'=' * 96}\n### 버그 둘을 고치고 다시 — 3층\n{'=' * 96}")
    print(f"  줄 수(같은 돌파 여러 날) {len(frame):,}줄")
    print(f"  **사건 수(한 돌파 한 번)  {len(once):,}건**  ← 이것으로 잰다")
    print(f"  1년 결과가 나온 사건      {int(once['r1y'].notna().sum()):,}건")
    print(f"\n  기준선 · 아무 종목이나  100번 중 {(bv > 0).mean() * 100:.0f}번 · "
          f"{np.median(bv):+.1f}%")
    v = once["r1y"].dropna()
    print(f"  목록 전체              100번 중 {(v > 0).mean() * 100:.0f}번 · "
          f"{np.median(v):+.1f}%")

    def block(title, column, bands):
        print(f"\n  ── {title} ──")
        print(f"     {'칸':<16}{'N':>6}{'이긴 횟수':>10}{'수익률':>9}{'앞':>8}{'뒤':>8}")
        for a, b, lab in bands:
            sel = once[(once[column] >= a) & (once[column] < b)]
            values = sel["r1y"].dropna()
            if values.size < 30:
                print(f"     {lab:<16}{len(sel):>6}   자리 부족")
                continue
            cells = ""
            for half in ("앞", "뒤"):
                hv = sel[sel["half"] == half]["r1y"].dropna()
                cells += f"{'—':>8}" if hv.size < 20 else f"{(hv > 0).mean() * 100:>7.0f}번"
            print(f"     {lab:<16}{values.size:>6,}{(values > 0).mean() * 100:>9.0f}번"
                  f"{np.median(values):>8.1f}%{cells}")

    block("① 회사 크기 (고친 시총)", "cap_rank",
          ((1, 26, "1~25위"), (26, 51, "26~50위"), (51, 101, "51~100위"),
           (101, 9999, "101위 아래")))
    block("② 테마 상태 (고친 시총)", "prox",
          ((95, 999, "95%↑"), (90, 95, "90~95%"), (85, 90, "85~90%"), (0, 85, "85% 미만")))
    block("③ 뚫기 전 60일 상승", "gain60",
          ((-999, 20, "20% 미만"), (20, 35, "20~35%"), (35, 50, "35~50%"),
           (50, 75, "50~75%"), (75, 9999, "75%↑")))
    block("④ 지금 눌린 폭", "drop",
          ((4, 6, "4~6%"), (6, 8, "6~8%"), (8, 10, "8~10%"), (10, 12, "10~12%"),
           (12, 16, "12~15%")))
    block("⑤ 돌파 뒤 며칠 (지피티 지적)", "wait",
          ((3, 5, "3~4일"), (5, 7, "5~6일"), (7, 9, "7~8일"), (9, 11, "9~10일")))

    once.to_csv(ROOT / "research" / "_data" / "layer3_events.csv", index=False)
    print(f"\n  사건 {len(once):,}건 저장 → research/_data/layer3_events.csv")
    print("  ※ 시총은 분할배수를 곱해 바로잡았다. 테마 명부는 여전히 오늘 것이다.")


if __name__ == "__main__":
    main()
