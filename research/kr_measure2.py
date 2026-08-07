"""상하님이 짚은 두 가지를 잰다 (2026-08-07).

**① 시가총액도 봐야 하지 않나** — 거래대금 500억은 시총이 작아도 걸린다. 테마가
   붙어 하루 폭발하면 잡주도 500억을 넘긴다. 시총 문턱을 같이 두면 걸러지는지 본다.
   시총 = **수정주가 × 오늘 상장주식수**. 액면분할이 이미 반영된 주가라 오늘 주식
   수를 곱하면 과거까지 일관된 값이 된다(유상증자만큼은 어긋난다).

**② 테마 동반을 어떻게 할 것인가** — 지금 방식은 **오늘의 테마 명부**로 12년 전을
   본다. 그때 그 종목이 그 테마였는지 알 수 없다(네이버가 과거 구성을 안 준다).
   그래서 테마 이름이 필요 없는 두 가지와 나란히 재 본다.
     ⓐ 같은 테마 동반 — 지금 방식(앞을 훔쳐볼 위험 있음)
     ⓑ 같이 움직이는 무리 — 신호 **직전 120일** 수익률 상관이 0.5 넘는 종목 중
        그날 같이 걸린 수. 그날까지의 시세만 쓰므로 훔쳐볼 것이 없다.
     ⓒ 그날 전체 동반 — 테마도 상관도 안 보고, 그날 명부 전체에서 몇 종목이
        같이 걸렸나. 가장 단순하다.
   ⓑ나 ⓒ가 ⓐ만큼 값을 하면 테마 명부 없이 갈 수 있다.

쓰는 법:  python research/kr_measure2.py cap      # 시가총액
          python research/kr_measure2.py together # 동반 세 가지
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from kr_measure import (CACHE, DAILY, ROSTER, forward_returns, line,  # noqa: E402
                        load_wide, summarise)

SHARES = CACHE.parent / "shares.csv"
CORR_WINDOW = 120     # 상관을 재는 창 (약 6개월)
CORR_EVERY = 21       # 한 달에 한 번 다시 잰다
CORR_LEVEL = 0.5      # 이보다 높으면 '같이 움직이는' 것으로 본다


def fetch_shares() -> None:
    """오늘 상장주식수를 받아 둔다."""
    import FinanceDataReader as fdr

    listing = fdr.StockListing("KRX")[["Code", "Stocks"]]
    listing.to_csv(SHARES, index=False)
    print(f"{len(listing):,}종목 -> {SHARES}")


def _signals(wide: dict[str, pd.DataFrame]):
    """상승 그물과 급락 그물을 만든다 (kr_measure와 같은 정의)."""
    close, high = wide["close"], wide["high"]
    dates = close.index
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    up = (days_since >= 1) & (days_since <= 10) & (from_peak <= -4.0) & (from_peak >= -6.0)

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_drop = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_drop <= -10.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    stock_drop = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    down = deep & (stock_drop <= -40.0) & (stock_drop >= -50.0)
    return up, down


# ── ① 시가총액 ─────────────────────────────────────────────────────────
def cap() -> None:
    if not SHARES.exists():
        fetch_shares()
    wide = load_wide()
    close = wide["close"]
    dates = close.index
    split = len(dates) // 2
    shares = pd.read_csv(SHARES, dtype={"Code": str}).set_index("Code")["Stocks"]
    shares = shares.reindex(close.columns)
    missing = int(shares.isna().sum())
    marcap = close.mul(shares, axis=1) / 1e8  # 억원
    value = (close * wide["volume"]).rolling(50, min_periods=20).mean() / 1e8
    up, down = _signals(wide)
    print(f"상장주식수 없는 종목 {missing}개는 시총 칸에서 빠진다\n")

    for title, signal, hold, floor in (
        ("상승장 (신고가 눌림 · 120거래일)", up, 120, 50),
        ("급락 후 반등장 (코스피 -10% 가장깊은날 · -40~-50% · 60거래일)", down, 60, 10),
    ):
        returns = forward_returns(wide, hold)
        print(f"\n{'=' * 96}\n### {title}\n{'=' * 96}")
        print("\n-- 시가총액만으로 갈라 보기 --")
        for label, low, high_cap in (("1,000억 미만", 0, 1000), ("1,000~3,000억", 1000, 3000),
                                     ("3,000억~1조", 3000, 10000), ("1조 이상", 10000, 9e9)):
            pool = (marcap > low) & (marcap <= high_cap)
            result = summarise(returns, signal & pool, dates, split, pool=pool)
            if result.get("전체") and result["전체"]["n"] >= 50:
                print(line(label, result))
        print(f"\n-- 거래대금 {floor}억↑ 안에서 시가총액으로 다시 갈라 보기 --")
        for label, low, high_cap in (("1,000억 미만", 0, 1000), ("1,000~3,000억", 1000, 3000),
                                     ("3,000억~1조", 3000, 10000), ("1조 이상", 10000, 9e9)):
            pool = (value >= floor) & (marcap > low) & (marcap <= high_cap)
            result = summarise(returns, signal & pool, dates, split, pool=pool)
            if result.get("전체") and result["전체"]["n"] >= 50:
                print(line(label, result))
        print("\n-- 두 문턱을 같이 걸면 (거래대금 500억↑ · 시총) --")
        for label, low in (("시총 문턱 없음", 0), ("시총 1,000억↑", 1000),
                           ("시총 3,000억↑", 3000), ("시총 1조↑", 10000)):
            pool = (value >= 500) & (marcap >= low)
            result = summarise(returns, signal & pool, dates, split, pool=pool)
            if result.get("전체") and result["전체"]["n"] >= 50:
                print(line(label, result))


# ── ② 동반 세 가지 ─────────────────────────────────────────────────────
def _corr_groups(close: pd.DataFrame) -> dict[int, np.ndarray]:
    """한 달에 한 번, 직전 120일 수익률 상관을 잰다. **그날까지의 시세만 쓴다.**"""
    returns = close.pct_change().to_numpy(dtype="float32")
    out: dict[int, np.ndarray] = {}
    for end in range(CORR_WINDOW, returns.shape[0] + 1, CORR_EVERY):
        window = returns[end - CORR_WINDOW:end]
        valid = np.isfinite(window)
        filled = np.where(valid, window, 0.0)
        counts = valid.sum(axis=0)
        mean = filled.sum(axis=0) / np.maximum(counts, 1)
        centred = np.where(valid, window - mean, 0.0)
        cov = centred.T @ centred
        deviation = np.sqrt(np.diag(cov))
        deviation[deviation == 0] = np.nan
        matrix = cov / np.outer(deviation, deviation)
        matrix[counts < 60, :] = np.nan
        matrix[:, counts < 60] = np.nan
        out[end] = (matrix >= CORR_LEVEL)
    return out


def together() -> None:
    wide = load_wide()
    close = wide["close"]
    dates = close.index
    split = len(dates) // 2
    value = (close * wide["volume"]).rolling(50, min_periods=20).mean() / 1e8
    up, down = _signals(wide)
    columns = list(close.columns)
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"]
    themes_of = {code: set(entry["themes"]) for code, entry in roster.items()}

    print("상관 표를 만드는 중...", flush=True)
    groups = _corr_groups(close)
    ends = np.array(sorted(groups))
    print(f"  {len(groups)}장 (한 달에 한 번 · 직전 {CORR_WINDOW}일 · 상관 {CORR_LEVEL} 이상)\n")

    for title, signal, hold, floor in (
        ("상승장 (신고가 눌림 · 거래대금 50억↑ · 120거래일)", up, 120, 50),
        ("급락 후 반등장 (코스피 -10% · -40~-50% · 거래대금 10억↑ · 60거래일)", down, 60, 10),
    ):
        pool = value >= floor
        mask = signal & pool
        array = mask.to_numpy()
        theme_count = np.zeros(array.shape, dtype="int16")
        move_count = np.zeros(array.shape, dtype="int16")
        all_count = np.zeros(array.shape, dtype="int16")
        for row in np.nonzero(array.any(axis=1))[0]:
            picked = np.nonzero(array[row])[0]
            all_count[row, picked] = len(picked)
            codes = [columns[i] for i in picked]
            counts: dict[str, int] = {}
            for code in codes:
                for theme in themes_of.get(code, ()):
                    counts[theme] = counts.get(theme, 0) + 1
            theme_count[row, picked] = [
                max((counts[t] for t in themes_of.get(code, ()) if t in counts), default=1)
                for code in codes
            ]
            position = ends[np.searchsorted(ends, row + 1) - 1] if row + 1 >= ends[0] else None
            if position is not None:
                block = groups[position][np.ix_(picked, picked)]
                move_count[row, picked] = np.nan_to_num(block).sum(axis=1)
        frames = {
            "ⓐ 같은 테마 동반": pd.DataFrame(theme_count, index=dates, columns=close.columns),
            "ⓑ 같이 움직이는 무리": pd.DataFrame(move_count, index=dates, columns=close.columns),
            "ⓒ 그날 전체 동반": pd.DataFrame(all_count, index=dates, columns=close.columns),
        }
        returns = forward_returns(wide, hold)
        print(f"\n{'=' * 96}\n### {title}\n{'=' * 96}")
        print(line("그물 전체", summarise(returns, mask, dates, split, pool=pool)))
        for name, table in frames.items():
            print(f"\n-- {name} --")
            buckets = ((("1개(혼자)", 0.5, 1.5), ("2개", 1.5, 2.5), ("3개", 2.5, 3.5),
                        ("4~9개", 3.5, 9.5), ("10개↑", 9.5, 9999))
                       if name != "ⓒ 그날 전체 동반" else
                       (("1~5개", 0.5, 5.5), ("6~15개", 5.5, 15.5), ("16~40개", 15.5, 40.5),
                        ("41개↑", 40.5, 9999)))
            for label, low, high_bucket in buckets:
                picked = mask & (table > low) & (table <= high_bucket)
                result = summarise(returns, picked, dates, split, pool=pool)
                if result.get("전체") and result["전체"]["n"] >= 50:
                    print(line(label, result))


# ── ③ 해마다 갈라 보기 ─────────────────────────────────────────────────
def yearly() -> None:
    """**자르는 날 하나에 기대지 않는다** (2026-08-07 상하님 지적).

    앞 6년·뒤 6년으로 가른 자리가 하필 코로나 폭락(2020-03) 바로 뒤였다. 바닥에서
    자르면 뒤쪽은 뭘 해도 좋아 보인다. 그래서 **해마다** 다시 재서, 좋은 해에만
    통한 것인지 12년 내내 통한 것인지 본다.

    숫자는 그해 '규칙'과 '그날 같은 울타리에서 아무 종목이나'의 차이(%p)다.
    """
    wide = load_wide()
    close = wide["close"]
    dates = close.index
    value = (close * wide["volume"]).rolling(50, min_periods=20).mean() / 1e8
    up, down = _signals(wide)
    columns = list(close.columns)

    groups = _corr_groups(close)
    ends = np.array(sorted(groups))
    move_count = np.zeros(up.shape, dtype="int16")
    array = (up & (value >= 50)).to_numpy()
    for row in np.nonzero(array.any(axis=1))[0]:
        picked = np.nonzero(array[row])[0]
        if row + 1 < ends[0]:
            continue
        position = ends[np.searchsorted(ends, row + 1) - 1]
        block = groups[position][np.ix_(picked, picked)]
        move_count[row, picked] = np.nan_to_num(block).sum(axis=1)
    moves = pd.DataFrame(move_count, index=dates, columns=close.columns)

    cases = (
        ("상승장 · 거래대금 500억↑", up & (value >= 500), value >= 500, 120),
        ("상승장 · 같이 움직이는 무리 4개↑", up & (value >= 50) & (moves >= 4),
         value >= 50, 120),
        ("급락 후 반등장 · -40~-50% 낙폭", down & (value >= 10), value >= 10, 60),
    )
    years = sorted({date.year for date in dates})
    print(f"{'':34}" + "".join(f"{year:>7}" for year in years))
    for title, mask, pool, hold in cases:
        returns = forward_returns(wide, hold)
        cells, wins, total = [], 0, 0
        for year in years:
            window = np.array([date.year == year for date in dates])
            picked = returns[window].where(mask[window])
            values = picked.to_numpy().ravel()
            values = values[~np.isnan(values)]
            if values.size < 20:
                cells.append("     ·")
                continue
            active = mask[window].any(axis=1).to_numpy()
            base = returns[window].where(pool[window])[active].to_numpy().ravel()
            base = base[~np.isnan(base)]
            edge = (values > 0).mean() * 100 - (base > 0).mean() * 100
            cells.append(f"{edge:+7.1f}")
            total += 1
            wins += edge > 0
        print(f"{title:<34}" + "".join(cells) + f"   → {wins}/{total}년 이김")
    print("\n· = 그해 자리가 20개 미만이라 재지 않음")


if __name__ == "__main__":
    {"shares": fetch_shares, "cap": cap, "together": together,
     "yearly": yearly}[sys.argv[1]]()
