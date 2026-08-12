"""크기 계층별로 갈라 재고, **일봉 20일선 대신 주봉 정배열**을 견준다 (2026-08-12).

상하님 두 가지 지시.

  ① "빅10 종목과 그 밑에 빅11~50위, 51~100위 종목과 달리 검정해봐라."
  ② "일봉 20일 중요한 게 아니고 **주봉이 정배열에 가깝냐**를 보는 게 더 맞지 않나?"

②는 근거가 있는 물음이다. `docs/METHOD_ORIGINS.md`에 적어 둔 이 기법의 출처를
보면 실무 쪽 세 사람이 다 **주봉 자리**를 본다 —

  · Weinstein(1988) Stage Analysis — **30주(≈150일) 이동평균**이 기준선. 2단계에서만 산다
  · Minervini Trend Template — 50 > 150 > 200일선 **정배열**, 200일선이 오르는 중
  · O'Neil CAN SLIM — 바닥 다지기(주 단위) 후 신고가 돌파

**일봉 20일선은 그 어디에도 없다.** 자비스가 20일선을 쓰게 된 것은 2026-07-19
첫 판(`297cfde`)에 '단기추세'로 넣은 것이고, 그때 잰 적이 없다. 그러니 견줘 본다.

## 무엇을 재나

크기 계층 — 그날 시가총액 등수로 **빅10 · 11~50위 · 51~100위 · 101위 아래**.
(시총 = 그날 종가 × 오늘 발행주식수. 한계는 `us_shares.py` 머리말에.)

잣대 넷 (모두 그날까지의 값)
  · 일봉 20일선 위      ← 지금 쓰는 것
  · 일봉 50일선 위      ← 10주선
  · 주봉 30주선 위      ← Weinstein 기준선 (150일선)
  · 주봉 정배열         ← Minervini: 종가>50>150>200일선 **그리고** 200일선 상승 중

세 토막으로 본다
  [1] 상하님 짐작 확인 — 급락이 깊어질수록 정말 '대부분 밑'인가. **크기 계층별로.**
  [2] 테마로 모았을 때 값이 갈리나 — 0인 테마 비율 · 1등과 꼴찌 차이
  [3] 성적을 가르나 — 그물을 계층으로 좁혀 놓고 상위 5등이 이기는가

쓰는 법:  python research/us_size_and_weekly.py
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

DEPTHS = ((-12.0, -6.0, "6~12%"), (-18.0, -12.0, "12~18%"),
          (-24.0, -18.0, "18~24%"), (-100.0, -24.0, "24% 아래"))
SIZES = ((1, 10, "빅10"), (11, 50, "11~50위"), (51, 100, "51~100위"),
         (101, 9999, "101위 아래"))
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))


def build() -> dict:
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, opens = wide["close"][stocks], wide["high"][stocks], wide["open"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    # ── 크기 계층 ────────────────────────────────────────────────────────
    shares = load_shares().reindex(close.columns)
    cap = close.mul(shares, axis=1)
    missing = [c for c in close.columns if not np.isfinite(shares.get(c, np.nan))]
    cap_rank = cap.rank(axis=1, ascending=False, method="min")

    # ── 잣대 넷 ─────────────────────────────────────────────────────────
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    rising200 = sma200 > sma200.shift(20)
    measures = {
        "일봉 20일선 위": close > sma20,
        "일봉 50일선 위": close > sma50,
        "주봉 30주선 위": close > sma150,
        "주봉 정배열": ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
                     & rising200),
    }

    # ── 그물 ────────────────────────────────────────────────────────────
    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    crash_lo = min(low for rule in j3.CRASH_REBOUND_RULES for low, _ in [rule["band"]])
    crash_hi = max(hi for rule in j3.CRASH_REBOUND_RULES for _, hi in [rule["band"]])
    market_lo, market_hi = j3.CRASH_MARKET_BAND
    market = ((qdrop <= market_hi) & (qdrop >= market_lo)).fillna(False)
    market_wide = pd.DataFrame(
        np.repeat(market.to_numpy()[:, None], close.shape[1], axis=1),
        index=dates, columns=close.columns)
    crash_net = (market_wide & has_theme & (from_high <= crash_hi)
                 & (from_high >= crash_lo)).fillna(False)

    return {
        "j3": j3, "dates": dates, "close": close, "opens": opens,
        "cap_rank": cap_rank, "missing": missing, "measures": measures,
        "themes_of": themes_of, "qdrop": qdrop, "crash_net": crash_net,
        "themes": j3.US_THEMES,
    }


def part1(env: dict) -> None:
    """상하님 짐작 확인 — 깊은 급락에서 '대부분 밑'인가. 크기 계층별로."""
    close, cap_rank, qdrop = env["close"], env["cap_rank"], env["qdrop"]
    print(f"\n{'=' * 112}\n### [1] 그날 그 계층 종목 중 **몇 %가 그 선 위**에 있었나"
          f"\n###     (상하님 짐작: 깊은 급락이면 대부분 20일선 밑일 것)\n{'=' * 112}")
    for name, mask in env["measures"].items():
        print(f"\n  ── {name} ──")
        print(f"     {'나스닥 칸':<12}{'날 수':>6}   " +
              "".join(f"{label:>12}" for _, _, label in SIZES))
        for low, high_, depth in DEPTHS:
            inside = ((qdrop <= high_) & (qdrop >= low)).fillna(False)
            days = inside[inside].index
            if len(days) < 10:
                print(f"     {depth:<12}{len(days):>6}   (날이 적어 건너뜀)")
                continue
            cells = ""
            for lo_rank, hi_rank, _ in SIZES:
                tier = ((cap_rank >= lo_rank) & (cap_rank <= hi_rank)).reindex(days)
                block = mask.reindex(days).where(tier)
                share = float(block.mean(axis=1).mean() * 100)
                cells += f"{share:>11.0f}%"
            print(f"     {depth:<12}{len(days):>6}   {cells}")


def part2(env: dict) -> None:
    """테마로 모았을 때 값이 갈리나."""
    qdrop, themes = env["qdrop"], env["themes"]
    print(f"\n\n{'=' * 112}\n### [2] 테마 20개로 모으면 값이 갈리나"
          f"  (칸: 0인 테마% · 1등과 꼴찌 차이)\n{'=' * 112}")
    theme_values = {name: per_theme(mask.astype(float) * 100, themes)
                    for name, mask in env["measures"].items()}
    print(f"  {'나스닥 칸':<12}{'날 수':>6}   " +
          "".join(f"{name:<24}" for name in theme_values))
    for low, high_, depth in DEPTHS:
        inside = ((qdrop <= high_) & (qdrop >= low)).fillna(False)
        days = inside[inside].index
        if len(days) < 10:
            print(f"  {depth:<12}{len(days):>6}   (날이 적어 건너뜀)")
            continue
        cells = ""
        for values in theme_values.values():
            block = values.reindex(days).dropna(how="all")
            if block.empty:
                cells += f"{'—':<24}"
                continue
            zero = float((block <= 0.0001).mean(axis=1).mean() * 100)
            spread = float((block.max(axis=1) - block.min(axis=1)).median())
            cells += f"{zero:>6.0f}%{spread:>10.1f}p       "
        print(f"  {depth:<12}{len(days):>6}   {cells}")
    return theme_values


def part3(env: dict, theme_values: dict) -> None:
    """성적을 가르나 — 그물을 계층으로 좁혀 놓고 상위 5등이 이기는가."""
    close, opens, dates = env["close"], env["opens"], env["dates"]
    cap_rank, themes_of = env["cap_rank"], env["themes_of"]
    crash_net = env["crash_net"]
    print(f"\n\n{'=' * 112}\n### [3] 급락 그물 안에서 '상위 5등 테마'가 성적을 가르나"
          f"\n###     창 2·3·4년 · 승률/수익률 둘 다 65%↑라야 합격\n{'=' * 112}")
    factors = {
        name: top_rank(values, themes_of, close.columns, 5).reindex(
            index=dates, columns=close.columns).fillna(False)
        for name, values in theme_values.items()
    }
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    slices = [("계층 안 나눔", crash_net)]
    for lo_rank, hi_rank, label in SIZES:
        tier = (cap_rank >= lo_rank) & (cap_rank <= hi_rank)
        slices.append((label, crash_net & tier.fillna(False)))

    for label, net in slices:
        total = int(net.to_numpy().sum())
        print(f"\n  ── {label} · 그물 안 {total:,}자리 ──")
        if total < 800:
            print("     자리가 적어 판정하지 않는다")
            continue
        for name, factor in factors.items():
            share = ((factor.to_numpy() & net.to_numpy()).sum()
                     / max(total, 1) * 100)
            marks = []
            for hold, hold_name in HOLDS:
                result = score(rets[hold], net, factor)
                worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                            default=float("nan"))
                marks.append(f"{hold_name} {verdict(result):<9}{worst:>7.1f}p")
            print(f"     {name:<18}해당 {share:>3.0f}%  " + " · ".join(marks))


def part4(env: dict, theme_values: dict) -> None:
    """테마 20개 순위 파트 — 여기서 20일선이 **40점**을 지고 있다. 그물 없음."""
    close, opens, dates = env["close"], env["opens"], env["dates"]
    themes_of, qdrop = env["themes_of"], env["qdrop"]
    j3 = env["j3"]
    qqq_sma200 = env["close"].index  # 자리표시(아래에서 다시 만든다)
    del qqq_sma200

    import us_yearly
    qqq = us_yearly.fetch()["close"]["QQQ"]
    up = qqq > qqq.rolling(200, min_periods=200).mean()
    up_wide = pd.DataFrame(np.repeat(up.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    enough = close.notna() & close.rolling(200, min_periods=200).mean().notna() & has_theme

    factors = {
        name: top_rank(values, themes_of, close.columns, 5).reindex(
            index=dates, columns=close.columns).fillna(False)
        for name, values in theme_values.items()
    }
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    print(f"\n\n{'=' * 112}\n### [4] 테마 20개 순위 파트 — 그물 없이 명부 전체."
          f"  **여기서 20일선이 40점을 지고 있다**\n{'=' * 112}")
    for label, phase in (("나스닥 200일선 위", enough & up_wide),
                         ("나스닥 200일선 아래", enough & ~up_wide)):
        net = phase.fillna(False)
        total = int(net.to_numpy().sum())
        print(f"\n  ── {label} · {total:,}자리 ──")
        for name, factor in factors.items():
            share = ((factor.to_numpy() & net.to_numpy()).sum() / max(total, 1) * 100)
            marks = []
            for hold, hold_name in HOLDS:
                result = score(rets[hold], net, factor)
                worst = min((result[y]["win_worst"] for y in WINDOWS if result[y]),
                            default=float("nan"))
                marks.append(f"{hold_name} {verdict(result):<9}{worst:>7.1f}p")
            print(f"     {name:<18}해당 {share:>3.0f}%  " + " · ".join(marks))
    del j3, qdrop


def main() -> None:
    env = build()
    if env["missing"]:
        print(f"※ 발행주식수를 못 받은 종목 {len(env['missing'])}개는 크기 계층에서 빠진다: "
              f"{', '.join(env['missing'][:10])}")
    part1(env)
    theme_values = part2(env)
    part3(env, theme_values)
    part4(env, theme_values)
    print("\n※ '최악'은 창 셋을 통틀어 가장 나빴던 창의 승률차다. 합격이어도 이 값이 "
          "크게 마이너스면 어떤 2년은 손해였다는 뜻이다.")


if __name__ == "__main__":
    main()
