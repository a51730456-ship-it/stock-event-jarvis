"""테마가 같이 움직이는 정도가 해마다 커졌나 (2026-08-06 사용자 물음).

"뒤 5년에만 테마가 통한 것"이 우연인지, 시장이 테마 중심으로 바뀐 것인지 가른다.
바뀐 것이라면 **테마 안 종목들이 같이 움직이는 정도**가 해마다 커졌어야 한다.

두 가지를 해마다 잰다.
  ① 같은 테마 종목쌍의 상관 — 얼마나 같이 움직이나
  ② 아무 종목쌍의 상관       — 시장 전체가 같이 움직인 정도(비교 기준)
  ③ 차이(①-②)              — **시장 탓을 뺀 순수 테마 결속력**

    python research/theme_cohesion_by_year.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis3_data import US_LARGE_CAP_UNIVERSE, US_THEMES

MEMBER = {}
for theme in US_THEMES:
    for s in theme["stocks"]:
        MEMBER.setdefault(s, []).append(theme["name"])

tick = [s for s in US_LARGE_CAP_UNIVERSE if s in MEMBER]
d = yf.download(tick, period="10y", interval="1d", auto_adjust=True,
                group_by="ticker", threads=8, progress=False)
closes = {}
for t in tick:
    try:
        s = d[t]["Close"].dropna()
    except Exception:
        continue
    if len(s) >= 400:
        closes[t] = s
frame = pd.DataFrame(closes)
rets = frame.pct_change().dropna(how="all")
names = list(frame.columns)
print(f"테마 종목 {len(names)}개 · {rets.index[0].date()} ~ {rets.index[-1].date()}")

# 같은 테마 종목쌍인지 미리 표시해 둔다
same = np.zeros((len(names), len(names)), dtype=bool)
for i, a in enumerate(names):
    for j, b in enumerate(names):
        if i < j and set(MEMBER.get(a, [])) & set(MEMBER.get(b, [])):
            same[i, j] = True
upper = np.triu(np.ones((len(names), len(names)), dtype=bool), 1)
print(f"같은 테마 종목쌍 {int(same.sum()):,}개 · 전체 쌍 {int(upper.sum()):,}개")
print("=" * 62)
print(f"  {'해':<8}{'거래일':>7}{'같은 테마':>11}{'아무 쌍':>10}{'차이':>9}")

rows = []
for year, part in rets.groupby(rets.index.year):
    part = part.dropna(axis=1, thresh=int(len(part) * 0.9))
    if len(part) < 60 or part.shape[1] < 50:
        continue
    keep = [names.index(c) for c in part.columns]
    corr = part.corr().values
    sub_same = same[np.ix_(keep, keep)]
    sub_up = np.triu(np.ones(corr.shape, dtype=bool), 1)
    theme_corr = float(np.nanmean(corr[sub_same]))
    all_corr = float(np.nanmean(corr[sub_up]))
    rows.append((year, len(part), theme_corr, all_corr))
    print(f"  {year:<8}{len(part):>7}{theme_corr:>11.3f}{all_corr:>10.3f}"
          f"{theme_corr - all_corr:>9.3f}")

# 앞 5년 / 뒤 5년으로 묶어서도 본다
front = [r for r in rows if r[0] <= 2021]
back = [r for r in rows if r[0] >= 2022]
if front and back:
    fg = np.mean([r[2] - r[3] for r in front])
    bg = np.mean([r[2] - r[3] for r in back])
    print(f"\n앞(~2021) 차이 평균 {fg:.3f} · 뒤(2022~) 차이 평균 {bg:.3f}"
          f" · 변화 {bg - fg:+.3f}")
    print("차이가 커졌으면 시장이 테마 중심으로 바뀐 것이고,"
          " 그대로면 뒤 5년 성적은 다른 이유다.")
