"""GPT 월간 순환 엑셀(M1~M12)을 이 집 합격선으로 다시 잰다 (2026-08-16).

원본: `GPT-나스닥_테마순환_월간M1-M12_예측신호_완성본_v1.xlsx`
      20개 테마 ETF의 2018-01~2026-07 월말 조정가격 · QQQ 저점 16회.

엑셀은 '다음달 Top5 적중률'로 신호를 줄 세웠다. 이 집 잣대는 다르다 —
**같은 그물(그달 20테마) 안에서 승률과 수익률 둘 다** 이겨야 하고, 여러 자리에서
모두 이겨야 한다(CLAUDE.md 0-1 마). 적중률은 '맞혔나'이지 '벌었나'가 아니다.

재는 것
  A. 고정 단계순서(M1~M12) — 앞을 안 보고 과거 저점의 그 단계 Top5를 고르면 버나
  B. 실시간 3개월 강도       — 매달 3개월 수익 상위 5테마를 고르면 버나
  C. 리더 피로 B            — Top5인데 QQQ 대비 1개월 약세 + 가속 음수
  D. ETF 프록시와 앱 명부    — 이 자료를 앱에 그대로 옮길 수 있나

쓰는 법:  python research/us_theme_rotation_audit.py
"""

from __future__ import annotations

import io
import pathlib
import sys

import numpy as np
import pandas as pd

XLSX = (pathlib.Path.home() / "Downloads"
        / "GPT-나스닥_테마순환_월간M1-M12_예측신호_완성본_v1.xlsx")
PASS_MARK = 65.0
TOP_N = 5

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def load():
    ret = pd.read_excel(XLSX, sheet_name="03_월간수익률", header=2)
    ret = ret.rename(columns={ret.columns[0]: "월"}).dropna(subset=["월"])
    ret["월"] = ret["월"].astype(str).str.slice(0, 7)
    ret = ret.set_index("월")

    proxy = pd.read_excel(XLSX, sheet_name="01_테마프록시", header=2)
    proxy = proxy.dropna(subset=["테마", "ETF"])
    theme_of = dict(zip(proxy["ETF"], proxy["테마"]))
    trust = dict(zip(proxy["테마"], proxy["12M Spearman"]))

    events = pd.read_excel(XLSX, sheet_name="04_저점이벤트", header=2)
    events = events.dropna(subset=["저점일"])
    events["저점일"] = pd.to_datetime(events["저점일"])
    return ret, theme_of, trust, events


def compare(picked: np.ndarray, rest: np.ndarray) -> tuple[float, float]:
    """그물 안 두 무리를 견준다 → (오른 비율 차 p, 중앙값 차 %p)"""
    picked = picked[~np.isnan(picked)]
    rest = rest[~np.isnan(rest)]
    if picked.size == 0 or rest.size == 0:
        return float("nan"), float("nan")
    return (((picked > 0).mean() - (rest > 0).mean()) * 100,
            (float(np.median(picked)) - float(np.median(rest))) * 100)


def verdict(wins: list, meds: list, least: int = 8) -> str:
    if len(wins) < least:
        return f"판정 못 함(자리 {len(wins)})"
    w = (np.array(wins) > 0).mean() * 100
    m = (np.array(meds) > 0).mean() * 100
    if w >= PASS_MARK and m >= PASS_MARK:
        return "○ 합격"
    if w <= 100 - PASS_MARK and m <= 100 - PASS_MARK:
        return "✗ 거꾸로"
    return "△ 안 됨"


def line(name: str, wins: list, meds: list, least: int = 8) -> None:
    if not wins:
        say(f"  {name:<22} 잴 자리 없음")
        return
    w = np.array(wins)
    m = np.array(meds)
    say(f"  {name:<22}자리 {len(w):>3} · 이긴 자리 {(w > 0).mean() * 100:>5.1f}% · "
        f"수익 이긴 자리 {(m > 0).mean() * 100:>5.1f}% · "
        f"가운데 {np.median(m):>+6.2f}%p   {verdict(list(w), list(m), least)}")


# ────────────────────────────────────────────────────────────── A
def part_a(ret, theme_of, events) -> None:
    say("=" * 86)
    say("A. 고정 단계순서(M1~M12) — 과거 저점의 그 단계 Top5를 고르면 버나")
    say("=" * 86)
    say("  저점 e의 M단계에서는 **e보다 앞선 저점들만** 써서 그 단계 평균등수를 내고")
    say("  상위 5테마를 고른다. 그 달 20테마 안에서 나머지와 견준다.")

    etfs = [c for c in ret.columns if c in theme_of]
    stage: dict[tuple, pd.Series] = {}     # (저점일, M) → 테마별 그달 수익
    for _, row in events.iterrows():
        for m in range(1, 13):
            month = row.get(f"M{m}")
            if not isinstance(month, str):
                month = str(month)[:7] if pd.notna(month) else None
            if not month or month not in ret.index:
                continue
            values = ret.loc[month, etfs].astype(float)
            values.index = [theme_of[e] for e in etfs]
            stage[(row["저점일"], m)] = values

    order = list(events["저점일"])
    for band_name, keep in (("전체", None),
                            ("얕은 -6~-12%", "-6~-12%"),
                            ("깊은 -12% 아래", "deep")):
        wins, meds = [], []
        for pos, date in enumerate(order):
            band = str(events.loc[events["저점일"] == date, "구간"].iloc[0])
            if keep == "-6~-12%" and band != "-6~-12%":
                continue
            if keep == "deep" and band == "-6~-12%":
                continue
            for m in range(1, 13):
                now = stage.get((date, m))
                if now is None or now.dropna().size < 15:
                    continue
                # 앞선 저점들만(같은 무리 안에서) 그 단계 등수를 모은다
                past_ranks = []
                for older in order[:pos]:
                    older_band = str(events.loc[events["저점일"] == older, "구간"].iloc[0])
                    if keep == "-6~-12%" and older_band != "-6~-12%":
                        continue
                    if keep == "deep" and older_band == "-6~-12%":
                        continue
                    past = stage.get((older, m))
                    if past is not None:
                        past_ranks.append(past.rank(ascending=False))
                if len(past_ranks) < 2:
                    continue
                mean_rank = pd.concat(past_ranks, axis=1).mean(axis=1)
                top = list(mean_rank.sort_values().head(TOP_N).index)
                picked = now[[t for t in now.index if t in top]].to_numpy(float)
                rest = now[[t for t in now.index if t not in top]].to_numpy(float)
                w, md = compare(picked, rest)
                if np.isnan(w):
                    continue
                wins.append(w)
                meds.append(md)
        line(band_name, wins, meds)

    say()
    say("  단계별로 갈라 본다 (전체 저점 · M1~M3 / M4~M6 / M7~M12)")
    for label, span in (("M1만", range(1, 2)), ("M1~M3", range(1, 4)),
                        ("M4~M6", range(4, 7)), ("M7~M12", range(7, 13))):
        wins, meds = [], []
        for pos, date in enumerate(order):
            for m in span:
                now = stage.get((date, m))
                if now is None or now.dropna().size < 15:
                    continue
                past_ranks = [stage[(o, m)].rank(ascending=False)
                              for o in order[:pos] if (o, m) in stage]
                if len(past_ranks) < 2:
                    continue
                mean_rank = pd.concat(past_ranks, axis=1).mean(axis=1)
                top = list(mean_rank.sort_values().head(TOP_N).index)
                picked = now[[t for t in now.index if t in top]].to_numpy(float)
                rest = now[[t for t in now.index if t not in top]].to_numpy(float)
                w, md = compare(picked, rest)
                if np.isnan(w):
                    continue
                wins.append(w)
                meds.append(md)
        line(label, wins, meds)


# ────────────────────────────────────────────────────────────── B
def part_b(ret, theme_of) -> None:
    say()
    say("=" * 86)
    say("B. 실시간 강도 — 매달 앞선 N개월 수익 상위 5테마를 고르면 다음 달에 버나")
    say("=" * 86)
    say("  저점과 상관없이 전 기간(2018-02~2026-07) 매달 잰다. 그물은 그달 20테마다.")

    etfs = [c for c in ret.columns if c in theme_of]
    frame = ret[etfs].astype(float)
    frame.columns = [theme_of[e] for e in etfs]
    months = list(frame.index)

    for span in (1, 3, 6, 12):
        wins, meds = [], []
        for pos in range(span, len(months) - 1):
            window = frame.iloc[pos - span:pos]
            if window.isna().all().all():
                continue
            strength = (1 + window).prod(skipna=False) - 1
            strength = strength.dropna()
            if strength.size < 15:
                continue
            top = list(strength.sort_values(ascending=False).head(TOP_N).index)
            nxt = frame.iloc[pos]
            picked = nxt[[t for t in nxt.index if t in top]].to_numpy(float)
            rest = nxt[[t for t in nxt.index if t not in top]].to_numpy(float)
            w, md = compare(picked, rest)
            if np.isnan(w):
                continue
            wins.append(w)
            meds.append(md)
        line(f"{span}개월 강도 상위 5", wins, meds, least=20)

    say()
    say("  QQQ를 이겼나 — 상위 5테마 평균이 QQQ보다 나은 달의 비율")
    qqq = ret["QQQ"].astype(float)
    for span in (1, 3, 6, 12):
        beat, total, edge = 0, 0, []
        for pos in range(span, len(months) - 1):
            window = frame.iloc[pos - span:pos]
            strength = ((1 + window).prod(skipna=False) - 1).dropna()
            if strength.size < 15:
                continue
            top = list(strength.sort_values(ascending=False).head(TOP_N).index)
            nxt = frame.iloc[pos]
            picked = nxt[[t for t in nxt.index if t in top]].dropna()
            if picked.empty or months[pos] not in qqq.index:
                continue
            gap = float(picked.mean()) - float(qqq.loc[months[pos]])
            edge.append(gap * 100)
            beat += gap > 0
            total += 1
        if total:
            say(f"    {span:>2}개월 강도 · {total}달 중 {beat}달 이김 "
                f"({beat / total * 100:.1f}%) · 한 달 평균 {np.mean(edge):+.2f}%p")


# ────────────────────────────────────────────────────────────── C
def part_c(ret, theme_of) -> None:
    say()
    say("=" * 86)
    say("C. 리더 피로 — 지금 Top5인데 QQQ 대비 1개월 약세면 다음 달에 빠지나")
    say("=" * 86)

    etfs = [c for c in ret.columns if c in theme_of]
    frame = ret[etfs].astype(float)
    frame.columns = [theme_of[e] for e in etfs]
    qqq = ret["QQQ"].astype(float)
    months = list(frame.index)

    tired, healthy = [], []
    for pos in range(4, len(months) - 1):
        window = frame.iloc[pos - 3:pos]
        strength = ((1 + window).prod(skipna=False) - 1).dropna()
        if strength.size < 15:
            continue
        top = list(strength.sort_values(ascending=False).head(TOP_N).index)
        last = frame.iloc[pos - 1]
        prev = frame.iloc[pos - 2]
        market = float(qqq.iloc[pos - 1]) if months[pos - 1] in qqq.index else np.nan
        nxt = frame.iloc[pos]
        for theme in top:
            value = last.get(theme)
            if value is None or np.isnan(value) or np.isnan(market):
                continue
            slowing = (value - (prev.get(theme) if prev.get(theme) is not None else np.nan))
            weak = value < market
            after = nxt.get(theme)
            if after is None or np.isnan(after):
                continue
            if weak and not np.isnan(slowing) and slowing < 0:
                tired.append(after)
            else:
                healthy.append(after)
    tired, healthy = np.array(tired), np.array(healthy)
    say(f"  피로 신호 걸린 자리 {tired.size} · 나머지 Top5 자리 {healthy.size}")
    if tired.size and healthy.size:
        say(f"    피로   다음달 오른 비율 {(tired > 0).mean() * 100:>5.1f}% · "
            f"중앙값 {np.median(tired) * 100:>+6.2f}%")
        say(f"    나머지 다음달 오른 비율 {(healthy > 0).mean() * 100:>5.1f}% · "
            f"중앙값 {np.median(healthy) * 100:>+6.2f}%")
        say(f"    차이   {((tired > 0).mean() - (healthy > 0).mean()) * 100:>+5.1f}p · "
            f"{(np.median(tired) - np.median(healthy)) * 100:>+6.2f}%p")
    say("  ※ 엑셀은 이 신호 표본이 전체 14건·OOS 8건이라고 적었다. 여기서는 문턱을")
    say("    같은 뜻으로 다시 짜 자리를 늘렸다. 그래도 한 무리가 30건 미만이면 못 쓴다.")


# ────────────────────────────────────────────────────────────── D
def part_d(trust) -> None:
    say()
    say("=" * 86)
    say("D. ETF 프록시와 앱 명부 — 이 자료를 자비스3에 그대로 옮길 수 있나")
    say("=" * 86)
    values = {k: float(v) for k, v in trust.items() if pd.notna(v)}
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    say(f"  20테마 평균 {np.mean(list(values.values())):.3f} · "
        f"0.5 미만 {sum(1 for v in values.values() if v < 0.5)}개 · "
        f"0.75 이상 {sum(1 for v in values.values() if v >= 0.75)}개")
    say("  가장 안 맞는 다섯: " + " · ".join(f"{k} {v:.2f}" for k, v in ordered[:5]))
    say("  가장 잘 맞는 다섯: " + " · ".join(f"{k} {v:.2f}" for k, v in ordered[-5:]))


def main() -> None:
    ret, theme_of, trust, events = load()
    say(f"월별 수익 {ret.shape[0]}달 · 테마 {len(theme_of)}개 · 저점 {len(events)}회")
    part_a(ret, theme_of, events)
    part_b(ret, theme_of)
    part_c(ret, theme_of)
    part_d(trust)

    out = pathlib.Path(__file__).resolve().parent / "_out" / "us_theme_rotation_audit.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(BUF.getvalue())
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
