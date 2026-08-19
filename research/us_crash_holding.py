"""급락 후 반등 — **얼마나 들고 있는 것이 유리했나** (2026-08-19 상하님 물음).

상하님 물음 — "파는 시점의 언제가 유리하다는 내용은 없었나?"

지시문 5장에는 있었다 — 나스닥이 깊게 빠졌으면 12개월, 얕으면 6개월에 팔라고.
그런데 그 숫자는 다른 명부에서 나온 것이라 **앱 명부로 다시 잰다.**

**이 프로그램은 앱을 바꾸지 않는다.** 파는 시점은 상하님이 정하신다(CLAUDE.md
0-1 바). 여기서는 지난 10년에 어느 기간이 어땠는지 숫자만 낸다.

재는 것
  A. 바닥에서 사서 얼마나 들고 있었을 때가 좋았나 (전체)
  B. 나스닥이 얼마나 깊게 빠진 바닥이었나에 따라 달랐나
  C. 배점 상위 종목만 골랐을 때도 같은 모양인가

쓰는 법:  python research/us_crash_holding.py
"""

from __future__ import annotations

import io
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

# 3개월·6개월·1년만 보면 그 사이가 안 보인다. 한 달 단위로 촘촘히 본다.
HOLDS = ((21, "1개월"), (42, "2개월"), (63, "3개월"), (84, "4개월"),
         (105, "5개월"), (126, "6개월"), (168, "8개월"), (210, "10개월"),
         (252, "1년"), (378, "1년 반"))

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def _table(title: str, groups: dict, note: str = "") -> None:
    say(f"  {title}")
    if note:
        say(f"    {note}")
    head = (f"    {'무리':<22}{'개수':>6}"
            + "".join(f"{label:>11}" for _d, label in HOLDS))
    say(head)
    say("    " + "-" * (len(head) - 4))
    for name, frame in groups.items():
        if frame is None or frame.empty:
            continue
        cells = []
        for days, _label in HOLDS:
            values = frame[f"r{days}"].dropna().to_numpy(float)
            cells.append(f"{np.median(values):>+10.1f}%" if values.size else f"{'-':>11}")
        say(f"    {name:<22}{len(frame):>6}" + "".join(cells))
    say()
    # 100번 중 몇 번 올랐나
    head2 = (f"    {'무리 (오른 횟수)':<22}{'개수':>6}"
             + "".join(f"{label:>11}" for _d, label in HOLDS))
    say(head2)
    say("    " + "-" * (len(head2) - 4))
    for name, frame in groups.items():
        if frame is None or frame.empty:
            continue
        cells = []
        for days, _label in HOLDS:
            values = frame[f"r{days}"].dropna().to_numpy(float)
            cells.append(f"{(values > 0).mean() * 100:>9.0f}번" if values.size
                         else f"{'-':>11}")
        say(f"    {name:<22}{len(frame):>6}" + "".join(cells))
    say()


def main() -> None:
    import jarvis3_data as j3
    import us_crash_newscore as base
    from us_rebound_shape import bottom_days
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][names], wide["high"][names]
    opens = wide["open"][names]
    qqq = wide["close"]["QQQ"].dropna()
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= base.MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma150 = close.rolling(150, min_periods=150).mean()
    ret120 = (close / close.shift(120) - 1.0) * 100.0
    vol60 = close.pct_change().rolling(60, min_periods=60).std() * 100.0

    # 나스닥 자신의 낙폭 — 그 바닥이 얼마나 깊었나를 가르는 값
    ndx_high = ixic.rolling(252, min_periods=252).max()
    ndx_drop = (ixic / ndx_high - 1.0) * 100.0

    at = {d: i for i, d in enumerate(dates)}
    days = sorted({d for series in (ixic, qqq) for step in base.STEPS
                   for d in bottom_days(series, step) if d in at})

    picks = []
    for day in days:
        idx = at[day]
        fh = from_high.iloc[idx]
        caught = [s for s in names
                  if not pd.isna(fh.get(s))
                  and base.STOCK_BAND[0] < fh[s] < base.STOCK_BAND[1]]
        if len(caught) < 20 or idx + 1 >= len(dates):
            continue
        entry = opens.iloc[idx + 1]
        vol_rank = vol60.iloc[idx][caught].rank(pct=True)
        theme_hits: dict[str, int] = {}
        for s in caught:
            for name in belongs.get(s) or []:
                theme_hits[name] = theme_hits.get(name, 0) + 1
        board_ret120, board_a150 = {}, {}
        for name, members in themes.items():
            vals = ret120.iloc[idx][members].dropna()
            if len(vals):
                board_ret120[name] = float(vals.mean())
            price, line = close.iloc[idx][members], sma150.iloc[idx][members]
            flags = [(p > l) for p, l in zip(price, line)
                     if np.isfinite(p) and np.isfinite(l)]
            if flags:
                board_a150[name] = float(np.mean(flags))
        top_ret120 = set(pd.Series(board_ret120).sort_values(ascending=False).head(3).index)
        top_a150 = set(pd.Series(board_a150).sort_values(ascending=False).head(3).index)
        depth = float(ndx_drop.get(day, np.nan))

        for s in caught:
            buy = base._f(entry.get(s))
            if np.isnan(buy) or buy <= 0:
                continue
            mine = belongs.get(s) or []
            rank = base._f(vol_rank.get(s))
            # 앱 배점 그대로 매긴다 — 변동성 40 · 30주선 30 · 동시하락 20 · 6개월 10
            score = 0.0
            if rank is not None and rank > 0.50:
                score += 40.0
            if any(n in top_a150 for n in mine):
                score += 30.0
            if max((theme_hits.get(n, 0) for n in mine), default=0) >= 4:
                score += 20.0
            if any(n in top_ret120 for n in mine):
                score += 10.0
            row = {"day": day, "ticker": s, "score": score, "ndx_drop": depth}
            for hold, _l in HOLDS:
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / buy - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s])
                    else np.nan)
            picks.append(row)

    frame = pd.DataFrame(picks)

    say("=" * 130)
    say("급락 후 반등 — 얼마나 들고 있는 것이 유리했나 (2026-08-19)")
    say("=" * 130)
    say("**이 표는 앱을 바꾸지 않습니다.** 파는 시점은 상하님이 정하십니다.")
    say(f"바닥 {frame['day'].nunique()}번 · 그날 조건에 걸린 종목 {len(frame)}개를 "
        "다음 날 아침에 샀다고 치고 잰 값입니다.")
    say("위 표는 가운데 수익, 아래 표는 100번 중 오른 횟수입니다.")
    say()

    say("=" * 130)
    say("A. 전체 — 들고 있는 기간별")
    say("=" * 130)
    _table("전체", {"조건에 걸린 종목 전부": frame})

    say("=" * 130)
    say("B. 나스닥이 얼마나 깊게 빠진 바닥이었나")
    say("=" * 130)
    groups = {}
    for label, low, high_ in (("얕음 (-12%보다 얕음)", -12.0, 0.0),
                              ("보통 (-12 ~ -18%)", -18.0, -12.0),
                              ("깊음 (-18%보다 깊음)", -100.0, -18.0)):
        sub = frame[(frame["ndx_drop"] > low) & (frame["ndx_drop"] <= high_)]
        if not sub.empty:
            groups[f"{label} · 바닥 {sub['day'].nunique()}번"] = sub
    _table("나스닥 낙폭별", groups,
           "지시문은 '깊으면 12개월 · 얕으면 6개월'이라 했습니다. 맞는지 봅니다.")

    say("=" * 130)
    say("C. 앱 배점 상위 종목만 골랐을 때도 같은 모양인가")
    say("=" * 130)
    _table("앱 배점별", {
        "70점 이상": frame[frame["score"] >= 70],
        "40~60점": frame[(frame["score"] >= 40) & (frame["score"] < 70)],
        "40점 미만": frame[frame["score"] < 40],
    })

    # 각 무리에서 가운데 수익이 가장 높았던 기간을 한 줄로 뽑는다.
    say("=" * 130)
    say("D. 한 줄 정리 — 무리마다 가운데 수익이 가장 높았던 기간")
    say("=" * 130)
    say(f"  {'무리':<30}{'가장 좋았던 기간':>18}{'그때 가운데 수익':>18}"
        f"{'1년 수익':>12}{'1년 오른 횟수':>15}")
    say("  " + "-" * 93)
    rows = [("전체", frame)]
    rows += [(name, sub) for name, sub in groups.items()]
    rows += [("배점 70점 이상", frame[frame["score"] >= 70]),
             ("배점 40점 미만", frame[frame["score"] < 40])]
    for name, sub in rows:
        if sub is None or sub.empty:
            continue
        best_label, best_value = "-", -999.0
        for days, label in HOLDS:
            values = sub[f"r{days}"].dropna().to_numpy(float)
            if values.size < 30:
                continue
            median = float(np.median(values))
            if median > best_value:
                best_label, best_value = label, median
        year = sub["r252"].dropna().to_numpy(float)
        say(f"  {name:<30}{best_label:>18}{best_value:>+17.1f}%"
            + (f"{np.median(year):>+11.1f}%{(year > 0).mean() * 100:>13.0f}번"
               if year.size else f"{'-':>12}{'-':>15}"))
    say()

    out = ROOT / "research" / "_out" / "us_crash_holding.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(BUF.getvalue())
    print(f"-> {out}")


if __name__ == "__main__":
    main()
