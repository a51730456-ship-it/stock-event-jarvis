"""상승장 **신고가 눌림매수**만 — 물음 다섯 개로 갈라 영향부터 본다 (2026-08-13).

상하님 지시 —
*"기준 자체가 상승장에서 52주 고점 뚫고 다시 눌릴 때 **언제** 매수하는 게,
**어떤 종목**, **어떤·몇 개 테마**, **어떤 눌린 폭** … 이런 것들이 **영향이 있냐부터**
확인해 봐야 될 것 아니냐. 여기서 급락 후 반등 종목이나 그 기준을 잡으면 안 되는 거야.
그래서 상승장 신고가 눌림매수 기준만 먼저 하자는 이야기야."*

**맞는 지적이다.** 그전 후보 목록은 급락 파트에서 그대로 빌려온 것이 섞여 있었다
('테마가 덜 빠졌나'·'최근 11일에 빠졌나'는 급락에서 만든 잣대다). 눌림매수는
**고점을 뚫은 종목이 잠깐 쉬는 자리**를 사는 것이라 물어야 할 것이 다르다.

## 다섯 축 (상하님 물음 그대로)

  [언제]     신고가 뒤 며칠에 사나 · 눌림이 멈춘 걸 보고 사나
  [눌린 폭]  얼마나 눌렸을 때 사나
  [어떤 종목] 뚫을 때 힘이 셌나 · 뚫기 전에 얼마나 올랐나 · 지수보다 센가 ·
             눌릴 때 거래량이 줄었나 · 변동성 · 크기
  [어떤 테마] 그 테마가 통째로 고점 근처인가 · 테마가 같이 오르나
  [몇 개 테마] 같은 테마에서 **동시에 몇 종목**이 이 자리에 왔나 ·
             그 종목이 테마를 몇 개 걸치나

## 무엇을 먼저 보나 — **배점이 아니라 영향**

각 후보의 **승률차**와 **수익률차**를 그대로 낸다. 방향(+/−)과 크기를 보고
"이 축은 영향이 있다 / 없다"를 먼저 가른다. 배점은 그다음이다.

그물은 앱 그대로 — 나스닥 200일선 위 + 고점 −10% 안 · 신고가 뒤 3~10일 ·
눌린 폭 −4~−15% · 테마 있는 종목.

쓰는 법:  python research/us_pullback_logic.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_edge_table import HOLDS, edge  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402


def build(gate_drop=None):
    """그 시장 조건에서의 (그물, 축, 값들). 여러 문턱으로 돌리려고 쪼갰다."""
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][stocks], wide["high"][stocks], wide["low"][stocks]
    opens, volume = wide["open"][stocks], wide["volume"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20)))

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    vol20 = volume.rolling(20, min_periods=10).mean()
    # 뚫던 날의 거래량 배수를 그 뒤 며칠 동안 들고 간다 — '돌파가 셌나'.
    burst = (volume / vol20).where(is_new_high).ffill()
    vol_now = volume.rolling(3, min_periods=2).mean() / vol20
    gain60_at_peak = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()
    rs20 = (close.pct_change(20) - qqq.pct_change(20).values[:, None]) * 100.0
    turnover = (close * volume).rolling(20, min_periods=10).mean()
    shares = load_shares().reindex(close.columns)
    cap_rank = close.mul(shares, axis=1).rank(axis=1, ascending=False, method="min")
    touched20 = (low <= sma20).rolling(5, min_periods=1).max().astype(bool)
    up_today = close > prev
    green = close > opens

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    theme_count = pd.DataFrame(
        np.repeat(np.array([[len(themes_of.get(s, ())) for s in close.columns]]),
                  len(dates), axis=0), index=dates, columns=close.columns)

    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    # **하락장 날은 한 줄도 안 쓴다** (2026-08-13 상하님 지시 — "나스닥이 상승과
    # 가깝거나 상승일 때 기준을 잡고 … 하락장일 때 종목 검색하지 말고").
    # 앱 그물은 고점 -10%까지 보는데 그건 이미 조정에 들어간 자리다.
    # 환경변수 US_GATE_DROP으로 문턱을 바꿔 가며 갈라 잰다.
    import os

    if gate_drop is None:
        gate_drop = float(os.environ.get("US_GATE_DROP",
                                         j3.BREAKOUT_MARKET_MAX_DROP))
    up_day = (qqq > qqq.rolling(200, min_periods=200).mean()) & (qdrop > gate_drop)
    market_days = int(up_day.sum())
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up_wide & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total = int(net.to_numpy().sum())

    # 같은 테마에서 **동시에 몇 종목**이 이 자리에 와 있나 (앱의 '같이 걸린 종목').
    together = pd.DataFrame(0, index=dates, columns=close.columns)
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if not members:
            continue
        count = net[members].sum(axis=1)
        for stock in members:
            together[stock] = np.maximum(together[stock], count)

    # ── 빠져 있던 잣대들 (2026-08-13 상하님 "뭐 중요한 기준이 빠졌는지도 찾아보고") ──
    # 눌림매수에서 물어야 하는데 여태 한 번도 안 잰 것들이다.
    qdrop_wide = pd.DataFrame(np.repeat(qdrop.to_numpy()[:, None], close.shape[1], axis=1),
                              index=dates, columns=close.columns)
    # ① 지수도 같이 눌렸나, 종목만 눌렸나 — 종목 눌림에서 지수 눌림을 뺀 값.
    solo_drop = from_peak - qdrop_wide
    # ② 눌림 저점을 찍고 며칠 지났나 — 신고가 뒤 구간의 최저 종가에서 며칠.
    since_low = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    roll_min = close.rolling(6, min_periods=2).min()
    at_low = close <= roll_min * 1.001
    since_low = order - order.where(at_low).ffill()
    # ③ ATR 대비 몇 배 눌렸나 — 원래 잘 흔들리는 종목인지 감안한 눌림 깊이.
    drop_in_atr = from_peak.abs() / atr.replace(0, np.nan)
    # ④ 사상 최고가를 뚫었나 — 위에 물린 사람이 없다.
    all_time = high.cummax()
    at_all_time = (peak >= all_time.shift(1) * 0.999)
    # ⑤ 뚫기 전에 얼마나 오래 다졌나 — 신고가 직전 60일의 고저 폭이 좁을수록 다진 것.
    base_range = ((high.rolling(60, min_periods=40).max()
                   / low.rolling(60, min_periods=40).min() - 1.0) * 100.0
                  ).where(is_new_high).ffill()

    near_high_share = per_theme((from_high > -5.0).astype(float) * 100.0, j3.US_THEMES)
    rose5_share = per_theme((close.pct_change(5) > 0).astype(float) * 100.0, j3.US_THEMES)
    above20_share = per_theme((close > sma20).astype(float) * 100.0, j3.US_THEMES)

    axes = {
        "① 언제 사나 — 신고가 뒤 며칠": {
            "신고가 뒤 3~4일": (days_since >= 3) & (days_since <= 4),
            "신고가 뒤 5~6일": (days_since >= 5) & (days_since <= 6),
            "신고가 뒤 7~8일": (days_since >= 7) & (days_since <= 8),
            "신고가 뒤 9~10일": (days_since >= 9) & (days_since <= 10),
        },
        "② 언제 사나 — 눌림이 멈춘 걸 보고": {
            "오늘 어제보다 올랐다": up_today,
            "오늘 양봉이다": green,
            "20일선에 닿았다 (최근 5일)": touched20,
            "아직 20일선 위에 있다": close > sma20,
        },
        "③ 어떤 눌린 폭": {
            "4~6% 눌림": (from_peak <= -4.0) & (from_peak > -6.0),
            "6~8% 눌림": (from_peak <= -6.0) & (from_peak > -8.0),
            "8~10% 눌림": (from_peak <= -8.0) & (from_peak > -10.0),
            "10~12% 눌림": (from_peak <= -10.0) & (from_peak > -12.0),
            "12~15% 눌림": (from_peak <= -12.0) & (from_peak >= -15.0),
        },
        "④ 어떤 종목 — 뚫을 때·뚫기 전": {
            "뚫던 날 거래량 1.5배↑": burst >= 1.5,
            "뚫던 날 거래량 2배↑": burst >= 2.0,
            "뚫기 전 60일 20%↓ 올랐다": gain60_at_peak <= 20.0,
            "뚫기 전 60일 20~50% 올랐다": (gain60_at_peak > 20.0) & (gain60_at_peak <= 50.0),
            "뚫기 전 60일 50%↑ 올랐다": gain60_at_peak > 50.0,
            "20일 상대강도 지수보다 +5%p↑": rs20 >= 5.0,
            "20일 상대강도 지수보다 아래": rs20 < 0.0,
        },
        "⑤ 어떤 종목 — 눌리는 모양·성질": {
            "눌리며 거래량 줄었다 (<0.9)": vol_now < 0.9,
            "눌리며 거래량 늘었다 (>1.2)": vol_now > 1.2,
            "주봉 오름세 (정배열)": aligned,
            "변동성 3% 이내": atr <= 3.0,
            "변동성 3~5%": (atr > 3.0) & (atr <= 5.0),
            "변동성 5%↑": atr > 5.0,
            "거래대금 상위 50": turnover.rank(axis=1, ascending=False, method="min") <= 50,
            "빅50 안": cap_rank <= 50,
        },
        "⑥ 몇 개 테마 — 같이 걸린 종목 수": {
            "같은 테마에서 나 혼자": together <= 1,
            "같은 테마 2개↑ 동반": together >= 2,
            "같은 테마 3개↑ 동반": together >= 3,
            "같은 테마 4개↑ 동반": together >= 4,
            "테마를 2개↑ 걸친 종목": theme_count >= 2,
        },
        "⑧ 빠져 있던 잣대 — 지수 대비·저점·다지기": {
            "지수보다 3%p↑ 더 눌렸다": solo_drop <= -3.0,
            "지수만큼만 눌렸다 (차이 3%p 안)": solo_drop > -3.0,
            "눌림 저점 찍고 1~2일 지났다": (since_low >= 1) & (since_low <= 2),
            "아직 저점 갱신 중 (0일)": since_low <= 0,
            "ATR 2배 이내로 눌렸다": drop_in_atr <= 2.0,
            "ATR 3배 넘게 눌렸다": drop_in_atr > 3.0,
            "사상 최고가를 뚫었다": at_all_time,
            "뚫기 전 60일 고저 30% 이내(다졌다)": base_range <= 30.0,
            "뚫기 전 60일 고저 50%↑(요동쳤다)": base_range > 50.0,
        },
        "⑦ 어떤 테마 — 테마 자체의 상태": {
            "테마가 통째로 고점 근처 상위3": top_rank(near_high_share, themes_of,
                                             close.columns, 3),
            "테마가 통째로 고점 근처 상위7": top_rank(near_high_share, themes_of,
                                             close.columns, 7),
            "테마가 같이 오르나 상위3": top_rank(rose5_share, themes_of, close.columns, 3),
            "테마가 같이 오르나 상위7": top_rank(rose5_share, themes_of, close.columns, 7),
            "테마 20일선 위 상위3": top_rank(above20_share, themes_of, close.columns, 3),
            "테마 20일선 위 상위7": top_rank(above20_share, themes_of, close.columns, 7),
        },
    }

    return {"net": net, "axes": axes, "close": close, "opens": opens,
            "dates": dates, "total": total, "gate_drop": gate_drop,
            "market_days": market_days}


def main() -> None:
    env = build()
    net, axes, close, opens, dates = (env["net"], env["axes"], env["close"],
                                      env["opens"], env["dates"])
    total, gate_drop, market_days = (env["total"], env["gate_drop"],
                                     env["market_days"])
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    print(f"\n{'#' * 104}\n### 상승장 · 52주 고점 뚫고 눌릴 때 — **무엇이 영향이 있나**"
          f"\n### 시장 조건: 나스닥 200일선 위 + 고점 {gate_drop:.0f}% 안 — "
          f"10년 중 {market_days:,}일 (하락장 제외)"
          f"\n### 그물 {total:,}자리 (신고가 뒤 {wait_lo}~{wait_hi}일 · 눌린 폭 4~15%)"
          f"\n{'#' * 104}")
    print("  칸은 '승률차 / 수익률차' (%p). 별표 * = 그 보유기간에서 걸러내기 통과.")

    summary = []
    for axis, factors in axes.items():
        print(f"\n  ── {axis} ──")
        print(f"     {'후보':<28}{'해당':>5}   "
              + "".join(f"{n:>15}" for _h, n in HOLDS))
        for name, mask in factors.items():
            factor = mask.reindex(index=dates, columns=close.columns).fillna(False)
            share = (factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100
            cells, passes, wins = "", 0, []
            for hold, _label in HOLDS:
                item = edge(rets[hold], net, factor)
                if not item.get("ok"):
                    cells += f"{'—':>15}"
                    continue
                star = "*" if item["passed"] else " "
                cells += f"{item['win_mid']:>+6.1f}/{item['ret_mid']:>+6.1f}{star}"
                passes += bool(item["passed"])
                wins.append(item["win_mid"])
            print(f"     {name:<28}{share:>4.0f}%   {cells}")
            if wins:
                summary.append((float(np.mean(wins)), passes, share, axis, name))

    print(f"\n{'#' * 104}\n### 영향이 큰 순서 (승률차 평균) — 배점은 그다음이다"
          f"\n{'#' * 104}")
    for win, passes, share, axis, name in sorted(summary, reverse=True)[:14]:
        usable = "" if 10.0 <= share <= 85.0 else "  ← 해당 비율이 못 가름"
        print(f"  {win:>+6.1f}p  통과 {passes}/4  해당 {share:>3.0f}%  "
              f"{axis[:2]} {name}{usable}")
    print("\n  ── 거꾸로 (사면 오히려 나쁜 것) ──")
    for win, passes, share, axis, name in sorted(summary)[:6]:
        print(f"  {win:>+6.1f}p  해당 {share:>3.0f}%  {axis[:2]} {name}")


if __name__ == "__main__":
    main()
