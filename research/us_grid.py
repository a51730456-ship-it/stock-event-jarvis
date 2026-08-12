"""**시장 조건 × 종목 조건**이 맞는지만 잰다 — 상하님 표 두 장 재현 (2026-08-12).

상하님 지시 — "지금 배점과 같이 돌릴 필요 없지. 그냥 시장이 종목이 맞는지를 돌려야지."

맞는 말이다. 상하님 설명서(`docs/US_METHOD_TABLES.md`, `assets/us_method_*.png`)에는
**배점이 없다.** '시장이 이 상태일 때 이런 자리의 종목을 산다'는 격자 지도다.
그러니 재야 할 것은 점수가 아니라 **격자의 칸이 맞는가**다.

여기서 하는 일은 하나다 — **상하님 표 1·표 2를 앱이 실제로 뒤지는 명부로 그대로 다시
그린다.** 상하님 표는 나스닥100 96종목으로 잰 것이고, 앱은 대형주 198종목을 뒤진다.
명부가 다르면 숫자도 달라진다. 같으면 설명서를 그대로 코드로 옮기면 된다.

세 가지를 안 한다 — 배점 안 매긴다 · 종목 안 고른다 · 순위 안 매긴다.
칸에 들어온 것을 **다 샀을 때** 어땠는지만 본다.

사는 것은 신호 **다음 거래일 시가**, 파는 것은 정해진 거래일 뒤 **종가**.
3개월=60 · 6개월=120 · 1년=250거래일.

쓰는 법:  python research/us_grid.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = (60, 120, 250)          # 3개월 · 6개월 · 1년


def cell(rets_by_hold: dict, net: pd.DataFrame) -> dict:
    out = {}
    for hold, rets in rets_by_hold.items():
        values = rets.where(net).stack().dropna()
        out[hold] = (len(values), (values > 0).mean() * 100 if len(values) else np.nan,
                     values.median() if len(values) else np.nan)
    return out


def episodes(flag: pd.Series) -> int:
    """참이 이어지는 덩어리 수 — '몇 번 왔나'."""
    return int((flag & ~flag.shift(1, fill_value=False)).sum())


def print_row(label: str, count_text: str, result: dict) -> None:
    cells = ""
    for hold in HOLDS:
        n, win, mid = result[hold]
        cells += "     자리없음     " if not n else f"{mid:>7.1f}% ({win:>4.1f}%)"
    print(f"  {label:<22}{count_text:>16}   {cells}")


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq, qqq_open = wide["close"]["QQQ"], wide["open"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens = wide["open"][stocks]
    dates = close.index

    rets = {h: (close.shift(-h) / opens.shift(-1) - 1.0) * 100.0 for h in HOLDS}
    qqq_rets = {h: (qqq.shift(-h) / qqq_open.shift(-1) - 1.0) * 100.0 for h in HOLDS}

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    high52 = high.rolling(252, min_periods=252).max()
    days_ago = order - order.where(high >= high52).ffill()
    from_high = (close / high52 - 1.0) * 100.0
    qqq_sma200 = qqq.rolling(200, min_periods=200).mean()
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    def spread(flag):
        return pd.DataFrame(np.repeat(flag.to_numpy()[:, None], close.shape[1], axis=1),
                            index=dates, columns=close.columns)

    valid = close.notna() & high52.notna()
    header = (f"  {'':<22}{'':>16}   " + "".join(f"{h // 21}개월{'':>10}" if h < 250
                                                 else f"1년{'':>12}" for h in HOLDS))

    # ══ 표 1 — 정상적인 상승일 때 ═════════════════════════════════════════
    market_on = (qqq > qqq_sma200) & (qqq_drop > -10.0)
    print(f"\n{'=' * 92}\n### 표 1 재현 — 정상적인 상승일 때"
          f"\n### 장세: 나스닥 200일선 위 + 고점에서 10% 안쪽일 때만\n{'=' * 92}")
    print(f"  명부 {len(stocks)}종목 · {dates[0].date()} ~ {dates[-1].date()}"
          f" · 장세 조건에 맞은 날 {int(market_on.sum()):,}일 / {len(dates):,}일")
    print(header + "\n" + f"  {'신고가 뒤 · 눌린 폭':<22}{'건수 (신호일)':>16}")
    m = spread(market_on) & valid
    for wait_lo, wait_hi in ((1, 3), (3, 5), (5, 10)):
        for drop_lo, drop_hi in ((-10.0, -6.0), (-15.0, -10.0)):
            net = (m & (days_ago >= wait_lo) & (days_ago <= wait_hi)
                   & (from_high >= drop_lo) & (from_high <= drop_hi)).fillna(False)
            total = int(net.to_numpy().sum())
            days = int(net.any(axis=1).sum())
            print_row(f"{wait_lo}~{wait_hi}일 · {abs(drop_hi):.0f}~{abs(drop_lo):.0f}%",
                      f"{total:,} ({days:,}일)", cell(rets, net))

    print("\n  ── 장세 조건을 뺐을 때 (앱은 지금 안 거른다) ──")
    for wait_lo, wait_hi in ((1, 3), (3, 5)):
        for drop_lo, drop_hi in ((-10.0, -6.0), (-15.0, -10.0)):
            net = (valid & (days_ago >= wait_lo) & (days_ago <= wait_hi)
                   & (from_high >= drop_lo) & (from_high <= drop_hi)).fillna(False)
            total = int(net.to_numpy().sum())
            days = int(net.any(axis=1).sum())
            print_row(f"{wait_lo}~{wait_hi}일 · {abs(drop_hi):.0f}~{abs(drop_lo):.0f}%",
                      f"{total:,} ({days:,}일)", cell(rets, net))

    print("\n  ── 앱이 지금 쓰는 칸 · 그리고 견줄 것 ──")
    app = (valid & (days_ago >= 1) & (days_ago <= 5)
           & (from_high >= -15.0) & (from_high <= -4.0)).fillna(False)
    print_row("앱: 1~5일 · 4~15%", f"{int(app.to_numpy().sum()):,}", cell(rets, app))
    shallow = (valid & (days_ago >= 1) & (days_ago <= 5)
               & (from_high > -6.0) & (from_high <= -4.0)).fillna(False)
    print_row("그중 4~6%만", f"{int(shallow.to_numpy().sum()):,}", cell(rets, shallow))
    anyday = valid.fillna(False)
    print_row("아무 날 아무 종목", f"{int(anyday.to_numpy().sum()):,}", cell(rets, anyday))
    print_row("QQQ 아무 날", "—",
              {h: (len(qqq_rets[h].dropna()),
                   (qqq_rets[h].dropna() > 0).mean() * 100,
                   qqq_rets[h].dropna().median()) for h in HOLDS})

    # ══ 표 2 — 나스닥 하락율 대비 상승수익률 ═══════════════════════════════
    print(f"\n\n{'=' * 92}\n### 표 2 재현 — 나스닥 하락율 대비 상승수익률\n{'=' * 92}")
    print(header + "\n" + f"  {'나스닥 하락 · 종목 낙폭':<22}{'건수 (사건수)':>16}")
    bands = ((-12.0, -6.0), (-18.0, -12.0), (-24.0, -18.0), (-30.0, -24.0), (-100.0, -30.0))
    for lo, hi in bands:
        inside = (qqq_drop <= hi) & (qqq_drop >= lo)
        events = episodes(inside.fillna(False))
        for s_lo, s_hi in ((-30.0, -20.0), (-50.0, -30.0)):
            net = (spread(inside) & valid & (from_high <= s_hi)
                   & (from_high >= s_lo)).fillna(False)
            total = int(net.to_numpy().sum())
            name = f"{abs(hi):.0f}~{abs(lo):.0f}%" if lo > -100 else "30% 아래"
            print_row(f"{name} · 종목 {abs(s_hi):.0f}~{abs(s_lo):.0f}%",
                      f"{total:,} ({events}번)", cell(rets, net))
        print()

    print("  ── 앱이 지금 쓰는 칸 ──")
    lo, hi = j3.CRASH_MARKET_BAND
    inside = (qqq_drop <= hi) & (qqq_drop >= lo)
    ep = (inside & ~inside.shift(1, fill_value=False)).cumsum().where(inside)
    mark = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": ep, "d": qqq_drop}).dropna().groupby("e"):
        mark.loc[group["d"].idxmin()] = True
    c_lo, c_hi = j3.CRASH_REBOUND_RULES[0]["band"]
    net = (spread(mark) & valid & (from_high <= c_hi) & (from_high >= c_lo)).fillna(False)
    print_row("앱: 10~20% 최저일 · 20~30%",
              f"{int(net.to_numpy().sum()):,} ({int(mark.sum())}번)", cell(rets, net))
    print_row("아무 날 20~50% 빠진 종목",
              f"{int(((from_high <= -20) & (from_high >= -50) & valid).to_numpy().sum()):,}",
              cell(rets, ((from_high <= -20) & (from_high >= -50) & valid).fillna(False)))

    print("\n※ 칸 안은 '가운데 수익률 (승률)'. 사는 것은 신호 다음 거래일 시가, "
          "파는 것은 정해진 거래일 뒤 종가."
          f"\n※ 명부 {len(stocks)}종목 · 10년 · **살아남은 대형주만**(망한 종목 없음)."
          "\n※ 상하님 표는 나스닥100 96종목으로 잰 것이라 숫자가 조금 다를 수 있다.")


if __name__ == "__main__":
    main()
