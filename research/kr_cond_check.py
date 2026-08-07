"""한국 '눌림목 찾기'의 **조건점수** 항목들을 같은 방법으로 잰다 (2026-08-07).

상승장·급락 후 반등장은 격자로 다 쟀는데 조건점수(_stock_score)는 한 번도
같은 잣대로 재 본 적이 없다. 그 화면은 '이걸 사라'가 아니라 '지금 사면 얼마나
위험한가'를 재는 것이지만, 점수가 실제 성적과 상관없다면 화면이 잘못 말하는 것이다.

**방법은 못박아 둔 그대로다** — 창 2·3·4년을 한 달씩 밀고, 그물 안에서 견주고,
승률과 수익률 둘 다 65% 이상이라야 합격.

그물은 눌림목 찾기가 실제로 보는 자리로 잡는다 — 거래대금 50억 이상이고
52주 고점 대비 -45~0% 안에 있는 종목(그 화면은 낙폭 폭이 넓다).

쓰는 법:  python research/kr_cond_check.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
from kr_measure import load_wide  # noqa: E402
from us_verify import MIN_SIDE, PASS_MARK, WINDOWS, score, show  # noqa: E402


def main() -> None:
    wide = load_wide()
    close, high, low = wide["close"], wide["high"], wide["low"]
    dates = close.index
    turnover = close * wide["volume"]
    value = turnover.rolling(50, min_periods=20).mean() / 1e8
    from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr = true_range.rolling(14, min_periods=10).mean() / close * 100.0
    ret20 = (close / close.shift(20) - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=15).mean()
    sma50 = close.rolling(50, min_periods=35).mean()
    sma200 = close.rolling(200, min_periods=140).mean()

    # 눌림목 찾기가 보는 자리 — 넓다(고점 대비 -45~0%).
    net = ((value >= 50) & (from_high <= 0.0) & (from_high >= -45.0)).fillna(False)
    hold = 120
    returns = (close.shift(-hold) / wide["open"].shift(-1) - 1.0) * 100.0
    print(f"### 한국 눌림목 찾기 조건점수 — 그물 안 {int(net.to_numpy().sum()):,}자리"
          f" · {hold}거래일 보유\n")
    print(f"창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 두 무리 각 {MIN_SIDE}건 이상 · "
          f"합격선 {PASS_MARK:.0f}% · 비교 상대는 같은 그물 안의 나머지")
    print(f"  {'배점 항목':<28}{'해당':>5}" + "".join(f"{y:>7}년       " for y in WINDOWS))
    for name, factor in (
        ("15점 신고가에 가까운가(-10%↑)", from_high >= -10.0),
        ("15점 신고가에서 멀다(-30%↓)", from_high <= -30.0),
        ("20점 20일선 위", close > sma20),
        ("20점 50일선 위", close > sma50),
        ("20점 200일선 위", close > sma200),
        ("15점 거래대금 500억↑", value >= 500),
        ("15점 거래대금 100억 미만", value < 100),
        ("10점 변동성 4% 미만", atr <= 4.0),
        ("10점 변동성 9%↑", atr >= 9.0),
        ("20점 20일 수익률 상위(+8%↑)", ret20 >= 8.0),
        ("20점 20일 수익률 하위(-8%↓)", ret20 <= -8.0),
    ):
        factor = factor.reindex(index=dates, columns=close.columns).fillna(False).astype(bool)
        got = float(factor.to_numpy()[net.to_numpy()].mean() * 100)
        show(name, got, score(returns, net, factor))


if __name__ == "__main__":
    main()
