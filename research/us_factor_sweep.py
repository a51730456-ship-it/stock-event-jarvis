"""논문에서 뽑은 기준 열여덟 개를 **한 번에** 잰다 (2026-08-13).

## 1. 먼저 자를 고친다 — 다섯 번째 결함

지금까지 쓴 「같은 날 견주기」는 **그날 총점 1등이 나머지 평균을 이겼나**였다.
후보가 2개 이상인 날만 쓰므로 **330일**밖에 안 된다. 오차가 ±5.4%p라
무엇을 재도 오차에 묻혔다. 2026-08-13에 상하님께 보고한 "테마 보탬이 세 배"도
사실은 오차 안이었다.

**짝 견주기로 바꾼다.** 같은 날 뜬 후보를 **둘씩 모두 짝지어**, 값이 높은 쪽이
실제로 더 벌었는지 센다.

    그날 후보가 4개면 짝은 6개다. 330일 → 수천 짝.

같은 날끼리만 견주므로 그날 시장이 좋았는지 나빴는지는 저절로 상쇄된다.
짝끼리는 서로 얽혀 있으므로(같은 날 같은 종목이 여러 짝에 낌) **오차는
날짜를 통째로 다시 뽑는 방식(블록 부트스트랩)으로 낸다.** 짝 수로 그냥
계산하면 오차가 실제보다 작게 나온다.

## 2. 논문에서 뽑은 기준

  종목 쪽
   1 12-2개월 상승      Jegadeesh & Titman(1993)  최근 1개월은 빼고 잰다      +
   2 12-7개월 상승      Novy-Marx(2012) 메아리    이게 진짜다                 +
   3 6-2개월 상승       Novy-Marx(2012)           최근 것은 별 의미 없다      0
   4 뚫기 전 60일 상승   지금 쓰는 것                                          +
   5 52주 고점 근접도    George & Hwang(2004)      과거수익률보다 낫다         +
   6 정보 이산도        Da·Gurun·Warachka(2014)   잔잔히 오른 것이 더 간다    −
   7 거래량 늘었나      Lee & Swaminathan(2000)   거래 많은 승자는 빨리 뒤집힘 −
   8 최근 변동성        Daniel & Moskowitz(2016)  변동성 크면 폭락            −
   9 변동폭 수축 (VCP)  Minervini                 눌림에 변동폭이 줄어야 한다 −
  10 거래량 마름        Minervini·O'Neil          눌림에 거래가 말라야 한다   −
  11 50일선 위          Minervini 추세 틀                                     +
  12 회사 크기          O'Neil (L = 업계 대장주)                              +

  테마 쪽
  13 테마 6개월 등수     Moskowitz & Grinblatt(1999)                          +
  14 테마 12-1개월 등수  M&G · Quantpedia 섹터 로테이션                        +
  15 테마 고점 근접도    George & Hwang(2004) 산업판                          +
  16 테마 근접도 등수    위를 등수로                                          +
  17 동료 신고가 비율    (내가 만든 자)                                       +
  18 테마 대장주 20일    Hou(2007) 산업 내 선행·후행                          +

## 3. 판정

네 보유기간(1·3·6개월·1년) **모두**에서 논문이 말한 방향으로 나오고,
오차 범위가 50%를 안 걸쳐야 **합격**이다. 하나라도 반대면 「부분」,
방향이 거꾸로면 「반대」로 적는다.

CLAUDE.md 0-1 마 — 파는 시점을 안 정하는 파트는 여러 보유기간에서 모두
합격한 것만 쓴다.

쓰는 법:  python research/us_factor_sweep.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

OUT = ROOT / "research" / "_data" / "factor_sweep_events.csv"
HOLDS = ((20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년"))
SPLIT = pd.Timestamp("2021-08-04")
DRAWS = 400


def build() -> pd.DataFrame:
    import jarvis3_data as j3
    from us_shares_history import daily_market_cap
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    low, opens = wide["low"][stocks], wide["open"][stocks]
    volume, qqq = wide["volume"][stocks], wide["close"]["QQQ"]
    dates = close.index

    themes: dict[str, list] = {}
    for theme in j3.US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if len(members) >= 3:
            themes[theme["name"]] = members
    belongs = sorted({s for m in themes.values() for s in m})
    n_themes = len(themes)
    print(f"  테마 {n_themes}개 · 소속 {len(belongs)}종목", flush=True)

    daily = close / close.shift(1) - 1.0
    high52 = high.rolling(252, min_periods=252).max()

    print("  종목 쪽 자를 만든다...", flush=True)
    mom_12_2 = (close.shift(21) / close.shift(252) - 1.0) * 100.0
    mom_12_7 = (close.shift(126) / close.shift(252) - 1.0) * 100.0
    mom_6_2 = (close.shift(42) / close.shift(126) - 1.0) * 100.0
    gh_stock = close / high52 * 100.0

    # 정보 이산도 (Frog in the Pan) — 1년 동안 오른 날·내린 날 비율.
    # 승자인데 오른 날이 많으면(잔잔히) 값이 음수 = 연속 정보 = 논문이 좋다는 쪽.
    year_ret = close / close.shift(252) - 1.0
    pos = (daily > 0).rolling(252, min_periods=200).mean()
    neg = (daily < 0).rolling(252, min_periods=200).mean()
    id_disc = np.sign(year_ret) * (neg - pos)

    turnover = (volume.rolling(60, min_periods=40).mean()
                / volume.rolling(252, min_periods=200).mean())
    vol60 = daily.rolling(60, min_periods=40).std() * 100.0
    span = (high - low) / close
    vcp = (span.rolling(5, min_periods=4).mean()
           / span.rolling(50, min_periods=30).mean())
    dryup = (volume.rolling(5, min_periods=4).mean()
             / volume.rolling(50, min_periods=30).mean())
    above50 = (close > close.rolling(50, min_periods=50).mean()).astype(float)

    print("  시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")

    print("  테마 쪽 자를 만든다...", flush=True)
    ret120 = close / close.shift(120) - 1.0
    ret252_21 = close.shift(21) / close.shift(252) - 1.0
    ok120 = close.notna() & close.shift(120).notna()
    ok252 = close.notna() & close.shift(252).notna()

    def peer_rank(values, ok):
        board = pd.DataFrame({n: values[m].where(ok[m]).mean(axis=1)
                              for n, m in themes.items()})
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for name, members in themes.items():
            total = ok[members].sum(axis=1)
            summed = values[members].where(ok[members]).sum(axis=1)
            for stock in members:
                left = total - ok[stock].astype(int)
                mine = (summed - values[stock].where(ok[stock]).fillna(0.0)) \
                    / left.where(left > 0)
                column = (board.lt(mine, axis=0).sum(axis=1)
                          / n_themes * 100.0).where(mine.notna())
                out[stock] = column if out[stock].isna().all() \
                    else np.fmax(out[stock], column)
        return out

    theme_r120 = peer_rank(ret120, ok120)
    theme_r252 = peer_rank(ret252_21, ok252)

    prox_board = {}
    for name, members in themes.items():
        total = cap[members].sum(axis=1, min_count=2)
        prox_board[name] = total / total.rolling(252, min_periods=200).max() * 100.0
    prox_board = pd.DataFrame(prox_board)
    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    prox_rank = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    nearhigh = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    leader20 = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    ret20 = close / close.shift(20) - 1.0
    near_ok = close.notna() & high52.notna()
    near_flag = close / high52 >= 0.90
    for name, members in themes.items():
        mine = prox_board[name]
        ranked = (prox_board.lt(mine, axis=0).sum(axis=1) / n_themes * 100.0)
        total = near_ok[members].sum(axis=1)
        hit = (near_flag[members] & near_ok[members]).sum(axis=1)
        # 테마 대장주 = 그날 시총이 가장 큰 동료 (Hou 2007 선행·후행)
        biggest = cap[members].idxmax(axis=1)
        for stock in members:
            prox[stock] = mine if prox[stock].isna().all() else np.fmax(prox[stock], mine)
            prox_rank[stock] = ranked if prox_rank[stock].isna().all() \
                else np.fmax(prox_rank[stock], ranked)
            left = total - near_ok[stock].astype(int)
            column = ((hit - (near_flag[stock] & near_ok[stock]).astype(int))
                      / left.where(left > 0) * 100.0)
            nearhigh[stock] = column if nearhigh[stock].isna().all() \
                else np.fmax(nearhigh[stock], column)
            # 후보 자신이 대장주면 그날은 빈칸으로 둔다 (자기를 보는 셈이 된다)
            pick = biggest.where(biggest != stock)
            lead = pd.Series(
                [np.nan if pd.isna(t) else ret20.at[d, t] * 100.0
                 for d, t in pick.items()], index=dates)
            leader20[stock] = lead if leader20[stock].isna().all() \
                else np.fmax(leader20[stock], lead)

    print("  그물을 친다...", flush=True)
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

    rows, cols = np.nonzero(net.to_numpy())
    frames = {
        "mom_12_2": mom_12_2, "mom_12_7": mom_12_7, "mom_6_2": mom_6_2,
        "gain60": gain60, "gh_stock": gh_stock, "id_disc": id_disc,
        "turnover": turnover, "vol60": vol60, "vcp": vcp, "dryup": dryup,
        "above50": above50, "cap_rank": cap_rank,
        "theme_r120": theme_r120, "theme_r252": theme_r252, "prox": prox,
        "prox_rank": prox_rank, "nearhigh": nearhigh, "leader20": leader20,
        "pullback": -from_peak, "wait": days_since,
    }
    table = {"date": dates[rows], "ticker": np.array(close.columns)[cols],
             "bid": breakout_id.to_numpy()[rows, cols]}
    for name, frame in frames.items():
        table[name] = frame.to_numpy()[rows, cols]
    for hold, _n in HOLDS:
        table[f"r{hold}"] = ((close.shift(-hold) / opens.shift(-1) - 1.0)
                             * 100.0).to_numpy()[rows, cols]

    events = (pd.DataFrame(table).sort_values("date")
              .drop_duplicates(["ticker", "bid"], keep="first").reset_index(drop=True))
    events["half"] = np.where(events["date"] < SPLIT, "앞", "뒤")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(OUT, index=False)
    return events


FACTORS = (
    ("1  12-2개월 상승", "mom_12_2", +1, "Jegadeesh & Titman 1993"),
    ("2  12-7개월 상승 (메아리)", "mom_12_7", +1, "Novy-Marx 2012"),
    ("3  6-2개월 상승", "mom_6_2", 0, "Novy-Marx 2012 (의미 없다)"),
    ("4  뚫기 전 60일 상승", "gain60", +1, "지금 쓰는 것"),
    ("5  52주 고점 근접도", "gh_stock", +1, "George & Hwang 2004"),
    ("6  정보 이산도", "id_disc", -1, "Frog in the Pan 2014"),
    ("7  거래량 늘었나", "turnover", -1, "Lee & Swaminathan 2000"),
    ("8  최근 변동성", "vol60", -1, "Daniel & Moskowitz 2016"),
    ("9  변동폭 수축 (VCP)", "vcp", -1, "Minervini"),
    ("10 거래량 마름", "dryup", -1, "Minervini · O'Neil"),
    ("11 50일선 위", "above50", +1, "Minervini 추세 틀"),
    ("12 회사 크기 (등수)", "cap_rank", -1, "O'Neil 업계 대장주"),
    ("13 테마 6개월 등수", "theme_r120", +1, "Moskowitz & Grinblatt 1999"),
    ("14 테마 12-1개월 등수", "theme_r252", +1, "M&G · 섹터 로테이션"),
    ("15 테마 고점 근접도", "prox", +1, "George & Hwang 산업판"),
    ("16 테마 근접도 등수", "prox_rank", +1, "위를 등수로"),
    ("17 동료 신고가 비율", "nearhigh", +1, "(내가 만든 자)"),
    ("18 테마 대장주 20일", "leader20", +1, "Hou 2007 선행·후행"),
    ("·  지금 눌린 폭", "pullback", +1, "지금 쓰는 것"),
)


def day_pairs(events: pd.DataFrame, column: str, hold: int) -> tuple:
    """날짜별 (값 큰 쪽이 이긴 짝 수, 전체 짝 수)."""
    data = events.dropna(subset=[column, f"r{hold}"])
    wins, totals = [], []
    for _day, group in data.groupby("date"):
        if len(group) < 2:
            continue
        value = group[column].to_numpy()
        got = group[f"r{hold}"].to_numpy()
        dv = value[:, None] - value[None, :]
        dr = got[:, None] - got[None, :]
        keep = np.triu(np.ones_like(dv, dtype=bool), 1) & (dv != 0) & (dr != 0)
        if not keep.any():
            continue
        agree = (np.sign(dv) == np.sign(dr)) & keep
        wins.append(int(agree.sum()))
        totals.append(int(keep.sum()))
    return np.array(wins), np.array(totals)


def rate_and_band(wins: np.ndarray, totals: np.ndarray) -> tuple:
    """짝 이긴 비율과, 날짜를 통째로 다시 뽑아 낸 오차 범위."""
    if totals.sum() < 100:
        return None, None, None, int(totals.sum())
    point = wins.sum() / totals.sum() * 100.0
    rng = np.random.default_rng(20260813)
    draws = np.empty(DRAWS)
    size = len(totals)
    for i in range(DRAWS):
        pick = rng.integers(0, size, size)
        draws[i] = wins[pick].sum() / max(totals[pick].sum(), 1) * 100.0
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)), \
        int(totals.sum())


def main() -> None:
    if OUT.exists() and "--reuse" in sys.argv:
        events = pd.read_csv(OUT, parse_dates=["date"])
    else:
        events = build()
    ready = events.dropna(subset=["r250"])
    print(f"\n{'=' * 112}\n### 논문 기준 열여덟 개 — 짝 견주기 "
          f"(사건 {len(events):,}건 · 1년 결과 있는 것 {len(ready):,}건)\n{'=' * 112}")
    print("  숫자 = 같은 날 뜬 두 종목 중 **값이 큰 쪽이 더 번 짝의 비율**.")
    print("  50%면 못 가른다. 괄호는 오차(날짜를 통째로 다시 뽑아 400번).")
    print("  ▲ = 논문 방향으로 유의 · ▽ = 반대로 유의 · · = 오차가 50%를 걸침\n")
    print(f"  {'항목':<26}{'짝':>7}" + "".join(f"{n:>21}" for _h, n in HOLDS) + "  판정")

    verdicts = []
    for label, column, want, source in FACTORS:
        line, marks = "", []
        pairs = 0
        for hold, _name in HOLDS:
            wins, totals = day_pairs(events, column, hold)
            point, low, high_, total = rate_and_band(wins, totals)
            pairs = max(pairs, total)
            if point is None:
                line += f"{'못 잼':>21}"
                marks.append(0)
                continue
            mark = "▲" if low > 50 else ("▽" if high_ < 50 else "·")
            marks.append(1 if low > 50 else (-1 if high_ < 50 else 0))
            line += f"{point:>9.1f}%({low:.0f}~{high_:.0f}){mark}"
        if want == 0:
            verdict = "예상대로 안 갈림" if all(m == 0 for m in marks) else "예상과 다름"
        elif all(m == want for m in marks):
            verdict = "**합격**"
        elif any(m == -want for m in marks):
            verdict = "반대"
        elif any(m == want for m in marks):
            verdict = "부분"
        else:
            verdict = "못 가름"
        verdicts.append((label, verdict, source))
        print(f"  {label:<26}{pairs:>7,}{line}  {verdict}")

    print(f"\n{'=' * 112}\n### 판정 모음\n{'=' * 112}")
    for group in ("**합격**", "부분", "반대", "못 가름", "예상대로 안 갈림", "예상과 다름"):
        rows = [(label, source) for label, verdict, source in verdicts if verdict == group]
        if not rows:
            continue
        print(f"\n  ── {group} ──")
        for label, source in rows:
            print(f"     {label:<26}{source}")

    print(f"\n  ※ 값이 큰 쪽 기준이다. 「반대」는 **작은 쪽이 좋다**는 뜻이므로 버리지 말 것.")
    print(f"  ※ 사건표 저장 → {OUT.relative_to(ROOT)}  (다시 돌릴 땐 --reuse)")


if __name__ == "__main__":
    main()
