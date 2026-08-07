"""미국테마 배점을 **해마다** 다시 잰다 (2026-08-07).

**왜.** 2026-08-06에 미국 배점을 정할 때 10년을 2021-08에서 **두 토막**으로만 갈랐다.
한국에서 같은 방법을 쓰다가 함정을 봤다 — '같이 움직이는 무리'가 앞뒤 두 토막으로는
앞 +13.0p / 뒤 +24.0p로 아주 좋아 보였는데, 해마다 재 보니 **잴 수 있는 해가 3년뿐**
이었다(상하님 지적: "자르는 날 문제 있는 것 아니냐"). 미국도 같은 방법을 썼으니
같은 함정에 걸릴 수 있다.

쟀던 대상 그대로 — `jarvis3_data.US_THEMES`의 198종목, 10년, 배당 반영 종가.

쓰는 법:  python research/us_yearly.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "research" / "_data" / "us_wide"


def fetch() -> dict[str, pd.DataFrame]:
    """테마 명부 종목의 10년치 일봉. 한 번 받아 두고 다시 쓴다."""
    if (CACHE / "close.parquet").exists():
        return {key: pd.read_parquet(CACHE / f"{key}.parquet")
                for key in ("open", "high", "low", "close", "volume")}
    import yfinance as yf

    import jarvis3_data as j3

    tickers = sorted({stock for theme in j3.US_THEMES for stock in theme["stocks"]})
    print(f"테마 명부 {len(tickers)}종목을 받는다...", flush=True)
    raw = yf.download(tickers + ["QQQ"], period="10y", interval="1d",
                      auto_adjust=True, group_by="ticker", threads=8, progress=False)
    frames: dict[str, dict[str, pd.Series]] = {
        key: {} for key in ("open", "high", "low", "close", "volume")
    }
    kept = 0
    for ticker in tickers + ["QQQ"]:
        try:
            table = raw[ticker].dropna(how="all")
        except Exception:
            continue
        if len(table) < 400:
            continue
        kept += 1
        for key, column in (("open", "Open"), ("high", "High"), ("low", "Low"),
                            ("close", "Close"), ("volume", "Volume")):
            frames[key][ticker] = table[column].astype("float32")
    CACHE.mkdir(parents=True, exist_ok=True)
    wide = {}
    for key, columns in frames.items():
        frame = pd.DataFrame(columns).sort_index()
        frame.index = frame.index.tz_localize(None)
        frame.to_parquet(CACHE / f"{key}.parquet")
        wide[key] = frame
    print(f"{kept}종목 · {wide['close'].shape[0]}거래일 "
          f"({wide['close'].index[0].date()} ~ {wide['close'].index[-1].date()})")
    return wide


def main() -> None:
    import jarvis3_data as j3

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    qqq = wide["close"]["QQQ"]
    close = wide["close"][stocks]
    high = wide["high"][stocks]
    dates = close.index

    # 화면이 쓰는 그물 그대로
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = ((days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo))
    # 상승장으로 친 날 — 나스닥이 200일선 위이고 고점 대비 -10% 안
    qqq_ma200 = qqq.rolling(200, min_periods=200).mean()
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    up_day = (qqq > qqq_ma200) & (qqq_drop > j3.BREAKOUT_MARKET_MAX_DROP)
    up_wide = pd.DataFrame(np.repeat(up_day.to_numpy()[:, None], close.shape[1], axis=1),
                           index=dates, columns=close.columns)
    breakout = net & up_wide

    # 급락 그물 — 나스닥 -6~-12% 구간의 가장 깊은 날, 종목 -20~-50%
    band_lo, band_hi = j3.CRASH_MARKET_BAND
    in_band = (qqq_drop <= band_hi) & (qqq_drop >= band_lo)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], close.shape[1], axis=1),
                        index=dates, columns=close.columns)
    stock_drop = (close / high.rolling(252, min_periods=252).max() - 1.0) * 100.0
    crash = deep & (stock_drop <= -20.0) & (stock_drop >= -50.0)

    # 배점 후보
    themes_of: dict[str, set[str]] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            themes_of.setdefault(stock, set()).add(theme["name"])
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    value = (close * wide["volume"][stocks]).rolling(50, min_periods=20).mean()
    above = (close * wide["volume"][stocks]) > value
    streak_values = above.to_numpy(dtype="int16", na_value=0)
    streak_out = np.zeros_like(streak_values)
    for row in range(1, streak_values.shape[0]):
        streak_out[row] = np.where(streak_values[row] > 0, streak_out[row - 1] + 1, 0)
    streak = pd.DataFrame(streak_out, index=dates, columns=close.columns)

    def together_of(mask: pd.DataFrame) -> pd.DataFrame:
        columns = list(mask.columns)
        array = mask.to_numpy()
        out = np.zeros(array.shape, dtype="int16")
        for row in np.nonzero(array.any(axis=1))[0]:
            picked = np.nonzero(array[row])[0]
            codes = [columns[i] for i in picked]
            counts: dict[str, int] = {}
            for code in codes:
                for theme in themes_of.get(code, ()):
                    counts[theme] = counts.get(theme, 0) + 1
            out[row, picked] = [
                max((counts[t] for t in themes_of.get(code, ()) if t in counts), default=1)
                for code in codes
            ]
        return pd.DataFrame(out, index=dates, columns=close.columns)

    years = sorted({date.year for date in dates})
    buy = wide["open"][stocks].shift(-1)
    returns = (close.shift(-120) / buy - 1.0) * 100.0

    for title, signal in (("상승장", breakout), ("급락 후 반등장", crash)):
        together = together_of(signal)
        cases = [
            ("40점 · 같은 테마 동반 3개↑", signal & (together >= 3)),
            ("25점 · 최근 11일 -5% 넘게 빠짐", signal & (recent11 <= -5.0)),
            ("15점 · 눌린 폭 10~15%" if title == "상승장" else "15점 · 낙폭 -30~-50%",
             signal & ((from_peak <= -10.0) & (from_peak >= -15.0) if title == "상승장"
                       else (stock_drop <= -30.0) & (stock_drop >= -50.0))),
            ("0점 · 거래대금 평소위 11일↑", signal & (streak >= 11)),
            ("0점 · 최근 60일 40% 넘게 오름", signal & (gain60 >= 40.0)),
        ]
        print(f"\n{'=' * 110}\n### 미국 {title} — 해마다 (숫자는 그날 아무 종목이나 산 것보다 몇 %p 더 이겼나)\n{'=' * 110}")
        print(f"{'':32}" + "".join(f"{year:>7}" for year in years))
        for name, mask in cases:
            cells, wins, total = [], 0, 0
            for year in years:
                window = np.array([date.year == year for date in dates])
                values = returns[window].where(mask[window]).to_numpy().ravel()
                values = values[~np.isnan(values)]
                if values.size < 20:
                    cells.append("     ·")
                    continue
                active = mask[window].any(axis=1).to_numpy()
                base = returns[window][active].to_numpy().ravel()
                base = base[~np.isnan(base)]
                edge = (values > 0).mean() * 100 - (base > 0).mean() * 100
                cells.append(f"{edge:+7.1f}")
                total += 1
                wins += edge > 0
            print(f"{name:<32}" + "".join(cells) + f"   → {wins}/{total}년")
    print("\n· = 그해 자리가 20개 미만이라 재지 않음")


if __name__ == "__main__":
    main()
