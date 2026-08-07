"""미국 '종목 조건점수'의 항목들을 같은 잣대로 잰다 (2026-08-07).

한국 조건점수를 재 봤더니 100점 중 40점이 거꾸로였다(`kr_cond_check.py`).
미국 조건점수는 항목 구성이 거의 같은데 **한 번도 재 본 적이 없다.** 한쪽만
고치고 두면 같은 앱 안에서 한 나라는 검증된 배점, 한 나라는 안 잰 배점이 된다.

방법은 못박아 둔 그대로다 — 창 2·3·4년을 한 달씩 밀고, **그물 안에서** 견주고,
승률과 수익률 둘 다 65% 이상이라야 합격.

그물은 미국 조건점수가 실제로 쓰이는 자리로 잡는다 — 52주 고점 대비 -45~0%.
(미국은 종목 수가 적어 거래대금 문턱을 따로 두지 않는다. 애초에 대형주뿐이다.)

쓰는 법:  python research/us_cond_check.py
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import MIN_SIDE, PASS_MARK, WINDOWS, score, show  # noqa: E402


def main() -> None:
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = (wide["close"][stocks], wide["high"][stocks],
                        wide["low"][stocks])
    dates = close.index
    volume = wide["volume"][stocks] if "volume" in wide else None

    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    ret20 = (close / close.shift(20) - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=15).mean()
    sma50 = close.rolling(50, min_periods=35).mean()
    sma200 = close.rolling(200, min_periods=140).mean()

    net = ((from_high <= 0.0) & (from_high >= -45.0)).fillna(False)
    hold = 120
    returns = (close.shift(-hold) / wide["open"][stocks].shift(-1) - 1.0) * 100.0

    print(f"### 미국 종목 조건점수 — 그물 안 {int(net.to_numpy().sum()):,}자리"
          f" · {hold}거래일 보유\n")
    print(f"창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"합격선 {PASS_MARK:.0f}% · 비교 상대는 같은 그물 안의 나머지")
    print(f"  {'배점 항목':<28}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))

    rows = [
        ("15점 신고가에 가까운가(-10%↑)", from_high >= -10.0),
        ("15점 신고가에서 멀다(-30%↓)", from_high <= -30.0),
        ("20점 20일선 위", close > sma20),
        ("20점 50일선 위", close > sma50),
        ("20점 200일선 위", close > sma200),
        ("10점 변동성 3% 미만", atr <= 3.0),
        ("10점 변동성 6%↑", atr >= 6.0),
        ("20점 20일 수익률 상위(+8%↑)", ret20 >= 8.0),
        ("20점 20일 수익률 하위(-8%↓)", ret20 <= -8.0),
    ]
    if volume is not None:
        value = (close * volume).rolling(50, min_periods=20).mean()
        rank = value.rank(axis=1, pct=True)
        rows.append(("15점 거래대금 상위 30%", rank >= 0.70))
        rows.append(("15점 거래대금 하위 30%", rank <= 0.30))

    for name, factor in rows:
        factor = (factor.reindex(index=dates, columns=close.columns)
                  .fillna(False).astype(bool))
        got = float(factor.to_numpy()[net.to_numpy()].mean() * 100)
        show(name, got, score(returns, net, factor))


if __name__ == "__main__":
    main()
