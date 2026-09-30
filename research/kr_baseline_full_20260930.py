"""아무 종목이나 두세 달 들면 — 상장폐지 종목을 넣으면 얼마나 달라지나 (2026-09-30, 자비스10 연구용).

사는 때: 신호 다음 거래일 시가 · 파는 때: N거래일 뒤 종가 (그 전에 폐지되면 마지막 거래 가격 — 정리매매 포함)
견줄 것: 같은 기간 코스피(다음 날 시가 → N일 뒤 종가)
울타리: 20일 평균 거래대금 ≥ 문턱 · 그날 거래가 있던 종목
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
W = ROOT / "research" / "_data" / "wide_full"
STEP = 5


def load():
    px = {k: pd.read_parquet(W / f"{k}.parquet") for k in ("open", "close", "volume")}
    kospi = pd.read_parquet(W / "kospi.parquet")
    meta = pd.read_csv(W / "meta.csv", dtype={"code": str}).set_index("code")
    return px, kospi, meta


def forward(px, kospi, hold):
    close_ff = px["close"].ffill()                     # 폐지 뒤엔 마지막 거래 가격이 남는다
    entry = px["open"].shift(-1)
    entry = entry.where(entry > 0)                    # 거래정지 다음 날은 시가가 0으로 온다 — 못 산다
    fwd = close_ff.shift(-hold) / entry - 1
    kf = kospi["Close"].shift(-hold) / kospi["Open"].shift(-1) - 1
    # 끝에서 hold 일 안 남은 날은 쓰지 않는다
    fwd.iloc[-hold - 1:] = np.nan
    return fwd * 100, kf * 100


def main() -> None:
    px, kospi, meta = load()
    value = (px["close"] * px["volume"]).rolling(20, min_periods=10).mean() / 1e8
    traded = px["volume"] > 0
    listed_now = meta["status"].eq("listed").reindex(px["close"].columns).fillna(False).to_numpy()
    is_kosdaq = meta["market"].eq("KOSDAQ").reindex(px["close"].columns).fillna(False).to_numpy()
    print(f"종목 {px['close'].shape[1]} · 폐지 {int((~listed_now).sum())}")
    for hold in (40, 60, 250):
        fwd, kf = forward(px, kospi, hold)
        print(f"\n### {hold}거래일 보유 (다음 날 시가 → {hold}일 뒤 종가)")
        for floor in (10, 50):
            uni = (value >= floor) & traded
            for label, mask in (("살아남은 종목만", listed_now), ("폐지 종목까지", np.ones_like(listed_now, bool)),
                                ("  └ 코스피 종목", ~is_kosdaq), ("  └ 코스닥 종목", is_kosdaq)):
                ups, beats, meds, n = [], [], [], 0
                for row in range(260, len(fwd) - hold - 1, STEP):
                    sel = uni.iloc[row].to_numpy() & mask
                    f = fwd.iloc[row].to_numpy()[sel]
                    f = f[~np.isnan(f)]
                    if len(f) < 30 or np.isnan(kf.iloc[row]):
                        continue
                    ups.append((f > 0).mean() * 100)
                    beats.append((f > kf.iloc[row]).mean() * 100)
                    meds.append(np.median(f))
                    n += len(f)
                print(f"  거래대금 {floor:>2}억↑ · {label:<10} 오름 {np.mean(ups):4.1f}번 · 코스피 이김 {np.mean(beats):4.1f}번 · "
                      f"가운데 {np.median(meds):+6.1f}%  ({len(meds)}날 · {n:,}건)")
        # 보유 중 폐지된 비율
        close = px["close"]
        last_day = close.apply(lambda s: s.last_valid_index())
        dead = pd.Series(~listed_now, index=close.columns)
        gone = []
        for row in range(260, len(close) - hold - 1, STEP):
            d0, d1 = close.index[row], close.index[row + hold]
            sel = ((value.iloc[row] >= 10) & traded.iloc[row]).to_numpy()
            codes = close.columns[sel]
            gone.append((dead[codes] & (last_day[codes] <= d1)).mean() * 100)
        print(f"  보유 중에 상장폐지된 종목: 100개 중 {np.mean(gone):.2f}개 (거래대금 10억↑)")


if __name__ == "__main__":
    main()
