"""**상하님 설명서 그물** vs **앱이 실제로 쓰는 그물** (2026-08-12).

상하님 물음 — "차라리 내가 만든 설명서가 더 맞았지 않냐?"

`docs/US_METHOD_TABLES.md` 표 1(2026-08-05 상하님 확정)은 이렇게 적고 있다.
  장세   나스닥 200일선 위 **그리고** 고점에서 10% 안쪽일 때만
  자리   신고가 뒤 1~3일 또는 3~5일 · **눌린 폭 10~15%** (굵은 두 줄 = 매수 자리)
  경고   "3~5일·4~6%는 앞 5년 −0.2 / 뒤 5년 −3.8%p로 **양쪽 다 졌다**"

그런데 앱(`jarvis3_data.BREAKOUT_PULLBACK_RULE`)은
  자리   신고가 뒤 1~5일 · 눌린 폭 **−4~−15%**  ← 4~6%까지 다 품었다
  장세   **안 거른다** (BREAKOUT_MARKET_MAX_DROP은 "알려만 준다")

즉 앱이 설명서보다 그물을 **넓혀** 놓았고, 설명서가 "지지 마라"고 못박은 자리까지
목록에 올리고 있다. 그 차이가 성적에서 얼마나 나는지 잰다.

표 2(급락)도 같이 본다 — 설명서는 나스닥 **−6~−12%**에 20~30% 빠진 종목, 앱은
**−10~−20% 최저일**로 바꿨다.

쓰는 법:  python research/us_spec_vs_app.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))


def line(name, values, bench, days):
    values = values.dropna()
    if values.empty:
        print(f"  {name:<34}{'자리 없음':>10}")
        return
    bench = bench.dropna()
    print(f"  {name:<34}{len(values):>8,}{(values > 0).mean() * 100:>10.1f}번"
          f"{values.median():>11.1f}%{values.mean():>10.1f}%"
          f"{(bench > 0).mean() * 100 if len(bench) else float('nan'):>10.1f}번"
          f"{bench.median() if len(bench) else float('nan'):>11.1f}%{days:>8,}")


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq, qqq_open = wide["close"]["QQQ"], wide["open"]["QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens = wide["open"][stocks]
    dates = close.index

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

    # 설명서 표 1의 장세 조건
    spec_market = spread((qqq > qqq_sma200) & (qqq_drop > -10.0))

    def rets(hold):
        return (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0

    def qqq_rets(hold):
        return (qqq.shift(-hold) / qqq_open.shift(-1) - 1.0) * 100.0

    def run(title, nets, holds):
        print(f"\n{'=' * 116}\n### {title}\n{'=' * 116}")
        print(f"  {'그물':<34}{'건수':>8}{'번 중 이김':>11}{'가운데':>11}{'평균':>10}"
              f"{'QQQ 이김':>10}{'QQQ 가운데':>11}{'신호일':>8}")
        for hold in holds:
            print(f"  ── {hold}거래일 보유 ──")
            r, qr = rets(hold), qqq_rets(hold)
            for name, net in nets.items():
                net = net.fillna(False)
                values = r.where(net).stack()
                signal_days = net.any(axis=1)
                line("   " + name, values, qr.where(signal_days), int(signal_days.sum()))

    # ── 상승장 ──────────────────────────────────────────────────────────
    lo, hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    app_net = (days_ago >= 1) & (days_ago <= 5) & (from_high >= lo) & (from_high <= hi)
    deep = (from_high >= -15.0) & (from_high <= -10.0)
    shallow = (from_high > -6.0) & (from_high <= -4.0)
    run("미국 상승장 — 상하님 설명서 그물 vs 앱 그물", {
        "앱: 1~5일 · −4~−15% · 장세 안 봄": app_net,
        "설명서: 1~3일 · 10~15% · 장세 봄": spec_market & (days_ago <= 3) & (days_ago >= 1) & deep,
        "설명서: 3~5일 · 10~15% · 장세 봄": spec_market & (days_ago > 3) & (days_ago <= 5) & deep,
        "설명서 두 줄 합침 (1~5일 · 10~15%)": spec_market & (days_ago >= 1) & (days_ago <= 5) & deep,
        "장세만 빼고 10~15%": (days_ago >= 1) & (days_ago <= 5) & deep,
        "설명서가 '지지 마라'던 4~6%": (days_ago >= 1) & (days_ago <= 5) & shallow,
    }, (60, 120, 250))

    # ── 급락 ────────────────────────────────────────────────────────────
    def deepest_of(band):
        low, high_ = band
        inside = (qqq_drop <= high_) & (qqq_drop >= low)
        episode = (inside & ~inside.shift(1, fill_value=False)).cumsum().where(inside)
        flag = pd.Series(False, index=dates)
        for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
            flag.loc[group["d"].idxmin()] = True
        return spread(flag), spread(inside)

    app_deep, _ = deepest_of(j3.CRASH_MARKET_BAND)
    _, spec_in = deepest_of((-12.0, -6.0))
    c_lo, c_hi = j3.CRASH_REBOUND_RULES[0]["band"]
    run("미국 급락 후 반등 — 설명서 표 2 vs 앱 그물", {
        "앱: 나스닥 −10~−20% 최저일 · 종목 −20~−30%":
            app_deep & (from_high <= c_hi) & (from_high >= c_lo),
        "설명서: 나스닥 −6~−12% 구간 · 종목 −20~−30%":
            spec_in & (from_high <= -20.0) & (from_high >= -30.0),
        "설명서: 나스닥 −6~−12% 구간 · 종목 −30~−50%":
            spec_in & (from_high < -30.0) & (from_high >= -50.0),
    }, (60, 120, 250))

    print("\n※ 사는 것은 신호 다음 거래일 시가, 파는 것은 정해진 거래일 뒤 종가."
          "\n※ 명부 198종목 · 2016-08~2026-08 10년 · 살아남은 대형주만."
          "\n※ 'QQQ 이김/가운데'는 **같은 신호일에 QQQ를 샀을 때**다.")


if __name__ == "__main__":
    main()
