"""첨부 엑셀(클로드_나스닥_테마상승률_v4)의 원자료 1,362행을 집값 규칙으로 다시 잰다.

목적 — 엑셀 '12 배점기준안' 시트가 스스로 "임의로 정했다"고 적어 둔 칸들이
정말 배점을 줄 만한지 확인한다. 이 프로젝트의 합격선(승률·수익률 둘 다 65%,
여러 보유기간에서 모두)을 그대로 적용한다.

재는 것
  A. 낙폭 깊이 게이트      — 깊은 하락 뒤가 정말 더 나은가
  B. 테마 순위 지속성      — 과거 등수로 다음 저점을 맞힐 수 있나 (앞을 안 보는 방식)
  C. 반등 확산(3개월 시점) — 5종목 중 몇 개 올랐나가 12개월을 가르나
  D. 표본 두께 / 한 종목 지배 — 얇은 테마 등수가 종목 하나로 만들어지나

쓰는 법:  python research/us_crash_xlsx_audit.py
"""

from __future__ import annotations

import io
import pathlib
import sys

import numpy as np
import pandas as pd

XLSX = pathlib.Path.home() / "Downloads" / "클로드_나스닥_테마상승률_v4.xlsx"
HORIZONS = ["3개월(%)", "6개월(%)", "9개월(%)", "12개월(%)"]
PASS_MARK = 65.0

BUF = io.StringIO()


def say(text: str = "") -> None:
    print(text, file=BUF)


def load() -> pd.DataFrame:
    raw = pd.read_excel(XLSX, sheet_name="13 원자료 1362행", header=4)
    raw = raw.dropna(subset=["테마", "종목", "저점일"])
    raw["저점일"] = pd.to_datetime(raw["저점일"])
    return raw


def wl(a: np.ndarray, b: np.ndarray) -> tuple[float, float, int, int]:
    """두 무리를 견준다 → (오른 비율 차이 p, 중앙값 차이 %, a개수, b개수)"""
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if a.size == 0 or b.size == 0:
        return float("nan"), float("nan"), a.size, b.size
    return ((a > 0).mean() - (b > 0).mean()) * 100, float(np.median(a) - np.median(b)), a.size, b.size


# ────────────────────────────────────────────────────────────── A
def part_a(raw: pd.DataFrame) -> None:
    say("=" * 78)
    say("A. 낙폭 깊이 게이트 — 깊은 하락(-18% 아래) 뒤가 정말 더 나은가")
    say("=" * 78)
    say("  같은 종목 무리를 깊은 저점 / 얕은 저점으로 갈라 견준다.")
    say(f"  {'보유':<8}{'오른 비율 차':>14}{'중앙값 차':>12}{'깊은 건수':>10}{'얕은 건수':>10}")
    deep = raw["QQQ 하락률(%)"] <= -18
    for col in HORIZONS:
        w, m, na, nb = wl(raw.loc[deep, col].to_numpy(float),
                          raw.loc[~deep, col].to_numpy(float))
        say(f"  {col:<8}{w:>+13.1f}p{m:>+11.1f}%{na:>10}{nb:>10}")

    say()
    say("  구간을 다섯으로 쪼개면 (12개월, 중앙값)")
    for band, grp in raw.groupby("하락구간"):
        v = grp["12개월(%)"].to_numpy(float)
        v = v[~np.isnan(v)]
        if v.size == 0:
            continue
        events = grp["저점일"].nunique()
        say(f"    {band:<10} 사건 {events}회 · 종목건수 {v.size:>4} · "
            f"오른 비율 {(v > 0).mean() * 100:>5.1f}% · 중앙값 {np.median(v):>+7.1f}%")


# ────────────────────────────────────────────────────────────── B
def part_b(raw: pd.DataFrame) -> None:
    say()
    say("=" * 78)
    say("B. 테마 순위 지속성 — 과거 등수로 다음 저점을 맞힐 수 있나")
    say("=" * 78)
    say("  앞을 보지 않는다. 저점 i에서는 저점 1..i-1까지만 써서 테마 등수를 매기고,")
    say("  그 등수 상위 5테마와 나머지를 저점 i의 실제 성적으로 견준다.")

    for col in HORIZONS:
        table = raw.pivot_table(index="저점일", columns="테마", values=col, aggfunc="mean")
        table = table.dropna(how="all")
        stock = raw.pivot_table(index="저점일", columns="종목", values=col, aggfunc="mean")
        theme_of = raw.drop_duplicates("종목").set_index("종목")["테마"]

        wins, meds, used = [], [], 0
        for pos in range(3, len(table)):          # 과거가 3회 이상 쌓인 뒤부터
            past = table.iloc[:pos].mean()
            now = table.iloc[pos]
            if now.dropna().size < 15:
                continue
            top = list(past.sort_values(ascending=False).head(5).index)
            date = table.index[pos]
            row = stock.loc[date].dropna()
            picked = row[[t for t in row.index if theme_of.get(t) in top]].to_numpy(float)
            rest = row[[t for t in row.index if theme_of.get(t) not in top]].to_numpy(float)
            w, m, na, nb = wl(picked, rest)
            if na < 5 or nb < 5:
                continue
            wins.append(w)
            meds.append(m)
            used += 1
        wins, meds = np.array(wins), np.array(meds)
        if used == 0:
            say(f"  {col:<8} 잴 수 있는 저점 없음")
            continue
        ws = (wins > 0).mean() * 100
        ms = (meds > 0).mean() * 100
        mark = "○ 합격" if ws >= PASS_MARK and ms >= PASS_MARK else "△ 안 됨"
        say(f"  {col:<8} 저점 {used:>2}회 · 이긴 저점 {ws:>5.1f}% · "
            f"수익 이긴 저점 {ms:>5.1f}% · 가운데 {np.median(wins):>+6.1f}p   {mark}")

    say()
    say("  이웃한 두 저점 사이 등수 상관 (스피어만, 12개월)")
    table = raw.pivot_table(index="저점일", columns="테마", values="12개월(%)", aggfunc="mean").dropna(how="all")
    rho = []
    for pos in range(1, len(table)):
        a, b = table.iloc[pos - 1], table.iloc[pos]
        pair = pd.concat([a, b], axis=1).dropna()
        if len(pair) < 10:
            continue
        rho.append(pair.corr(method="spearman").iloc[0, 1])
    rho = np.array(rho)
    say(f"    {len(rho)}쌍 · 가운데 {np.median(rho):+.3f} · 평균 {rho.mean():+.3f} · "
        f"양수 비율 {(rho > 0).mean() * 100:.0f}%")

    say()
    say("  같은 구간끼리만 견준 등수 상관 (-6~-12% 8회)")
    shallow = raw[raw["하락구간"] == "-6~-12%"]
    t2 = shallow.pivot_table(index="저점일", columns="테마", values="12개월(%)", aggfunc="mean").dropna(how="all")
    rho2 = []
    for i in range(len(t2)):
        for j in range(i + 1, len(t2)):
            pair = pd.concat([t2.iloc[i], t2.iloc[j]], axis=1).dropna()
            if len(pair) < 10:
                continue
            rho2.append(pair.corr(method="spearman").iloc[0, 1])
    rho2 = np.array(rho2)
    if rho2.size:
        say(f"    {rho2.size}쌍 · 가운데 {np.median(rho2):+.3f} · 양수 비율 {(rho2 > 0).mean() * 100:.0f}%")


# ────────────────────────────────────────────────────────────── C
def part_c(raw: pd.DataFrame) -> None:
    say()
    say("=" * 78)
    say("C. 반등 확산 — 3개월 시점에 몇 종목이 올랐나가 그 뒤를 가르나")
    say("=" * 78)
    say("  저점 3개월 뒤 테마 5종목 중 오른 종목 수로 갈라, 6·9·12개월 성적을 본다.")

    rows = []
    for (date, theme), grp in raw.groupby(["저점일", "테마"]):
        v3 = grp["3개월(%)"].to_numpy(float)
        v3 = v3[~np.isnan(v3)]
        if v3.size < 3:
            continue
        rows.append({
            "저점일": date, "테마": theme,
            "종목수": v3.size, "오른수": int((v3 > 0).sum()),
            "오른비율": (v3 > 0).mean(),
            "6개월(%)": grp["6개월(%)"].mean(),
            "9개월(%)": grp["9개월(%)"].mean(),
            "12개월(%)": grp["12개월(%)"].mean(),
        })
    wide = pd.DataFrame(rows)

    say(f"  {'3개월 오른 비율':<16}{'묶음수':>7}{'6개월':>10}{'9개월':>10}{'12개월':>10}{'12개월 플러스':>12}")
    for label, lo, hi in [("전부 (100%)", 0.999, 1.01), ("대부분 (60~99%)", 0.60, 0.999),
                          ("절반 (40~60%)", 0.40, 0.60), ("소수 (1~40%)", 0.001, 0.40),
                          ("전멸 (0%)", -0.01, 0.001)]:
        sub = wide[(wide["오른비율"] > lo) & (wide["오른비율"] <= hi)] if lo > 0 else \
              wide[wide["오른비율"] <= hi]
        if len(sub) == 0:
            continue
        v12 = sub["12개월(%)"].dropna()
        say(f"  {label:<16}{len(sub):>7}{sub['6개월(%)'].median():>+9.1f}%"
            f"{sub['9개월(%)'].median():>+9.1f}%{v12.median():>+9.1f}%"
            f"{(v12 > 0).mean() * 100:>11.0f}%")

    say()
    say("  합격선 검사 — '4~5종목 상승' vs '3종목 이하 상승' (저점별로 따로 셈)")
    for col in ["6개월(%)", "9개월(%)", "12개월(%)"]:
        wins, meds, used = [], [], 0
        for date, grp in wide.groupby("저점일"):
            a = grp.loc[grp["오른비율"] >= 0.8, col].to_numpy(float)
            b = grp.loc[grp["오른비율"] < 0.8, col].to_numpy(float)
            w, m, na, nb = wl(a, b)
            if na < 3 or nb < 3:
                continue
            wins.append(w)
            meds.append(m)
            used += 1
        wins, meds = np.array(wins), np.array(meds)
        if used == 0:
            say(f"  {col:<8} 잴 수 있는 저점 없음")
            continue
        ws, ms = (wins > 0).mean() * 100, (meds > 0).mean() * 100
        mark = "○ 합격" if ws >= PASS_MARK and ms >= PASS_MARK else "△ 안 됨"
        say(f"  {col:<8} 저점 {used:>2}회 · 이긴 저점 {ws:>5.1f}% · "
            f"수익 이긴 저점 {ms:>5.1f}% · 가운데 {np.median(meds):>+6.1f}%   {mark}")

    share = (wide["오른비율"] >= 0.8).mean() * 100
    say(f"  걸리는 비율 {share:.0f}%  (10~85% 밖이면 못 쓴다)")


# ────────────────────────────────────────────────────────────── D
def part_d(raw: pd.DataFrame) -> None:
    say()
    say("=" * 78)
    say("D. 표본 두께와 한 종목 지배 — 테마 등수가 종목 하나로 만들어지나")
    say("=" * 78)

    done = raw.dropna(subset=["12개월(%)"])
    say("  저점마다 테마 평균에서 '가장 잘 오른 한 종목'을 빼면 등수가 몇 칸 움직이나")
    moves_thin, moves_thick = [], []
    for date, grp in done.groupby("저점일"):
        full, trimmed, size = {}, {}, {}
        for theme, g in grp.groupby("테마"):
            v = g["12개월(%)"].to_numpy(float)
            if v.size < 2:
                continue
            full[theme] = v.mean()
            trimmed[theme] = np.sort(v)[:-1].mean()
            size[theme] = v.size
        if len(full) < 10:
            continue
        r1 = pd.Series(full).rank(ascending=False)
        r2 = pd.Series(trimmed).rank(ascending=False)
        for theme in r1.index:
            gap = abs(r1[theme] - r2[theme])
            (moves_thin if size[theme] <= 3 else moves_thick).append(gap)
    say(f"    종목 3개 이하 테마 : 평균 {np.mean(moves_thin):.2f}칸 (n={len(moves_thin)})")
    say(f"    종목 4개 이상 테마 : 평균 {np.mean(moves_thick):.2f}칸 (n={len(moves_thick)})")

    say()
    say("  테마 안 종목 성적이 얼마나 흩어지나 (12개월, 저점×테마 묶음별)")
    spread = []
    for (date, theme), g in done.groupby(["저점일", "테마"]):
        v = g["12개월(%)"].to_numpy(float)
        if v.size < 4:
            continue
        spread.append(v.max() - v.min())
    say(f"    가운데 벌어짐 {np.median(spread):.0f}%p  (n={len(spread)}) "
        f"— 같은 테마라도 1등과 꼴찌가 이만큼 갈린다")

    say()
    say("  테마 안 '종목 등수'는 다음 저점에도 이어지나 (스피어만, 12개월)")
    rhos = []
    for theme, g in done.groupby("테마"):
        t = g.pivot_table(index="저점일", columns="종목", values="12개월(%)", aggfunc="mean")
        for pos in range(1, len(t)):
            pair = pd.concat([t.iloc[pos - 1], t.iloc[pos]], axis=1).dropna()
            if len(pair) < 4:
                continue
            rhos.append(pair.corr(method="spearman").iloc[0, 1])
    rhos = np.array(rhos)
    say(f"    {rhos.size}쌍 · 가운데 {np.median(rhos):+.3f} · 양수 비율 {(rhos > 0).mean() * 100:.0f}%")


def main() -> None:
    raw = load()
    say(f"원자료 {len(raw)}행 · 테마 {raw['테마'].nunique()}개 · "
        f"종목 {raw['종목'].nunique()}개 · 저점 {raw['저점일'].nunique()}회")
    say(f"12개월이 채워진 저점 {raw.dropna(subset=['12개월(%)'])['저점일'].nunique()}회")
    part_a(raw)
    part_b(raw)
    part_c(raw)
    part_d(raw)

    out = pathlib.Path(__file__).resolve().parent / "_out" / "us_crash_xlsx_audit.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(BUF.getvalue(), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(BUF.getvalue())
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
