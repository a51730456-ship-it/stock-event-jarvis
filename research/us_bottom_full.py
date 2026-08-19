"""나스닥 **최저점 전부** × 테마 20개 × 시총 상위 5종목 — 통째로 잰다 (2026-08-15).

상하님 지시 —
"넌 그냥 과거 최저점만 보면 된다. −12 −18 이런 거 필요없다. 그냥 최저점에서 테마들이
어떻게 움직였는지, 그 테마의 상위 5개들이 어떤 수익 손실을 3개월·6개월·1년 기준만
적으면 되지. 그리고 얼만큼 눌린 것이 시가총액이 높은 것인지 제일 작은 5등인지.
테마 20개로 확대하고, 또 너가 생각해서 검토하고, 내가 준 자료에 테마 방법에
효과 있는 것들을 검증하란 이야기지."

## 그대로 한다

  자리   나스닥 종합이 고점 대비 −5% 아래로 내려간 **모든 국면의 최저점**.
         **−12·−18·−24 문턱은 안 쓴다.** 그래서 자리가 여섯이 아니라 스무 개다.
  대상   테마 **20개 전부** × 각 테마의 **시가총액 상위 5종목**
  적을 것 종목마다 — 고점 대비 얼마나 눌렸나 · 시총 몇 등인가 ·
         3개월·6개월·1년 수익률 (다음 날 시가 매수 → 60·120·250거래일 뒤 종가)

## 그다음 넷을 본다

  ㉮ 테마별  — 어느 테마가 바닥에서 잘 갔나
  ㉯ 시총 순위별 — **1등이 나은가 5등이 나은가.** 눌린 폭도 함께.
     Moskowitz & Grinblatt(1999)은 "산업 모멘텀의 이익은 **가장 크고 유동성 높은
     종목**에서 나온다"고 했다(docs/METHOD_ORIGINS.md). 그 말이 우리 자료에서도
     맞는지 본다.
  ㉰ 눌린 폭별 — 많이 빠진 것이 나은가 덜 빠진 것이 나은가
  ㉱ 상하님이 주신 자료의 잣대들 — 종목마다 재서 성적을 가른다
       · Weinstein(1988) 30주선 — 종목이 150일선 위인가
       · George & Hwang(2004) — 지금 값 ÷ 52주 최고가
       · Minervini Trend Template — 50>150>200일선 줄서기
       · Moskowitz & Grinblatt(1999) — 시가총액 · 거래대금
       · Jegadeesh & Titman(1993) — 최근 12개월 수익률

성적을 합칠 때는 **언제나 중간값**이다. 평균은 2020년 한 번에 끌려간다.

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_bottom_full.py
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

HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
START_EDGE, END_EDGE = -5.0, -1.0
TOP_STOCKS = 5
OUT = ROOT / "research" / "_out" / "나스닥최저점_테마20_전체.txt"


def mid(values):
    return float(np.median(values)) if len(values) else float("nan")


def main() -> None:
    from us_yearly import fetch
    import jarvis3_data as j3

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][names], wide["high"][names], wide["low"][names]
    opens, volume = wide["open"][names], wide["volume"][names]
    dates = list(close.index)
    at = {d: i for i, d in enumerate(dates)}
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"].dropna()

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
    themes = {n: m for n, m in themes.items() if len(m) >= 2}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    gh = (close / high52) * 100.0                      # George & Hwang
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above150 = close > sma150                          # Weinstein 30주선
    trend_template = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
                      & (sma200 > sma200.shift(20)))   # Minervini
    money = (close * volume).rolling(20, min_periods=10).mean()
    mom12 = (close / close.shift(250) - 1.0) * 100.0   # Jegadeesh & Titman

    # ── 최저점 모으기 — 문턱 없이 국면마다 하나 ────────────────────────────────
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

    bottoms = []
    for a, b in episodes:
        segment = drop.iloc[a:b + 1]
        worst_day, worst = segment.idxmin(), float(segment.min())
        pos = index.index(worst_day)
        buy = index[pos + 1] if pos + 1 < len(index) else None
        if buy is None or buy not in at or at[buy] + 60 >= len(dates):
            continue
        bottoms.append((worst_day, worst, buy))

    lines: list[str] = []

    def w(text: str = "") -> None:
        lines.append(text); print(text)

    w("=" * 108)
    w("나스닥 최저점 전부 × 테마 20개 × 시총 상위 5종목")
    w("만든 날 2026-08-15 · research/us_bottom_full.py")
    w("=" * 108)
    w()
    w(f"자리   나스닥 하락 국면의 최저점 {len(bottoms)}개 — **문턱(−12·−18·−24)을 안 씁니다**")
    w(f"대상   테마 {len(themes)}개 × 시총 상위 {TOP_STOCKS}종목")
    w("성적   최저점 **다음 거래일 시가**에 사서 60·120·250거래일 뒤 종가")
    w("합칠 때는 **언제나 중간값**입니다.")
    w()
    w("최저점 목록")
    w(f"{'':<4}{'최저점 날짜':<14}{'그날 낙폭':>10}   {'사는 날'}")
    w("─" * 52)
    for i, (worst_day, worst, buy) in enumerate(bottoms, 1):
        w(f"{i:<4}{str(worst_day.date()):<14}{worst:>9.1f}%   {buy.date()}")
    w()

    # ── 자리마다 · 테마마다 · 종목마다 ────────────────────────────────────────
    records = []
    for worst_day, worst, buy in bottoms:
        for theme_name, members in themes.items():
            valid = [t for t in members if pd.notna(cap.loc[buy].get(t))]
            picks = sorted(valid, key=lambda t: -cap.loc[buy][t])[:TOP_STOCKS]
            for place, ticker in enumerate(picks, 1):
                buy_price = opens.loc[buy].get(ticker)
                if pd.isna(buy_price):
                    continue
                row = {
                    "최저점": worst_day.date(), "지수낙폭": round(worst, 1),
                    "사는날": buy.date(), "테마": theme_name, "종목": ticker,
                    "시총등수": place,
                    "시총(십억$)": round(float(cap.loc[buy][ticker]) / 1e9, 1),
                    "눌린폭(%)": (None if pd.isna(from_high.loc[buy].get(ticker))
                                else round(float(from_high.loc[buy][ticker]), 1)),
                    "30주선위": bool(above150.loc[buy].get(ticker, False)),
                    "줄서기": bool(trend_template.loc[buy].get(ticker, False)),
                    "52주위치(%)": (None if pd.isna(gh.loc[buy].get(ticker))
                                  else round(float(gh.loc[buy][ticker]), 1)),
                    "거래대금(백만$)": (None if pd.isna(money.loc[buy].get(ticker))
                                   else round(float(money.loc[buy][ticker]) / 1e6, 0)),
                    "12개월모멘텀(%)": (None if pd.isna(mom12.loc[buy].get(ticker))
                                   else round(float(mom12.loc[buy][ticker]), 1)),
                }
                for hold, label in HOLDS:
                    sell_pos = at[buy] + hold
                    if sell_pos < len(dates):
                        sell = float(close.loc[dates[sell_pos]][ticker])
                        row[label] = round((sell / float(buy_price) - 1.0) * 100.0, 1)
                        row[f"{label}매도일"] = dates[sell_pos].date()
                    else:
                        row[label] = None
                        row[f"{label}매도일"] = None
                records.append(row)

    frame = pd.DataFrame(records)
    w(f"모은 줄 — {len(frame):,}개 (자리 {len(bottoms)} × 테마 {len(themes)} × 종목 {TOP_STOCKS})")
    w()

    def block(title: str, group_col: str, order=None) -> None:
        w("=" * 108)
        w(title)
        w("=" * 108)
        head = (f"{group_col:<22}{'줄 수':>7}{'눌린폭 중간':>13}"
                + "".join(f"{label + ' 중간':>13}" for _h, label in HOLDS)
                + f"{'1년 오른 비율':>15}")
        w(head); w("─" * 106)
        keys = order if order is not None else sorted(frame[group_col].dropna().unique())
        for key in keys:
            part = frame[frame[group_col] == key]
            if part.empty:
                continue
            line = f"{str(key):<22}{len(part):>7}"
            pressed = part["눌린폭(%)"].dropna()
            line += f"{mid(pressed.tolist()):>12.1f}%"
            for _hold, label in HOLDS:
                values = part[label].dropna().tolist()
                line += ("  잴 수 없음".rjust(13) if not values
                         else f"{mid(values):>+12.1f}%")
            year = part["1년"].dropna()
            line += ("".rjust(15) if year.empty
                     else f"{(year > 0).mean() * 100:>13.0f}번")
            w(line)
        w()

    theme_order = sorted(themes, key=lambda n: -mid(
        frame[frame["테마"] == n]["1년"].dropna().tolist()) if
        len(frame[frame["테마"] == n]["1년"].dropna()) else 0)
    block("㉮ 테마별 — 바닥에서 산 뒤 어느 테마가 잘 갔나 (1년 중간값 순)",
          "테마", theme_order)
    block("㉯ 시총 순위별 — 1등이 나은가 5등이 나은가 "
          "(Moskowitz & Grinblatt 1999 검증)", "시총등수", [1, 2, 3, 4, 5])

    # ㉰ 눌린 폭별
    w("=" * 108)
    w("㉰ 눌린 폭별 — 많이 빠진 것이 나은가 덜 빠진 것이 나은가")
    w("=" * 108)
    bands = ((-1e9, -50, "−50% 아래"), (-50, -35, "−35~−50%"),
             (-35, -20, "−20~−35%"), (-20, -10, "−10~−20%"), (-10, 1e9, "−10% 안"))
    head = (f"{'눌린 폭':<16}{'줄 수':>7}" +
            "".join(f"{label + ' 중간':>13}" for _h, label in HOLDS) + f"{'1년 오른 비율':>15}")
    w(head); w("─" * 80)
    for lo, hi, label in bands:
        part = frame[(frame["눌린폭(%)"] > lo) & (frame["눌린폭(%)"] <= hi)]
        if part.empty:
            continue
        line = f"{label:<16}{len(part):>7}"
        for _hold, hold_label in HOLDS:
            values = part[hold_label].dropna().tolist()
            line += ("  잴 수 없음".rjust(13) if not values else f"{mid(values):>+12.1f}%")
        year = part["1년"].dropna()
        line += ("".rjust(15) if year.empty else f"{(year > 0).mean() * 100:>13.0f}번")
        w(line)
    w()

    # ㉱ 상하님이 주신 자료의 잣대들
    w("=" * 108)
    w("㉱ 상하님이 주신 자료의 잣대 — 바닥에서 실제로 값을 했나")
    w("   (근거 논문·책은 docs/METHOD_ORIGINS.md)")
    w("=" * 108)
    tests = (
        ("Weinstein 30주선 위", lambda f: f["30주선위"], "예", "아니오"),
        ("Minervini 줄서기", lambda f: f["줄서기"], "예", "아니오"),
        ("George·Hwang 52주 위치 위쪽 절반",
         lambda f: f["52주위치(%)"] > f["52주위치(%)"].median(), "위쪽", "아래쪽"),
        ("M&G 시가총액 위쪽 절반",
         lambda f: f["시총(십억$)"] > f["시총(십억$)"].median(), "큰 쪽", "작은 쪽"),
        ("M&G 거래대금 위쪽 절반",
         lambda f: f["거래대금(백만$)"] > f["거래대금(백만$)"].median(), "많은 쪽", "적은 쪽"),
        ("J&T 12개월 모멘텀 위쪽 절반",
         lambda f: f["12개월모멘텀(%)"] > f["12개월모멘텀(%)"].median(), "위쪽", "아래쪽"),
    )
    head = (f"{'잣대':<30}{'가름':<10}{'줄 수':>7}"
            + "".join(f"{label:>12}" for _h, label in HOLDS) + "   자리별 이김")
    w(head); w("─" * 106)
    for test_name, picker, yes_label, no_label in tests:
        won = {label: [0, 0] for _h, label in HOLDS}
        for _day, part in frame.groupby("사는날"):
            flag = picker(part)
            for _hold, label in HOLDS:
                yes = part[flag][label].dropna().tolist()
                no = part[~flag][label].dropna().tolist()
                if len(yes) < 5 or len(no) < 5:
                    continue
                won[label][1] += 1
                won[label][0] += 1 if mid(yes) > mid(no) else 0
        flag_all = picker(frame)
        for label_text, mask in ((yes_label, flag_all), (no_label, ~flag_all)):
            part = frame[mask]
            line = f"{test_name if label_text == yes_label else '':<30}{label_text:<10}{len(part):>7}"
            for _hold, hold_label in HOLDS:
                values = part[hold_label].dropna().tolist()
                line += ("잴 수 없음".rjust(12) if not values else f"{mid(values):>+11.1f}%")
            if label_text == yes_label:
                line += "   " + " · ".join(
                    f"{hold_label} {won[hold_label][0]}/{won[hold_label][1]}"
                    for _h, hold_label in HOLDS)
            w(line)
        w("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    csv_path = OUT.with_suffix(".csv")
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n텍스트 → {OUT}")
    print(f"엑셀   → {csv_path}  ({len(frame):,}줄)")


if __name__ == "__main__":
    main()
