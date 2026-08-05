"""등급표 — 종목 낙폭을 20~30%와 30~50%로 갈라서."""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd

S = str(Path(__file__).parent / "_data")
data = pickle.load(open(S + r"\us_adj2.pkl", "rb"))


def prep(df):
    c, h = df["Close"], df["High"]
    hi = h.rolling(252, min_periods=252).max()
    return pd.DataFrame({"open": df["Open"], "close": c, "hi252": hi,
                         "dd": c / hi - 1.0}, index=df.index)


Q = prep(data["QQQ"])
STK = {t: prep(v) for t, v in data.items() if t not in ("QQQ", "SPY")}
GR = [(-0.06, 0.00, "-0~-6%"), (-0.12, -0.06, "-6~-12%"), (-0.18, -0.12, "-12~-18%"),
      (-0.24, -0.18, "-18~-24%"), (-0.30, -0.24, "-24~-30%"), (-2.00, -0.30, "-30% 아래")]
# 종목 낙폭 두 갈래
SB = [(-0.30, -0.20, "20~30%"), (-0.50, -0.30, "30~50%")]
HOLD = 120


def fwd(m, i, h):
    b, e = i + 1, i + 1 + h
    if e >= len(m):
        return None
    bu, se = m["open"].iat[b], m["close"].iat[e]
    if not np.isfinite(bu) or not np.isfinite(se) or bu <= 0:
        return None
    return se / bu - 1.0


def st(rs, least=30):
    if not rs or len(rs) < least:
        return None
    a = np.array(rs)
    return {"n": len(a), "mean": a.mean() * 100, "med": np.median(a) * 100, "win": (a > 0).mean() * 100}


def fmt(s):
    return f"{s['mean']:+6.1f} {s['med']:+6.1f} {s['win']:5.1f}" if s else "     —      —     — "


dd = Q["dd"].dropna()
ipos = {d: i for i, d in enumerate(Q.index)}

qall, qq = [], {n: [] for _l, _h, n in GR}
for i in range(251, len(Q) - HOLD - 1):
    v = Q["dd"].iat[i]
    if not np.isfinite(v):
        continue
    r = fwd(Q, i, HOLD)
    if r is None:
        continue
    qall.append(r)
    for lo, hi, nm in GR:
        if lo < v <= hi:
            qq[nm].append(r)
            break

sall = []
pick = {n: {b[2]: [] for b in SB} for _l, _h, n in GR}
for t, m in STK.items():
    fh = m["dd"].values
    for i in range(251, len(m) - HOLD - 1):
        qi = ipos.get(m.index[i])
        if qi is None or not np.isfinite(Q["dd"].iat[qi]) or not np.isfinite(fh[i]):
            continue
        r = fwd(m, i, HOLD)
        if r is None:
            continue
        sall.append(r)
        v = Q["dd"].iat[qi]
        for lo, hi, nm in GR:
            if lo < v <= hi:
                for blo, bhi, bnm in SB:
                    if blo <= fh[i] < bhi:
                        pick[nm][bnm].append(r)
                        break
                break

print("6달(120거래일) 보유 · 배당 포함 · 미국 대형주 169종목")
print("숫자 세 개 = 평균 / 가운데 값 / 100번 중 이익\n")
head = (f"{'나스닥 고점 대비':<13}{'날 비율':>8}{'나스닥을 사면':>22}"
        f"{'20~30% 빠진 종목':>22}{'30~50% 빠진 종목':>22}")
print(head)
print("-" * 92)
print(f"{'아무 날이나':<12}{'—':>9}{fmt(st(qall)):>22}"
      f"{'(아무 종목이나 ' + fmt(st(sall)).strip() + ')':>44}")
print("-" * 92)
for lo, hi, nm in GR:
    sel = dd[(dd > lo) & (dd <= hi)]
    print(f"{nm:<13}{len(sel)/len(dd)*100:7.1f}%{fmt(qq[nm] and st(qq[nm])):>22}"
          f"{fmt(st(pick[nm]['20~30%'])):>22}{fmt(st(pick[nm]['30~50%'])):>22}")

print("\n잰 횟수")
for lo, hi, nm in GR:
    a, b = pick[nm]["20~30%"], pick[nm]["30~50%"]
    print(f"  {nm:<12} 20~30% {len(a):>6,}번   30~50% {len(b):>6,}번")
