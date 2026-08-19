"""급락 배점 — **바닥 하나를 빼도 버티나** (2026-08-19 상하님 지시).

상하님 — "남은 한계 두 가지도 지금 해라."

한계 하나는 **바닥이 아홉 번뿐**이라는 것이다. 아홉 번은 적다. 그중 한 번이
유난히 좋아서 배점이 통과한 것이라면, 그 한 번을 빼면 무너져야 한다.
**하나씩 빼 보면 그게 드러난다**(CLAUDE.md 0-1 마의 leave-one-out).

또 하나는 **명부가 지금 살아남은 종목뿐**이라는 것이다. 상장폐지된 회사가
빠져 있어 과거 성적이 실제보다 좋게 나온다. 상장폐지 자료가 없어 고칠 수는
없지만, **얼마나 치우쳤는지 크기는 잴 수 있다** — 10년 내내 자료가 있는
종목과 나중에 들어온 종목을 갈라 보면 된다.

쓰는 법:  python research/us_crash_leaveout.py
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


def _build():
    """앱 배점 그대로 매긴 표를 만든다. us_crash_holding과 같은 방식이다."""
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
    # 10년 내내 자료가 있는 종목인가 — 생존편향 크기를 재는 데 쓴다
    full_history = {s: bool(close[s].dropna().index[0] <= dates[10]) for s in names}

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

        for s in caught:
            buy = base._f(entry.get(s))
            if np.isnan(buy) or buy <= 0:
                continue
            mine = belongs.get(s) or []
            rank = base._f(vol_rank.get(s))
            row = {
                "day": day, "ticker": s,
                "vol_top": bool(rank is not None and rank > 0.50),
                "a150_top": bool(any(n in top_a150 for n in mine)),
                "together4": max((theme_hits.get(n, 0) for n in mine), default=0) >= 4,
                "ret120_top": bool(any(n in top_ret120 for n in mine)),
                "full_history": full_history.get(s, False),
            }
            for hold in (60, 120, 250):
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / buy - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s])
                    else np.nan)
            picks.append(row)
    return pd.DataFrame(picks)


def _wins(frame, mask, hold: int, drop_day=None):
    """그 잣대가 이긴 바닥 수 / 잴 수 있었던 바닥 수."""
    wins = total = 0
    for day, chunk in frame.groupby("day"):
        if drop_day is not None and day == drop_day:
            continue
        sel = mask.loc[chunk.index]
        a = chunk[sel][f"r{hold}"].dropna()
        b = chunk[~sel][f"r{hold}"].dropna()
        if len(a) < 3 or len(b) < 3:
            continue
        total += 1
        if np.median(a) > np.median(b):
            wins += 1
    return wins, total


def main() -> None:
    frame = _build()
    holds = ((60, "3개월"), (120, "6개월"), (250, "1년"))
    rules = [
        ("주가 변동성 큰 쪽 절반 (40점)", frame["vol_top"]),
        ("테마 30주선 위 상위 3등 (30점)", frame["a150_top"]),
        ("같은 테마 4개 이상 하락 (20점)", frame["together4"]),
        ("테마 6개월 수익 상위 3등 (10점)", frame["ret120_top"]),
    ]
    bottoms = sorted(frame["day"].unique())

    say("=" * 108)
    say("급락 배점 — 바닥 하나를 빼도 버티나 (2026-08-19)")
    say("=" * 108)
    say(f"바닥 {len(bottoms)}번 · 걸린 종목 {len(frame)}개")
    say()
    say("읽는 법 — '전부'는 아홉 번 다 넣고 잰 값이고, 그 옆 숫자들은")
    say("           그 바닥 **하나를 빼고** 다시 잰 값입니다.")
    say("           빼도 비슷하면 한 번에 매달린 결론이 아닙니다.")
    say()

    for hold, label in holds:
        say(f"■ {label} 보유")
        head = f"    {'잣대':<28}{'전부':>8}" + "".join(
            f"{str(pd.Timestamp(d).date())[2:]:>10}" for d in bottoms)
        say(head)
        say("    " + "-" * (len(head) - 4))
        for name, mask in rules:
            base_w, base_t = _wins(frame, mask, hold)
            cells = []
            for day in bottoms:
                w, t = _wins(frame, mask, hold, drop_day=day)
                cells.append(f"{w}/{t}".rjust(10) if t else f"{'—':>10}")
            say(f"    {name:<28}{f'{base_w}/{base_t}':>8}" + "".join(cells))
        say()

    say("=" * 108)
    say("한 번을 빼서 **절반 밑으로 무너지는** 자리가 있나")
    say("=" * 108)
    broken = []
    for name, mask in rules:
        for hold, label in holds:
            for day in bottoms:
                w, t = _wins(frame, mask, hold, drop_day=day)
                if t >= 4 and w / t < 0.5:
                    broken.append((name, label, str(pd.Timestamp(day).date()), w, t))
    if broken:
        for name, label, day, w, t in broken:
            say(f"  {name} · {label} — {day}을 빼면 {w}/{t}로 무너진다")
    else:
        say("  없다. **어느 바닥 하나를 빼도 네 항목이 다 절반을 넘긴다.**")
    say()

    say("=" * 108)
    say("생존편향 크기 — 10년 내내 있던 종목과 나중에 들어온 종목")
    say("=" * 108)
    say("  명부에 있는 종목만 재는 한 상장폐지된 회사는 빠져 있다. 그 크기를")
    say("  가늠하려고, **10년 내내 자료가 있던 종목**과 그 사이에 새로 들어온")
    say("  종목(상장·상장이전)을 갈라 본다. 새로 들어온 쪽이 훨씬 좋다면")
    say("  '살아남아 명부에 든 종목'이라는 치우침이 그만큼 크다는 뜻이다.")
    say()
    head = (f"    {'무리':<24}{'개수':>7}"
            + "".join(f"{label + ' 가운데':>14}{'오름':>7}" for _d, label in holds))
    say(head)
    say("    " + "-" * (len(head) - 4))
    for label, mask in (("10년 내내 있던 종목", frame["full_history"]),
                        ("그 사이 새로 들어온 종목", ~frame["full_history"])):
        sub = frame[mask]
        if sub.empty:
            continue
        cells = []
        for hold, _l in holds:
            v = sub[f"r{hold}"].dropna().to_numpy(float)
            cells.append(f"{np.median(v):>+13.1f}%{(v > 0).mean() * 100:>6.0f}번"
                         if v.size else f"{'—':>14}{'—':>7}")
        say(f"    {label:<24}{len(sub):>7}" + "".join(cells))
    say()
    share = frame["full_history"].mean() * 100
    say(f"  걸린 종목 가운데 10년 내내 있던 것이 {share:.0f}%다.")
    say()

    out = ROOT / "research" / "_out" / "us_crash_leaveout.txt"
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
