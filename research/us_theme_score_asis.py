"""테마 20개 순위 배점을 **화면이 실제로 주는 방식 그대로** 잰다 (2026-08-12).

**왜.** 지금까지 이 파트를 검증할 때는 늘 "그날 상위 N등 테마에 속하면 해당"으로
쟀다. 그런데 화면은 그렇게 점수를 주지 않는다 — `_scale(값, 낮음, 높음, 점수)`로
**비율에 비례해 연속으로** 준다.

    20일선 위 비율   25% → 0점 · 85% → 40점 (사이는 비례)      40점
    5일 오른 비율    20% → 0점 · 80% → 30점                    30점
    20일 오른 비율   25% → 0점 · 85% → 20점                    20점
    덜 빠졌나       -30% → 0점 · -2% → 10점                    10점

**같은 값을 쓰지만 순위를 매기는 규칙이 다르다.** 등수로 재면 "상위 5등 안이냐"
하나만 보는데, 화면은 네 항목의 점수를 **더해서** 한 줄로 세운다. 그래서
등수로 합격이어도 화면 점수로는 안 갈릴 수 있고, 그 반대일 수도 있다.

여기서는 **화면이 내는 최종 점수를 그대로 만들어** 잰다.
  ① 그날 20개 테마의 최종 점수를 계산한다(화면과 같은 식·같은 문턱)
  ② 상위 3·5·7등 테마에 속한 종목이 나머지를 이기나
  ③ 항목 하나씩 빼 보고 점수가 나빠지는지 본다 — 40점이 제값을 하는지 보려는 것

국면(나스닥 200일선 위/아래)으로 갈라 잰다. 상하님 지적 — "테마 수익률이
하락장에는 의미가 없지."

쓰는 법:  python research/us_theme_score_asis.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_theme_rank import per_theme, top_rank  # noqa: E402
from us_verify import WINDOWS, score, verdict  # noqa: E402

HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    sma20 = close.rolling(20, min_periods=20).mean()
    from_high = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0

    weights = j3.THEME_SCORE_WEIGHTS
    # 화면과 **같은 문턱**이다(jarvis3_data의 _scale 호출부를 그대로 옮겼다).
    pieces = {
        "20일선 위 비율": (per_theme((close > sma20).astype(float) * 100, j3.US_THEMES),
                      25.0, 85.0, weights["above20"]),
        "5일 오른 비율": (per_theme((close.pct_change(5) > 0).astype(float) * 100,
                                j3.US_THEMES), 20.0, 80.0, weights["rose5"]),
        "20일 오른 비율": (per_theme((close.pct_change(20) > 0).astype(float) * 100,
                                 j3.US_THEMES), 25.0, 85.0, weights["rose20"]),
        "덜 빠졌나": (per_theme(from_high, j3.US_THEMES), -30.0, -2.0,
                   weights["less_drop"]),
    }

    def scaled(frame, low, high_, points):
        return ((frame - low) / (high_ - low) * points).clip(lower=0.0, upper=points)

    parts = {name: scaled(frame, low, high_, points)
             for name, (frame, low, high_, points) in pieces.items()}
    total = sum(parts.values())

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    enough = (close.notna()
              & close.rolling(200, min_periods=200).mean().notna() & has_theme)

    up = qqq > qqq.rolling(200, min_periods=200).mean()
    up_wide = pd.DataFrame(np.repeat(up.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    print(f"\n{'=' * 116}\n### 테마 20개 순위 — **화면이 주는 최종 점수 그대로**"
          f"  (창 2·3·4년 · 승률/수익률 둘 다 65%↑라야 합격)\n{'=' * 116}")
    print(f"  화면 배점: " + " · ".join(
        f"{name} {points:.0f}점" for name, (_f, _l, _h, points) in pieces.items()))

    candidates = {"네 항목 다 (화면 그대로)": total}
    # 항목 하나씩 빼 본다 — 그 항목이 제값을 하면 빼면 나빠져야 한다.
    for name in parts:
        candidates[f"└ {name} 뺀 것"] = total - parts[name]
    # 항목 하나만으로 줄 세워 본다 — 어느 항목이 혼자서도 값을 하는지 본다.
    for name, piece in parts.items():
        candidates[f"■ {name} 하나만"] = piece

    for label, phase in (("나스닥 200일선 위", enough & up_wide),
                         ("나스닥 200일선 아래", enough & ~up_wide)):
        net = phase.fillna(False)
        count = int(net.to_numpy().sum())
        print(f"\n  ── {label} · {count:,}자리 ──")
        print(f"     {'무엇으로 줄 세우나':<26}{'등수':>5}{'해당':>6}   "
              + "".join(f"{name:>10}" for _h, name in HOLDS))
        for name, values in candidates.items():
            for top in (3, 5):
                factor = top_rank(values, themes_of, close.columns, top).reindex(
                    index=dates, columns=close.columns).fillna(False)
                share = ((factor.to_numpy() & net.to_numpy()).sum()
                         / max(count, 1) * 100)
                cells = "".join(
                    f"{verdict(score(rets[hold], net, factor)).split()[0]:>10}"
                    for hold, _n in HOLDS)
                print(f"     {name if top == 3 else '':<26}{top:>4}등{share:>5.0f}%   {cells}")

    print("\n  ○=합격 · △=안 됨 · ✗=거꾸로")
    print("  '뺀 것'이 '다 넣은 것'보다 좋으면 그 항목은 점수를 깎아 먹고 있다는 뜻이다.")


if __name__ == "__main__":
    main()
