"""인기 테마 10개 × 시총 상위 5종목 = 50종목을 **나스닥 저점부터** 하나씩 본다.

2026-08-15 상하님 지시 —
"각 테마 상위 테마, 10년간 인기 테마 10개를 선정하고 그 각 테마의 시가총액 상위 5개,
그러면 50개 종목이 될 것 아니냐. 이 종목들을 나스닥 최저점부터 3개월·6개월·1년
검토해 보라고. 그러면 시간이 좀 걸리더라도 평균값 중간값 이런 거 필요 없이 각 종목별
상승율 하락율이 나올 것 아니냐. 그 각 종목이 갖고 있는 테마를 다 더하고 나누면 그
테마의 평균값이 나올 것 아니냐. 그리고 평균값 말고 또 중간값이 나오잖아."

## 그대로 한다

  ① **인기 테마 10개** — 테마에 속한 회사들의 **몸값(시가총액) 합계**를 10년 내내
     날마다 더해, 그 10년 가운데 값이 큰 테마 열 개. 앱이 「테마가 1년 최고에 붙어
     있나」를 잴 때 쓰는 몸값 합계와 **같은 방식**이다.
  ② **테마마다 시총 상위 5종목** — 그날 기준 몸값이 큰 다섯. 낙폭으로 거르지 않는다.
     상하님이 "시가총액 상위 5개"라 하셨으니 그대로 한다.
  ③ **자리** — 나스닥 종합이 −12·−18·−24%까지 빠졌다 **바닥 찍은 다음 날**(여섯 번).
  ④ **성적** — 다음 날 시가에 사서 3개월·6개월·1년 뒤 종가. **종목마다 그대로 적는다.**
  ⑤ 그다음에 테마별로 묶어 **평균값과 중간값을 둘 다** 낸다.

자세한 표는 화면에 다 찍고, 같은 것을 CSV로도 남긴다(research/_out/).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_theme_top5.py
"""

from __future__ import annotations

import csv
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_crash_appstyle import turn_days  # noqa: E402

STEPS = (-12.0, -18.0, -24.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
TOP_THEMES = 10
TOP_STOCKS = 5
OUT_DIR = ROOT / "research" / "_out"


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, opens = wide["close"][names], wide["open"][names]
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    shares = {}
    with (ROOT / "data" / "us_shares.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                shares[row["ticker"]] = float(row["shares"])
            except (TypeError, ValueError):
                continue
    have = [t for t in names if t in shares]
    cap = close[have] * pd.Series({t: shares[t] for t in have})

    themes = {t["name"]: [s for s in t["stocks"] if s in cap.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= TOP_STOCKS}

    # ① 인기 테마 10개 — 몸값 합계의 10년 **가운데 값**이 큰 순서
    size = {n: float(np.median(cap[m].sum(axis=1).dropna())) for n, m in themes.items()}
    popular = sorted(size, key=lambda n: -size[n])[:TOP_THEMES]

    print("① 10년간 인기 테마 10개 — 테마 몸값(시가총액) 합계의 10년 가운데 값")
    print("─" * 76)
    for rank, name in enumerate(popular, 1):
        print(f"   {rank:>2}등 {name:<20} {size[name]/1e12:>7.2f}조 달러"
              f"   ({len(themes[name])}종목)")
    dropped = [n for n in sorted(size, key=lambda n: -size[n])[TOP_THEMES:]]
    print(f"\n   뺀 테마 {len(dropped)}개 — {' · '.join(dropped)}")

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}
    bottoms = sorted({d for step in STEPS for d in turn_days(ixic, step)
                      if d in close.index})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_rows = []

    print(f"\n\n② 나스닥 저점 {len(bottoms)}번 × 테마 {TOP_THEMES}개 × 시총 상위"
          f" {TOP_STOCKS}종목 — 종목마다 그대로")
    for day in bottoms:
        print("\n" + "═" * 96)
        print(f"{day.date()} · 나스닥 바닥 다음 날")
        print("═" * 96)
        for name in popular:
            members = [t for t in themes[name] if pd.notna(cap.loc[day].get(t))]
            picks = sorted(members, key=lambda t: -cap.loc[day][t])[:TOP_STOCKS]
            if not picks:
                continue
            print(f"\n  ▣ {name}")
            head = (f"    {'종목':<8}{'시총':>10}" +
                    "".join(f"{label:>11}" for _h, label in HOLDS))
            print(head)
            by_hold = {label: [] for _h, label in HOLDS}
            for ticker in picks:
                cells = []
                for hold, label in HOLDS:
                    value = rets[hold].loc[day].get(ticker)
                    if pd.isna(value):
                        cells.append("아직".rjust(11))
                    else:
                        cells.append(f"{float(value):>+10.1f}%")
                        by_hold[label].append(float(value))
                    csv_rows.append({
                        "저점": day.date(), "테마": name, "종목": ticker,
                        "시총(억달러)": round(float(cap.loc[day][ticker]) / 1e8, 1),
                        "보유": label,
                        "수익률(%)": ("" if pd.isna(value) else round(float(value), 2)),
                    })
                print(f"    {ticker:<8}{cap.loc[day][ticker]/1e9:>8.0f}십억"
                      + "".join(cells))
            avg = "    " + f"{'평균':<8}{'':>10}"
            med = "    " + f"{'중간값':<8}{'':>10}"
            for _hold, label in HOLDS:
                values = by_hold[label]
                avg += ("아직".rjust(11) if not values
                        else f"{np.mean(values):>+10.1f}%")
                med += ("아직".rjust(11) if not values
                        else f"{np.median(values):>+10.1f}%")
            print(avg); print(med)

    # ③ 테마별로 여섯 자리를 모아 본다
    print("\n\n" + "═" * 96)
    print("③ 테마별 종합 — 여섯 자리 50종목을 테마마다 모아")
    print("═" * 96)
    head = f"{'테마':<20}" + "".join(f"{label + ' 평균':>13}{label + ' 중간':>13}"
                                     for _h, label in HOLDS)
    print(head); print("─" * 96)
    frame = pd.DataFrame(csv_rows)
    frame = frame[frame["수익률(%)"] != ""]
    for name in popular:
        line = f"{name:<20}"
        for _hold, label in HOLDS:
            part = frame[(frame["테마"] == name) & (frame["보유"] == label)]
            values = pd.to_numeric(part["수익률(%)"], errors="coerce").dropna()
            if values.empty:
                line += "아직".rjust(13) + "아직".rjust(13)
            else:
                line += f"{values.mean():>+12.1f}%{values.median():>+12.1f}%"
        print(line)
    print("─" * 96)
    line = f"{'열 테마 전부':<20}"
    for _hold, label in HOLDS:
        values = pd.to_numeric(
            frame[frame["보유"] == label]["수익률(%)"], errors="coerce").dropna()
        line += f"{values.mean():>+12.1f}%{values.median():>+12.1f}%"
    print(line)

    path = OUT_DIR / "us_crash_theme_top5.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\n표 전부를 여기에도 적었습니다 → {path}  ({len(csv_rows):,}줄)")


if __name__ == "__main__":
    main()
