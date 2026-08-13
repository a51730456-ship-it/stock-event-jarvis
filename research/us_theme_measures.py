"""테마를 **재는 법**을 바꿔서 다시 잰다 (2026-08-13).

## 왜 이걸 만드나 — 자가 잘못됐다는 의심

지금까지 테마 상태를 **「테마 합산 시총 ÷ 그 52주 최고」**(근접도)로 쟀다.
이 자에는 결함이 넷 있다.

**① 절대 수준을 쟀다. 그날 테마들끼리 줄을 세우지 않았다.** ← 가장 큰 것
상승장에서는 **모든 테마가 자기 최고 근처**다. 그래서 사건 1,459건 중
**1,068건(73%)이 「95%↑」 한 칸에 몰렸다.** 한 칸에 다 들어가면 그 자는
못 가르는 게 당연하다. 산업 모멘텀 논문(Moskowitz & Grinblatt 1999)은
**그날 산업들을 서로 줄 세워 상위 몇 %인지**로 잰다. 절대 수준이 아니다.

**② 대장주 하나가 테마 전체를 대신한다.**
합산 시총은 시총 가중이라 반도체 테마면 NVDA 하나가 절반을 넘는다.
'테마가 좋다'가 사실상 'NVDA가 좋다'가 된다. **머릿수로 세면** 이게 풀린다.

**③ 후보 종목 자신이 그 합계에 들어가 있다.**
후보가 오르면 테마 점수도 오른다. 같은 것을 두 번 세는 것이다.

**④ 값이 아니라 낙폭을 쟀다.**
근접도는 '고점에서 얼마나 안 밀렸나'다. 모멘텀은 '얼마나 올랐나'다. 다른 것이다.

## 그래서 자를 아홉 개 만들어 견준다

  A 동료 20일 오름 비율    동료 중 최근 20일 오른 종목이 몇 %  (머릿수·후보 제외)
  B 동료 60일 오름 비율    동료 중 최근 60일 오른 종목이 몇 %
  C 동료 20일 평균 상승    동료들의 최근 20일 상승률 평균
  D 동료 신고가 비율       동료 중 자기 52주 고점 10% 안이 몇 %
  E 동료 60일 상승 **등수**  그날 테마들 중 상위 몇 %      ← 논문 방식
  F 동료 120일 상승 **등수** 그날 테마들 중 상위 몇 %      ← 논문 방식(6개월)
  G 근접도 **등수**         같은 자를 등수로만 바꾼 것     ← ①만 고친 것
  H 근접도 (지금 쓰는 자)   비교용
  I 테마 몇 개에 드나       여러 테마 걸친 종목이 유리한지 확인

E·F·G가 H보다 잘 갈리면 **문제는 테마가 아니라 자였다**는 뜻이다.
G가 H보다 잘 갈리면 **①(절대 수준)이 범인**이라고 딱 집을 수 있다.

## 어떻게 판정하나

  · 칸별 승률·수익률 (앞 2016~2021 / 뒤 2021~2026 갈라서)
  · **같은 날 견주기** — 한 날에 여러 후보가 뜰 때 그 자가 순서를 가르나.
    배점은 결국 그날 목록 안에서 순서를 정하는 것이므로 이것이 진짜 시험이다.
  · **몰림** — 한 칸에 몇 %가 들어가나. 85% 넘게 몰리면 그 자는 못 가른다.
  · **겹침** — 종목 자신의 60일 상승과 얼마나 같이 움직이나.
  · 표본 30건 미만은 「못 잼」.

1층·2층 고정 — QQQ 정배열 + 고점 −5% 안 · 신고가 뒤 3~10일 · 고점 −4~−15%.
같은 돌파는 한 번만 센다.

쓰는 법:  python research/us_theme_measures.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

OUT = ROOT / "research" / "_data" / "theme_measures_events.csv"
SPLIT = pd.Timestamp("2021-08-04")


def build() -> pd.DataFrame:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    themes: dict[str, list] = {}
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if len(members) >= 3:
            themes[theme["name"]] = members
    belongs = sorted({s for m in themes.values() for s in m})
    count_of = pd.Series({s: sum(s in m for m in themes.values()) for s in belongs})
    n_themes = len(themes)
    print(f"  테마 {n_themes}개 · 소속 종목 {len(belongs)}개", flush=True)

    ret20 = close / close.shift(20) - 1.0
    ret60 = close / close.shift(60) - 1.0
    ret120 = close / close.shift(120) - 1.0
    high52 = high.rolling(252, min_periods=252).max()
    ok20 = close.notna() & close.shift(20).notna()
    ok60 = close.notna() & close.shift(60).notna()
    ok120 = close.notna() & close.shift(120).notna()

    def peer_ratio(flag: pd.DataFrame, ok: pd.DataFrame) -> pd.DataFrame:
        """동료(후보 제외) 중 flag가 참인 비율 %. 여러 테마면 가장 센 쪽."""
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for members in themes.values():
            total = ok[members].sum(axis=1)
            hit = (flag[members] & ok[members]).sum(axis=1)
            for stock in members:
                left = total - ok[stock].astype(int)
                column = ((hit - (flag[stock] & ok[stock]).astype(int))
                          / left.where(left > 0) * 100.0)
                out[stock] = column if out[stock].isna().all() \
                    else np.fmax(out[stock], column)
        return out

    def peer_value(values: pd.DataFrame, ok: pd.DataFrame) -> dict:
        """테마별로 {종목: 동료 평균} 을 돌려준다. 등수 매길 때 쓴다."""
        table = {}
        for name, members in themes.items():
            total = ok[members].sum(axis=1)
            summed = values[members].where(ok[members]).sum(axis=1)
            table[name] = {}
            for stock in members:
                left = total - ok[stock].astype(int)
                own = values[stock].where(ok[stock]).fillna(0.0)
                table[name][stock] = (summed - own) / left.where(left > 0)
        return table

    def peer_mean(values: pd.DataFrame, ok: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for name, column_of in peer_value(values, ok).items():
            for stock, column in column_of.items():
                scaled = column * 100.0
                out[stock] = scaled if out[stock].isna().all() \
                    else np.fmax(out[stock], scaled)
        return out

    def peer_rank(values: pd.DataFrame, ok: pd.DataFrame) -> pd.DataFrame:
        """동료 평균 상승률이 **그날 테마들 중** 상위 몇 %인가 (논문 방식).

        절대 수준이 아니라 등수다. 상승장에 다 같이 오르면 절대 수준은
        전부 높아 못 가르지만, 등수는 언제나 갈린다.
        """
        table = peer_value(values, ok)
        board = pd.DataFrame({name: values[m].where(ok[m]).mean(axis=1)
                              for name, m in themes.items()})
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for name, column_of in table.items():
            for stock, mine in column_of.items():
                lower = board.lt(mine, axis=0).sum(axis=1)
                column = (lower / n_themes * 100.0).where(mine.notna())
                out[stock] = column if out[stock].isna().all() \
                    else np.fmax(out[stock], column)
        return out

    print("  동료를 세는 자를 만든다...", flush=True)
    breadth20 = peer_ratio(ret20 > 0, ok20)
    breadth60 = peer_ratio(ret60 > 0, ok60)
    strength20 = peer_mean(ret20, ok20)
    nearhigh = peer_ratio(close / high52 >= 0.90, close.notna() & high52.notna())
    rank60 = peer_rank(ret60, ok60)
    rank120 = peer_rank(ret120, ok120)

    print("  시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")
    prox_board = pd.DataFrame({
        name: (cap[m].sum(axis=1, min_count=2)
               / cap[m].sum(axis=1, min_count=2).rolling(252, min_periods=200).max()
               * 100.0)
        for name, m in themes.items()})
    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    prox_rank = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    for name, members in themes.items():
        mine = prox_board[name]
        ranked = (prox_board.lt(mine, axis=0).sum(axis=1)
                  / n_themes * 100.0).where(mine.notna())
        for stock in members:
            prox[stock] = mine if prox[stock].isna().all() else np.fmax(prox[stock], mine)
            prox_rank[stock] = ranked if prox_rank[stock].isna().all() \
                else np.fmax(prox_rank[stock], ranked)

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60 = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()
    breakout_id = order.where(is_new_high).ffill()

    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in belongs for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    ma = {n: qqq.rolling(n, min_periods=n).mean() for n in (20, 60, 120, 200)}
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    gate = ((qqq > ma[20]) & (ma[20] > ma[60]) & (ma[60] > ma[120])
            & (ma[120] > ma[200]) & (qdrop > -5.0)).fillna(False)
    up = pd.DataFrame(np.repeat(gate.to_numpy()[:, None], close.shape[1], axis=1),
                      index=dates, columns=close.columns)
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    net = (up & has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
           & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    ret1y = (close.shift(-250) / opens.shift(-1) - 1.0) * 100.0
    rows, cols = np.nonzero(net.to_numpy())
    tickers = np.array(close.columns)[cols]
    frame = pd.DataFrame({
        "date": dates[rows],
        "ticker": tickers,
        "bid": breakout_id.to_numpy()[rows, cols],
        "wait": days_since.to_numpy()[rows, cols],
        "pullback": -from_peak.to_numpy()[rows, cols],
        "cap": cap_rank.to_numpy()[rows, cols],
        "gain60": gain60.to_numpy()[rows, cols],
        "breadth20": breadth20.to_numpy()[rows, cols],
        "breadth60": breadth60.to_numpy()[rows, cols],
        "strength20": strength20.to_numpy()[rows, cols],
        "nearhigh": nearhigh.to_numpy()[rows, cols],
        "rank60": rank60.to_numpy()[rows, cols],
        "rank120": rank120.to_numpy()[rows, cols],
        "prox_rank": prox_rank.to_numpy()[rows, cols],
        "prox": prox.to_numpy()[rows, cols],
        "n_theme": [count_of.get(t, 0) for t in tickers],
        "ret": ret1y.to_numpy()[rows, cols],
    })
    events = (frame.sort_values("date")
              .drop_duplicates(["ticker", "bid"], keep="first")
              .dropna(subset=["ret"]).reset_index(drop=True))
    events["half"] = np.where(events["date"] < SPLIT, "앞", "뒤")
    return events


QUARTERS = ((0, 25, "하위 25%"), (25, 50, "25~50%"), (50, 75, "50~75%"), (75, 101, "상위 25%"))
MEASURES = (
    ("A 동료 20일 오름 비율", "breadth20",
     ((0, 40, "40% 미만"), (40, 60, "40~60%"), (60, 80, "60~80%"), (80, 101, "80%↑"))),
    ("B 동료 60일 오름 비율", "breadth60",
     ((0, 40, "40% 미만"), (40, 60, "40~60%"), (60, 80, "60~80%"), (80, 101, "80%↑"))),
    ("C 동료 20일 평균 상승", "strength20",
     ((-999, 0, "내렸다"), (0, 3, "0~3%"), (3, 7, "3~7%"), (7, 9999, "7%↑"))),
    ("D 동료 신고가 비율", "nearhigh",
     ((0, 50, "50% 미만"), (50, 70, "50~70%"), (70, 90, "70~90%"), (90, 101, "90%↑"))),
    ("E 동료 60일 상승 등수  ← 논문 방식", "rank60", QUARTERS),
    ("F 동료 120일 상승 등수 ← 논문 방식(6개월)", "rank120", QUARTERS),
    ("G 근접도 **등수**      ← 절대수준만 고친 것", "prox_rank", QUARTERS),
    ("H 근접도 (지금 쓰는 자)", "prox",
     ((0, 85, "85% 미만"), (85, 95, "85~95%"), (95, 99, "95~99%"), (99, 999, "99%↑"))),
    ("I 테마 몇 개에 드나", "n_theme",
     ((1, 2, "1개"), (2, 3, "2개"), (3, 99, "3개↑"))),
)


def same_day(events: pd.DataFrame, mask: pd.Series) -> tuple:
    table = events.assign(g=mask).groupby(["date", "g"]).ret.mean().unstack().dropna()
    if len(table) < 30:
        return len(table), None, None
    gap = table[True] - table[False]
    return len(gap), 100 * (gap > 0).mean(), gap.median()


def main() -> None:
    events = build()
    print(f"\n{'=' * 100}\n### 테마를 재는 법 아홉 가지 — 사건 {len(events):,}건 "
          f"(앞 {(events.half == '앞').sum()} · 뒤 {(events.half == '뒤').sum()})\n{'=' * 100}")
    print(f"  목록 전체  100번 중 {(events.ret > 0).mean() * 100:.0f}번 · "
          f"{events.ret.median():+.1f}%")

    for title, column, bands in MEASURES:
        biggest = 0
        print(f"\n  ── {title} ──")
        print(f"     {'칸':<12}{'N':>6}{'몰림':>7}{'이긴 횟수':>10}{'수익률':>9}"
              f"{'앞':>7}{'뒤':>7}{'같은 날 견주기':>24}")
        for low, high_, label in bands:
            mask = (events[column] >= low) & (events[column] < high_)
            sel = events[mask]
            share = len(sel) / len(events) * 100
            biggest = max(biggest, share)
            if len(sel) < 30:
                print(f"     {label:<12}{len(sel):>6}{share:>6.0f}%   못 잼 (30건 미만)")
                continue
            cells = ""
            for half in ("앞", "뒤"):
                part = sel[sel.half == half].ret
                cells += f"{'—':>7}" if len(part) < 20 else f"{(part > 0).mean() * 100:>6.0f}번"
            days, win, gap = same_day(events, mask)
            tail = f"{'같이 뜬 날 ' + str(days) + '일 못 잼':>24}" if win is None else \
                f"{days:>9}일{win:>5.0f}%{gap:>+7.1f}%p"
            print(f"     {label:<12}{len(sel):>6,}{share:>6.0f}%"
                  f"{(sel.ret > 0).mean() * 100:>9.0f}번{sel.ret.median():>8.1f}%"
                  f"{cells}{tail}")
        corr = events[[column, "gain60"]].corr().iloc[0, 1]
        note = "  ← 한 칸에 몰려 못 가른다" if biggest >= 85 else ""
        print(f"     └ 가장 큰 칸 {biggest:.0f}%{note} · 종목 60일 상승과 겹침 {corr:+.2f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(OUT, index=False)
    print(f"\n  사건 {len(events):,}건 저장 → {OUT.relative_to(ROOT)}")
    print("  ※ 테마 명부는 오늘 것이다 — 이 편향은 남는다.")


if __name__ == "__main__":
    main()
