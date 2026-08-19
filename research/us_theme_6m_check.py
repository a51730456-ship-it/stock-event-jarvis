"""테마 **6개월 수익률**이 급락 후 반등 자리에서 값을 하나 (2026-08-16).

왜 재나 — GPT 월간 순환 엑셀을 이 집 잣대로 다시 재니(`us_theme_rotation_audit.py`)
ETF 기준 '6개월 강도 상위 5테마'가 수익 쪽 63.2%로 합격선(65%)에 가장 가까웠다.
앱은 예전에 **테마 60일(3개월)** 수익률을 재고 떨어뜨렸지만 **120일(6개월)은 이
그물에서 한 번도 안 쟀다**. ETF가 아니라 **앱 명부 200종목·앱 그물**로 잰다.

방법은 2026-08-14 확정 때(`us_crash_final.py`)와 **같은 자리·같은 잣대**다.
  · 사는 날 — 나스닥(IXIC·QQQ)이 −12·−18·−24%에 닿은 날 / 그 하락의 저점 다음 날
  · 그물   — 종목 고점 대비 −20~−50%
  · 보유   — 60·120·250일 셋 다 (앱이 파는 날을 안 정하므로)
  · 판정   — ① 등수 상관 ② **상위 N등 vs 나머지**의 오른 비율·중앙값 차이

지금 40점을 지고 있는 '테마 30주선 위 비율'을 같이 놓아 견준다.

쓰는 법:  python research/us_theme_6m_check.py
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
STOCK_BAND = (-50.0, -20.0)
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3
TOP_NS = (3, 5)

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def touch_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """고점 대비 `step`%에 **처음 닿은 날**. 한 하락 사건에 한 번만."""
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    days, armed = [], True
    for day, value in drop.items():
        if value <= step and armed:
            days.append(day)
            armed = False
        elif value > -1.0:
            armed = True
    return days


def turn_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """그 하락 사건의 **최저일 다음 거래일** — '급락 후 반등' 자리."""
    drop = (index_close / index_close.cummax() - 1.0) * 100.0
    index = list(drop.index)
    out, start = [], None
    for i, value in enumerate(drop.to_numpy()):
        if value <= step and start is None:
            start = i
        elif start is not None and value > -1.0:
            seg = drop.iloc[start:i]
            pos = index.index(seg.idxmin())
            if pos + 1 < len(index):
                out.append(index[pos + 1])
            start = None
    if start is not None:
        seg = drop.iloc[start:]
        pos = index.index(seg.idxmin())
        if pos + 1 < len(index):
            out.append(index[pos + 1])
    return out


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][names], wide["high"][names]
    opens, qqq = wide["open"][names], wide["close"]["QQQ"].dropna()
    dates = close.index
    ixic = pd.read_parquet(ROOT / "research" / "_data" / "ixic.parquet")["close"]
    ixic = ixic.reindex(dates).ffill().dropna()

    themes = {t["name"]: [s for s in t["stocks"] if s in close.columns]
              for t in j3.US_THEMES}
    themes = {n: m for n, m in themes.items() if len(m) >= MIN_MEMBERS}
    belongs = {s: [n for n, m in themes.items() if s in m] for s in close.columns}

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma150 = close.rolling(150, min_periods=150).mean()
    above150 = (close > sma150).astype(float)
    ret60 = (close / close.shift(60) - 1.0) * 100.0
    ret120 = (close / close.shift(120) - 1.0) * 100.0
    ret250 = (close / close.shift(250) - 1.0) * 100.0

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _l in HOLDS}
    at = {d: i for i, d in enumerate(dates)}

    def board_at(idx: int, hold: int):
        fh = from_high.iloc[idx]
        a150, r60, r120, r250 = (above150.iloc[idx], ret60.iloc[idx],
                                 ret120.iloc[idx], ret250.iloc[idx])
        forward = rets[hold].iloc[idx]
        rows = []
        for stock in names:
            v = fh.get(stock)
            if pd.isna(v) or not (STOCK_BAND[0] < v < STOCK_BAND[1]):
                continue
            if pd.isna(forward.get(stock)) or not belongs.get(stock):
                continue
            rows.append((belongs[stock][0], v, a150.get(stock), r60.get(stock),
                         r120.get(stock), r250.get(stock), forward.get(stock)))
        if len(rows) < 20:
            return None
        frame = pd.DataFrame(rows, columns=[
            "theme", "drop", "above150", "r60", "r120", "r250", "ret"]).dropna()
        board = frame.groupby("theme").agg(
            drop=("drop", "mean"), above150=("above150", "mean"),
            r60=("r60", "mean"), r120=("r120", "mean"), r250=("r250", "mean"),
            ret=("ret", "mean"), n=("ret", "size"))
        board = board[board["n"] >= MIN_MEMBERS]
        return board if len(board) >= 8 else None

    GAUGES = (
        ("테마 30주선 위 비율 (지금 40점)", "above150"),
        ("테마가 덜 빠졌나 (2026-08-14 뺌)", "drop"),
        ("테마 3개월 수익률 (예전 미달)", "r60"),
        ("**테마 6개월 수익률** (이번 후보)", "r120"),
        ("테마 1년 수익률 (같이 봄)", "r250"),
    )

    anchors = (("① 문턱에 닿은 날 — 아직 떨어지는 중", touch_days),
               ("② 저점 다음 날 — 급락 후 반등 자리", turn_days))

    say("앱 명부 200종목 · 앱 그물(종목 -20~-50%) · 나스닥 IXIC와 QQQ 둘 다")
    say(f"보유 {' · '.join(l for _h, l in HOLDS)} · 테마는 구성종목 {MIN_MEMBERS}개 이상만")

    for anchor_name, finder in anchors:
        days = []
        for series in (ixic, qqq):
            for step in STEPS:
                days += [d for d in finder(series, step) if d in at]
        days = sorted(set(days))
        say()
        say("=" * 92)
        say(f"{anchor_name}  —  자리 {len(days)}번")
        say("=" * 92)
        say(f"  {', '.join(str(d.date()) for d in days)}")
        say()

        for top_n in TOP_NS:
            say(f"  ── 상위 {top_n}등 vs 나머지 ──"
                "  (이긴 자리 = 상위가 나머지보다 중앙값이 높은 자리)")
            head = ("  " + "잣대".ljust(34)
                    + "  ".join(f"{label:>22}" for _h, label in HOLDS))
            say(head)
            say("  " + "─" * (len(head) - 2))
            for title, key in GAUGES:
                cells = []
                for hold, _label in HOLDS:
                    wins, gaps, plus_gap = 0, [], 0
                    tried = 0
                    for day in days:
                        board = board_at(at[day], hold)
                        if board is None:
                            continue
                        order = board[key].rank(ascending=False)
                        top = order[order <= top_n].index
                        rest = order[order > top_n].index
                        if len(top) < 2 or len(rest) < 3:
                            continue
                        a = board.loc[top, "ret"].to_numpy(float)
                        b = board.loc[rest, "ret"].to_numpy(float)
                        tried += 1
                        gap = float(np.median(a) - np.median(b))
                        gaps.append(gap)
                        wins += 1 if gap > 0 else 0
                        plus_gap += 1 if (a > 0).mean() > (b > 0).mean() else 0
                    if tried:
                        cells.append(f"{wins}/{tried}({wins / tried * 100:3.0f}%)"
                                     f"{np.median(gaps):+6.1f}%p".rjust(22))
                    else:
                        cells.append("—".rjust(22))
                say("  " + title.ljust(34) + "  ".join(cells))
            say()

        say("  ── 등수 상관 (잣대 등수와 실제 수익 등수가 맞나) ──")
        head = ("  " + "잣대".ljust(34)
                + "  ".join(f"{label:>22}" for _h, label in HOLDS))
        say(head)
        say("  " + "─" * (len(head) - 2))
        for title, key in GAUGES:
            cells = []
            for hold, _label in HOLDS:
                plus, tried, corrs = 0, 0, []
                for day in days:
                    board = board_at(at[day], hold)
                    if board is None:
                        continue
                    corr = board[key].rank().corr(board["ret"].rank())
                    if pd.isna(corr):
                        continue
                    tried += 1
                    plus += 1 if corr > 0 else 0
                    corrs.append(corr)
                cells.append((f"{plus}/{tried}({plus / tried * 100:3.0f}%)"
                              f"{np.mean(corrs):+6.2f}".rjust(22))
                             if tried else "—".rjust(22))
            say("  " + title.ljust(34) + "  ".join(cells))

    # ── 겹침 — 두 잣대가 같은 테마를 고르면 점수를 두 번 주는 셈이다 ──────────
    say()
    say("=" * 92)
    say("겹침 — 상위 3등이 얼마나 같은 테마인가 (두 자리 전부·보유 6개월 기준)")
    say("=" * 92)
    all_days = []
    for _n, finder in anchors:
        for series in (ixic, qqq):
            for step in STEPS:
                all_days += [d for d in finder(series, step) if d in at]
    all_days = sorted(set(all_days))
    pairs = (("above150", "r120"), ("drop", "r120"), ("r60", "r120"),
             ("above150", "drop"))
    for left, right in pairs:
        shares, both_empty = [], 0
        for day in all_days:
            board = board_at(at[day], 120)
            if board is None:
                continue
            a = set(board[left].rank(ascending=False).nsmallest(3).index)
            b = set(board[right].rank(ascending=False).nsmallest(3).index)
            if not a or not b:
                both_empty += 1
                continue
            shares.append(len(a & b) / 3 * 100)
        if shares:
            say(f"  {left:>9} vs {right:<9} 자리 {len(shares):>3} · "
                f"3개 중 평균 {np.mean(shares) / 100 * 3:.2f}개가 같다 "
                f"({np.mean(shares):.0f}%)")

    say()
    say("**자리가 몇 번뿐이다. 이 숫자 하나로 배점을 정하지 않는다.**")
    say("합격 조건 — 여섯 자리(문턱·반등 × 3개월·6개월·1년) 모두에서 앞서야 한다")
    say("(2026-08-14에 30주선 40점을 정한 것과 같은 조건).")

    out = ROOT / "research" / "_out" / "us_theme_6m_check.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(BUF.getvalue())
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
