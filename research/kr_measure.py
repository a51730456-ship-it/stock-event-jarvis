"""한국(코스피) 재검증 — 미국과 **똑같은 자**로 재서 견줄 수 있게 한다.

특히 확인할 것: 설명서에 적힌 '고점 대비 -10~-30%'가 맞는지.
지금 코드(jarvis4_data.CRASH_REBOUND_RULES)는 -30~-50%만 본다.
"""
import pickle
from pathlib import Path
import numpy as np
import pandas as pd

SCRATCH = str(Path(__file__).parent / "_data")
with open(SCRATCH + r"\kr_daily.pkl", "rb") as f:
    RAW = pickle.load(f)
STOCKS = RAW["stocks"]
KOSPI = RAW["kospi"]


def metrics(df):
    hi252 = df["High"].rolling(252, min_periods=252).max()
    return pd.DataFrame({
        "open": df["Open"], "high": df["High"], "close": df["Close"],
        "hi252": hi252,
        "from_high": df["Close"] / hi252 - 1.0,
        "is_new_high": df["High"] >= hi252,
    }, index=df.index)


M = {c: metrics(v["df"]) for c, v in STOCKS.items()}
POS = {c: {d: i for i, d in enumerate(m.index)} for c, m in M.items()}
KM = metrics(KOSPI)


def fwd_return(m, i, hold):
    b, s = i + 1, i + 1 + hold
    if s >= len(m):
        return None
    buy, sell = m["open"].iat[b], m["close"].iat[s]
    if not np.isfinite(buy) or not np.isfinite(sell) or buy <= 0:
        return None
    return sell / buy - 1.0


def stat(rs):
    if not rs:
        return None
    a = np.array(rs)
    return {"n": len(a), "med": float(np.median(a)) * 100,
            "win": float((a > 0).mean()) * 100, "mean": float(a.mean()) * 100}


def line(name, s, width=34):
    if s is None:
        return f"  {name:<{width}} —"
    return (f"  {name:<{width}} {s['n']:>7,}건  가운데 {s['med']:+6.2f}%  "
            f"100번 중 {s['win']:4.1f}번  평균 {s['mean']:+6.2f}%")


d0 = min(m.index[0] for m in M.values()).date()
d1 = max(m.index[-1] for m in M.values()).date()
print("=" * 100)
print(f"한국(코스피) 재검증 — 대형주 {len(STOCKS)}종목 · {d0} ~ {d1}")
print("=" * 100)

# ── 국면 나누기 ──────────────────────────────────────────────────────
ma200 = KM["close"].rolling(200, min_periods=200).mean()
up_regime = ((KM["close"] > ma200) & (KM["from_high"] > -0.10)).fillna(False)
UP_DAYS = {d: bool(v) for d, v in up_regime.items()}

# 미국과 같은 자 — 고점대비 -10% 아래 · 어제 내림 · 오늘 오름
crash_us_style = ((KM["from_high"] <= -0.10) &
                  (KM["close"].diff() > 0) &
                  (KM["close"].shift(1).diff() < 0)).fillna(False)
CRASH_DAYS = [d for d, v in crash_us_style.items() if v]

# 지금 앱이 쓰는 자 — -15% 아래 국면에서 '처음' 오른 날 한 번
FIRST_REBOUND = []
in_phase = False
for d in KM.index:
    fh = KM["from_high"].get(d)
    if not np.isfinite(fh):
        continue
    if not in_phase and fh <= -0.15:
        in_phase, fired = True, False
    if in_phase:
        if fh > -0.05:
            in_phase = False
            continue
        if not fired:
            i = KM.index.get_loc(d)
            if i > 0 and KM["close"].iat[i] > KM["close"].iat[i - 1]:
                FIRST_REBOUND.append(d)
                fired = True

print(f"\n[국면 나누기 — 코스피 기준]")
print(f"  평상시 상승장(200일선 위 · 고점대비 -10% 위): {sum(UP_DAYS.values())}일")
print(f"  급락 후 반등일(미국과 같은 자): {len(CRASH_DAYS)}일")
print(f"  급락 국면 첫 반등일(지금 앱의 자): {len(FIRST_REBOUND)}번 — "
      + ", ".join(str(d.date()) for d in FIRST_REBOUND))

# ── 갈래 1 — 신고가 눌림매수 ─────────────────────────────────────────
def breakout_signals(m, wait=(3, 5), band=(-0.06, -0.04)):
    out, n = [], len(m)
    nh, close, high = m["is_new_high"].values, m["close"].values, m["high"].values
    hi252 = m["hi252"].values
    i = 251
    while i < n:
        if not (np.isfinite(hi252[i]) and nh[i]):
            i += 1
            continue
        peak, fired, j = high[i], False, i
        for k in range(1, wait[1] + 1):
            j = i + k
            if j >= n or nh[j]:
                break
            peak = max(peak, high[j])
            if k >= wait[0]:
                drop = close[j] / peak - 1.0
                if band[0] <= drop <= band[1]:
                    out.append(j)
                    fired = True
                    break
        i = (j if fired else i + 1)
    return out


print("\n" + "=" * 100)
print("갈래 1 — 상승장 신고가 눌림매수")
print("=" * 100)
for hold in (20, 60, 120):
    rs, years = [], {}
    for c, m in M.items():
        for j in breakout_signals(m):
            if not UP_DAYS.get(m.index[j], False):
                continue
            r = fwd_return(m, j, hold)
            if r is not None:
                rs.append(r)
                years.setdefault(m.index[j].year, []).append(r)
    base = []
    updays = {d for d, v in UP_DAYS.items() if v}
    for c, m in M.items():
        for i in range(251, len(m) - hold - 1):
            if m.index[i] not in updays or not np.isfinite(m["hi252"].iat[i]):
                continue
            r = fwd_return(m, i, hold)
            if r is not None:
                base.append(r)
    sb = stat(base)
    print(line(f"규칙 · {hold}거래일 보유", stat(rs)))
    print(line(f"  기준선(아무 날이나) · {hold}일", sb))
    if hold == 120:
        tot = better = 0
        for y in sorted(years):
            s = stat(years[y])
            if s and s["n"] >= 20:
                tot += 1
                better += (s["win"] > sb["win"])
        print(f"      해마다 갈라 보면 {tot}년 중 {better}년만 기준선보다 나았다")

# ── 갈래 2 — 낙폭 종목 ──────────────────────────────────────────────
BANDS = [(-0.10, 0.00, "-0~-10%"), (-0.20, -0.10, "-10~-20%"),
         (-0.30, -0.20, "-20~-30%"), (-0.40, -0.30, "-30~-40%"),
         (-0.50, -0.40, "-40~-50%"), (-1.00, -0.50, "-50% 아래")]


def band_table(days, title):
    print("\n" + "-" * 100)
    print(title)
    print("-" * 100)
    for hold in (20, 60, 120):
        print(f"\n▶ {hold}거래일 보유")
        buckets = {b[2]: [] for b in BANDS}
        allrs = []
        for c, m in M.items():
            p, fh = POS[c], m["from_high"].values
            for d in days:
                i = p.get(d)
                if i is None or not np.isfinite(fh[i]):
                    continue
                r = fwd_return(m, i, hold)
                if r is None:
                    continue
                allrs.append(r)
                for lo, hi, name in BANDS:
                    if lo <= fh[i] < hi:
                        buckets[name].append(r)
                        break
        print(line("기준선(그날 아무 종목이나)", stat(allrs)))
        for _, _, name in BANDS:
            print(line(name, stat(buckets[name])))
        # 설명서가 말하는 묶음끼리
        wide = buckets["-10~-20%"] + buckets["-20~-30%"]
        deep = buckets["-30~-40%"] + buckets["-40~-50%"]
        print(line("  ▶ 설명서가 말한 -10~-30%", stat(wide)))
        print(line("  ▶ 지금 코드가 쓰는 -30~-50%", stat(deep)))


band_table(CRASH_DAYS, f"갈래 2 — 급락 후 반등장 · 미국과 같은 자({len(CRASH_DAYS)}일)")
band_table(FIRST_REBOUND, f"갈래 2 — 급락 국면 첫 반등일만({len(FIRST_REBOUND)}번) · 지금 앱의 자")

# ── 미국과 무엇이 다른가 ────────────────────────────────────────────
print("\n" + "=" * 100)
print("코스피는 미국과 무엇이 다른가 — 바탕값")
print("=" * 100)
for hold in (20, 60, 120):
    rs = []
    for c, m in M.items():
        for i in range(251, len(m) - hold - 1):
            if not np.isfinite(m["hi252"].iat[i]):
                continue
            r = fwd_return(m, i, hold)
            if r is not None:
                rs.append(r)
    print(line(f"아무 날·아무 종목 · {hold}일 (전체기간)", stat(rs)))

nh_rate = np.mean([m["is_new_high"].loc[m["hi252"].notna()].mean() for m in M.values()]) * 100
fh_med = np.median(np.concatenate([m["from_high"].dropna().values for m in M.values()])) * 100
print(f"\n  52주 신고가가 나는 날의 비율   {nh_rate:5.2f}%")
print(f"  고점 대비 위치의 가운데 값     {fh_med:+6.2f}%")
print(f"  코스피가 200일선 위인 날 비율  {up_regime.mean()*100:5.1f}%")
kn = KM["is_new_high"].loc[KM["hi252"].notna()]
print(f"  코스피 지수가 신고가인 날 비율 {kn.mean()*100:5.2f}%")
