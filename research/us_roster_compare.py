"""옛 명부와 새 명부를 **나란히 놓고** 처음부터 다시 잰다 (2026-08-13).

## 왜 통째로 다시 재나

명부는 그물과 같은 급이다(CLAUDE.md 0-1 라). 명부가 바뀌면
  · 어떤 날 어떤 종목이 후보인지(그물)가 바뀌고
  · 테마 근접도 값이 바뀌고
  · 따라서 배점 판정이 통째로 바뀐다
2026-08-09에 종목 하나(CRWD→ORCL) 바꿨더니 판정이 뒤집힌 적이 있다.

## 재는 법 (2026-08-13에 두 번 고친 자)

**짝 견주기** — 같은 날 뜬 후보를 둘씩 모두 짝지어, 값이 큰 쪽이 실제로
더 벌었는지 센다. 「그날 1등 하나」만 보던 옛 자는 330일밖에 못 써서
무엇을 재도 오차에 묻혔다.

**연 단위 오차** — 1년 수익률은 오늘 산 것과 내일 산 것이 364일 겹친다.
날짜 단위로 오차를 내면 실제보다 작게 나온다. 연도를 통째로 다시 뽑는다.

**네 보유기간 모두** — 1·3·6개월·1년. 파는 시점을 안 정하는 파트는
여러 기간에서 모두 합격한 것만 쓴다(CLAUDE.md 0-1 마).

**가짜 테마 시험** — 종목을 제비뽑기로 같은 크기 묶음으로 나눠 똑같이 잰다.
가짜도 비슷하게 나오면 그 명부의 효과는 진짜가 아니다.

쓰는 법:  python research/us_roster_compare.py [가짜뽑기횟수]
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((20, "1개월"), (60, "3개월"), (120, "6개월"), (250, "1년"))
SHUFFLES = int(sys.argv[1]) if len(sys.argv) > 1 else 100
DRAWS = 3000


def steps(values: np.ndarray, spec) -> np.ndarray:
    out = np.full(len(values), np.nan)
    for low, high, share in spec:
        out = np.where((values >= low) & (values < high), share, out)
    return out


GAIN = ((-999, 20, 0.13), (20, 35, 0.37), (35, 50, 0.50), (50, 75, 0.63), (75, 9999, 1.0))
PULL = ((4, 6, 0.50), (6, 8, 0.50), (8, 10, 1.0), (10, 12, 0.70), (12, 16, 0.60))
OLD_THEME = ((0, 85, 0.0), (85, 95, 1.0), (95, 999, 0.3))


class Board:
    """가격·시총을 한 번만 만들어 두고 명부만 갈아 끼운다."""

    def __init__(self) -> None:
        from us_shares_history import daily_market_cap
        from us_yearly import fetch

        wide = fetch()
        stocks = [c for c in wide["close"].columns if c != "QQQ"]
        self.close = wide["close"][stocks]
        self.high = wide["high"][stocks]
        self.opens = wide["open"][stocks]
        self.qqq = wide["close"]["QQQ"]
        self.dates = self.close.index
        print("  시총을 만든다(오래 걸린다)...", flush=True)
        self.cap = daily_market_cap(self.close)

        high52 = self.high.rolling(252, min_periods=252).max()
        order = pd.DataFrame(
            np.arange(len(self.dates))[:, None].repeat(self.close.shape[1], axis=1),
            index=self.dates, columns=self.close.columns)
        is_high = self.high >= high52.shift(1)
        peak = self.high.where(is_high).ffill()
        self.since = order - order.where(is_high).ffill()
        self.from_peak = (self.close / peak - 1.0) * 100.0
        self.gain60 = ((self.close / self.close.shift(60) - 1.0)
                       * 100.0).where(is_high).ffill()
        self.bid = order.where(is_high).ffill()

        ma = {n: self.qqq.rolling(n, min_periods=n).mean() for n in (20, 60, 120, 200)}
        drop = (self.qqq / self.qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
        self.gate = ((self.qqq > ma[20]) & (ma[20] > ma[60]) & (ma[60] > ma[120])
                     & (ma[120] > ma[200]) & (drop > -5.0)).fillna(False)
        self.ret = {h: (self.close.shift(-h) / self.opens.shift(-1) - 1.0) * 100.0
                    for h, _n in HOLDS}

    def prox(self, groups: list[list[str]]) -> pd.DataFrame:
        out = pd.DataFrame(np.nan, index=self.dates, columns=self.close.columns)
        for members in groups:
            members = [s for s in members if s in self.cap.columns]
            if len(members) < 3:
                continue
            total = self.cap[members].sum(axis=1, min_count=2)
            value = total / total.rolling(252, min_periods=200).max() * 100.0
            for stock in members:
                out[stock] = value if out[stock].isna().all() \
                    else np.fmax(out[stock], value)
        return out

    def events(self, groups: list[list[str]]) -> pd.DataFrame:
        import jarvis3_data as j3

        belongs = {s for m in groups for s in m if s in self.close.columns}
        has = pd.DataFrame(
            np.repeat(np.array([[s in belongs for s in self.close.columns]]),
                      len(self.dates), axis=0),
            index=self.dates, columns=self.close.columns)
        up = pd.DataFrame(
            np.repeat(self.gate.to_numpy()[:, None], self.close.shape[1], axis=1),
            index=self.dates, columns=self.close.columns)
        lo, hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
        dlo, dhi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
        net = (up & has & (self.since >= lo) & (self.since <= hi)
               & (self.from_peak <= dhi) & (self.from_peak >= dlo)).fillna(False)
        prox = self.prox(groups)
        rows, cols = np.nonzero(net.to_numpy())
        table = {
            "date": self.dates[rows],
            "ticker": np.array(self.close.columns)[cols],
            "bid": self.bid.to_numpy()[rows, cols],
            "gain60": self.gain60.to_numpy()[rows, cols],
            "pullback": -self.from_peak.to_numpy()[rows, cols],
            "prox": prox.to_numpy()[rows, cols],
        }
        for hold, _n in HOLDS:
            table[f"r{hold}"] = self.ret[hold].to_numpy()[rows, cols]
        frame = (pd.DataFrame(table).sort_values("date")
                 .drop_duplicates(["ticker", "bid"], keep="first").reset_index(drop=True))
        frame["yr"] = frame.date.dt.year
        return frame


def pairs_by_year(events: pd.DataFrame, values: np.ndarray, hold: int) -> dict:
    data = events.assign(_f=values).dropna(subset=["_f", f"r{hold}"])
    rows: dict = {}
    for year, group in data.groupby("yr"):
        win = tot = 0
        for _day, day in group.groupby("date"):
            if len(day) < 2:
                continue
            value = day["_f"].to_numpy()
            got = day[f"r{hold}"].to_numpy()
            dv = value[:, None] - value[None, :]
            dr = got[:, None] - got[None, :]
            keep = np.triu(np.ones_like(dv, dtype=bool), 1) & (dv != 0) & (dr != 0)
            if not keep.any():
                continue
            win += int(((np.sign(dv) == np.sign(dr)) & keep).sum())
            tot += int(keep.sum())
        if tot:
            rows[year] = (win, tot)
    return rows


def band(rows: dict) -> tuple:
    if not rows:
        return None, None, None, 0
    keys = list(rows)
    win = np.array([rows[k][0] for k in keys])
    tot = np.array([rows[k][1] for k in keys])
    if tot.sum() < 100:
        return None, None, None, int(tot.sum())
    point = win.sum() / tot.sum() * 100.0
    rng = np.random.default_rng(20260813)
    draws = np.empty(DRAWS)
    for i in range(DRAWS):
        pick = rng.integers(0, len(keys), len(keys))
        draws[i] = win[pick].sum() / max(tot[pick].sum(), 1) * 100.0
    return point, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)), \
        int(tot.sum())


def line(events: pd.DataFrame, values: np.ndarray) -> tuple:
    text, passed = "", 0
    for hold, _name in HOLDS:
        point, low, high, _tot = band(pairs_by_year(events, values, hold))
        if point is None:
            text += f"{'못 잼':>19}"
            continue
        mark = "▲" if low > 50 else ("▽" if high < 50 else "·")
        passed += 1 if low > 50 else 0
        text += f"{point:>10.1f}%({low:.0f}~{high:.0f}){mark}"
    return text, passed


def placebo(board: Board, groups: list[list[str]], events_maker) -> dict:
    sizes = [len(m) for m in groups]
    slots = [s for m in groups for s in m]
    rng = np.random.default_rng(20260813)
    got = {h: [] for h, _n in HOLDS}
    for turn in range(SHUFFLES):
        mixed = list(slots)
        rng.shuffle(mixed)
        fake, at = [], 0
        for size in sizes:
            fake.append(mixed[at:at + size])
            at += size
        events = events_maker(fake)
        for hold, _n in HOLDS:
            rows = pairs_by_year(events, events.prox.values, hold)
            win = sum(v[0] for v in rows.values())
            tot = sum(v[1] for v in rows.values())
            got[hold].append(win / tot * 100.0 if tot else np.nan)
        if (turn + 1) % 20 == 0:
            print(f"      {turn + 1}/{SHUFFLES}...", flush=True)
    return got


def main() -> None:
    import jarvis3_data as j3
    import us_theme_roster_v2 as v2

    board = Board()
    rosters = {
        "옛 명부 (20개·137종목)": [list(t["stocks"]) for t in j3.US_THEMES],
        "새 명부 (19개·115종목)": [list(t["stocks"]) for t in v2.build()],
    }

    made = {}
    for name, groups in rosters.items():
        events = board.events(groups)
        made[name] = (events, groups)
        ready = events.dropna(subset=["r250"])
        print(f"\n  {name} — 사건 {len(events):,}건 (1년 결과 {len(ready):,}건)", flush=True)

    head = "".join(f"{n:>19}" for _h, n in HOLDS)
    print(f"\n{'=' * 110}\n### ① 항목별 — 짝 견주기 · 연 단위 오차\n{'=' * 110}")
    print(f"  {'':<32}{head}  합격")
    for name, (events, _g) in made.items():
        print(f"\n  ── {name} ──")
        for label, values in (
                ("테마 고점 근접도 (계단 없이)", events.prox.values),
                ("테마 근접도 · 지금 세 칸 배점", steps(events.prox.values, OLD_THEME)),
                ("뚫기 전 60일 상승", events.gain60.values),
                ("지금 눌린 폭", events.pullback.values)):
            text, passed = line(events, values)
            print(f"  {label:<32}{text}  {passed}/4")

    print(f"\n{'=' * 110}\n### ② 비중 — 종목상승 / 눌림 / 테마\n{'=' * 110}")
    print(f"  {'':<32}{head}  합격")
    for name, (events, _g) in made.items():
        gain = steps(events.gain60.values, GAIN)
        pull = steps(events.pullback.values, PULL)
        theme = np.clip((events.prox.values - 80.0) / 20.0, 0, 1)
        old = steps(events.prox.values, OLD_THEME)
        print(f"\n  ── {name} ──")
        for label, score in (
                ("70 / 20 / 10  지금 배점", 70 * gain + 20 * pull + 10 * old),
                ("70 / 20 / 10  근접도 그대로", 70 * gain + 20 * pull + 10 * theme),
                ("50 / 10 / 40  근접도 그대로", 50 * gain + 10 * pull + 40 * theme),
                ("40 /  0 / 60  눌림 뺌", 40 * gain + 60 * theme),
                ("30 /  0 / 70  눌림 뺌", 30 * gain + 70 * theme),
                ("0  /  0 / 100 테마만", theme),
                ("100 / 0 / 0  종목만", gain)):
            text, passed = line(events, score)
            print(f"  {label:<32}{text}  {passed}/4")

    print(f"\n{'=' * 110}\n### ③ 가짜 테마 시험 — 제비뽑기 {SHUFFLES}번\n{'=' * 110}")
    for name, (events, groups) in made.items():
        print(f"\n  ── {name} ──", flush=True)
        truth = {}
        for hold, _n in HOLDS:
            rows = pairs_by_year(events, events.prox.values, hold)
            truth[hold] = (sum(v[0] for v in rows.values())
                           / sum(v[1] for v in rows.values()) * 100.0)
        fake = placebo(board, groups, board.events)
        print(f"     {'보유':<8}{'진짜':>9}{'가짜 가운데':>13}{'가짜 95%':>18}"
              f"{'진짜보다 잘한 가짜':>20}")
        for hold, label in HOLDS:
            arr = np.array(fake[hold])
            beat = int((arr >= truth[hold]).sum())
            print(f"     {label:<8}{truth[hold]:>8.1f}번{np.median(arr):>12.1f}번"
                  f"{np.percentile(arr, 2.5):>10.1f}~{np.percentile(arr, 97.5):.1f}번"
                  f"{beat:>15}번 / {SHUFFLES}")

    print("\n  ※ ▲ = 오차 아래끝이 50%를 넘음(합격) · · = 오차가 50%를 걸침(못 가름)")
    print("  ※ 가짜가 5번 이하로 이기면 그 명부의 테마 효과는 진짜다.")


if __name__ == "__main__":
    main()
