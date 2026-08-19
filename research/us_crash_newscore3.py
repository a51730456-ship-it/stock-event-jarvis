"""급락 후 반등장 배점 — **200종목 전부 + 지금 화면이 쓰는 테마 순위**로 다시 잰다.

상하님 지시(2026-08-19) — "200종목 다 하고, 지난번에 다시 정리한 테마 기준도
그 기준으로 그 종목으로 다시 배점을 하라."

앞의 두 프로그램(us_crash_newscore.py·2.py)은 지시문이 말한 항목과 지금 배점
세 가지를 쟀다. 여기서는 두 가지를 더 한다.

  1. **200종목 전부가 들어갔는지** 확인한다. 테마에 속하지 않은 종목이
     몇 개이고 그 종목들 성적이 어떤지 따로 적는다.
  2. 화면 「20개 테마 실시간 순위」가 쓰는 **그 점수 방식 그대로**(20일선 위 40 ·
     5일 오른 비율 30 · 20일 오른 비율 20 · 덜 빠졌나 10) 과거 날짜에서 테마
     순위를 매기고, 상위 3등·5등에 속한 종목이 나았는지 잰다.

쓰는 법:  python research/us_crash_newscore3.py
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


def _scale(value, low, high, points):
    """jarvis3_data._scale과 같은 계산 — 낮으면 0점, 높으면 만점, 사이는 비례."""
    if value is None or not np.isfinite(value):
        return 0.0
    if high == low:
        return 0.0
    share = (float(value) - low) / (high - low)
    return float(min(max(share, 0.0), 1.0) * points)


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
    sma20 = close.rolling(20, min_periods=20).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    ret5 = (close / close.shift(5) - 1.0) * 100.0
    ret20 = (close / close.shift(20) - 1.0) * 100.0
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

        # ── 화면 「20개 테마 실시간 순위」와 같은 점수 방식 ───────────────
        board_rank_score, board_ret120, board_a150 = {}, {}, {}
        for name, members in themes.items():
            price = close.iloc[idx][members]
            line20 = sma20.iloc[idx][members]
            flags20 = [(p > l) for p, l in zip(price, line20)
                       if np.isfinite(p) and np.isfinite(l)]
            up5 = [v > 0 for v in ret5.iloc[idx][members] if np.isfinite(v)]
            up20 = [v > 0 for v in ret20.iloc[idx][members] if np.isfinite(v)]
            drops = [v for v in fh[members] if np.isfinite(v)]
            board_rank_score[name] = round(
                _scale(np.mean(flags20) * 100 if flags20 else None, 25, 85, 40.0)
                + _scale(np.mean(up5) * 100 if up5 else None, 20, 80, 30.0)
                + _scale(np.mean(up20) * 100 if up20 else None, 25, 85, 20.0)
                + _scale(np.mean(drops) if drops else None, -30.0, -2.0, 10.0), 1)
            vals = ret120.iloc[idx][members].dropna()
            if len(vals):
                board_ret120[name] = float(vals.mean())
            line150 = sma150.iloc[idx][members]
            flags150 = [(p > l) for p, l in zip(price, line150)
                        if np.isfinite(p) and np.isfinite(l)]
            if flags150:
                board_a150[name] = float(np.mean(flags150))

        order = pd.Series(board_rank_score).sort_values(ascending=False)
        rank_top3 = set(order.head(3).index)
        rank_top5 = set(order.head(5).index)
        top_ret120 = set(pd.Series(board_ret120).sort_values(ascending=False).head(3).index)
        top_a150 = set(pd.Series(board_a150).sort_values(ascending=False).head(3).index)

        for s in caught:
            buy = base._f(entry.get(s))
            if np.isnan(buy) or buy <= 0:
                continue
            mine = belongs.get(s) or []
            row = {"day": day, "ticker": s,
                   "has_theme": 1.0 if mine else 0.0,
                   "vol_rank": base._f(vol_rank.get(s)),
                   "deep_rank": base._f(deep_rank.get(s)),
                   "above20": base._above(close.iloc[idx].get(s), sma20.iloc[idx].get(s)),
                   "together": max((theme_hits.get(n, 0) for n in mine), default=0),
                   "rank_top3": 1.0 if any(n in rank_top3 for n in mine) else 0.0,
                   "rank_top5": 1.0 if any(n in rank_top5 for n in mine) else 0.0,
                   "t_ret120_top": 1.0 if any(n in top_ret120 for n in mine) else 0.0,
                   "t_a150_top": 1.0 if any(n in top_a150 for n in mine) else 0.0}
            for hold, _l in base.HOLDS:
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / buy - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s])
                    else np.nan)
            picks.append(row)

    frame = pd.DataFrame(picks)
    holds = base.HOLDS

    say("=" * 104)
    say("급락 후 반등장 배점 — 200종목 전부 + 화면 테마 순위로 다시 잰 결과 (2026-08-19)")
    say("=" * 104)
    say(f"명단: {len(names)}종목 (화면이 실제로 뒤지는 명단 그대로)")
    say(f"그 가운데 테마에 속한 종목 {sum(1 for s in names if belongs.get(s))}개 · "
        f"어느 테마에도 없는 종목 {sum(1 for s in names if not belongs.get(s))}개")
    say(f"재는 자리: 나스닥 바닥 다음 거래일 {frame['day'].nunique()}번 · "
        f"조건에 걸린 종목 모두 {len(frame)}개")
    say(f"  그 가운데 테마 있는 종목 {int(frame['has_theme'].sum())}개 · "
        f"테마 없는 종목 {int((1 - frame['has_theme']).sum())}개")
    say()

    say("=" * 104)
    say("1. 테마가 없는 종목은 성적이 어떤가 (테마 항목이 0점이 되는 종목들)")
    say("=" * 104)
    head = (f"  {'무리':<28}{'개수':>6}"
            + "".join(f"{label + ' 가운데':>14}{'오름':>7}" for _d, label in holds))
    say(head)
    say("  " + "-" * (len(head) - 2))
    for label, mask in (("테마에 속한 종목", frame["has_theme"] == 1),
                        ("어느 테마에도 없는 종목", frame["has_theme"] == 0)):
        sub = frame[mask]
        if sub.empty:
            continue
        cells = []
        for hold, _l in holds:
            v = sub[f"r{hold}"].dropna().to_numpy(float)
            cells.append(f"{np.median(v):>+13.1f}%{(v > 0).mean() * 100:>6.0f}번"
                         if v.size else f"{'-':>14}{'-':>7}")
        say(f"  {label:<28}{len(sub):>6}" + "".join(cells))
    say()

    say("=" * 104)
    say("2. 잣대별 성적 — 화면 테마 순위를 넣어 다시 잰다")
    say("=" * 104)
    say("  '이긴바닥'은 그 잣대로 고른 종목의 가운데 수익이 나머지보다 높았던 바닥 수입니다.")
    say()
    rules = [
        ("주가 변동성 큰 쪽 절반", frame["vol_rank"] > 0.50),
        ("주가 변동성 큰 쪽 1/3", frame["vol_rank"] > 2 / 3),
        ("고점 대비 낙폭 큰 쪽 1/3", frame["deep_rank"] > 2 / 3),
        ("20일선 위", frame["above20"] == 1),
        ("같은 테마 4개 이상 동시 하락", frame["together"] >= 4),
        ("화면 테마 순위 상위 3등", frame["rank_top3"] == 1),
        ("화면 테마 순위 상위 5등", frame["rank_top5"] == 1),
        ("테마 6개월 수익률 상위 3등", frame["t_ret120_top"] == 1),
        ("테마 30주선 위 상위 3등", frame["t_a150_top"] == 1),
    ]
    head = (f"  {'잣대':<30}{'걸림':>7}"
            + "".join(f"{label + ' 이긴바닥':>16}{'수익차':>9}" for _d, label in holds))
    say(head)
    say("  " + "-" * (len(head) - 2))
    for label, mask in rules:
        share = mask.sum() / len(frame) * 100 if len(frame) else 0
        cells = []
        for hold, _l in holds:
            wins = total = 0
            for _day, chunk in frame.groupby("day"):
                sel = mask.loc[chunk.index]
                a = chunk[sel][f"r{hold}"].dropna()
                b = chunk[~sel][f"r{hold}"].dropna()
                if len(a) < 3 or len(b) < 3:
                    continue
                total += 1
                if np.median(a) > np.median(b):
                    wins += 1
            a_all = frame[mask][f"r{hold}"].dropna()
            b_all = frame[~mask][f"r{hold}"].dropna()
            gap = (np.median(a_all) - np.median(b_all)
                   if len(a_all) and len(b_all) else np.nan)
            cells.append(f"{wins:>13}/{total:<2}"
                         + (f"{gap:>+8.1f}%" if np.isfinite(gap) else f"{'-':>9}"))
        say(f"  {label:<30}{share:>6.0f}%" + "".join(cells))
    say()

    say("=" * 104)
    say("3. 화면 테마 순위와 지금 쓰는 테마 항목이 겹치나")
    say("=" * 104)
    tests = {
        "화면 테마 순위 상위 5": frame["rank_top5"] == 1,
        "테마 6개월 수익 상위 3": frame["t_ret120_top"] == 1,
        "테마 30주선 상위 3": frame["t_a150_top"] == 1,
        "테마 4개 동시하락": frame["together"] >= 4,
        "변동성 큰 절반": frame["vol_rank"] > 0.5,
    }
    keys = list(tests)
    say(f"  {'':<24}" + "".join(f"{k:>22}" for k in keys))
    for a in keys:
        cells = [f"{(tests[a] & tests[b]).sum() / max(tests[a].sum(), 1) * 100:>21.0f}%"
                 for b in keys]
        say(f"  {a:<24}" + "".join(cells))
    say()
    say("  가로줄 항목에 걸린 종목 가운데 세로줄 항목에도 걸린 비율입니다.")
    say()

    out = ROOT / "research" / "_out" / "us_crash_newscore3.txt"
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
