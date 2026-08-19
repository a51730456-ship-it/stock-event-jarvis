"""급락 후 반등 조사 **전부를 텍스트 한 장으로** 만든다 (2026-08-15).

상하님 지시 — "텍스트로 다 만들어 봐라. 날짜까지."

## 무엇이 들어가나

  1부  나스닥 10년 하락 국면 **전부** (21개) — 시작·최저점 날짜·낙폭·끝난 날
  2부  그중 앱이 쓰는 여섯 자리 — 최저점 날짜와 **사는 날**
  3부  10년 인기 테마 10개 (몸값 합계 가운데 값)
  4부  자리 여섯 × 테마 열 × 시총 상위 다섯 종목 = 종목마다 한 줄
       **매수일·매수가 · 3개월/6개월/1년 매도일·매도가·수익률**을 전부 적는다
  5부  테마별 종합 — 평균값과 중간값을 **둘 다**
  6부  이 조사의 한계 — 숨기지 않고 적는다

값은 배당 반영 종가(yfinance auto_adjust)다. **매수는 다음 거래일 시가**,
매도는 그날부터 60·120·250거래일 뒤 종가다(앱 설명서 규칙 그대로).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_report_text.py
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

STEPS = (-12.0, -18.0, -24.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
START_EDGE, END_EDGE = -5.0, -1.0
TOP_THEMES, TOP_STOCKS = 10, 5
OUT = ROOT / "research" / "_out" / "급락후반등_조사보고서.txt"


def main() -> None:
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, opens = wide["close"][names], wide["open"][names]
    dates = list(close.index)
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"].dropna()

    import jarvis3_data as j3
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
    size = {n: float(np.median(cap[m].sum(axis=1).dropna())) for n, m in themes.items()}
    popular = sorted(size, key=lambda n: -size[n])[:TOP_THEMES]

    lines: list[str] = []

    def w(text: str = "") -> None:
        lines.append(text)
        print(text)

    w("=" * 100)
    w("급락 후 반등장 (낙폭종목) — 조사 보고서")
    w("만든 날 2026-08-15 · research/us_crash_report_text.py")
    w("=" * 100)
    w()
    w(f"쓴 자료  나스닥 종합지수 {len(ixic):,}일 "
      f"({ixic.index[0].date()} ~ {ixic.index[-1].date()})")
    w(f"         명부 종목 {len(names)}개 일봉 {len(dates):,}일 "
      f"({dates[0].date()} ~ {dates[-1].date()})")
    w("         값은 배당 반영 종가. 매수는 다음 거래일 시가, 매도는 그날부터")
    w("         60·120·250거래일 뒤 종가입니다.")
    w()

    # ── 1부 ──────────────────────────────────────────────────────────────────
    drop = (ixic / ixic.cummax() - 1.0) * 100.0
    index = list(drop.index)
    episodes, start = [], None
    for i, value in enumerate(drop.to_numpy()):
        if value <= START_EDGE and start is None:
            start = i
        elif start is not None and value > END_EDGE:
            episodes.append((start, i - 1)); start = None
    if start is not None:
        episodes.append((start, len(index) - 1))

    w("=" * 100)
    w("1부 · 나스닥 하락 국면 전부 — 고점 대비 −5% 아래로 내려간 것")
    w("=" * 100)
    w("**「고점 날짜」가 그 국면의 꼭대기입니다.** 「−5% 닿은 날」은 거기서 5% 내려온")
    w("날이고, 「최저점」은 그 국면에서 가장 깊었던 날입니다. 셋은 서로 다른 날입니다.")
    w("")
    w(f"{'번호':<5}{'고점 날짜':<13}{'고점 지수':>10}  {'−5% 닿은 날':<14}"
      f"{'최저점 날짜':<13}{'최저 낙폭':>10}  {'끝난 날':<13}   {'닿은 문턱':<15}{'앱이 썼나'}")
    w("─" * 118)
    used = []
    peak_series = ixic.cummax()
    for number, (a, b) in enumerate(episodes, 1):
        segment = drop.iloc[a:b + 1]
        worst_day, worst = segment.idxmin(), float(segment.min())
        # 이 국면의 꼭대기 — 최저점 날까지의 사상 최고가와 같은 값이 처음 찍힌 날
        peak_value = float(peak_series.loc[worst_day])
        before = ixic.loc[:worst_day]
        peak_day = before[before >= peak_value - 1e-9].index[0]
        pos = index.index(worst_day)
        next_day = index[pos + 1] if pos + 1 < len(index) else None
        touched = [s for s in STEPS if worst <= s]
        touch = " ".join(f"{int(s)}%" for s in touched) or "—"
        if not touched:
            mark = "안 씀 · −12% 못 닿음"
        elif next_day is None or next_day not in close.index:
            mark = "안 씀 · 종목 자료 밖"
        else:
            mark = f"썼다 → {next_day.date()}"
            used.append((worst_day, worst, next_day, touch))
        w(f"{number:<5}{str(peak_day.date()):<13}{peak_value:>10,.0f}  "
          f"{str(index[a].date()):<14}{str(worst_day.date()):<13}"
          f"{worst:>9.1f}%  {str(index[b].date()):<13}   "
          f"{touch:<15}{mark}")
    w()
    w(f"국면 {len(episodes)}개 중 앱이 쓴 것 {len(used)}개.")
    w()

    # ── 2부 ──────────────────────────────────────────────────────────────────
    w("=" * 100)
    w("2부 · 앱이 쓰는 여섯 자리")
    w("=" * 100)
    w(f"{'':<4}{'고점 날짜':<13}{'고점 지수':>10}   {'최저점 날짜':<14}{'그날 낙폭':>10}"
      f"   {'사는 날':<14}{'고점→바닥':>9}   {'닿은 문턱'}")
    w("─" * 104)
    for i, (worst_day, worst, next_day, touch) in enumerate(used, 1):
        peak_value = float(peak_series.loc[worst_day])
        before = ixic.loc[:worst_day]
        peak_day = before[before >= peak_value - 1e-9].index[0]
        days = len(ixic.loc[peak_day:worst_day]) - 1
        w(f"{i:<4}{str(peak_day.date()):<13}{peak_value:>10,.0f}   "
          f"{str(worst_day.date()):<14}{worst:>9.1f}%   "
          f"{str(next_day.date()):<14}{days:>8}일   {touch}")
    w()

    # ── 3부 ──────────────────────────────────────────────────────────────────
    w("=" * 100)
    w("3부 · 10년간 인기 테마 10개 — 테마 몸값(시가총액) 합계의 10년 가운데 값")
    w("=" * 100)
    for rank, name in enumerate(popular, 1):
        w(f"   {rank:>2}등  {name:<22}{size[name]/1e12:>7.2f}조 달러  "
          f"({len(themes[name])}종목)")
    left = [n for n in sorted(size, key=lambda n: -size[n])[TOP_THEMES:]]
    w()
    w(f"   뺀 테마 {len(left)}개 — {' · '.join(left)}")
    w()

    # ── 4부 ──────────────────────────────────────────────────────────────────
    w("=" * 100)
    w("4부 · 자리 여섯 × 테마 열 × 시총 상위 다섯 종목 — 종목마다 날짜까지")
    w("=" * 100)
    at = {d: i for i, d in enumerate(dates)}
    rows_for_csv = []
    for _worst_day, _worst, buy_day, _touch in used:
        w()
        w("█" * 100)
        w(f"█  사는 날 {buy_day.date()}  (그 앞 최저점 {_worst_day.date()} · {_worst:.1f}%)")
        w("█" * 100)
        for name in popular:
            members = [t for t in themes[name] if pd.notna(cap.loc[buy_day].get(t))]
            picks = sorted(members, key=lambda t: -cap.loc[buy_day][t])[:TOP_STOCKS]
            if not picks:
                continue
            w()
            w(f"  ▣ {name}")
            w(f"    {'종목':<7}{'시총(십억$)':>12}  {'매수일':<12}{'매수가':>10}  │"
              + "".join(f"  {label} 매도일{'':<4}{'매도가':>9}{'수익률':>9}  │"
                        for _h, label in HOLDS))
            gathered = {label: [] for _h, label in HOLDS}
            for ticker in picks:
                pos = at[buy_day]
                buy_price = float(opens.loc[buy_day][ticker]) if pd.notna(
                    opens.loc[buy_day].get(ticker)) else None
                if buy_price is None:
                    continue
                cells = ""
                for hold, label in HOLDS:
                    sell_pos = pos + hold
                    if sell_pos >= len(dates):
                        cells += f"  {'아직':<12}{'':>12}{'':>9}  │"
                        sell_day = None; profit = None
                    else:
                        sell_day = dates[sell_pos]
                        sell_price = float(close.loc[sell_day][ticker])
                        profit = (sell_price / buy_price - 1.0) * 100.0
                        gathered[label].append(profit)
                        cells += (f"  {str(sell_day.date()):<12}"
                                  f"{sell_price:>12.2f}{profit:>+8.1f}%  │")
                    rows_for_csv.append({
                        "사는날": buy_day.date(), "테마": name, "종목": ticker,
                        "매수가": round(buy_price, 2), "보유": label,
                        "매도일": (sell_day.date() if sell_day is not None else ""),
                        "수익률(%)": ("" if profit is None else round(profit, 2)),
                    })
                w(f"    {ticker:<7}{cap.loc[buy_day][ticker]/1e9:>12,.0f}  "
                  f"{str(buy_day.date()):<12}{buy_price:>10.2f}  │" + cells)
            avg = f"    {'평균':<7}{'':>12}  {'':<12}{'':>10}  │"
            med = f"    {'중간값':<7}{'':>12}  {'':<12}{'':>10}  │"
            for _hold, label in HOLDS:
                values = gathered[label]
                avg += (f"  {'':<12}{'':>12}"
                        + (f"{'아직':>9}" if not values else f"{np.mean(values):>+8.1f}%")
                        + "  │")
                med += (f"  {'':<12}{'':>12}"
                        + (f"{'아직':>9}" if not values else f"{np.median(values):>+8.1f}%")
                        + "  │")
            w(avg); w(med)
    w()

    # ── 5부 ──────────────────────────────────────────────────────────────────
    frame = pd.DataFrame(rows_for_csv)
    frame["수익률(%)"] = pd.to_numeric(frame["수익률(%)"], errors="coerce")
    w("=" * 100)
    w("5부 · 테마별 종합 — 여섯 자리를 모아, 평균값과 중간값을 둘 다")
    w("=" * 100)
    w(f"{'테마':<22}" + "".join(f"{label+' 평균':>12}{label+' 중간':>12}"
                                for _h, label in HOLDS) + f"{'줄 수':>8}")
    w("─" * 100)
    for name in popular:
        line = f"{name:<22}"
        part = frame[frame["테마"] == name]
        for _hold, label in HOLDS:
            values = part[part["보유"] == label]["수익률(%)"].dropna()
            line += ("아직".rjust(12) + "아직".rjust(12) if values.empty
                     else f"{values.mean():>+11.1f}%{values.median():>+11.1f}%")
        line += f"{len(part['수익률(%)'].dropna()):>8}"
        w(line)
    w("─" * 100)
    line = f"{'열 테마 전부':<22}"
    for _hold, label in HOLDS:
        values = frame[frame["보유"] == label]["수익률(%)"].dropna()
        line += f"{values.mean():>+11.1f}%{values.median():>+11.1f}%"
    w(line + f"{len(frame['수익률(%)'].dropna()):>8}")
    w()

    # ── 6부 ──────────────────────────────────────────────────────────────────
    w("=" * 100)
    w("6부 · 이 조사의 한계 — 숨기지 않고 적습니다")
    w("=" * 100)
    w()
    w("① 자리가 여섯 번뿐입니다.")
    w("   2026-03-31 자리는 아직 3개월치밖에 안 지났습니다. 6개월·1년을 잴 수 있는")
    w("   자리는 다섯 번입니다. 다섯 번은 우연과 실력을 가르기에 너무 적습니다.")
    w()
    w("② 2016-02-11 급락(−18.2%)은 뺐습니다.")
    w("   진짜 급락인데 명부 종목 일봉이 2016-08-08부터라 성적을 못 잽니다.")
    w()
    w("③ 명부는 지금 종목입니다.")
    w("   10년 전에 그 자리에 있던 종목이 아니라, 지금 앱이 보는 199종목으로")
    w("   과거를 되짚었습니다. 그동안 망하거나 상장폐지된 회사는 빠져 있어")
    w("   성적이 실제보다 좋게 나옵니다(생존 편향).")
    w()
    w("④ 시가총액은 지금 주식수로 냈습니다.")
    w("   과거 주식수를 쓰지 않았으므로 옛 순위가 조금 다를 수 있습니다.")
    w()
    w("⑤ 테마 명부는 앱이 정한 것입니다.")
    w("   종목 하나를 바꾸면 테마 평균이 바뀝니다(2026-08-09에 실제로 겪었습니다).")
    w()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    csv_path = OUT.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_for_csv[0]))
        writer.writeheader(); writer.writerows(rows_for_csv)
    print(f"\n텍스트 → {OUT}")
    print(f"엑셀   → {csv_path}  ({len(rows_for_csv):,}줄)")


if __name__ == "__main__":
    main()
