"""「한국시장 설명」에 넣을 숫자를 상장폐지 포함 자료로 다시 잰다 (2026-09-30, 자비스10).

A. 12년 통째 — 2014-07-09 에 거래되던 종목을 그날 사서 2026-09-30 까지 들었다면(폐지되면 마지막 가격)
B. 아무 종목 1년 — 거래대금 10억↑ · 다음 날 시가 → 250일 뒤 종가 · 같은 기간 코스피
C. 많이 오른 종목 따라 사기 — 6개월 상승률 상위 20% vs 나머지, 1년 뒤
D. 코스피 오른 몫이 며칠(몇 달)에 몰렸나 — 가장 좋은 달 N개를 빼면
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_baseline_full_20260930 import forward, load  # noqa: E402


def main() -> None:
    px, kospi, meta = load()
    close, vol = px["close"], px["volume"]
    k = kospi["Close"]
    start, end = close.index[0], close.index[-1]

    # A
    first = close.iloc[0]
    alive0 = first.notna() & (vol.iloc[0] > 0)
    last = close.ffill().iloc[-1]
    tot = (last[alive0] / first[alive0] - 1) * 100
    kt = (k.iloc[-1] / k.iloc[0] - 1) * 100
    dead = meta["status"].eq("delisted").reindex(close.columns).fillna(False)
    print(f"[A] {start.date()} → {end.date()} · 첫날 거래된 종목 {int(alive0.sum())}개 (그중 뒤에 폐지 {int(dead[alive0].sum())}개)")
    print(f"    코스피 {k.iloc[0]:,.0f} → {k.iloc[-1]:,.0f} ({kt:+.0f}%) · 종목 가운데 {tot.median():+.0f}% · 오른 종목 {(tot>0).mean()*100:.0f}% · "
          f"코스피 이긴 종목 100개 중 {(tot>kt).mean()*100:.0f}개 · 반토막 넘게 난 종목 {(tot<=-50).mean()*100:.0f}%")
    k24 = k.loc[:"2024-12-31"].iloc[-1]
    c24 = close.ffill().loc[:"2024-12-31"].iloc[-1]
    t24 = (c24[alive0] / first[alive0] - 1) * 100
    kt24 = (k24 / k.iloc[0] - 1) * 100
    print(f"    (2024년 말에서 끊으면) 코스피 {kt24:+.0f}% · 종목 가운데 {t24.median():+.0f}% · 코스피 이긴 종목 {(t24>kt24).mean()*100:.0f}개")

    # B · C
    value20 = (close * vol).rolling(20, min_periods=10).mean() / 1e8
    base = (value20 >= 10) & (vol > 0) & (close.notna().cumsum() >= 250)
    fwd, kf = forward(px, kospi, 250)
    F, KF, U = fwd.to_numpy(), kf.to_numpy(), base.to_numpy()
    mom = (close / close.shift(120) - 1).where(base).rank(axis=1, pct=True, ascending=False).to_numpy()
    ups, beats, meds, kup, top_m, rest_m = [], [], [], [], [], []
    for row in range(260, len(close) - 251, 5):
        sel = U[row] & np.isfinite(F[row])
        if sel.sum() < 100 or np.isnan(KF[row]):
            continue
        f = F[row][sel]
        ups.append((f > 0).mean() * 100)
        beats.append((f > KF[row]).mean() * 100)
        meds.append(np.median(f))
        kup.append(KF[row] > 0)
        m = mom[row][sel]
        top_m.append(np.median(f[m <= 0.2]))
        rest_m.append(np.median(f[m > 0.2]))
    print(f"[B] 아무 종목 1년: 오름 100번 중 {np.mean(ups):.0f}번 · 코스피 이김 {np.mean(beats):.0f}번 · 가운데 {np.median(meds):+.1f}% "
          f"· 같은 날 코스피 1년 오름 {np.mean(kup)*100:.0f}번 ({len(meds)}날)")
    print(f"[C] 6개월 많이 오른 20% → 1년 뒤 가운데 {np.median(top_m):+.1f}% · 나머지 {np.median(rest_m):+.1f}% "
          f"(차이 {np.median(np.array(top_m)-np.array(rest_m)):+.1f}%p)")

    # D — 코스피 30년 달별
    y = pd.read_csv(pathlib.Path(__file__).resolve().parent / "_data/kospi_yahoo_19961211_20260930.csv",
                    header=[0, 1], index_col=0, parse_dates=True)
    y.columns = [c[0] for c in y.columns]
    mr = y["Close"].resample("ME").last().pct_change().dropna()
    for a, b in (("2014-07", "2026-09"), ("1997-01", "2026-09")):
        r = mr.loc[a:b]
        total = (1 + r).prod() - 1
        out = [f"[D] {a}~{b} ({len(r)}달) 코스피 {total*100:+.0f}%"]
        for n in (5, 10):
            drop = r.drop(r.nlargest(n).index)
            out.append(f"좋은 {n}달 빼면 {((1+drop).prod()-1)*100:+.0f}%")
        print(" · ".join(out))


if __name__ == "__main__":
    main()
