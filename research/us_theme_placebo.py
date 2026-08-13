"""**가짜 테마 시험** — 테마 효과가 진짜인지 명부 탓인지 가른다 (2026-08-13).

## 무엇을 확인하나

2026-08-13 측정에서 **테마 고점 근접도**만 살아남았다. 같은 날 뜬 두 종목을
견주면 근접도 높은 쪽이 100번 중 53번 이겼고, 10년 중 7년에서 그랬다.

그런데 **테마 명부가 오늘 것**이다. 지금 20개 테마(반도체·AI·양자컴퓨팅 …)는
2026년에 잘 나가는 묶음이다. 그 묶음으로 2018년을 재면, 그 종목들이 2018년부터
지금까지 잘 나갔기 때문에 오늘 한 조에 있는 것이므로 **결과를 보고 조를 짠 셈**이
된다. 시험 문제를 풀기 전에 답안지를 본 것과 같다.

## 어떻게 가르나

종목을 **제비뽑기로** 20묶음으로 나눈다. 반도체 회사와 은행과 항공사가 한 조에
들어가는, 아무 뜻 없는 묶음이다. 그러고 나서 **진짜 테마에 한 것과 똑같이** 잰다.

  · 가짜도 53번쯤 맞히면 → 테마 내용이 아니라 **오늘 명부를 쓴 탓**이다.
    배점에 넣으면 안 된다. 명부를 FINVIZ 것으로 바꿔도 소용없다(그것도 오늘 것).
  · 가짜는 50번(반반)이면 → 진짜 테마가 하는 일이 맞다. 배점에 넣어도 된다.

## 공정하게 하려고 맞춘 것

가짜 묶음은 진짜와 **크기가 같고**(10·9·8·8·10·…), **한 종목이 몇 개 테마에
걸치는지도 같다**(14종목이 2개 이상). 그물(어떤 날 어떤 종목이 후보인가)은
**진짜와 똑같이 두고 근접도만 바꾼다.** 그래야 근접도 하나만 견주게 된다.

제비뽑기를 100번 한다. **가짜 100번 중 진짜보다 잘 맞힌 것이 몇 번인지** 센다.
다섯 번 이하면 진짜라고 볼 만하고, 스무 번을 넘으면 명부 탓이다.

쓰는 법:  python research/us_theme_placebo.py [뽑기횟수]
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

EVENTS = ROOT / "research" / "_data" / "factor_sweep_events.csv"
HOLDS = ((20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년"))
SHUFFLES = int(sys.argv[1]) if len(sys.argv) > 1 else 100


def theme_prox(cap: pd.DataFrame, groups: list[list[str]],
               columns: pd.Index) -> pd.DataFrame:
    """묶음마다 (합산 시총 ÷ 그 252일 최고) 를 내고, 종목에 가장 센 쪽을 붙인다."""
    out = pd.DataFrame(np.nan, index=cap.index, columns=columns)
    for members in groups:
        members = [s for s in members if s in cap.columns]
        if len(members) < 3:
            continue
        total = cap[members].sum(axis=1, min_count=2)
        value = total / total.rolling(252, min_periods=200).max() * 100.0
        for stock in members:
            out[stock] = value if out[stock].isna().all() \
                else np.fmax(out[stock], value)
    return out


def main() -> None:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    events = pd.read_csv(EVENTS, parse_dates=["date"])
    events["yr"] = events.date.dt.year

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close = wide["close"][stocks]
    print("  시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)

    real = [[s for s in t["stocks"] if s in close.columns] for t in j3.US_THEMES]
    real = [m for m in real if len(m) >= 3]
    sizes = [len(m) for m in real]
    slots: list[str] = []
    for members in real:
        slots.extend(members)
    pool = sorted(set(slots))
    print(f"  진짜 테마 {len(real)}개 · 자리 {len(slots)}개 · 종목 {len(pool)}개", flush=True)

    # ── 날짜별로 미리 갈라 둔다 (제비뽑기마다 다시 안 하려고) ──────────────
    order = {t: i for i, t in enumerate(close.columns)}
    row_of = {d: i for i, d in enumerate(close.index)}
    days = []
    for (year, day), group in events.groupby(["yr", "date"]):
        if len(group) < 2:
            continue
        rows = np.array([row_of[day]] * len(group))
        cols = np.array([order[t] for t in group.ticker])
        rets = {h: group[f"r{h}"].to_numpy() for h, _n in HOLDS}
        days.append((year, rows, cols, rets))
    years = sorted({d[0] for d in days})
    print(f"  견줄 날 {len(days)}일 · {len(years)}개 연도", flush=True)

    def score(prox: pd.DataFrame) -> dict:
        table = prox.to_numpy()
        got = {}
        for hold, _name in HOLDS:
            wins = {y: 0 for y in years}
            total = {y: 0 for y in years}
            for year, rows, cols, rets in days:
                value = table[rows, cols]
                ret = rets[hold]
                keep = ~np.isnan(value) & ~np.isnan(ret)
                if keep.sum() < 2:
                    continue
                value, ret = value[keep], ret[keep]
                dv = value[:, None] - value[None, :]
                dr = ret[:, None] - ret[None, :]
                mask = np.triu(np.ones_like(dv, dtype=bool), 1) & (dv != 0) & (dr != 0)
                if not mask.any():
                    continue
                wins[year] += int(((np.sign(dv) == np.sign(dr)) & mask).sum())
                total[year] += int(mask.sum())
            hit = sum(wins.values())
            all_ = sum(total.values())
            got[hold] = hit / all_ * 100.0 if all_ else np.nan
        return got

    truth = score(theme_prox(cap, real, close.columns))
    print(f"\n  진짜 테마 — " + " · ".join(
        f"{name} {truth[h]:.1f}번" for h, name in HOLDS), flush=True)

    rng = np.random.default_rng(20260813)
    fake = {h: [] for h, _n in HOLDS}
    print(f"\n  가짜 테마를 {SHUFFLES}번 뽑는다...", flush=True)
    for turn in range(SHUFFLES):
        mixed = list(slots)
        rng.shuffle(mixed)
        groups, at = [], 0
        for size in sizes:
            groups.append(mixed[at:at + size])
            at += size
        got = score(theme_prox(cap, groups, close.columns))
        for hold, _n in HOLDS:
            fake[hold].append(got[hold])
        if (turn + 1) % 10 == 0:
            print(f"    {turn + 1}/{SHUFFLES}...", flush=True)

    print(f"\n{'=' * 96}\n### 가짜 테마 시험 결과 — 제비뽑기 {SHUFFLES}번\n{'=' * 96}")
    print(f"  {'보유':<8}{'진짜':>10}{'가짜 가운데':>14}{'가짜 위아래 95%':>20}"
          f"{'진짜보다 잘한 가짜':>20}")
    verdicts = []
    for hold, name in HOLDS:
        arr = np.array(fake[hold])
        beat = int((arr >= truth[hold]).sum())
        verdicts.append(beat)
        print(f"  {name:<8}{truth[hold]:>9.1f}번{np.median(arr):>13.1f}번"
              f"{np.percentile(arr, 2.5):>11.1f}~{np.percentile(arr, 97.5):.1f}번"
              f"{beat:>15}번 / {SHUFFLES}")

    print(f"\n  ── 읽는 법 ──")
    print(f"     '진짜보다 잘한 가짜'가 5번 이하면 → 진짜 테마가 하는 일이 맞다.")
    print(f"     20번을 넘으면 → 아무 묶음이나 그만큼 나온다는 뜻이다. 명부 탓이다.")
    worst = max(verdicts[1:])   # 1개월은 원래 약해서 뺀다
    if worst <= 5:
        print(f"\n  **통과.** 3개월·6개월·1년에서 가짜가 진짜를 이긴 것이 "
              f"많아야 {worst}번뿐이다.")
    elif worst <= 20:
        print(f"\n  **애매하다.** 가짜가 최대 {worst}번 이겼다. 배점을 크게 올리면 안 된다.")
    else:
        print(f"\n  **탈락.** 가짜가 최대 {worst}번 이겼다. 아무 묶음이나 이만큼 나온다.")
        print(f"     테마 명부를 FINVIZ 것으로 바꿔도 소용없다 — 그것도 오늘 명부다.")


if __name__ == "__main__":
    main()
