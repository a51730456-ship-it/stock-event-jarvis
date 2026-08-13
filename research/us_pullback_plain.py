"""상승장 눌림매수 — **승률과 수익률 그대로** 낸다 (2026-08-13 상하님 지시).

*"그 자리에 몇 번 나왔다 라고 하면 내가 이해를 할 수 없다. 승률이나 확률
수익률 이런 식으로 이야기해야 알아먹는다."*

**맞는 말이다.** 그동안 낸 것은 전부 '차이'(승률차 +7.6%p)였다. 차이는 배점을
정할 때 필요한 값이지, 사람이 읽는 값이 아니다. 여기서는 **그냥 승률과 수익률**을
낸다 — "그 자리에서 사면 100번 중 몇 번 이겼고 가운데 얼마 벌었나."

  기준선  그날 명부 아무 종목이나 산 것
  그물    52주 신고가 뒤 3~10일 · 고점보다 4~15% 아래 · 테마 있는 종목
  배점    그 안에서 항목별로

시장 관문은 **나스닥 200일선 위**만 쓴다(2026-08-13 실측 — '고점 -10% 안'을
붙이면 +3.3p가 -5.1p로 뒤집힌다).

쓰는 법:  python research/us_pullback_plain.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, volume = wide["close"][stocks], wide["high"][stocks], wide["volume"][stocks]
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
    vol_now = volume.rolling(3, min_periods=2).mean() / volume.rolling(
        20, min_periods=10).mean()
    shares = load_shares().reindex(close.columns)
    cap_rank = close.mul(shares, axis=1).rank(axis=1, ascending=False, method="min")

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

    up_day = qqq > qqq.rolling(200, min_periods=200).mean()
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up_wide & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    together = pd.DataFrame(0, index=dates, columns=close.columns)
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if not members:
            continue
        count = net[members].sum(axis=1)
        for stock in members:
            together[stock] = np.maximum(together[stock], count)

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    # 기준선 — 상승장인 날 명부 아무 종목이나.
    base_mask = (up_wide & close.notna()).fillna(False)

    def line(name, mask, indent=""):
        cells = ""
        for hold, _label in HOLDS:
            values = rets[hold].where(mask).to_numpy().ravel()
            values = values[~np.isnan(values)]
            if values.size < 200:
                cells += f"{'—':>18}"
                continue
            win = (values > 0).mean() * 100
            mid = float(np.median(values))
            cells += f"  100번 중 {win:>2.0f}번 {mid:>+6.1f}%"
        days = float(mask.to_numpy().sum())
        print(f"  {indent}{name:<26}{cells}")
        return days

    print(f"\n{'=' * 116}\n### 상승장 눌림매수 — **승률과 수익률 그대로**"
          f"\n### 나스닥 200일선 위인 날만 · 10년 · 다음 거래일 시가에 사서\n{'=' * 116}")
    print(f"  {'':<26}" + "".join(f"{n:>18}" for _h, n in HOLDS))
    print()
    line("아무 종목이나 샀으면", base_mask)
    print()
    line("이 그물에서 샀으면", net)
    print()
    print("  ── 그 안에서 배점 항목별로 ──")
    for name, mask in (
        ("40점 · 테마 2개↑ 걸침", theme_count >= 2),
        ("30점 · 같은 테마 4개↑ 동반", together >= 4),
        ("20점 · 빅50 안", cap_rank <= 50),
        ("10점 · 뚫기 전 60일 50%↑", gain60_at_peak > 50.0),
        ("(참고) 눌린 폭 10~15%", (from_peak <= -10.0) & (from_peak >= -15.0)),
        ("(참고) 같은 테마에서 혼자", together <= 1),
        ("(참고) 눌리며 거래량 줄었다", vol_now < 0.9),
    ):
        line(name, net & mask.reindex_like(net).fillna(False))

    print("\n  ── 점수를 합치면 ──")
    score = (40 * (theme_count >= 2).astype(float)
             + 30 * (together >= 4).astype(float)
             + 20 * (cap_rank <= 50).fillna(False).astype(float)
             + 10 * (gain60_at_peak > 50.0).fillna(False).astype(float))
    for lo, hi, label in ((70, 101, "70점 이상"), (40, 70, "40~60점"),
                          (10, 40, "10~30점"), (0, 10, "0점")):
        mask = net & (score >= lo) & (score < hi)
        share = mask.to_numpy().sum() / max(net.to_numpy().sum(), 1) * 100
        line(f"{label} (그물의 {share:.0f}%)", mask)

    print("\n  ※ '100번 중 N번'은 이겼다는 뜻(수익 0보다 큼), 옆 %는 그때 벌었던 "
          "가운데값이다.")
    print("  ※ 지금 살아 있는 회사만 봤다. 망한 회사는 빠져 있어 실제보다 좋게 나온다.")


if __name__ == "__main__":
    main()
