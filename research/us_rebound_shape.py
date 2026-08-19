"""바닥을 찍었다 치고 — 무엇이 빨리·많이 오르나 (2026-08-16 상하님 지시).

상하님 지적 — "칼이 떨어진다고 기준을 잡으면 이 테마를 쓸 수가 없지.
넌 그저 최저점을 찍었다 치고 몇 개월 뒤 뒤처진 종목들이 반등하더라
뭐 이런 기준을 찾아서 확률을 계산하는 거야."

**그래서 자리를 하나로 줄인다.** 지금까지는 '문턱에 닿은 날(아직 떨어지는 중)'과
'바닥 다음 날'을 둘 다 이겨야 합격이었다. 이 파트 이름이 「급락 **후 반등**장」이므로
**바닥 다음 날 하나만** 본다. 떨어지는 중인 날은 이 파트의 자리가 아니다.

재는 것 — 전부 **확률(100번 중 몇 번)**로 낸다.
  A. 어떤 형태의 종목이 빨리·많이 오르나
  B. 처음에 뒤처진 종목이 나중에 오나 (상하님이 말씀하신 그 기준)
  C. 몇 개 테마가 같이 움직이나 · 같이 움직일 때가 더 좋은가
  D. 테마 순환 순서 — 이 테마 다음에 무엇이 왔나 (배점 아님 · 참고용)

쓰는 법:  python research/us_rebound_shape.py
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
STOCK_BAND = (-60.0, -20.0)          # 그물 — 고점 대비 이만큼 빠진 종목
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MIN_MEMBERS = 3

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def bottom_days(index_close: pd.Series, step: float) -> list[pd.Timestamp]:
    """그 하락 사건의 **최저일 다음 거래일**. 여기가 이 파트의 유일한 자리다."""
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


def show_groups(title: str, groups: dict, note: str = "") -> None:
    """무리별 확률표 — 100번 중 몇 번 올랐나 · 얼마나 벌었나 · 며칠 만에 +20%."""
    say(f"  {title}")
    if note:
        say(f"    {note}")
    head = (f"    {'무리':<22}{'자리수':>7}"
            + "".join(f"{label + ' 오름':>12}{label + ' 가운데':>13}" for _d, label in HOLDS)
            + f"{'+20%까지':>10}")
    say(head)
    say("    " + "─" * (len(head) - 4))
    for name, rows in groups.items():
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        cells = []
        for days, _label in HOLDS:
            values = frame[f"r{days}"].dropna().to_numpy(float)
            if values.size == 0:
                cells.append(f"{'—':>12}{'—':>13}")
                continue
            cells.append(f"{(values > 0).mean() * 100:>10.0f}번"
                         f"{np.median(values):>+12.1f}%")
        speed = frame["days20"].dropna().to_numpy(float)
        speed_text = f"{np.median(speed):>8.0f}일" if speed.size else "       —"
        say(f"    {name:<22}{len(frame):>7}" + "".join(cells) + speed_text)
    say()


def main() -> None:
    import jarvis3_data as j3
    from us_yearly import fetch

    wide = fetch()
    names = [c for c in wide["close"].columns if c != "QQQ"]
    close, high, low = wide["close"][names], wide["high"][names], wide["low"][names]
    opens = wide["open"][names]
    volume = wide["volume"][names]
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
    sma150 = close.rolling(150, min_periods=150).mean()
    sma20 = close.rolling(20, min_periods=20).mean()
    ret20 = (close / close.shift(20) - 1.0) * 100.0
    ret120 = (close / close.shift(120) - 1.0) * 100.0
    turnover = (close * volume).rolling(50, min_periods=20).mean()
    span = (high - low) / close * 100.0
    atr_pct = span.rolling(14, min_periods=14).mean()

    at = {d: i for i, d in enumerate(dates)}
    days = sorted({d for series in (ixic, qqq) for step in STEPS
                   for d in bottom_days(series, step) if d in at})

    say("=" * 104)
    say("바닥을 찍었다 치고 — 무엇이 빨리·많이 오르나")
    say("=" * 104)
    say(f"자리(바닥 다음 거래일) {len(days)}번 — "
        + ", ".join(str(d.date()) for d in days))
    say(f"그물 — 그날 고점 대비 {abs(STOCK_BAND[1]):.0f}~{abs(STOCK_BAND[0]):.0f}% 빠진 종목")
    say("'오름'은 100번 중 몇 번 올랐나 · '가운데'는 가운데 수익 · '+20%까지'는 며칠 걸렸나")
    say()

    # ── 자리마다 그물에 걸린 종목을 모은다 ────────────────────────────────
    picks = []
    for day in days:
        idx = at[day]
        fh = from_high.iloc[idx]
        caught = [s for s in names
                  if not pd.isna(fh.get(s)) and STOCK_BAND[0] < fh[s] < STOCK_BAND[1]]
        if len(caught) < 20:
            continue
        # 그날 걸린 것들 안에서의 등수(그물 안 비교 — CLAUDE.md 0-1 마)
        turn_rank = turnover.iloc[idx][caught].rank(pct=True)
        atr_rank = atr_pct.iloc[idx][caught].rank(pct=True)
        theme_hits: dict[str, int] = {}
        for s in caught:
            for name in belongs.get(s) or []:
                theme_hits[name] = theme_hits.get(name, 0) + 1
        entry = opens.iloc[idx + 1] if idx + 1 < len(dates) else None
        if entry is None:
            continue
        for s in caught:
            buy = entry.get(s)
            if not buy or pd.isna(buy):
                continue
            row = {"day": day, "ticker": s, "buy": float(buy),
                   "drop": float(fh[s]),
                   "turn": float(turn_rank.get(s, np.nan)),
                   "atr": float(atr_rank.get(s, np.nan)),
                   "ret20": _f(ret20.iloc[idx].get(s)),
                   "ret120": _f(ret120.iloc[idx].get(s)),
                   "above150": _above(close.iloc[idx].get(s), sma150.iloc[idx].get(s)),
                   "above20": _above(close.iloc[idx].get(s), sma20.iloc[idx].get(s)),
                   "theme": (belongs.get(s) or [""])[0],
                   "together": max((theme_hits.get(n, 0) for n in belongs.get(s) or []),
                                   default=0)}
            for hold, _label in HOLDS:
                target = idx + hold
                row[f"r{hold}"] = (
                    (float(close.iloc[target][s]) / row["buy"] - 1.0) * 100.0
                    if target < len(dates) and not pd.isna(close.iloc[target][s]) else np.nan)
            # +20%까지 며칠 — 250일 안에 못 닿으면 비운다(0으로 채우지 않는다)
            window = close.iloc[idx + 1: idx + 251][s]
            hit = window[window >= row["buy"] * 1.20]
            row["days20"] = float(len(window[:hit.index[0]])) if len(hit) else np.nan
            # 저점 뒤 첫 한 달에 얼마나 올랐나 — B에서 '뒤처짐'을 가르는 값
            after = idx + 21
            row["first_month"] = (
                (float(close.iloc[after][s]) / row["buy"] - 1.0) * 100.0
                if after < len(dates) and not pd.isna(close.iloc[after][s]) else np.nan)
            picks.append(row)

    frame = pd.DataFrame(picks)
    say(f"그물에 걸린 자리 모두 합쳐 {len(frame)}개 · 자리당 평균 "
        f"{len(frame) / max(len(days), 1):.0f}개")
    say()

    # ── A. 어떤 형태가 빨리·많이 오르나 ──────────────────────────────────
    say("=" * 104)
    say("A. 어떤 형태의 종목이 빨리·많이 오르나")
    say("=" * 104)
    base = {"바탕 (걸린 것 전부)": frame.to_dict("records")}
    show_groups("바탕", base)

    show_groups("① 얼마나 빠졌나", {
        "-20~-30% 빠짐": _pick(frame, frame["drop"].between(-30, -20)),
        "-30~-40% 빠짐": _pick(frame, frame["drop"].between(-40, -30)),
        "-40~-60% 빠짐": _pick(frame, frame["drop"].between(-60, -40)),
    })
    show_groups("② 반년 성적 (바닥 전 6개월)", {
        "반년 +20%↑ (안 밀린 것)": _pick(frame, frame["ret120"] > 20),
        "반년 0~+20%": _pick(frame, frame["ret120"].between(0, 20)),
        "반년 -20~0%": _pick(frame, frame["ret120"].between(-20, 0)),
        "반년 -20%↓ (많이 밀린 것)": _pick(frame, frame["ret120"] < -20),
    })
    show_groups("③ 바닥 직전 한 달", {
        "직전 한 달 덜 빠짐(상위 절반)":
            _pick(frame, frame["ret20"] > frame["ret20"].median()),
        "직전 한 달 더 빠짐(하위 절반)":
            _pick(frame, frame["ret20"] <= frame["ret20"].median()),
    })
    show_groups("④ 같은 테마에서 몇 개가 같이 걸렸나", {
        "1~2개": _pick(frame, frame["together"] <= 2),
        "3개": _pick(frame, frame["together"] == 3),
        "4개": _pick(frame, frame["together"] == 4),
        "5개 이상": _pick(frame, frame["together"] >= 5),
    })
    show_groups("⑤ 흔들림(변동성)", {
        "많이 흔들림(상위 1/3)": _pick(frame, frame["atr"] > 2 / 3),
        "가운데": _pick(frame, frame["atr"].between(1 / 3, 2 / 3)),
        "덜 흔들림(하위 1/3)": _pick(frame, frame["atr"] < 1 / 3),
    })
    show_groups("⑥ 거래대금", {
        "큰 쪽(상위 1/3)": _pick(frame, frame["turn"] > 2 / 3),
        "가운데": _pick(frame, frame["turn"].between(1 / 3, 2 / 3)),
        "작은 쪽(하위 1/3)": _pick(frame, frame["turn"] < 1 / 3),
    })
    show_groups("⑦ 30주선 위인가 (지금 30점짜리)", {
        "30주선 위": _pick(frame, frame["above150"] == 1),
        "30주선 아래": _pick(frame, frame["above150"] == 0),
    })

    # ── B. 뒤처진 것이 나중에 오나 ───────────────────────────────────────
    say("=" * 104)
    say("B. 처음에 뒤처진 종목이 나중에 오나 — 상하님이 말씀하신 그 기준")
    say("=" * 104)
    say("  바닥 뒤 **첫 한 달** 성적으로 무리를 가르고, 그 뒤를 본다.")
    say("  (첫 한 달은 이미 지난 일이라 그때 서서 고를 수 있는 값이다)")
    say()
    ok = frame.dropna(subset=["first_month"]).copy()
    ok["group"] = ok.groupby("day")["first_month"].transform(
        lambda s: pd.qcut(s, 4, labels=["뒤처짐(하위 1/4)", "중하", "중상",
                                        "앞섬(상위 1/4)"], duplicates="drop"))
    later = {}
    for label in ("뒤처짐(하위 1/4)", "중하", "중상", "앞섬(상위 1/4)"):
        sub = ok[ok["group"] == label]
        if sub.empty:
            continue
        rows = []
        for _i, r in sub.iterrows():
            rows.append({"r60": r["r60"], "r120": r["r120"], "r250": r["r250"],
                         "days20": r["days20"]})
        later[label] = rows
    show_groups("첫 한 달 성적으로 가른 뒤 — 그 자리에서 산 것과 같은 셈",
                later, "숫자는 **바닥에서 산 것 기준**이라 첫 달 성적이 이미 들어 있다")

    say("  ── 첫 한 달 뒤에 **그때 사면** 어떻게 되나 (뒤처진 것을 그때 사는 셈) ──")
    head = (f"    {'무리':<22}{'자리수':>7}"
            + f"{'그 뒤 2개월 오름':>17}{'가운데':>10}"
            + f"{'그 뒤 5개월 오름':>17}{'가운데':>10}"
            + f"{'그 뒤 11개월 오름':>18}{'가운데':>10}")
    say(head)
    say("    " + "─" * (len(head) - 4))
    for label in ("뒤처짐(하위 1/4)", "중하", "중상", "앞섬(상위 1/4)"):
        sub = ok[ok["group"] == label]
        if sub.empty:
            continue
        cells = []
        for hold in (60, 120, 250):
            # 첫 한 달 뒤에 산 셈 — (1+전체) / (1+첫달) - 1
            after = ((1 + sub[f"r{hold}"] / 100) / (1 + sub["first_month"] / 100) - 1) * 100
            after = after.dropna().to_numpy(float)
            cells.append(f"{(after > 0).mean() * 100:>15.0f}번"
                         f"{np.median(after):>+9.1f}%" if after.size
                         else f"{'—':>15}{'—':>10}")
        say(f"    {label:<22}{len(sub):>7}" + "".join(cells))
    say()

    # ── C. 몇 개 테마가 같이 움직이나 ────────────────────────────────────
    say("=" * 104)
    say("C. 몇 개 테마가 같이 움직이나")
    say("=" * 104)
    per_day = []
    for day, sub in frame.groupby("day"):
        board = sub.groupby("theme")["r120"].mean().dropna()
        if board.empty:
            continue
        per_day.append({"day": day, "themes": len(board),
                        "up": int((board > 0).sum()),
                        "share": (board > 0).mean() * 100,
                        "median": float(board.median())})
    board_frame = pd.DataFrame(per_day)
    say(f"  {'바닥일':<14}{'테마수':>7}{'6개월 뒤 오른 테마':>20}{'비율':>8}{'테마 가운데 수익':>16}")
    say("  " + "─" * 66)
    for _i, r in board_frame.iterrows():
        say(f"  {str(r['day'].date()):<14}{int(r['themes']):>7}{int(r['up']):>20}"
            f"{r['share']:>7.0f}%{r['median']:>+15.1f}%")
    if len(board_frame) > 1:
        say()
        wide_days = board_frame[board_frame["share"] >= 80]["day"]
        narrow_days = board_frame[board_frame["share"] < 80]["day"]
        say(f"  테마 열에 여덟 이상이 오른 바닥 {len(wide_days)}번 · "
            f"그렇지 않은 바닥 {len(narrow_days)}번")
        for label, chosen in (("넓게 오른 바닥", wide_days), ("좁게 오른 바닥", narrow_days)):
            sub = frame[frame["day"].isin(chosen)]
            if sub.empty:
                continue
            v = sub["r250"].dropna().to_numpy(float)
            if v.size:
                say(f"    {label:<14} 1년 뒤 100번 중 {(v > 0).mean() * 100:.0f}번 오름 · "
                    f"가운데 {np.median(v):+.1f}%")
    say()

    # ── D. 순환 순서 (배점 아님 · 참고용) ────────────────────────────────
    say("=" * 104)
    say("D. 테마 순환 순서 — 이 테마 다음에 무엇이 왔나 (**배점 아님 · 참고용**)")
    say("=" * 104)
    say("  바닥에서 1·2·3개월 구간마다 테마 등수를 매기고, 앞 구간 1등이던 테마 다음에")
    say("  어느 테마가 1등이 됐는지 센다. 자리가 적어 **확률이라 부르기 어렵다.**")
    say()
    seq = []
    for day in days:
        idx = at[day]
        legs = []
        for start, stop in ((1, 21), (21, 63), (63, 126), (126, 252)):
            a, b = idx + start, idx + stop
            if b >= len(dates):
                legs.append(None)
                continue
            scores = {}
            for name, members in themes.items():
                vals = []
                for s in members:
                    p0, p1 = close.iloc[a].get(s), close.iloc[b].get(s)
                    if p0 and p1 and not pd.isna(p0) and not pd.isna(p1):
                        vals.append(p1 / p0 - 1.0)
                if len(vals) >= MIN_MEMBERS:
                    scores[name] = float(np.mean(vals))
            legs.append(max(scores, key=scores.get) if scores else None)
        seq.append((day, legs))
    labels = ("1개월", "1~3개월", "3~6개월", "6~12개월")
    say(f"  {'바닥일':<14}" + "".join(f"{l + ' 1등':>22}" for l in labels))
    say("  " + "─" * 102)
    for day, legs in seq:
        say(f"  {str(day.date()):<14}"
            + "".join(f"{(name or '—'):>22}" for name in legs))
    say()
    follow: dict[str, dict[str, int]] = {}
    for _day, legs in seq:
        for i in range(len(legs) - 1):
            if legs[i] and legs[i + 1]:
                follow.setdefault(legs[i], {})
                follow[legs[i]][legs[i + 1]] = follow[legs[i]].get(legs[i + 1], 0) + 1
    say("  앞 구간 1등 → 다음 구간 1등 (몇 번 중 몇 번)")
    for leader, nexts in sorted(follow.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(nexts.values())
        parts = " · ".join(f"{k} {v}/{total}"
                           for k, v in sorted(nexts.items(), key=lambda kv: -kv[1]))
        say(f"    {leader:<20} → {parts}")
    say()
    say("  **읽는 법** — 같은 테마가 두 번 이어 1등인 경우가 아니면 자리가 한 번씩뿐이다.")
    say("  고정된 순서는 이 자료로 못 만든다. 화면에는 참고로만 적는다.")

    out = ROOT / "research" / "_out" / "us_rebound_shape.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(BUF.getvalue())
    print(f"저장: {out}")


def _f(value):
    return np.nan if value is None or pd.isna(value) else float(value)


def _above(price, line):
    if price is None or line is None or pd.isna(price) or pd.isna(line):
        return np.nan
    return 1.0 if float(price) > float(line) else 0.0


def _pick(frame: pd.DataFrame, mask) -> list:
    return frame[mask.fillna(False)].to_dict("records")


if __name__ == "__main__":
    main()
