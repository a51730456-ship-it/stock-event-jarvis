"""3층(배점)만 다시 잰다 — **미래정보 없는 후보 넷** (2026-08-13 상하님 확정).

1층·2층은 **고정**이다. 더 안 건드린다.
  1층  QQQ가 200일선 위
  2층  52주 신고가 뒤 3~10거래일 · 그 고점보다 4~15% 아래 · 테마 있는 종목

## 왜 다시 재나

3층 후보 중 테마표를 쓰는 것 둘이 **미래정보**였다. 테마표는 2026년에 만든 것인데
2016년에 갖다 붙였다. '테마 2개 이상 걸친 종목'은 사실상 NVDA·AVGO·VRT 등
**14개 종목을 지목한 것**이라, "지금 와서 보니 잘 오른 종목이 잘 올랐다"를 잰 셈이다.
빅50도 **오늘** 발행주식수를 썼다. 둘 다 근거가 될 수 없다.

## 다시 재는 후보 넷 — 전부 그날까지의 값만 쓴다

  ① 뚫기 전 60일 상승률          신고가 찍던 날의 직전 60일 상승폭 (구간별)
  ② 그날 같이 신고가 찍은 종목 수   명부 전체의 그날 신고가 개수 = **시장 폭**
  ③ 무리 동반강세               과거 252일 **일간수익률** 상관 상위 20종목이
                            지금 같이 고점 근처인 비율 = **종목 무리 효과**
  ④ 그날 시가총액 상위 50        그날 종가 × **그날** 발행주식수

**②와 ③은 별개다.** ②는 시장 전체가 달아올랐나, ③은 이 종목의 무리가 같이 가나다.
③은 주가가 아니라 **일간수익률**로 상관을 잰다 — 주가로 재면 둘 다 우상향했다는
이유만으로 비슷해 보인다.

## 방법

단독 → 두 개 조합 → 세 개 조합 순으로 본다. **점수는 마지막에 정한다.**
결과는 **QQQ 상승 국면별로** 나눠 본다 — 한 국면이 전체를 끌어올린 거면 탈락이다.
걸린 거래는 전부 CSV로 남긴다(`research/_data/layer3_trades.csv`).

쓰는 법:  python research/us_layer3.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
CORR_LOOKBACK = 252     # 상관을 재는 과거 길이(거래일)
CORR_STEP = 21          # 한 달에 한 번 다시 잰다
CORR_PEERS = 20         # 무리 크기
TRADES_CSV = ROOT / "research" / "_data" / "layer3_trades.csv"


def peer_strength(close: pd.DataFrame, from_high: pd.DataFrame) -> pd.DataFrame:
    """③ 무리 동반강세 — 과거 252일 **일간수익률** 상관 상위 20종목 중
    지금 고점 −5% 안에 있는 비율.

    **그 날짜 이후 자료는 한 줄도 안 쓴다.** 상관은 그날까지의 수익률로만 잰다.
    한 달에 한 번 다시 재고 그동안은 그 무리를 유지한다(매일 재면 너무 느리다).
    """
    returns = close.pct_change()
    near = (from_high > -5.0)
    out = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    columns = list(close.columns)
    for start in range(CORR_LOOKBACK, len(close), CORR_STEP):
        window = returns.iloc[start - CORR_LOOKBACK:start]
        enough = window.notna().sum() >= CORR_LOOKBACK * 0.8
        usable = [c for c in columns if enough.get(c, False)]
        if len(usable) < 30:
            continue
        corr = window[usable].corr()
        np.fill_diagonal(corr.values, np.nan)
        stop = min(start + CORR_STEP, len(close))
        block = near.iloc[start:stop]
        for stock in usable:
            peers = corr[stock].nlargest(CORR_PEERS).index
            out.iloc[start:stop, columns.index(stock)] = (
                block[list(peers)].mean(axis=1).to_numpy() * 100)
    return out


def main() -> None:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60_at_peak = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    # ── 1층·2층 (고정) ──────────────────────────────────────────────────
    ma200 = (qqq > qqq.rolling(200, min_periods=200).mean()).fillna(False)
    up = pd.DataFrame(np.repeat(ma200.to_numpy()[:, None], close.shape[1], axis=1),
                      index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)
    total = int(net.to_numpy().sum())

    # ── 후보 넷 ─────────────────────────────────────────────────────────
    # ② 그날 같이 신고가 찍은 종목 수 — 명부 전체 (시장 폭)
    breadth = is_new_high.sum(axis=1)
    breadth_wide = pd.DataFrame(
        np.repeat(breadth.to_numpy()[:, None], close.shape[1], axis=1),
        index=dates, columns=close.columns)
    # ③ 무리 동반강세
    print("무리(상관 상위 20) 동반강세를 계산한다 — 한 달에 한 번 다시 잰다...",
          flush=True)
    peers = peer_strength(close, from_high)
    # ④ 그날 시가총액 순위
    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")
    cap_known = cap.notna()
    print(f"그날 시총을 잴 수 있는 칸: "
          f"{(cap_known & net).to_numpy().sum() / max(total, 1) * 100:.0f}% "
          f"(그물 안 기준)\n", flush=True)

    singles = {
        "① 뚫기 전 60일 0~20%": (gain60_at_peak > 0) & (gain60_at_peak <= 20),
        "① 뚫기 전 60일 20~50%": (gain60_at_peak > 20) & (gain60_at_peak <= 50),
        "① 뚫기 전 60일 50%↑": gain60_at_peak > 50,
        "② 그날 신고가 5개 이하": breadth_wide <= 5,
        "② 그날 신고가 6~15개": (breadth_wide > 5) & (breadth_wide <= 15),
        "② 그날 신고가 16개↑": breadth_wide > 15,
        "③ 무리 강세 30% 이하": peers <= 30,
        "③ 무리 강세 30~60%": (peers > 30) & (peers <= 60),
        "③ 무리 강세 60%↑": peers > 60,
        "④ 그날 시총 상위50": (cap_rank <= 50) & cap_known,
        "④ 그날 시총 51~100": (cap_rank > 50) & (cap_rank <= 100) & cap_known,
        "④ 그날 시총 101위 아래": (cap_rank > 100) & cap_known,
    }

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}
    base = (up & close.notna()).fillna(False)

    def stat(values):
        values = values[~np.isnan(values)]
        return None if values.size < 100 else (values.size, (values > 0).mean() * 100,
                                               float(np.median(values)))

    def row(name, mask, when=None):
        sel = mask if when is None else mask.loc[when]
        source = rets if when is None else {h: rets[h].loc[when] for h, _ in HOLDS}
        cells = ""
        got0 = None
        for hold, _label in HOLDS:
            got = stat(source[hold].where(sel).to_numpy().ravel())
            got0 = got0 or got
            cells += "       —      " if not got else f" {got[1]:>3.0f}번 {got[2]:>+6.1f}%"
        count = int(sel.to_numpy().sum())
        print(f"  {name:<26}{count:>7,}{count / max(total, 1) * 100:>5.0f}%{cells}")

    print(f"\n{'=' * 106}\n### 3층만 다시 — 미래정보 없는 후보 넷"
          f"\n### 1층 QQQ 200일선 위 · 2층 신고가 뒤 {wait_lo}~{wait_hi}일 · "
          f"고점보다 {abs(drop_hi):.0f}~{abs(drop_lo):.0f}% 아래 · 그물 {total:,}자리"
          f"\n{'=' * 106}")
    print(f"  {'':<26}{'자리':>7}{'몫':>5}" + "".join(f"{n:>14}" for _h, n in HOLDS))
    print()
    row("아무 종목이나 (기준선)", base)
    row("그물 전체", net)
    print("\n  ── 단독 ──")
    for name, mask in singles.items():
        row(name, net & mask.reindex_like(net).fillna(False))

    # ── 조합 ────────────────────────────────────────────────────────────
    best = {
        "①60%↑": gain60_at_peak > 50,
        "②신고가16↑": breadth_wide > 15,
        "③무리60%↑": peers > 60,
        "④시총50": (cap_rank <= 50) & cap_known,
    }
    keys = list(best)
    print("\n  ── 두 개 조합 ──")
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            mask = best[keys[i]] & best[keys[j]]
            row(f"{keys[i]} + {keys[j]}", net & mask.reindex_like(net).fillna(False))
    print("\n  ── 세 개 조합 ──")
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            for k in range(j + 1, len(keys)):
                mask = best[keys[i]] & best[keys[j]] & best[keys[k]]
                row(f"{keys[i]}+{keys[j]}+{keys[k]}",
                    net & mask.reindex_like(net).fillna(False))

    # ── QQQ 상승 국면별 ─────────────────────────────────────────────────
    epi = (ma200 & ~ma200.shift(1, fill_value=False)).cumsum().where(ma200)
    print(f"\n  ── QQQ 상승 국면별 (1년 보유) ──")
    groups = [(g.index[0], g.index[-1]) for _e, g in
              pd.DataFrame({"e": epi}).dropna().groupby("e") if len(g) >= 120]
    print(f"  {'':<26}" + "".join(f"{a.date().strftime('%y.%m'):>14}" for a, _b in groups))
    for name, mask in (("아무 종목이나", base), ("그물 전체", net),
                       *((k, net & v.reindex_like(net).fillna(False))
                         for k, v in best.items())):
        cells = ""
        for a, b in groups:
            when = (dates >= a) & (dates <= b)
            got = stat(rets[250].loc[when].where(mask.loc[when]).to_numpy().ravel())
            cells += f"{'—':>14}" if not got else f"{got[1]:>7.0f}번{got[2]:>+6.1f}"
        print(f"  {name:<26}{cells}")

    # ── 원거래 저장 ──────────────────────────────────────────────────────
    rows_idx, cols_idx = np.nonzero(net.to_numpy())
    frame = pd.DataFrame({
        "date": dates[rows_idx],
        "ticker": [close.columns[c] for c in cols_idx],
        "from_peak": from_peak.to_numpy()[rows_idx, cols_idx],
        "days_since_high": days_since.to_numpy()[rows_idx, cols_idx],
        "gain60_at_peak": gain60_at_peak.to_numpy()[rows_idx, cols_idx],
        "breadth": breadth_wide.to_numpy()[rows_idx, cols_idx],
        "peer_strength": peers.to_numpy()[rows_idx, cols_idx],
        "cap_rank": cap_rank.to_numpy()[rows_idx, cols_idx],
        **{f"ret_{h}d": rets[h].to_numpy()[rows_idx, cols_idx] for h, _n in HOLDS},
    })
    TRADES_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TRADES_CSV, index=False)
    print(f"\n  원거래 {len(frame):,}줄 저장 → {TRADES_CSV}")
    print("  ※ 명부는 오늘 살아 있는 199종목이다. 망한 회사는 빠져 있다(생존편향).")


if __name__ == "__main__":
    main()
