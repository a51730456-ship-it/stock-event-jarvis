"""kr_daily_full(상장폐지 포함 3,367종목)을 날짜×종목 표로 묶는다 (2026-09-30, 자비스10 연구용).

빼는 것: 스팩·리츠·선박투자·인프라·우선주(이름 끝 '우'·'우B'…) — 회사 주식이 아니거나 따로 노는 것.
기간: 2014-07-09(지금 상장 종목 네이버 3,000줄의 시작) ~ 2026-09-30.
결과: research/_data/wide_full/{open,high,low,close,volume}.parquet · meta.csv
      코스피 지수는 research/_data/kospi_yahoo_19961211_20260930.csv 에서 같은 날짜로 맞춘다.
"""
from __future__ import annotations

import pathlib
import re

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "_data"
SRC = DATA / "kr_daily_full"
OUT = DATA / "wide_full"
START = "2014-07-09"

_NOT_COMMON = ("스팩", "SPAC", "리츠", "선박", "인프라", "기업인수목적")
_PREF = re.compile(r"(\d?우[A-C]?|\(전환\))$")


def excluded(name: str) -> bool:
    return any(t in name for t in _NOT_COMMON) or bool(_PREF.search(name))


def main() -> None:
    uni = pd.read_csv(DATA / "kr_universe_20260930.csv", dtype={"code": str}).drop_duplicates("code")
    uni = uni[~uni["name"].map(excluded)]
    frames = {k: {} for k in ("open", "high", "low", "close", "volume")}
    for code in uni["code"]:
        p = SRC / f"{code}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype={"date": str})
        if df.empty:
            continue
        df.index = pd.to_datetime(df["date"], format="%Y%m%d")
        df = df.loc[START:]
        if df.empty:
            continue
        for k in frames:
            frames[k][code] = df[k].astype(float)
    OUT.mkdir(parents=True, exist_ok=True)
    kospi = pd.read_csv(DATA / "kospi_yahoo_19961211_20260930.csv", header=[0, 1], index_col=0, parse_dates=True)
    kospi.columns = [c[0] for c in kospi.columns]
    for k, cols in frames.items():
        wide = pd.DataFrame(cols).sort_index()
        # 거래 없는 날(거래정지)은 네이버가 줄을 안 주거나 거래량 0 — 값은 비워 둔다(0으로 안 채운다)
        wide.to_parquet(OUT / f"{k}.parquet")
    idx = pd.DataFrame(frames["close"]).sort_index().index
    kospi.reindex(idx).to_parquet(OUT / "kospi.parquet")
    meta = uni[uni["code"].isin(frames["close"])].copy()
    meta.to_csv(OUT / "meta.csv", index=False, encoding="utf-8-sig")
    print(f"종목 {len(frames['close'])} (상장 {int((meta.status == 'listed').sum())} · 폐지 {int((meta.status == 'delisted').sum())}) · 날짜 {len(idx)} ({idx[0].date()} ~ {idx[-1].date()})")


if __name__ == "__main__":
    main()
