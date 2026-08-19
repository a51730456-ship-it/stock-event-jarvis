"""급락 후 반등장 — **배점을 새로 짜기 위한 실측** (2026-08-19 상하님 지시).

상하님이 새 지시문을 주셨다. 그 지시문은 "흔들림이 큰 종목 50점 · 많이 빠진
종목 30점 · 20일선 위 20점"이라고 정해 두었는데, 그 숫자는 **다른 명단
(20테마 96종목)**에서 나온 값이다. 우리 앱은 200종목을 본다. 명단이 다르면
같은 잣대라도 결과가 뒤집힌다(2026-08-09에 종목 하나를 바꿨더니 실제로 뒤집혔다).

그래서 지시문이 말한 항목들을 **우리 앱 명단·우리 앱 조건**에서 다시 잰다.
재는 자리는 2026-08-16과 똑같이 **나스닥이 바닥을 찍은 바로 다음 거래일**이다.
비교 대상도 그대로다 — 지금 화면이 쓰고 있는 세 항목을 나란히 놓는다.

쓰는 법:  python research/us_crash_newscore.py
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

STEPS = (-12.0, -18.0, -24.0)
STOCK_BAND = (-50.0, -20.0)          # 지금 앱이 쓰는 조건 그대로
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3
BIGTECH = {"MSFT", "GOOGL", "AMZN", "META", "AAPL", "ORCL"}

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def _f(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return np.nan
    return out if np.isfinite(out) else np.nan


def _above(price, line):
    price, line = _f(price), _f(line)
    if np.isnan(price) or np.isnan(line):
        return np.nan
    return 1.0 if price > line else 0.0


def main() -> None:
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
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    ret120 = (close / close.shift(120) - 1.0) * 100.0
    vol60 = close.pct_change().rolling(60, min_periods=60).std() * 100.0

    at = {d: i for i, d in enumerate(dates)}
    days = sorted({d for series in (ixic, qqq) for step in STEPS
                   for d in bottom_days(series, step) if d in at})

    picks = []
    for day in days:
        idx = at[day]
        fh = from_high.iloc[idx]
        caught = [s for s in names
                  if not pd.isna(fh.get(s)) and STOCK_BAND[0] < fh[s] < STOCK_BAND[1]]
        if len(caught) < 20 or idx + 1 >= len(dates):
            continue
        entry = opens.iloc[idx + 1]

        vol_rank = vol60.iloc[idx][caught].rank(pct=True)
        deep_rank = (-fh[caught]).rank(pct=True)      # 많이 빠질수록 1에 가깝다

        theme_hits: dict[str, int] = {}
        for s in caught:
            for name in belongs.get(s) or []:
                theme_hits[name] = theme_hits.get(name, 0) + 1

        # 지금 화면이 쓰는 테마 등수 두 개 — 명단 전체로 매긴다(화면과 같은 방식)
        board_ret120, board_above150 = {}, {}
        for name, members in themes.items():
            vals = ret120.iloc[idx][members].dropna()
            if len(vals):
                board_ret120[name] = float(vals.mean())
            flags = [_above(close.iloc[idx].get(s), sma150.iloc[idx].get(s))
                     for s in members]
            flags = [v for v in flags if not np.isnan(v)]
            if flags:
                board_above150[name] = float(np.mean(flags))
        top_ret120 = set(pd.Series(board_ret120).sort_values(ascending=False).head(3).index)
        top_above150 = set(pd.Series(board_above150).sort_values(ascending=False).head(3).index)

        for s in caught:
            buy = _f(entry.get(s))
            if np.isnan(buy) or buy <= 0:
                continue
            mine = belongs.get(s) or []
            row = {
                "day": day, "ticker": s, "buy": buy,
                "drop": float(fh[s]),
                "vol_rank": _f(vol_rank.get(s)),
                "deep_rank": _f(deep_rank.get(s)),
                "above20": _above(close.iloc[idx].get(s), sma20.iloc[idx].get(s)),
                "above150": _above(close.iloc[idx].get(s), sma150.iloc[idx].get(s)),
                "bigtech": 1.0 if s in BIGTECH else 0.0,
                "theme": (mine or [""])[0],
                "together": max((theme_hits.get(n, 0) for n in mine), default=0),
                "t_ret120_top": 1.0 if any(n in top_ret120 for n in mine) else 0.0,
                "t_a150_top": 1.0 if any(n in top_above150 for n in mine) else 0.0,
            }
            for hold, _label in HOLDS:
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / buy - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s])
                    else np.nan)
            picks.append(row)

    frame = pd.DataFrame(picks)

    say("=" * 100)
    say("급락 후 반등장 — 새 배점을 짜기 위한 실측 (2026-08-19)")
    say("=" * 100)
    say(f"재는 자리: 나스닥이 바닥을 찍은 다음 거래일 {frame['day'].nunique()}번")
    say("  " + ", ".join(str(pd.Timestamp(d).date()) for d in sorted(frame["day"].unique())))
    say(f"보는 종목: 그날 1년 최고가보다 {abs(STOCK_BAND[1]):.0f}~{abs(STOCK_BAND[0]):.0f}% "
        f"낮게 내려온 종목 (지금 앱 조건 그대로)")
    say(f"모두 합쳐 {len(frame)}개 · 바닥 한 번당 평균 "
        f"{len(frame) / max(frame['day'].nunique(), 1):.0f}개")
    say()
    say("읽는 법 — '이긴바닥'은 그 잣대로 고른 종목들의 가운데 수익이")
    say("           나머지 종목들보다 높았던 바닥이 몇 번이었나입니다.")
    say("           '수익차'는 고른 쪽 가운데 수익에서 나머지 쪽을 뺀 값입니다.")
    say()

    rules = [
        ("[새] 흔들림 큰 쪽 1/4", frame["vol_rank"] > 0.75),
        ("[새] 흔들림 큰 쪽 1/3", frame["vol_rank"] > 2 / 3),
        ("[새] 흔들림 큰 쪽 절반", frame["vol_rank"] > 0.50),
        ("[새] 흔들림 작은 1/4 뺀 나머지", frame["vol_rank"] > 0.25),
        ("[새] 많이 빠진 쪽 1/4", frame["deep_rank"] > 0.75),
        ("[새] 많이 빠진 쪽 1/3", frame["deep_rank"] > 2 / 3),
        ("[새] 많이 빠진 쪽 절반", frame["deep_rank"] > 0.50),
        ("[새] 20일선 위", frame["above20"] == 1),
        ("[새] 대형기술주 6개", frame["bigtech"] == 1),
        ("[지금] 같은 테마 4개 이상 하락", frame["together"] >= 4),
        ("[지금] 테마 6개월 수익 상위 3", frame["t_ret120_top"] == 1),
        ("[지금] 테마 30주선 상위 3", frame["t_a150_top"] == 1),
    ]

    head = (f"  {'잣대':<30}{'걸림':>7}"
            + "".join(f"{label + ' 이긴바닥':>16}{'수익차':>9}" for _d, label in HOLDS))
    say(head)
    say("  " + "-" * (len(head) - 2))
    for label, mask in rules:
        sub = frame[mask]
        share = len(sub) / len(frame) * 100 if len(frame) else 0
        cells = []
        for hold, _lab in HOLDS:
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

    # 지시문은 '여행/모빌리티 테마는 감점'이라 했는데 우리 명단에는 그 테마가 없다.
    say("=" * 100)
    say("테마별 성적 (지시문의 '테마 감점'을 우리 명단에서 확인)")
    say("=" * 100)
    say(f"  {'테마':<22}{'걸림':>7}" + "".join(f"{label + ' 가운데':>14}" for _d, label in HOLDS))
    say("  " + "-" * 70)
    board = []
    for name, sub in frame.groupby("theme"):
        if not name or len(sub) < 20:
            continue
        row = {"name": name, "n": len(sub)}
        for hold, _lab in HOLDS:
            v = sub[f"r{hold}"].dropna().to_numpy(float)
            row[f"m{hold}"] = float(np.median(v)) if v.size else np.nan
        board.append(row)
    for row in sorted(board, key=lambda r: (r.get("m250") if np.isfinite(r.get("m250", np.nan))
                                            else -999), reverse=True):
        say(f"  {row['name']:<22}{row['n']:>7}"
            + "".join(f"{row[f'm{h}']:>+13.1f}%" for h, _l in HOLDS))
    say()

    out = ROOT / "research" / "_out" / "us_crash_newscore.txt"
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
