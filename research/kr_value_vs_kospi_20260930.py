"""'싼 종목'은 코스피를 이기나 — 상장폐지 포함 · 그때 공시된 실적만 (2026-09-30, 자비스10).

재료
  주가(수정): research/_data/wide_full (네이버, 상장폐지 포함 3,011종목)
  시가총액: research/_data/marcap (FinanceData/marcap — 날짜별 시가총액·주식 수, 폐지 종목 포함)
  실적: research/_data/dart_fundamentals_2015_2025.csv (사업보고서 · 공시 접수일 다음 날부터 사용)
싼 정도(클수록 쌈): 장부가/시총 · 영업이익/시총 · 매출/시총 · 셋을 합친 등수
사는 때 다음 날 시가 · 파는 때 40·60·250거래일 뒤 종가(그 전에 폐지되면 마지막 가격) · 같은 기간 코스피와 견줌
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_baseline_full_20260930 import forward, load  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent / "_data"
SPLIT = pd.Timestamp("2021-01-01")
STALE_DAYS = 460          # 사업보고서가 이보다 오래되면(다음 해 보고서가 없으면) 안 쓴다


def marcap_wide(codes, dates) -> pd.DataFrame:
    parts = []
    for y in range(2014, 2027):
        p = DATA / "marcap" / f"marcap-{y}.parquet"
        m = pd.read_parquet(p, columns=["Code", "Date", "Marcap"])
        parts.append(m[m["Code"].isin(codes)])
    m = pd.concat(parts)
    w = m.pivot_table(index="Date", columns="Code", values="Marcap", aggfunc="last")
    return w.reindex(index=dates, columns=codes).ffill(limit=5) / 1e8   # 억 원


def fundamentals(codes, dates) -> dict[str, pd.DataFrame]:
    f = pd.read_csv(DATA / "dart_fundamentals_2015_2025.csv", dtype={"stock_code": str, "rcept_no": str})
    f = f[f["stock_code"].isin(codes)]
    # 연결(CFS) 우선, 없으면 별도(OFS)
    f["pri"] = (f["fs_div"] == "CFS").astype(int)
    f = f.sort_values("pri").drop_duplicates(["stock_code", "year", "account"], keep="last")
    f["avail"] = pd.to_datetime(f["rcept_no"].str[:8], format="%Y%m%d", errors="coerce") + pd.Timedelta(days=1)
    out = {}
    idx = pd.DatetimeIndex(dates)
    for acc in ("equity", "op_income", "sales", "liabilities"):
        a = f[f["account"] == acc].dropna(subset=["avail"]).sort_values("avail")
        cols = {}
        for code, g in a.groupby("stock_code"):
            s = g.drop_duplicates("avail", keep="last").set_index("avail")["amount"]
            pos = s.index.searchsorted(idx, side="right") - 1
            val = np.where(pos >= 0, s.to_numpy()[np.clip(pos, 0, None)], np.nan)
            age = np.where(pos >= 0, (idx - s.index[np.clip(pos, 0, None)]).days, 99999)
            val[age > STALE_DAYS] = np.nan
            cols[code] = val
        out[acc] = pd.DataFrame(cols, index=idx).reindex(columns=codes) / 1e8   # 억 원
    return out


def pct_rank(df, uni, ascending=False):
    return df.where(uni).rank(axis=1, pct=True, ascending=ascending)


def main() -> None:
    px, kospi, meta = load()
    close, vol = px["close"], px["volume"]
    codes = list(close.columns)
    dates = close.index
    mc = marcap_wide(codes, dates)
    fu = fundamentals(codes, dates)
    print(f"시가총액 있는 칸 {mc.notna().to_numpy().mean()*100:.0f}% · 자본 있는 칸 {fu['equity'].notna().to_numpy().mean()*100:.0f}%")

    ret = close.pct_change(fill_method=None)
    value = close * vol / 1e8
    value20 = value.rolling(20, min_periods=10).mean()
    history = close.notna().cumsum() >= 250
    base = (value20 >= 10) & (vol > 0) & history & mc.notna() & fu["equity"].notna()
    bad = ((pct_rank(ret.rolling(60, min_periods=50).std(), base) <= 0.4)
           | (pct_rank(ret.rolling(20, min_periods=15).max(), base) <= 0.4)
           | (pct_rank(close / close.shift(20) - 1, base) <= 0.2)
           | (pct_rank(value.rolling(5).mean() / value.rolling(60, min_periods=40).mean(), base) <= 0.2))
    clean = base & ~bad

    bp = fu["equity"] / mc
    op = fu["op_income"] / mc
    sp = fu["sales"] / mc
    combo = (pct_rank(bp, base) + pct_rank(op, base) + pct_rank(sp, base)) / 3   # 작을수록 쌈 (순이익은 첫 받기에서 빠져 영업이익으로 대신)
    profit = (fu["op_income"] > 0) & (fu["equity"] > 0)
    size_rank = pct_rank(mc, base)            # 0에 가까울수록 큰 회사
    small = size_rank >= 0.7                  # 울타리 안 작은 30%
    cheap = pct_rank(combo, base, ascending=True) <= 0.2

    factors = {"장부가/시총": bp, "영업이익/시총": op, "매출/시총": sp, "셋 합친 싼 정도": -combo}
    rules = [
        ("아무 종목 (실적·시총 있는 10억↑)", base),
        ("싼 20% (셋 합친 등수)", base & cheap),
        ("싼 20% + 영업흑자", base & cheap & profit),
        ("싼 20% + 영업흑자 + 빼기 통과", clean & cheap & profit),
        ("싼 20% + 영업흑자 + 작은 회사 30%", base & cheap & profit & small),
        ("싼 20% + 영업흑자 + 작은 회사 + 빼기 통과", clean & cheap & profit & small),
        ("싼 20% + 영업흑자 + 큰 회사 30%", base & cheap & profit & (size_rank <= 0.3)),
    ]
    k = kospi["Close"]
    for hold in (60, 250):
        fwd, kf = forward(px, kospi, hold)
        F, KF = fwd.to_numpy(), kf.to_numpy()
        print(f"\n######## {hold}거래일 보유 ########")
        U = base.to_numpy()
        for name, fac in factors.items():
            A = fac.to_numpy()
            meds = {g: [] for g in range(5)}
            for row in range(260, len(dates) - hold - 1, 5):
                sel = U[row] & np.isfinite(A[row]) & np.isfinite(F[row])
                if sel.sum() < 100:
                    continue
                r = pd.Series(A[row][sel]).rank(pct=True, ascending=False).to_numpy()
                q = np.minimum((r * 5).astype(int), 4)
                for g in range(5):
                    meds[g].append(np.median(F[row][sel][q == g]))
            print(f"  [{name}] 1=가장 쌈 → 가운데: " + " · ".join(f"{g+1}무리 {np.median(meds[g]):+5.1f}%" for g in range(5)))
        for name, mask in rules:
            M = mask.fillna(False).to_numpy()
            ups = beats = cnt = 0
            port, kos, pbeat, pa, pb = [], [], [], [], []
            for row in range(260, len(dates) - hold - 1, 5):
                sel = M[row] & np.isfinite(F[row])
                if sel.sum() < 3 or np.isnan(KF[row]):
                    continue
                f = np.clip(F[row][sel], -100, 300)      # 한 종목이 묶음을 좌우하지 않게 +300% 에서 자른다
                cnt += len(f)
                ups += (f > 0).sum()
                beats += (f > KF[row]).sum()
                port.append(f.mean())
                kos.append(KF[row])
                pbeat.append(f.mean() > KF[row])
                (pa if dates[row] < SPLIT else pb).append(f.mean() - KF[row])
            if not port:
                print(f"  {name}: 없음")
                continue
            print(f"  {name}\n      종목 {cnt:,}건 · 오름 {ups/cnt*100:4.1f}번 · 코스피 이김 {beats/cnt*100:4.1f}번 ‖ 목록 {len(port)}날 · "
                  f"묶음이 코스피 이긴 날 {np.mean(pbeat)*100:4.1f}% · 묶음 평균 {np.mean(port):+5.1f}% vs 코스피 {np.mean(kos):+5.1f}% "
                  f"· 코스피보다 (앞 {np.mean(pa) if pa else float('nan'):+5.1f} · 뒤 {np.mean(pb) if pb else float('nan'):+5.1f}) · 평균 {cnt/len(port):.0f}종목")


if __name__ == "__main__":
    main()
