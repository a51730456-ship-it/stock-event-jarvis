"""한국 두 갈래를 미국과 **같은 잣대**로 다시 잰다 (2026-08-07).

**왜 다시 재나.** 지금 화면(자비스4)의 배점은 2026-08-01에 정한 것인데,
  ① 12년을 **통째로 한 번** 쟀다 — 미국은 2026-08-06에 기간을 반으로 갈라
     **양쪽에서 다 이긴 것만** 점수를 주도록 바꿨다. 한쪽 시기에만 통한 값을
     순위 맨 앞에 두면 화면이 그 시기에만 맞는 자리를 1등으로 올린다.
  ② **시총 상위 197종목**으로 쟀다 — 화면이 실제로 뒤지는 것은 네이버 테마
     266개의 2,272종목이다. 미국에서 같은 어긋남을 고치자 결론이 뒤집혔다
     (낙폭 배점 25점 → 15점).

**앞을 훔쳐보지 않는다.** 신호를 만드는 값은 모두 그날까지의 것이고, 사는 값은
다음 거래일 시가, 파는 값은 정해진 거래일 뒤 종가다.

쓰는 법:
    python research/kr_measure.py load     # 시세를 넓은 표로 묶어 저장(한 번만)
    python research/kr_measure.py breakout # 상승 그물 격자
    python research/kr_measure.py crash    # 급락 그물 격자
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAILY = ROOT / "research" / "_data" / "kr_daily"
CACHE = ROOT / "research" / "_data" / "wide"
ROSTER = ROOT / "data" / "kr_roster.json"

HOLDS = (20, 60, 120)
# 지수는 종목이 아니다. 명부에서 빼고 '시장이 얼마나 빠졌나'에만 쓴다.
INDEX_SYMBOLS = ("KOSPI", "KOSDAQ")
# 네이버는 한 번에 3,000**거래일**을 준다. 거래정지가 잦은 종목은 그 3,000줄이
# 2007년까지 뻗어서, 그냥 합치면 날짜 축이 4,727일이 되고 그 앞쪽에는 종목이
# 몇 개밖에 없다. 지수(코스피)가 시작하는 날부터만 본다 — 여기부터 거의 모든
# 종목에 자료가 있다.
START = "2014-05-19"


# ── 1단계 · 시세를 넓은 표로 묶는다 ──────────────────────────────────────
def build_wide() -> None:
    """종목 2,272개 CSV를 '날짜 × 종목' 표 다섯 장으로 묶어 저장한다.

    이렇게 두면 rolling·기준선 계산이 한 번에 돌아간다. 종목마다 따로 돌리면
    같은 계산을 2,272번 반복하게 된다.
    """
    frames: dict[str, dict[str, pd.Series]] = {
        key: {} for key in ("open", "high", "low", "close", "volume")
    }
    files = sorted(DAILY.glob("*.csv"))
    for index, path in enumerate(files, 1):
        code = path.stem
        table = pd.read_csv(path)
        if table.empty:
            continue
        table["date"] = pd.to_datetime(table["date"], format="%Y%m%d")
        table = table.drop_duplicates("date").set_index("date").sort_index()
        for key in frames:
            frames[key][code] = table[key].astype("float32")
        if index % 500 == 0:
            print(f"  {index}/{len(files)}", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    dates = None
    for key, columns in frames.items():
        wide = pd.DataFrame(columns).sort_index()
        wide = wide.loc[wide.index >= START]
        wide.to_parquet(CACHE / f"{key}.parquet")
        dates = wide.index
        stocks = [c for c in wide.columns if c not in INDEX_SYMBOLS]
        print(f"{key}: {wide.shape[0]}일 × {len(stocks)}종목(+지수 {len(wide.columns) - len(stocks)})")
    have = pd.read_parquet(CACHE / "close.parquet").notna().sum(axis=1)
    print(f"기간 {dates[0].date()} ~ {dates[-1].date()} · {len(dates)}거래일")
    print(f"자료 있는 종목 수 — 첫날 {have.iloc[0]}개 · 마지막날 {have.iloc[-1]}개")
    print(f"가르는 날 {dates[len(dates) // 2].date()}")


def load_wide() -> dict[str, pd.DataFrame]:
    wide = {key: pd.read_parquet(CACHE / f"{key}.parquet")
            for key in ("open", "high", "low", "close", "volume")}
    stocks = [c for c in wide["close"].columns if c not in INDEX_SYMBOLS]
    return {key: frame[stocks] for key, frame in wide.items()}


# ── 2단계 · 성적표 ──────────────────────────────────────────────────────
def forward_returns(wide: dict[str, pd.DataFrame], hold: int) -> pd.DataFrame:
    """신호가 난 날 기준 성적. 다음 거래일 **시가**에 사서 hold거래일 뒤 **종가**에 판다."""
    buy = wide["open"].shift(-1)
    sell = wide["close"].shift(-hold)
    return (sell / buy - 1.0) * 100.0


def summarise(returns: pd.DataFrame, mask: pd.DataFrame, dates: pd.DatetimeIndex,
              split: int, pool: pd.DataFrame | None = None) -> dict:
    """고른 자리의 성적과, **같은 날 아무 종목이나** 샀을 때의 기준선을 같이 낸다.

    살아남은 종목만 보고 재면 성적이 좋게 나온다. 그 치우침은 기준선에도 똑같이
    걸리므로 **그 차이**로만 값을 했는지 알 수 있다.

    **pool은 반드시 신호와 같은 울타리여야 한다**(2026-08-07에 실제로 틀렸다).
    거래대금 500억 이상으로 신호를 걸러 놓고 기준선은 2,272종목 전부로 뒀더니
    '규칙이 좋다'가 아니라 '큰 종목이 작은 종목보다 낫다'를 재고 있었다.
    같은 울타리 안에서 비교해야 규칙이 값을 했는지 알 수 있다.
    """
    out = {}
    for label, lo, hi in (("전체", 0, len(dates)), ("앞", 0, split), ("뒤", split, len(dates))):
        window = slice(lo, hi)
        picked = returns.iloc[window].where(mask.iloc[window])
        values = picked.to_numpy().ravel()
        values = values[~np.isnan(values)]
        if values.size == 0:
            out[label] = None
            continue
        # 기준선 — 신호가 하나라도 난 날의, **같은 울타리 안 모든 종목** 성적
        active = mask.iloc[window].any(axis=1)
        window_returns = returns.iloc[window]
        if pool is not None:
            window_returns = window_returns.where(pool.iloc[window])
        base = window_returns[active.to_numpy()].to_numpy().ravel()
        base = base[~np.isnan(base)]
        out[label] = {
            "n": int(values.size),
            "win": float((values > 0).mean() * 100),
            "median": float(np.median(values)),
            "base_win": float((base > 0).mean() * 100) if base.size else float("nan"),
            "base_median": float(np.median(base)) if base.size else float("nan"),
            "days": int(active.sum()),
        }
        out[label]["edge_win"] = out[label]["win"] - out[label]["base_win"]
        out[label]["edge_median"] = out[label]["median"] - out[label]["base_median"]
    return out


def line(name: str, result: dict) -> str:
    parts = [f"{name:<26}"]
    for label in ("전체", "앞", "뒤"):
        item = result.get(label)
        if not item:
            parts.append(f"{label} —".ljust(28))
            continue
        parts.append(
            f"{label} {item['win']:5.1f}%({item['edge_win']:+5.1f}p) "
            f"중앙{item['median']:+6.1f}%({item['edge_median']:+5.1f}p) n={item['n']:>6,} "
        )
    return "".join(parts)


# ── 3단계 · 상승 그물 (신고가 눌림) ─────────────────────────────────────
def breakout_grid() -> None:
    wide = load_wide()
    close, high = wide["close"], wide["high"]
    dates = close.index
    split = len(dates) // 2

    # 52주(252거래일) 신고가 — 그날 고가가 지난 252일 고가의 최대를 넘은 날
    prior_max = high.rolling(252, min_periods=252).max().shift(1)
    is_new_high = high >= prior_max
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    last_high_at = order.where(is_new_high).ffill()
    peak = high.where(is_new_high).ffill()
    days_since = order - last_high_at
    from_peak = (close / peak - 1.0) * 100.0

    print("\n### 상승 그물 격자 — 신고가 뒤 며칠 × 눌린 폭 (120거래일 보유)\n")
    returns = forward_returns(wide, 120)
    for wait_max in (3, 5, 7, 10):
        for lo, hi in ((-6.0, -4.0), (-10.0, -4.0), (-15.0, -4.0),
                       (-15.0, -10.0), (-20.0, -10.0)):
            mask = ((days_since >= 1) & (days_since <= wait_max)
                    & (from_peak <= hi) & (from_peak >= lo))
            result = summarise(returns, mask, dates, split)
            print(line(f"1~{wait_max}일 · {hi:.0f}~{lo:.0f}%", result))


# ── 4단계 · 급락 그물 (낙폭 종목) ───────────────────────────────────────
def crash_grid() -> None:
    wide = load_wide()
    close = wide["close"]
    dates = close.index

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_from_high = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0

    high = wide["high"]
    stock_from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    split = len(dates) // 2

    print("\n### 급락 그물 — 코스피 문턱 × 신호 방식 × 종목 낙폭\n")
    for threshold in (-5.0, -8.0, -10.0, -15.0):
        in_band = kospi_from_high <= threshold
        # ① 첫 반등일 — 국면에 들어간 뒤 처음으로 종가가 오른 날(지금 한국 방식)
        episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
        up_day = kospi > kospi.shift(1)
        first_rebound = pd.Series(False, index=dates)
        for _, group in pd.DataFrame({"e": episode, "up": up_day}).dropna().groupby("e"):
            hits = group.index[group["up"].astype(bool)]
            if len(hits):
                first_rebound.loc[hits[0]] = True
        # ② 가장 깊은 날 — 그 국면에서 코스피가 가장 많이 빠진 날(미국 방식)
        deepest = pd.Series(False, index=dates)
        for _, group in pd.DataFrame({"e": episode, "d": kospi_from_high}).dropna().groupby("e"):
            deepest.loc[group["d"].idxmin()] = True

        for signal_name, signal in (("첫반등일", first_rebound), ("가장깊은날", deepest)):
            days = int(signal.sum())
            print(f"\n-- 코스피 {threshold:.0f}% 이하 · {signal_name} ({days}번) --")
            if days == 0:
                continue
            signal_wide = pd.DataFrame(
                np.repeat(signal.to_numpy()[:, None], close.shape[1], axis=1),
                index=dates, columns=close.columns)
            for hold in HOLDS:
                returns = forward_returns(wide, hold)
                for lo, hi in ((-30.0, -20.0), (-40.0, -30.0), (-50.0, -40.0), (-50.0, -20.0)):
                    mask = (signal_wide & (stock_from_high <= hi) & (stock_from_high >= lo))
                    result = summarise(returns, mask, dates, split)
                    if result.get("전체") and result["전체"]["n"] >= 30:
                        print(line(f"{hold}일 · {hi:.0f}~{lo:.0f}%", result))


# ── 5단계 · 거래대금으로 갈라 본다 ──────────────────────────────────────
def liquidity_split() -> None:
    """화면은 **거래대금 상위 8종목**만 보여준다. 그 몫에서도 같은 결론인가.

    명부 2,272종목에는 하루 몇억도 안 되는 종목이 잔뜩 있다. 그런 종목까지 넣어
    재면 '화면이 보여줄 리 없는 종목'의 성적이 결론을 흔든다. 그래서 그날의
    50일 평균 거래대금으로 갈라 다시 본다.
    """
    wide = load_wide()
    close, high = wide["close"], wide["high"]
    dates = close.index
    split = len(dates) // 2
    value = (close * wide["volume"]).rolling(50, min_periods=20).mean() / 1e8  # 억원

    prior_max = high.rolling(252, min_periods=252).max().shift(1)
    is_new_high = high >= prior_max
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    breakout = ((days_since >= 1) & (days_since <= 10)
                & (from_peak <= -4.0) & (from_peak >= -6.0))

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_from_high = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_from_high <= -10.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_from_high}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep_wide = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                             index=dates, columns=close.columns)
    stock_from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    crash = deep_wide & (stock_from_high <= -40.0) & (stock_from_high >= -50.0)

    tiers = (("전부", 0), ("10억↑", 10), ("50억↑", 50), ("100억↑", 100), ("500억↑", 500))
    for name, signal, hold in (("상승 그물 1~10일·-4~-6%", breakout, 120),
                               ("급락 그물 -10%·가장깊은날·-40~-50%", crash, 60)):
        print(f"\n### {name} · {hold}거래일 보유 — 거래대금으로 갈라 보기\n")
        returns = forward_returns(wide, hold)
        for label, floor in tiers:
            pool = value >= floor
            result = summarise(returns, signal & pool, dates, split, pool=pool)
            if result.get("전체"):
                print(line(f"{label:<8}", result))


# ── 6단계 · 배점 후보 ───────────────────────────────────────────────────
def _together_counts(mask: pd.DataFrame) -> pd.DataFrame:
    """같은 날 **같은 테마에서 몇 종목이 같이 걸렸나**.

    한 종목이 여러 테마에 속하므로, 그 종목이 속한 테마들 중 **가장 많이 걸린
    테마**의 수를 쓴다(미국 together_count와 같은 정의). 자기 자신을 포함한다.
    """
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"]
    themes_of = {code: set(entry["themes"]) for code, entry in roster.items()}
    out = pd.DataFrame(0, index=mask.index, columns=mask.columns, dtype="int16")
    columns = list(mask.columns)
    array = mask.to_numpy()
    for row in np.nonzero(array.any(axis=1))[0]:
        picked = [columns[i] for i in np.nonzero(array[row])[0]]
        counts: dict[str, int] = {}
        for code in picked:
            for theme in themes_of.get(code, ()):
                counts[theme] = counts.get(theme, 0) + 1
        out.iloc[row, [columns.index(c) for c in picked]] = [
            max((counts[t] for t in themes_of.get(code, ()) if t in counts), default=1)
            for code in picked
        ]
    return out


def _atr_ratio(wide: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """14일 변동성(ATR)을 주가로 나눈 값 — '얼마나 흔들리나'."""
    prev_close = wide["close"].shift(1)
    true_range = pd.concat([
        (wide["high"] - wide["low"]).stack(),
        (wide["high"] - prev_close).abs().stack(),
        (wide["low"] - prev_close).abs().stack(),
    ], axis=1).max(axis=1).unstack()
    return true_range.rolling(14, min_periods=10).mean() / wide["close"] * 100.0


def _streak(above: pd.DataFrame) -> pd.DataFrame:
    """며칠 **연속** 참인가. 거짓이 나오면 0으로 되돌아간다."""
    values = above.to_numpy(dtype="int16", na_value=0)
    out = np.zeros_like(values)
    for row in range(1, values.shape[0]):
        out[row] = np.where(values[row] > 0, out[row - 1] + 1, 0)
    return pd.DataFrame(out, index=above.index, columns=above.columns)


def factors() -> None:
    wide = load_wide()
    close, high = wide["close"], wide["high"]
    dates = close.index
    split = len(dates) // 2
    value = (close * wide["volume"]).rolling(50, min_periods=20).mean() / 1e8  # 억원

    prior_max = high.rolling(252, min_periods=252).max().shift(1)
    is_new_high = high >= prior_max
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()
    kospi_from_high = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_from_high <= -10.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_from_high}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep_wide = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                             index=dates, columns=close.columns)
    stock_from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0

    # 배점은 **그물 안에서** 잰다. 화면이 안 보여줄 종목으로 배점을 정하면 안 된다.
    up_pool = value >= 50
    up_mask = ((days_since >= 1) & (days_since <= 10)
               & (from_peak <= -4.0) & (from_peak >= -6.0) & up_pool)
    down_pool = value >= 10
    down_mask = (deep_wide & (stock_from_high <= -40.0) & (stock_from_high >= -50.0)
                 & down_pool)

    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    streak = _streak((close * wide["volume"]) > (close * wide["volume"]).rolling(50, min_periods=20).mean())
    atr = _atr_ratio(wide)

    for title, mask, pool, hold in (
        ("상승장 (신고가 눌림 · 거래대금 50억↑ · 120거래일)", up_mask, up_pool, 120),
        ("급락 후 반등장 (코스피 -10% 가장깊은날 · -40~-50% · 거래대금 10억↑ · 60거래일)",
         down_mask, down_pool, 60),
    ):
        returns = forward_returns(wide, hold)
        print(f"\n\n{'=' * 100}\n### {title}\n{'=' * 100}")
        whole = summarise(returns, mask, dates, split, pool=pool)
        print(line("그물 전체", whole))
        together = _together_counts(mask)
        for factor_name, table, buckets in (
            ("같은 테마 동반", together,
             (("1개(혼자)", 0.5, 1.5), ("2개", 1.5, 2.5), ("3개", 2.5, 3.5), ("4개↑", 3.5, 99))),
            ("최근 11일 등락", recent11,
             ((">-5% 빠짐", -999, -5), ("-5~0%", -5, 0), ("0~+5%", 0, 5), ("+5%↑ 오름", 5, 999))),
            ("거래대금 평소위 연속", streak,
             (("0일", -0.5, 0.5), ("1~3일", 0.5, 3.5), ("4~10일", 3.5, 10.5), ("11일↑", 10.5, 999))),
            ("최근 60일 상승폭", gain60,
             (("0% 이하", -999, 0), ("0~15%", 0, 15), ("15~40%", 15, 40), ("40%↑", 40, 999))),
            ("거래대금 크기", value,
             (("50~100억", 0, 100), ("100~500억", 100, 500), ("500~2000억", 500, 2000),
              ("2000억↑", 2000, 9e9))),
            ("변동성(ATR/주가)", atr,
             (("2% 미만", 0, 2), ("2~4%", 2, 4), ("4~6%", 4, 6), ("6%↑", 6, 999))),
        ):
            print(f"\n-- {factor_name} --")
            for label, lo, hi in buckets:
                picked = mask & (table > lo) & (table <= hi)
                result = summarise(returns, picked, dates, split, pool=pool)
                if result.get("전체") and result["전체"]["n"] >= 50:
                    print(line(label, result))


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "load"
    {"load": build_wide, "breakout": breakout_grid, "crash": crash_grid,
     "liquidity": liquidity_split, "factors": factors}[stage]()
