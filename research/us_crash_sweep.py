"""급락 후 반등장 배점을 **새 자로** 다시 잰다 (2026-08-14).

## 왜 다시 재나

지금 급락 배점 세 항목(테마가 덜 빠졌나 40 · 테마 주봉이 오름세인가 30 ·
테마가 20일선 위인가 20)은 **2026-08-12에 옛 자로 정한 것**이다. 옛 자는
`us_verify.py`의 「창 2·3·4년을 한 달씩 밀며 승률·수익률 둘 다 65% 이상」이다.

그런데 2026-08-13에 상승장을 **새 자**로 다시 재니 결과가 뒤집혔다.

  · 옛 자는 「그날 총점 1등이 나머지 평균을 이겼나」라 후보가 둘 이상인 330일밖에
    못 썼고 오차가 ±5.4%p였다. 무엇을 재도 오차에 묻혔다.
  · 새 자는 같은 날 뜬 후보를 **둘씩 모두 짝지어** 센다(330일 → 3,683짝).
  · 오차도 날짜가 아니라 **연도를 통째로** 다시 뽑아 낸다. 1년 수익률은 날마다
    364일씩 겹쳐서, 날짜 단위로 내면 오차가 실제보다 작게 나온다.

새 자로 재니 상승장에서 **테마를 그날 등수로 매기는 자가 전부 무너졌다**
(네 번 중 0번). 살아남은 것은 **테마 근접도를 칸 없이 그대로 쓰는 것** 하나뿐이었다.

**급락 배점 세 항목은 전부 그 '등수 자'다.** 그러니 같은 의심을 받아야 한다.
이 스크립트가 그것을 잰다.

## 무엇을 재나

  ① 테마가 덜 빠졌나        — 지금 40점. 등수와 원값 둘 다
  ② 테마 주봉이 오름세인가   — 지금 30점. 등수와 원값 둘 다
  ③ 테마가 20일선 위인가     — 지금 20점. 등수와 원값 둘 다
  ④ **테마 근접도(칸 없이)** — 상승장에서 유일하게 살아남은 자. 급락에도 통하나
  ⑤ 참고 — 종목 낙폭 · 회사 크기 · 종목 50일선 위

## 그물 (jarvis3_data와 같게)

  나스닥(QQQ)이 1년 최고 대비 **−6% 아래인 날 전부**
  그 종목이 1년 최고 대비 **−20 ~ −50%**
  US_THEMES에 속한 종목만 (테마 항목이 늘 비는 종목은 뺀다)

보유는 정하지 않는다 — 3개월·6개월·1년(60·120·250거래일)을 따로 잰다.
사는 값은 **신호 다음 거래일 시가**다(앱 규칙과 같다).

## 판정

  ▲ 오차의 아래끝이 50%를 넘음 = 통과
  · 오차가 50%를 걸침 = 못 가름

세 보유기간 중 **몇 번 통과했나**로 적는다. 파는 시점을 앱이 정하지 않으므로
한 기간에서만 통하는 값은 쓰지 않는다(CLAUDE.md 0-1 마).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_sweep.py
          (--reuse 를 붙이면 만들어 둔 사건표를 다시 쓴다)
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

OUT = ROOT / "research" / "_data" / "crash_sweep_events.csv"
HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
MARKET_DROP = -6.0            # 나스닥이 1년 최고 대비 이보다 낮은 날
STOCK_BAND = (-50.0, -20.0)   # 종목 낙폭
DRAWS = 2000


def build() -> pd.DataFrame:
    """급락 그물에 걸린 자리마다 잣대와 앞날 수익률을 적어 둔다."""
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
    print(f"  테마 {len(themes)}개 · 소속 {len(belongs)}종목", flush=True)

    # ── 그물 ────────────────────────────────────────────────────────────
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    gate = (qqq_drop < MARKET_DROP).fillna(False)
    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    low_band, high_band = STOCK_BAND
    in_band = (from_high > low_band) & (from_high < high_band)
    net = in_band[belongs].where(gate, False).fillna(False)
    print(f"  급락 날 {int(gate.sum())}일 · 그물 자리 {int(net.to_numpy().sum()):,}개",
          flush=True)

    # ── 종목 쪽 잣대 ────────────────────────────────────────────────────
    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma150 = close.rolling(150, min_periods=150).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    above20 = (close > sma20).astype(float)
    above50 = (close > sma50).astype(float)
    # 주봉 오름세(Minervini) — 종가>50>150>200 이고 200일선이 20일 전보다 위
    aligned = ((close > sma50) & (sma50 > sma150) & (sma150 > sma200)
               & (sma200 > sma200.shift(20))).astype(float)

    print("  시총을 만든다(오래 걸린다)...", flush=True)
    cap = daily_market_cap(close)
    cap_rank = cap.rank(axis=1, ascending=False, method="min")

    # ── 테마 쪽 잣대 ────────────────────────────────────────────────────
    def spread(values: pd.DataFrame) -> pd.DataFrame:
        """테마별 평균을 구해 소속 종목마다 되돌려 준다(원값)."""
        board = pd.DataFrame({name: values[m].mean(axis=1)
                              for name, m in themes.items()})
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for name, members in themes.items():
            for stock in members:
                out[stock] = board[name] if out[stock].isna().all() \
                    else np.fmax(out[stock], board[name])
        return out

    def to_rank(values: pd.DataFrame) -> pd.DataFrame:
        """그날 테마끼리 줄 세운 등수(1등이 가장 좋다) → **부호를 뒤집어** 돌려준다.

        짝 견주기는 '값이 큰 쪽이 더 벌었나'를 보므로, 등수는 작을수록 좋다는 뜻을
        **큰 값이 좋다**로 맞춰야 한다. 그래서 음수로 준다.
        """
        board = pd.DataFrame({name: values[m].mean(axis=1)
                              for name, m in themes.items()})
        rank = board.rank(axis=1, ascending=False, method="min")
        out = pd.DataFrame(np.nan, index=dates, columns=close.columns)
        for name, members in themes.items():
            for stock in members:
                out[stock] = -rank[name] if out[stock].isna().all() \
                    else np.fmax(out[stock], -rank[name])
        return out

    print("  테마 쪽 자를 만든다...", flush=True)
    theme_less_drop = spread(from_high)          # 덜 빠졌나 (원값, 클수록 덜 빠짐)
    theme_less_drop_rank = to_rank(from_high)
    theme_aligned = spread(aligned)              # 주봉 오름세 비율
    theme_aligned_rank = to_rank(aligned)
    theme_above20 = spread(above20)              # 20일선 위 비율
    theme_above20_rank = to_rank(above20)

    # 테마 근접도 — 합산 시총 ÷ 그 합의 252일 최고 × 100 (상승장에서 살아남은 자)
    prox = pd.DataFrame(np.nan, index=dates, columns=close.columns)
    for name, members in themes.items():
        total = cap[members].sum(axis=1, min_count=2)
        value = total / total.rolling(252, min_periods=200).max() * 100.0
        for stock in members:
            prox[stock] = value if prox[stock].isna().all() \
                else np.fmax(prox[stock], value)

    # ── 앞날 수익률 — **다음 거래일 시가**에 산다 ────────────────────────
    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _label in HOLDS}

    columns = {
        "less_drop": theme_less_drop, "less_drop_rank": theme_less_drop_rank,
        "aligned": theme_aligned, "aligned_rank": theme_aligned_rank,
        "above20": theme_above20, "above20_rank": theme_above20_rank,
        "prox": prox,
        "stock_drop": from_high, "stock_above50": above50,
        "cap_rank": -cap_rank,          # 큰 회사가 좋다는 쪽으로 부호를 맞춘다
    }

    print("  사건표를 만든다...", flush=True)
    rows = []
    index = {stock: i for i, stock in enumerate(close.columns)}
    net_np = net.to_numpy()
    for day_i, day in enumerate(dates):
        hits = np.flatnonzero(net_np[day_i])
        if len(hits) < 2:            # 짝을 못 만드는 날은 버린다
            continue
        picked = [net.columns[h] for h in hits]
        row = {"date": day, "ticker": picked}
        frame = pd.DataFrame({"date": day, "ticker": picked})
        for name, table in columns.items():
            frame[name] = [table.iat[day_i, index[t]] for t in picked]
        for hold, _label in HOLDS:
            frame[f"r{hold}"] = [rets[hold].iat[day_i, index[t]] for t in picked]
        rows.append(frame)
    events = pd.concat(rows, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(OUT, index=False)
    print(f"  사건표 {len(events):,}줄 → {OUT}", flush=True)
    return events


def day_pairs(events: pd.DataFrame, column: str, hold: int) -> pd.DataFrame:
    """날짜마다 (값 큰 쪽이 이긴 짝 수, 전체 짝 수). 연도도 같이 담는다."""
    data = events.dropna(subset=[column, f"r{hold}"])
    out = []
    for day, group in data.groupby("date"):
        if len(group) < 2:
            continue
        value = group[column].to_numpy(dtype=float)
        got = group[f"r{hold}"].to_numpy(dtype=float)
        dv = value[:, None] - value[None, :]
        dr = got[:, None] - got[None, :]
        keep = np.triu(np.ones_like(dv, dtype=bool), 1) & (dv != 0) & (dr != 0)
        if not keep.any():
            continue
        agree = (np.sign(dv) == np.sign(dr)) & keep
        out.append((pd.Timestamp(day).year, int(agree.sum()), int(keep.sum())))
    return pd.DataFrame(out, columns=["year", "wins", "totals"])


def rate_and_band(pairs: pd.DataFrame) -> tuple:
    """짝 이긴 비율과, **연도를 통째로 다시 뽑아** 낸 오차 범위.

    1년 수익률은 날마다 364일씩 겹치므로 날짜 단위로 오차를 내면 실제보다 작게
    나온다. 그래서 연도를 뽑는다(블록 부트스트랩).
    """
    if pairs.empty or pairs["totals"].sum() < 200:
        return None, None, None, int(pairs["totals"].sum() if not pairs.empty else 0)
    point = pairs["wins"].sum() / pairs["totals"].sum() * 100.0
    years = sorted(pairs["year"].unique())
    by_year = {y: pairs[pairs["year"] == y] for y in years}
    rng = np.random.default_rng(20260814)
    draws = np.empty(DRAWS)
    for i in range(DRAWS):
        pick = rng.integers(0, len(years), len(years))
        wins = sum(by_year[years[p]]["wins"].sum() for p in pick)
        totals = sum(by_year[years[p]]["totals"].sum() for p in pick)
        draws[i] = wins / max(totals, 1) * 100.0
    return (point, float(np.percentile(draws, 2.5)),
            float(np.percentile(draws, 97.5)), int(pairs["totals"].sum()))


FACTORS = (
    ("① 테마가 덜 빠졌나 (원값)", "less_drop", "지금 40점"),
    ("① 테마가 덜 빠졌나 (등수)", "less_drop_rank", "지금 40점 · 앱이 쓰는 방식"),
    ("② 테마 주봉 오름세 (원값)", "aligned", "지금 30점"),
    ("② 테마 주봉 오름세 (등수)", "aligned_rank", "지금 30점 · 앱이 쓰는 방식"),
    ("③ 테마 20일선 위 (원값)", "above20", "지금 20점"),
    ("③ 테마 20일선 위 (등수)", "above20_rank", "지금 20점 · 앱이 쓰는 방식"),
    ("④ 테마 근접도 (칸 없이)", "prox", "상승장에서 유일하게 살아남은 자"),
    ("·  종목 낙폭 (덜 빠진 쪽)", "stock_drop", "참고 — 그물이 이미 쓴 값"),
    ("·  종목 50일선 위", "stock_above50", "참고"),
    ("·  회사 크기 (큰 쪽)", "cap_rank", "참고"),
)


def main() -> None:
    if OUT.exists() and "--reuse" in sys.argv:
        events = pd.read_csv(OUT, parse_dates=["date"])
        print(f"  사건표를 다시 쓴다 — {len(events):,}줄")
    else:
        events = build()

    ready = events.dropna(subset=["r250"])
    print(f"\n급락 그물 {len(events):,}자리 · 1년 성적까지 나온 것 {len(ready):,}자리")
    print(f"날짜 {events['date'].nunique():,}일 · 연도 "
          f"{sorted(pd.to_datetime(events['date']).dt.year.unique())}\n")

    head = "항목".ljust(26) + "".join(label.rjust(18) for _h, label in HOLDS) + "  통과"
    print(head)
    print("─" * len(head))
    for title, column, note in FACTORS:
        cells, passed = [], 0
        for hold, _label in HOLDS:
            point, low, high, total = rate_and_band(day_pairs(events, column, hold))
            if point is None:
                cells.append("자료부족".rjust(18))
                continue
            mark = "▲" if low > 50.0 else "·"
            passed += 1 if mark == "▲" else 0
            cells.append(f"{point:.1f}({low:.0f}~{high:.0f}){mark}".rjust(18))
        print(title.ljust(26) + "".join(cells) + f"  {passed}/{len(HOLDS)}   {note}")
    print("\n▲ = 오차 아래끝이 50%를 넘음(통과) · · = 오차가 50%를 걸침(못 가름)")


if __name__ == "__main__":
    main()
