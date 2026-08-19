"""급락 후 반등장 — 새 항목과 지금 항목이 **겹치는가**, 같이 쓰면 좋아지는가.

us_crash_newscore.py에서 항목 하나하나는 재 봤다. 그런데 점수를 정하려면
두 가지를 더 알아야 한다.

  1. 새 항목(흔들림·낙폭)과 지금 항목(테마 세 가지)이 **같은 종목을 고르는가**.
     같은 종목을 고른다면 둘 다 점수를 주는 것은 한 가지를 두 번 세는 셈이다.
  2. 두 가지를 **같이 만족한 종목**이 하나만 만족한 종목보다 나은가.

쓰는 법:  python research/us_crash_newscore2.py
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

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def main() -> None:
    import us_crash_newscore as base

    # 첫 프로그램의 계산을 그대로 다시 쓴다 — 표를 만드는 부분만 갈아 끼운다.
    frame = _build(base)
    holds = base.HOLDS

    tests = {
        "흔들림 큰 절반": frame["vol_rank"] > 0.50,
        "많이 빠진 1/3": frame["deep_rank"] > 2 / 3,
        "테마 4개 동시하락": frame["together"] >= 4,
        "테마 6개월 상위3": frame["t_ret120_top"] == 1,
        "테마 30주선 상위3": frame["t_a150_top"] == 1,
    }

    say("=" * 96)
    say("1. 항목끼리 얼마나 겹치나 — 두 항목을 **함께** 만족한 종목의 비율")
    say("=" * 96)
    keys = list(tests)
    say(f"  {'':<20}" + "".join(f"{k:>20}" for k in keys))
    for a in keys:
        cells = []
        for b in keys:
            both = (tests[a] & tests[b]).sum()
            only_a = tests[a].sum()
            cells.append(f"{both / max(only_a, 1) * 100:>19.0f}%")
        say(f"  {a:<20}" + "".join(cells))
    say()
    say("  읽는 법 — 가로줄 항목에 걸린 종목 가운데 세로줄 항목에도 걸린 비율입니다.")
    say("            숫자가 크면 두 항목이 같은 종목을 고르고 있다는 뜻입니다.")
    say()

    say("=" * 96)
    say("2. 두 항목을 같이 쓰면 좋아지나")
    say("=" * 96)
    pairs = [
        ("흔들림 큰 절반", "테마 6개월 상위3"),
        ("흔들림 큰 절반", "테마 30주선 상위3"),
        ("흔들림 큰 절반", "테마 4개 동시하락"),
        ("흔들림 큰 절반", "많이 빠진 1/3"),
        ("많이 빠진 1/3", "테마 6개월 상위3"),
    ]
    head = (f"  {'무리':<38}{'개수':>6}"
            + "".join(f"{label + ' 가운데':>14}{'오름':>7}" for _d, label in holds))
    for a, b in pairs:
        say("  " + "-" * (len(head) - 2))
        say(head)
        groups = {
            f"{a} + {b} 둘 다": tests[a] & tests[b],
            f"{a}만": tests[a] & ~tests[b],
            f"{b}만": ~tests[a] & tests[b],
            "둘 다 아님": ~tests[a] & ~tests[b],
        }
        for label, mask in groups.items():
            sub = frame[mask]
            if sub.empty:
                continue
            cells = []
            for hold, _l in holds:
                v = sub[f"r{hold}"].dropna().to_numpy(float)
                cells.append(f"{np.median(v):>+13.1f}%{(v > 0).mean() * 100:>6.0f}번"
                             if v.size else f"{'-':>14}{'-':>7}")
            say(f"  {label:<38}{len(sub):>6}" + "".join(cells))
        say()

    say("=" * 96)
    say("3. 20일선 위는 정말 거꾸로인가 — 흔들림을 같게 맞춰 놓고 다시 본다")
    say("=" * 96)
    head = (f"  {'무리':<38}{'개수':>6}"
            + "".join(f"{label + ' 가운데':>14}{'오름':>7}" for _d, label in holds))
    say(head)
    say("  " + "-" * (len(head) - 2))
    for band_label, band in (("흔들림 큰 절반 안에서", frame["vol_rank"] > 0.5),
                             ("흔들림 작은 절반 안에서", frame["vol_rank"] <= 0.5)):
        for name, mask in (("20일선 위", frame["above20"] == 1),
                           ("20일선 아래", frame["above20"] == 0)):
            sub = frame[band & mask]
            if sub.empty:
                continue
            cells = []
            for hold, _l in holds:
                v = sub[f"r{hold}"].dropna().to_numpy(float)
                cells.append(f"{np.median(v):>+13.1f}%{(v > 0).mean() * 100:>6.0f}번"
                             if v.size else f"{'-':>14}{'-':>7}")
            say(f"  {band_label + ' / ' + name:<38}{len(sub):>6}" + "".join(cells))
    say()

    out = ROOT / "research" / "_out" / "us_crash_newscore2.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(BUF.getvalue())
    print(f"-> {out}")


def _build(base):
    """us_crash_newscore.main()이 만드는 표를 그대로 다시 만든다."""
    import jarvis3_data as j3
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
    sma20 = close.rolling(20, min_periods=20).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    ret120 = (close / close.shift(120) - 1.0) * 100.0
    vol60 = close.pct_change().rolling(60, min_periods=60).std() * 100.0

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
        deep_rank = (-fh[caught]).rank(pct=True)
        theme_hits: dict[str, int] = {}
        for s in caught:
            for name in belongs.get(s) or []:
                theme_hits[name] = theme_hits.get(name, 0) + 1
        board_ret120, board_above150 = {}, {}
        for name, members in themes.items():
            vals = ret120.iloc[idx][members].dropna()
            if len(vals):
                board_ret120[name] = float(vals.mean())
            flags = [base._above(close.iloc[idx].get(s), sma150.iloc[idx].get(s))
                     for s in members]
            flags = [v for v in flags if not np.isnan(v)]
            if flags:
                board_above150[name] = float(np.mean(flags))
        top_ret120 = set(pd.Series(board_ret120).sort_values(ascending=False).head(3).index)
        top_a150 = set(pd.Series(board_above150).sort_values(ascending=False).head(3).index)

        for s in caught:
            buy = base._f(entry.get(s))
            if np.isnan(buy) or buy <= 0:
                continue
            mine = belongs.get(s) or []
            row = {"day": day, "ticker": s,
                   "vol_rank": base._f(vol_rank.get(s)),
                   "deep_rank": base._f(deep_rank.get(s)),
                   "above20": base._above(close.iloc[idx].get(s), sma20.iloc[idx].get(s)),
                   "together": max((theme_hits.get(n, 0) for n in mine), default=0),
                   "t_ret120_top": 1.0 if any(n in top_ret120 for n in mine) else 0.0,
                   "t_a150_top": 1.0 if any(n in top_a150 for n in mine) else 0.0}
            for hold, _l in base.HOLDS:
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / buy - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s])
                    else np.nan)
            picks.append(row)
    return pd.DataFrame(picks)


if __name__ == "__main__":
    main()
