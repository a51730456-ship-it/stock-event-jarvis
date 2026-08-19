"""급락 후 반등 배점의 **0점 항목 셋이 과거에 점수를 받은 적이 있나** (2026-08-15).

상하님 물음 — "과거에 급락 후 반등 종목이 심사항목에 0점 된 종목들이 배점을 받은
적이 있는지 확인해 봐라. 저거 선정한 게 급락 반등 전용 배점에 맞는 것인지
확인하는 것이야. 코드 수정하는 게 아니야."

## 무엇을 묻는 것인가 — 앞서 잰 것과 다른 물음이다

2026-08-14에 잰 것은 **"그 잣대로 고른 테마가 뒤에 더 벌었나"**(맞히나)였다.
여기서 묻는 것은 그 앞 단계다 — **"그 문턱을 통과한 종목이 실제로 있기는 했나."**

  · 한 번도 통과한 적이 없으면 → 맞히고 못 맞히고를 따지기 전에 **빈 기준**이다.
  · 자주 통과했으면 → 앱이 예전에 주던 점수를 지금은 안 주고 있는 것이다.

둘은 다른 이야기이고, 화면에 무엇을 적어야 하는지도 달라진다.

## 어떻게 재나 — 앱과 **같은 방식**으로

자리   나스닥 종합(IXIC)이 −12%·−18%·−24%에 **처음 닿은 날** + **저점 다음 날**
후보   그 자리에서 1년 고점 대비 −20~−50% 빠진 종목 (앱의 급락 그물)
테마값 **명부 200종목 전체** 평균 (앱의 `_attach_theme_rank`와 같다)
등수   테마 20개를 줄 세운 등수. 종목이 여러 테마에 걸치면 **가장 좋은 등수**를 쓴다
       (앱이 그렇게 한다 — 그래서 한 종목의 줄마다 테마 이름이 다를 수 있다).

항목   ① 테마 30주선 위   상위 3등  → 지금 40점
       ② 테마가 덜 빠졌나 상위 5등  → 지금 0점 (2026-08-14 이전 40점)
       ③ 테마 주봉 오름세 상위 5등  → 지금 0점 (이전 30점)
       ④ 테마 20일선 위   상위 5등  → 지금 0점 (이전 20점)

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_zero_items.py
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_crash_appstyle import touch_days, turn_days  # noqa: E402  같은 자리를 쓴다

STEPS = (-12.0, -18.0, -24.0)
STOCK_BAND = (-50.0, -20.0)
MIN_MEMBERS = 3


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][names], wide["high"][names]
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > close.rolling(20, min_periods=20).mean()).astype(float)
    above150 = (close > sma150).astype(float)
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)

    def by_theme(table: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({n: table[m].mean(axis=1) for n, m in themes.items()})

    board = {"above150": by_theme(above150), "drop": by_theme(from_high),
             "aligned": by_theme(aligned), "above20": by_theme(above20)}

    # 항목 — (이름, 판, 상위 몇 등, 지금 점수, 예전 점수)
    ITEMS = (
        ("① 테마 30주선 위",   "above150", j3.CRASH_ABOVE150_TOP_N, 40.0, 0.0),
        ("② 테마가 덜 빠졌나", "drop",     j3.CRASH_LESS_DROP_TOP_N, 0.0, 40.0),
        ("③ 테마 주봉 오름세", "aligned",  j3.CRASH_SPREAD_TOP_N,    0.0, 30.0),
        ("④ 테마 20일선 위",   "above20",  j3.CRASH_SPREAD_TOP_N,    0.0, 20.0),
    )

    # 자리 모으기 — 문턱에 처음 닿은 날 + 저점 다음 날
    spots: list[tuple[str, pd.Timestamp]] = []
    for step in STEPS:
        for day in touch_days(ixic, step):
            spots.append((f"문턱 {int(step)}%", day))
        for day in turn_days(ixic, step):
            spots.append((f"반등 {int(step)}%", day))
    spots = [(label, day) for label, day in spots if day in from_high.index]
    spots.sort(key=lambda item: item[1])

    print(f"자리 {len(spots)}개 · 테마 {len(themes)}개 · 명부 {len(names)}종목")
    print(f"기간 {dates[0].date()} ~ {dates[-1].date()}\n")

    rows = []
    per_item_hits = {name: 0 for name, *_ in ITEMS}
    per_item_spots = {name: 0 for name, *_ in ITEMS}
    total_candidates = 0
    all_zero = 0

    for label, day in spots:
        drop_today = from_high.loc[day]
        pool = [s for s in names
                if pd.notna(drop_today.get(s))
                and STOCK_BAND[0] <= drop_today[s] <= STOCK_BAND[1]
                and belongs.get(s)]
        if not pool:
            continue
        # 테마 등수 — 높을수록 좋은 값은 내림차순 1등
        places = {}
        for key in ("above150", "drop", "aligned", "above20"):
            series = board[key].loc[day].dropna()
            if series.empty:
                places[key] = {}
                continue
            order = series.sort_values(ascending=False)
            places[key] = {name: i for i, name in enumerate(order.index, 1)}

        total_candidates += len(pool)
        hit_counts = {}
        for item_name, key, top_n, _now, _was in ITEMS:
            table = places[key]
            hits = 0
            for ticker in pool:
                best = min((table[t] for t in belongs[ticker] if t in table),
                           default=None)
                if best is not None and best <= top_n:
                    hits += 1
            hit_counts[item_name] = hits
            per_item_hits[item_name] += hits
            per_item_spots[item_name] += 1 if hits else 0
        if not any(hit_counts.values()):
            all_zero += 1
        rows.append((label, day.date(), len(pool), hit_counts))

    print("=" * 92)
    print("① 그 문턱을 통과한 종목이 있기는 했나 — 과거 급락 자리 전부")
    print("=" * 92)
    head = f"{'항목':<22}{'지금':>6}{'예전':>6}   {'통과 종목':>10}{'통과 비율':>10}   {'통과한 자리':>12}"
    print(head); print("─" * len(head.replace("항목", "AA")))
    for item_name, _key, top_n, now, was in ITEMS:
        hits = per_item_hits[item_name]
        spots_hit = per_item_spots[item_name]
        print(f"{item_name} 상위{top_n}등".ljust(22)
              + f"{now:>5.0f}점{was:>5.0f}점"
              + f"{hits:>11,}{hits / max(total_candidates, 1) * 100:>9.1f}%"
              + f"{spots_hit:>9} / {len(rows)}자리")
    print(f"\n후보 종목 자리 합계 {total_candidates:,}개 · 네 항목 모두 0인 자리 "
          f"{all_zero}개 / {len(rows)}개")

    print("\n" + "=" * 92)
    print("② 자리마다 몇 종목이 통과했나 — 앞뒤 열 자리씩")
    print("=" * 92)
    head2 = f"{'자리':<14}{'날짜':<12}{'후보':>6}" + "".join(
        f"{name[:9]:>12}" for name, *_ in ITEMS)
    print(head2); print("─" * 90)
    show = rows[:10] + ([("…", "…", "…", None)] if len(rows) > 20 else []) + rows[-10:]
    for label, day, pool_n, counts in show:
        if counts is None:
            print("…"); continue
        print(f"{label:<14}{str(day):<12}{pool_n:>6}"
              + "".join(f"{counts[name]:>12}" for name, *_ in ITEMS))

    # ── ③ 오늘 화면 종목이 규칙에 맞는지 ────────────────────────────────────
    print("\n" + "=" * 92)
    print("③ 오늘 화면에 뽑힌 종목 — 줄마다 어느 테마로 재고 있나")
    print("=" * 92)
    try:
        found = j3.find_crash_rebound_stocks()
        for row in (found.get("rows") or [])[:5]:
            scored = j3.crash_rebound_score(row)
            print(f"\n{row['ticker']} · 소속 테마 {', '.join(row.get('themes') or [])}"
                  f" · 총점 {scored['score']}/{scored['max']}")
            for name, value, maximum, text in scored["parts"]:
                print(f"    {name:<34}{value:>5.1f} / {maximum:<5.1f} | {text}")
    except Exception as exc:                       # 장이 닫혔거나 자료를 못 받을 때
        print(f"오늘 목록을 못 받았습니다 — {exc}")


if __name__ == "__main__":
    main()
