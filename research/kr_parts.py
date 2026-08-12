"""한국테마를 **파트별로, 앱이 실제로 쓰는 그물 그대로** 잰다 (2026-08-12).

미국은 오늘 `research/us_parts.py`로 파트를 갈라 다시 쟀다. 한국은 상승장·급락
두 갈래만 새 그물에서 쟀고(`kr_score_new.py`), **눌림목 찾기·테마 순위·순위 7은
앱 그물로 재 본 적이 없다.** 이 파일이 그 셋을 잰다.

잣대는 `docs/US_THEME_SPEC.md` 2부 그대로다 — 창 2·3·4년을 한 달씩 밀고,
**그물 안에서** 견주고, 승률·수익률 둘 다 65%↑라야 합격. 배점 계단은 40·30·20·10
넷뿐. 해당 비율이 85%↑거나 10%↓면 합격이어도 '못 가름'(순위를 못 가른다).

**앱 코드에서 그대로 읽어 온 것** (`jarvis4_data.py`, 추측하지 않았다)

  _series_metrics (372줄)
      high52          = 최근 **248**일 High의 최대값   (daily.tail(248))
      high52_days_ago = 그 최대값을 찍고 며칠 지났나   (오늘이면 0)
      from_high_pct   = (오늘 종가 / high52 − 1) × 100
      sma20/50/200    = 최근 20/50/200일 **종가** 평균
      atr_pct         = 14일 평균 True Range / 오늘 종가 × 100
      avg_trading_value = 20일 평균 거래량 × 오늘 종가

  find_pullback_stocks (3545줄)
      ① 테마 2개 이상 소속            min_theme_count = 2
      ② 유동성 200억↑                 min_trading_value = 2e10
         liquidity_value = max(오늘 거래대금, 오늘 종가 × 전일 거래량)
      ③ 유동성 상위 **50종목만** 본다  scan_limit = 50   ← 이게 그물의 일부다
      ④ 신고가 뒤 1~30일               high_days_min/max
      ⑤ from_high_pct < 0
      ⑥ 조건점수(신고가 시점) 75↑      min_stock_score = 75
      ⑦ 유동성 상위 25종목만 수급 조회

  _theme_score (1707줄) — 100점
      코스피 대비 당일 상대강도 35 · 구성종목 상승 비율 25 ·
      3%↑ 종목 비율 20 · 총 거래대금 20 (log10, 1.0~4.2)

  get_theme_rankings (1745줄)
      당일 등락률 상위 **40개**를 후보로 잡고, 점수로 줄 세워 **상위 20개**를 쓴다.

  get_theme_leaders (2261줄) + find_top_reviewed_stocks (2368줄) = 순위 7
      상위 20 테마 × 테마 안 **거래대금 상위 8종목**을 한 자루에 담아
      _stock_score 하나로 줄 세운다.

  SCORE_WEIGHTS (68줄) — 신고가 35 · 변동성 25 · 유동성 20 · 수급 20 ·
      추세 0 · 상대강도 0

**못 재는 것 — 수급.** 외국인·기관 순매수는 12년치 과거 자료가 없다.
눌림목의 수급 15점, 조건점수의 수급 20점은 **못 잰 항목**이다(0점도 아니고 합격도 아니다).

**베끼지 않고 다시 계산하지 않는다.** 앱 함수를 그대로 부를 수는 없다(네이버를
장중에 두드리는 함수라 과거를 못 준다). 대신 위처럼 **한 줄씩 맞춘 그물**을 쓰고,
어긋날 수 있는 곳은 주석에 적었다.

쓰는 법 (윈도우는 PYTHONIOENCODING=utf-8 필수):
    python research/kr_parts.py pullback   # ① 눌림목 찾기
    python research/kr_parts.py theme      # ② 테마 순위 (국면 둘로 갈라)
    python research/kr_parts.py top7       # ③ 순위 7 (조건점수)
    python research/kr_parts.py old        # ④ 상승장·급락 (이미 잰 것 → 계단 표)
    python research/kr_parts.py all
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from kr_measure import DAILY, ROSTER, load_wide  # noqa: E402
from us_verify import (  # noqa: E402
    MIN_SIDE, MIN_WINDOWS, PASS_MARK, STEP_DAYS, WINDOWS, verdict,
)

# 앱에 '며칠 들고 있어라'가 없는 파트는 셋 다 잰다 (기준: 파는 시점은 앱이 안 정한다).
HOLDS = (60, 120, 250)
SHARE_HIGH = 85.0     # 해당 비율이 이보다 높으면 못 가른다
SHARE_LOW = 10.0      # 이보다 낮아도 못 쓴다
LADDER = (40, 30, 20, 10)

# 앱 _is_excluded (1859줄)와 같은 규칙
_EXCLUDE_PATTERNS = ("스팩", "SPAC", "리츠")


def _excluded(name: str) -> bool:
    if any(token in name for token in _EXCLUDE_PATTERNS):
        return True
    return name.endswith("우") or name.endswith("우B") or name.endswith("3우B")


# ── 빠른 채점 ────────────────────────────────────────────────────────────
# us_verify.score()와 **같은 값**을 내되, 그물에 걸린 자리만 뽑아 두고 창을
# 밀면서 잘라 쓴다. 통째로 nan을 거르면 한 항목에 14초가 걸려 60항목이면 15분이다.
class Net:
    """그물 하나를 '자리 목록'으로 눌러 둔 것. 항목마다 다시 안 만든다."""

    def __init__(self, returns: pd.DataFrame, net: pd.DataFrame, n_dates: int):
        # us_verify.score()는 nan만 걸러낸다(±inf는 남긴다). 잣대를 바꾸지 않으려고
        # 여기서도 똑같이 nan만 거른다 — isfinite로 바꾸면 값이 미세하게 달라진다.
        block = returns.to_numpy()
        mask = (net.to_numpy() & ~np.isnan(block))
        self.rows, self.cols = np.nonzero(mask)          # 행 오름차순으로 나온다
        self.values = block[self.rows, self.cols]
        self.n_dates = n_dates
        self.total = int(self.rows.size)

    def run(self, factor: np.ndarray) -> dict:
        flag = factor[self.rows, self.cols]
        out: dict[int, dict | None] = {}
        for years in WINDOWS:
            length = int(years * 252)
            wins, medians = [], []
            for start in range(0, self.n_dates - length + 1, STEP_DAYS):
                lo = int(np.searchsorted(self.rows, start, "left"))
                hi = int(np.searchsorted(self.rows, start + length, "left"))
                if hi - lo < 2 * MIN_SIDE:
                    continue
                block, mark = self.values[lo:hi], flag[lo:hi]
                a, b = block[mark], block[~mark]
                if a.size < MIN_SIDE or b.size < MIN_SIDE:
                    continue
                wins.append((a > 0).mean() * 100 - (b > 0).mean() * 100)
                medians.append(float(np.median(a) - np.median(b)))
            if len(wins) < MIN_WINDOWS:
                out[years] = None
                continue
            wins, medians = np.array(wins), np.array(medians)
            out[years] = {
                "n": wins.size,
                "win_share": float((wins > 0).mean() * 100),
                "median_share": float((medians > 0).mean() * 100),
                "win_mid": float(np.median(wins)),
                "win_worst": float(wins.min()),
            }
        return out

    def share(self, factor: np.ndarray) -> float:
        if not self.total:
            return 0.0
        return float(factor[self.rows, self.cols].mean() * 100)


def show(name: str, share: float, result: dict) -> tuple[str, float | None]:
    cells, worst = "", []
    for years in WINDOWS:
        item = result.get(years)
        if not item:
            cells += f"{'—':^16}"
            continue
        cells += f"{item['win_share']:>4.0f}/{item['median_share']:>3.0f}%({item['n']:>3}) "
        worst.append(item["win_worst"])
    mark = verdict(result)
    if mark == "○ 합격" and not (SHARE_LOW <= share <= SHARE_HIGH):
        mark = "✎ 못 가름"
    worst_text = f"{min(worst):+6.1f}p" if worst else "     —"
    print(f"  {name:<30}{share:>4.0f}%  {cells} {mark:<10} 최악 {worst_text}")
    return mark, (min(worst) if worst else None)


def run_part(title: str, net_frame: pd.DataFrame, factors: dict,
             returns_by_hold: dict[int, pd.DataFrame], n_dates: int) -> None:
    """한 파트를 보유기간마다 재고, 마지막에 40·30·20·10 계단을 얹는다."""
    net_bool = net_frame.fillna(False).to_numpy().astype(bool)
    prepared = {name: frame.to_numpy().astype(bool)
                for name, frame in factors.items()}
    print(f"\n{'=' * 118}\n### {title}\n{'=' * 118}")
    print(f"    그물 안 {int(net_bool.sum()):,}자리")
    ladder_source: dict[int, list] = {}
    for hold, returns in returns_by_hold.items():
        holder = Net(returns, pd.DataFrame(net_bool, index=net_frame.index,
                                           columns=net_frame.columns), n_dates)
        print(f"\n  ── {hold}거래일 보유 · 성적 잴 수 있는 자리 {holder.total:,}개 "
              f"· 합격선 {PASS_MARK:.0f}%")
        print(f"  {'후보':<30}{'해당':>5}" + "".join(f"{y:>9}년      " for y in WINDOWS))
        passed = []
        for name, factor in prepared.items():
            mark, worst = show(name, holder.share(factor), holder.run(factor))
            if mark == "○ 합격":
                passed.append((worst, name, holder.share(factor)))
        passed.sort(key=lambda item: -item[0])
        ladder_source[hold] = passed
        if passed:
            print(f"  ▶ 합격 {len(passed)}개 — 가장 나쁜 창이 좋은 순")
            for rank, (worst, name, share) in enumerate(passed, 1):
                step = LADDER[rank - 1] if rank <= len(LADDER) else 0
                print(f"     {rank}. [{step:>2}점] {name}  "
                      f"(최악 {worst:+.1f}p · 해당 {share:.0f}%)")
        else:
            print("  ▶ 합격 0개")
    _ladder(title, ladder_source)


def _ladder(title: str, source: dict[int, list]) -> None:
    print(f"\n  ◆ {title} — 40·30·20·10 계단")
    for hold, passed in source.items():
        if not passed:
            print(f"    {hold}일: 합격 0개 → 배점 없음(0점 만점)")
            continue
        cells = " · ".join(
            f"{LADDER[i]}점 {name}" for i, (_w, name, _s) in enumerate(passed[:4]))
        total = sum(LADDER[:min(4, len(passed))])
        print(f"    {hold}일: {cells}   → {total}점 만점")


# ── 지표 만들기 ──────────────────────────────────────────────────────────
def build():
    wide = load_wide()
    close, high, low = wide["close"], wide["high"], wide["low"]
    volume, open_ = wide["volume"], wide["open"]
    dates = close.index
    codes = list(close.columns)

    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["stocks"]
    names = {code: entry["name"] for code, entry in roster.items()}
    themes_of = {code: [t for t in entry["themes"]] for code, entry in roster.items()
                 if code in close.columns}
    members: dict[str, list[str]] = {}
    for code, group in themes_of.items():
        for theme in group:
            members.setdefault(theme, []).append(code)
    members = {name: group for name, group in members.items() if len(group) >= 3}
    themes_of = {code: [t for t in group if t in members]
                 for code, group in themes_of.items()}

    keep = np.array([not _excluded(names.get(code, "")) for code in codes])
    print(f"명부 {len(codes):,}종목 · 테마 있는 것 {sum(1 for c in themes_of if themes_of[c]):,}개"
          f" · 3종목 이상 테마 {len(members):,}개 · 우선주·스팩·리츠 제외 {int((~keep).sum()):,}개")

    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(len(codes), axis=1),
                         index=dates, columns=codes)
    # 앱은 daily.tail(248)의 High 최대값을 쓴다. 오늘이 그 최대값이면 days_ago=0.
    high248 = high.rolling(248, min_periods=248).max()
    at_high = high >= high248
    days_ago = order - order.where(at_high).ffill()
    from_high = (close / high248 - 1.0) * 100.0

    sma20 = close.rolling(20, min_periods=20).mean()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    gap20 = (close / sma20 - 1.0) * 100.0

    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr_pct = true_range.rolling(14, min_periods=14).mean() / close * 100.0

    turnover = close * volume                          # 하루 거래대금(원)
    avg_value = volume.rolling(20, min_periods=20).mean() * close   # 앱 avg_trading_value
    liquidity = np.maximum(turnover, close * volume.shift(1))       # 앱 liquidity_value
    liquidity = pd.DataFrame(liquidity, index=dates, columns=codes)

    change = close.pct_change() * 100.0
    ret5 = (close / close.shift(5) - 1.0) * 100.0
    ret20 = (close / close.shift(20) - 1.0) * 100.0
    ret60 = (close / close.shift(60) - 1.0) * 100.0

    index_table = pd.read_csv(DAILY / "KOSPI.csv")
    index_table["date"] = pd.to_datetime(index_table["date"], format="%Y%m%d")
    kospi = index_table.set_index("date")["close"].reindex(dates).ffill()

    return dict(
        wide=wide, close=close, high=high, low=low, open=open_, volume=volume,
        dates=dates, codes=codes, names=names, themes_of=themes_of, members=members,
        keep=keep, days_ago=days_ago, from_high=from_high, high248=high248,
        sma20=sma20, sma50=sma50, sma200=sma200, gap20=gap20, atr_pct=atr_pct,
        turnover=turnover, avg_value=avg_value, liquidity=liquidity,
        change=change, ret5=ret5, ret20=ret20, ret60=ret60, kospi=kospi,
    )


def returns_for(ctx, holds=HOLDS) -> dict[int, pd.DataFrame]:
    """다음 거래일 **시가**에 사서 hold거래일 뒤 **종가**에 판다."""
    return {hold: (ctx["close"].shift(-hold) / ctx["open"].shift(-1) - 1.0) * 100.0
            for hold in holds}


def theme_frame(ctx, source: pd.DataFrame, how: str = "mean") -> pd.DataFrame:
    out = {}
    for name, group in ctx["members"].items():
        block = source[group]
        out[name] = block.sum(axis=1) if how == "sum" else block.mean(axis=1)
    return pd.DataFrame(out, index=ctx["dates"])


def top_share(ctx, values: pd.DataFrame, share: float) -> pd.DataFrame:
    """그날 테마를 줄 세워 **상위 몇 %** 안에 드는 테마에 속하면 True.

    한국 테마는 266개다. 미국(20개)의 '3등·5등'을 그대로 쓰면 1%가 돼 버린다.
    """
    ranks = values.rank(axis=1, pct=True, ascending=False)
    winners = ranks <= share
    out = {}
    for code in ctx["codes"]:
        group = [t for t in ctx["themes_of"].get(code, ()) if t in winners.columns]
        out[code] = winners[group].any(axis=1) if group else False
    return pd.DataFrame(out, index=values.index, columns=ctx["codes"]).fillna(False)


def together(ctx, mask: pd.DataFrame) -> pd.DataFrame:
    """같은 테마에서 함께 걸린 종목 수 (앱 화면의 '테마 동반'과 같은 뜻)."""
    counts = pd.DataFrame(0, index=ctx["dates"], columns=ctx["codes"], dtype="int16")
    for name, group in ctx["members"].items():
        n = mask[group].sum(axis=1).to_numpy()
        for code in group:
            counts[code] = np.maximum(counts[code].to_numpy(), n)
    return counts


def theme_measures(ctx) -> dict[str, pd.DataFrame]:
    """테마를 줄 세울 잣대들. 앱 배점 넷 + 미국에서 1~4등을 쓸어간 확산 계열."""
    close, sma20 = ctx["close"], ctx["sma20"]
    kospi_change = ctx["kospi"].pct_change() * 100.0
    theme_change = theme_frame(ctx, ctx["change"])
    return {
        # ── 앱 _theme_score가 쓰는 넷 ──
        "[앱35] 코스피 대비 당일 강도": theme_change.sub(kospi_change, axis=0),
        "[앱25] 구성종목 상승 비율": theme_frame(ctx, (ctx["change"] > 0).astype("float32") * 100),
        "[앱20] 3%↑ 종목 비율": theme_frame(ctx, (ctx["change"] >= 3).astype("float32") * 100),
        "[앱20] 테마 총 거래대금": theme_frame(ctx, ctx["turnover"], how="sum"),
        # ── 미국에서 값을 한 확산 계열 ──
        "20일선 위 종목 비율": theme_frame(ctx, (close > sma20).astype("float32") * 100),
        "5일간 오른 종목 비율": theme_frame(ctx, (close.pct_change(5) > 0).astype("float32") * 100),
        "20일간 오른 종목 비율": theme_frame(ctx, (close.pct_change(20) > 0).astype("float32") * 100),
        "덜 빠졌나(고점 대비)": theme_frame(ctx, ctx["from_high"]),
        # ── 미국에서 국면마다 뒤집힌 수익률 계열 ──
        "20일 수익률": theme_frame(ctx, ctx["ret20"]),
        "60일 수익률": theme_frame(ctx, ctx["ret60"]),
        "거래대금 늘었나": theme_frame(
            ctx, ctx["turnover"].rolling(5, min_periods=3).mean()
            / ctx["turnover"].rolling(60, min_periods=30).mean() * 100),
    }


def app_theme_score(ctx) -> pd.DataFrame:
    """앱 _theme_score 100점을 테마×날짜로 그대로 계산한다."""
    def scale(frame, lo, hi, points):
        return ((frame - lo) / (hi - lo)).clip(0, 1) * points

    kospi_change = ctx["kospi"].pct_change() * 100.0
    theme_change = theme_frame(ctx, ctx["change"])
    up_ratio = theme_frame(ctx, (ctx["change"] > 0).astype("float32") * 100)
    strong = theme_frame(ctx, (ctx["change"] >= 3).astype("float32") * 100)
    total_value = theme_frame(ctx, ctx["turnover"], how="sum")
    return (scale(theme_change.sub(kospi_change, axis=0), -2.0, 9.0, 35)
            + scale(up_ratio, 30, 98, 25)
            + scale(strong, 0, 65, 20)
            + scale(np.log10((total_value / 1e8).clip(lower=1e-6)), 1.0, 4.2, 20))


# ── ① 눌림목 찾기 ────────────────────────────────────────────────────────
def part_pullback(ctx) -> None:
    close, dates, codes = ctx["close"], ctx["dates"], ctx["codes"]
    theme_count = pd.DataFrame(
        np.repeat(np.array([[len(ctx["themes_of"].get(c, ())) for c in codes]]),
                  len(dates), axis=0), index=dates, columns=codes)
    keep = pd.DataFrame(np.repeat(ctx["keep"][None, :], len(dates), axis=0),
                        index=dates, columns=codes)

    # 앱 순서 그대로: 테마 2개↑ → 유동성 200억↑ → **유동성 상위 50** → 신고가 뒤 1~30일
    liquid = (theme_count >= 2) & keep & (ctx["liquidity"] >= 2e10)
    rank = ctx["liquidity"].where(liquid).rank(axis=1, ascending=False, method="first")
    scan = liquid & (rank <= 50)
    net = (scan & (ctx["days_ago"] >= 1) & (ctx["days_ago"] <= 30)
           & (ctx["from_high"] < 0)).fillna(False)

    counts = together(ctx, net)
    measures = theme_measures(ctx)
    gap_abs = ctx["gap20"].abs()
    factors = {
        # ── _pullback_quality 25점: 신고가 최근성 (20일 이내 만점 → 120일 0점) ──
        "[최근성] 신고가 뒤 1~10일": ctx["days_ago"] <= 10,
        "[최근성] 신고가 뒤 1~20일(만점)": ctx["days_ago"] <= 20,
        "[최근성] 신고가 뒤 21~30일": ctx["days_ago"] >= 21,
        # ── 25점: 20일선 이격 (±2% 만점 → ±8% 0점) ──
        "[이격] 20일선 ±2% 이내(만점)": gap_abs <= 2,
        "[이격] 20일선 ±5% 이내": gap_abs <= 5,
        "[이격] 20일선 ±8% 밖(0점)": gap_abs > 8,
        # ── 0점: 장기 추세 (2026-08-07에 뺐다. 앱 그물에서도 그런지 다시 본다) ──
        "[추세] 50일선 위": close > ctx["sma50"],
        "[추세] 200일선 위": close > ctx["sma200"],
        # ── 25점: 눌린 깊이 (−5~−20% 만점) ──
        "[깊이] 고점 대비 −2~−5%": (ctx["from_high"] > -5) & (ctx["from_high"] <= -2),
        "[깊이] 고점 대비 −5~−20%(만점)": (ctx["from_high"] > -20) & (ctx["from_high"] <= -5),
        "[깊이] 고점 대비 −20~−30%": (ctx["from_high"] > -30) & (ctx["from_high"] <= -20),
        "[깊이] 고점 대비 −30% 아래": ctx["from_high"] <= -30,
        # ── 15점: 수급 — 과거 자료가 없어 **못 잰다**(표에 안 넣는다) ──
        # ── 견줄 것 ──
        "변동성 4% 미만": ctx["atr_pct"] <= 4,
        "변동성 6%↑": ctx["atr_pct"] >= 6,
        "거래대금 500억↑": ctx["avg_value"] >= 5e10,
        "테마 동반 3개↑": counts >= 3,
        "테마 동반 5개↑": counts >= 5,
        "테마 20일선위비율 상위 20%": top_share(ctx, measures["20일선 위 종목 비율"], 0.20),
        "테마 덜빠졌나 상위 20%": top_share(ctx, measures["덜 빠졌나(고점 대비)"], 0.20),
        "테마 20일수익률 상위 20%": top_share(ctx, measures["20일 수익률"], 0.20),
    }
    factors = {k: v.reindex(index=dates, columns=codes).fillna(False)
               for k, v in factors.items()}
    run_part("① 한국 눌림목 찾기 — 앱 그물(테마 2개↑ · 유동성 200억↑ · 상위50 · "
             "신고가 뒤 1~30일 · 눌려 있음)",
             net, factors, returns_for(ctx), len(dates))

    # 앱은 여기에 '**신고가를 찍던 날**의 조건점수 75↑'를 더 건다(score_at_past, 2679줄).
    # 그 함수는 수급을 일부러 뺀 80점을 100점으로 환산하므로(2724줄
    # `raw_score / 80 * 100`), 75점 게이트 = **80점 만점에서 60점↑**이다.
    # 과거 자료로도 똑같이 잴 수 있는 게이트라 여기서는 그대로 건다.
    gate = _score80(ctx).to_numpy()
    back = np.arange(len(dates))[:, None] - ctx["days_ago"].fillna(9999).to_numpy().astype(int)
    ok_back = back >= 0
    peak_score = np.take_along_axis(gate, np.clip(back, 0, None), axis=0)
    gated = (net & pd.DataFrame(ok_back & (peak_score >= 60.0),
                                index=dates, columns=codes)).fillna(False)
    print(f"\n  · 참고 — 신고가 시점 조건점수 게이트(80점 만점에서 60점↑ = 화면의 75점)를 "
          f"더 걸면 {int(net.to_numpy().sum()):,}자리 → {int(gated.to_numpy().sum()):,}자리")
    run_part("①-b 같은 그물 + 신고가 시점 조건점수 75↑ 게이트", gated, factors,
             returns_for(ctx), len(dates))


def _score80(ctx) -> pd.DataFrame:
    """_stock_score에서 **잴 수 있는 세 항목만** 더한 80점 (수급·추세·상대강도 제외).

    앱의 계단(1907~1935줄)을 그대로 옮겼다.
    """
    high_points = ((ctx["from_high"] + 45) / 45).clip(0, 1) * 35.0
    value = ctx["avg_value"].to_numpy()
    liquidity = np.select(
        [value >= 5e10, value >= 2e10, value >= 1e10, value >= 3e9],
        [1.00, 0.87, 0.67, 0.40], default=0.13) * 20.0
    liquidity = np.where(np.isnan(value), 0.0, liquidity)
    atr = ctx["atr_pct"].to_numpy()
    risk = np.select([atr <= 4, atr <= 6, atr <= 9, atr <= 13],
                     [1.00, 0.80, 0.50, 0.20], default=0.0) * 25.0
    risk = np.where(np.isnan(atr), 0.0, risk)
    parts = pd.DataFrame(liquidity + risk, index=ctx["dates"], columns=ctx["codes"])
    total = high_points.fillna(0.0) + parts
    # 앱의 추격 금지 감점(1962~1965줄)도 그대로 뺀다.
    total = total - (ctx["ret5"] >= 25).astype("float32") * 12.0
    total = total - (ctx["change"] >= 20).astype("float32") * 12.0
    return total.clip(0.0, 100.0)


# ── ② 테마 순위 ──────────────────────────────────────────────────────────
def part_theme(ctx) -> None:
    dates, codes, close = ctx["dates"], ctx["codes"], ctx["close"]
    measures = theme_measures(ctx)
    factors = {}
    for label, values in measures.items():
        for share in (0.05, 0.20):
            factors[f"{label} 상위 {share:.0%}"] = top_share(ctx, values, share)
    app_score = app_theme_score(ctx)
    for share in (0.05, 0.20):
        factors[f"[앱] 테마 조건점수 100점 상위 {share:.0%}"] = top_share(ctx, app_score, share)
    factors = {k: v.reindex(index=dates, columns=codes).fillna(False)
               for k, v in factors.items()}

    # 그물이 없다 — 명부 전체. 국면(코스피 200일선 위/아래)으로만 가른다.
    has_theme = pd.DataFrame(
        np.repeat(np.array([[bool(ctx["themes_of"].get(c)) for c in codes]]),
                  len(dates), axis=0), index=dates, columns=codes)
    keep = pd.DataFrame(np.repeat(ctx["keep"][None, :], len(dates), axis=0),
                        index=dates, columns=codes)
    ready = close.notna() & has_theme & keep & ctx["sma200"].notna()
    kospi_up = ctx["kospi"] > ctx["kospi"].rolling(200, min_periods=200).mean()
    phase = pd.DataFrame(np.repeat(kospi_up.to_numpy()[:, None], len(codes), axis=1),
                         index=dates, columns=codes)
    print(f"\n  코스피 200일선 **위** {int(kospi_up.sum()):,}일 · "
          f"**아래** {int((~kospi_up).sum()):,}일")
    for label, mask in (("코스피 200일선 **위**", phase),
                        ("코스피 200일선 **아래**", ~phase)):
        run_part(f"② 한국 테마 순위 — 그물 없음(명부 전체) · 국면: {label}",
                 (ready & mask).fillna(False), factors, returns_for(ctx), len(dates))


# ── ③ 순위 7 ─────────────────────────────────────────────────────────────
def part_top7(ctx) -> None:
    dates, codes = ctx["dates"], ctx["codes"]
    app_score = app_theme_score(ctx)
    theme_change = theme_frame(ctx, ctx["change"])

    # 앱: 당일 등락률 상위 40개를 후보로 → 점수로 줄 세워 상위 20개.
    # (앱은 '직전 조회 상위권'도 후보에 남기지만 그건 상태값이라 과거로 못 되살린다.)
    cand = theme_change.rank(axis=1, ascending=False, method="first") <= 40
    ranked = app_score.where(cand).rank(axis=1, ascending=False, method="first")
    top20 = (ranked <= 20).fillna(False)

    # 테마마다 **거래대금 상위 8종목**만 심사한다.
    turnover = ctx["turnover"]
    net = np.zeros((len(dates), len(codes)), dtype=bool)
    index_of = {code: i for i, code in enumerate(codes)}
    for name, group in ctx["members"].items():
        if name not in top20.columns:
            continue
        picked = top20[name].to_numpy()
        if not picked.any():
            continue
        inside = (turnover[group].rank(axis=1, ascending=False, method="first") <= 8)
        block = inside.to_numpy() & picked[:, None]
        for j, code in enumerate(group):
            net[:, index_of[code]] |= block[:, j]
    net = pd.DataFrame(net, index=dates, columns=codes)
    net = (net & ctx["close"].notna()
           & pd.DataFrame(np.repeat(ctx["keep"][None, :], len(dates), axis=0),
                          index=dates, columns=codes)).fillna(False)

    # 상대강도 — 앱은 '그 테마 구성종목 20일 수익률의 중앙값'과 견준다.
    # 종목이 여러 테마면 앱은 심사된 테마 기준이라 여기서는 평균으로 대신한다.
    theme_ret20 = theme_frame(ctx, ctx["ret20"])
    own = pd.DataFrame({
        code: (theme_ret20[[t for t in ctx["themes_of"].get(code, ())
                            if t in theme_ret20.columns]].mean(axis=1)
               if any(t in theme_ret20.columns for t in ctx["themes_of"].get(code, ()))
               else pd.Series(np.nan, index=dates))
        for code in codes}, index=dates)
    relative = ctx["ret20"] - own

    factors = {
        # ── 신고가 35점 (앱은 −45~0을 자로 편다) ──
        "[신고가35] 고점 대비 −10%↑": ctx["from_high"] >= -10,
        "[신고가35] 고점 대비 −5%↑": ctx["from_high"] >= -5,
        "[신고가35] 고점 대비 −30% 아래": ctx["from_high"] <= -30,
        # ── 변동성 25점 ──
        "[변동성25] 4% 미만(만점)": ctx["atr_pct"] <= 4,
        "[변동성25] 6% 미만": ctx["atr_pct"] <= 6,
        "[변동성25] 9%↑": ctx["atr_pct"] >= 9,
        # ── 유동성 20점 ──
        "[유동성20] 거래대금 500억↑(만점)": ctx["avg_value"] >= 5e10,
        "[유동성20] 거래대금 200억↑": ctx["avg_value"] >= 2e10,
        "[유동성20] 거래대금 100억 미만": ctx["avg_value"] < 1e10,
        # ── 추세 0점 (거꾸로였다던 항목 — 앱 그물에서 다시 본다) ──
        "[추세0] 20일선 위": ctx["close"] > ctx["sma20"],
        "[추세0] 50일선 위": ctx["close"] > ctx["sma50"],
        "[추세0] 200일선 위": ctx["close"] > ctx["sma200"],
        # ── 상대강도 0점 ──
        "[상대강도0] 테마보다 앞섬": relative >= 0,
        "[상대강도0] 테마보다 +8%p↑": relative >= 8,
        "[상대강도0] 테마보다 −8%p↓": relative <= -8,
        # ── 수급 20점: 과거 자료 없음 — 못 잰다 ──
        # ── 감점 규칙 ──
        "[감점] 5일 +25%↑ 급등": ctx["ret5"] >= 25,
    }
    factors = {k: v.reindex(index=dates, columns=codes).fillna(False)
               for k, v in factors.items()}
    run_part("③ 한국 순위 7 — 앱 그물(테마 점수 상위 20 × 테마 안 거래대금 상위 8)",
             net, factors, returns_for(ctx), len(dates))


# ── ④ 상승장·급락 — kr_score_new.py가 이미 쟀다. 계단만 얹는다 ────────────
def part_old(ctx) -> None:
    close, high = ctx["close"], ctx["high"]
    dates, codes = ctx["dates"], ctx["codes"]
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(len(codes), axis=1),
                         index=dates, columns=codes)
    # kr_score_new.py와 **한 글자도 다르지 않게** 만든다(252일·shift(1) 기준).
    is_new_high = high >= high.rolling(252, min_periods=252).max().shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    from_high = (close / high.rolling(252, min_periods=60).max() - 1.0) * 100.0
    turnover = ctx["turnover"]
    value = turnover.rolling(50, min_periods=20).mean() / 1e8
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    atr = ctx["atr_pct"]
    flow = (turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean())

    kospi = ctx["kospi"]
    kospi_drop = (kospi / kospi.rolling(252, min_periods=60).max() - 1.0) * 100.0
    in_band = kospi_drop <= -15.0
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": kospi_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    deep = pd.DataFrame(np.repeat(deepest.to_numpy()[:, None], len(codes), axis=1),
                        index=dates, columns=codes)

    pool = value >= 50
    up_net = (pool & (days_since >= 3) & (days_since <= 10)
              & (from_peak <= -4.0) & (from_peak >= -6.0))
    down_net = deep & pool & (from_high <= -40.0) & (from_high >= -60.0)
    has_theme = pd.DataFrame(
        np.repeat(np.array([[bool(ctx["themes_of"].get(c)) for c in codes]]),
                  len(dates), axis=0), index=dates, columns=codes)

    measures = theme_measures(ctx)
    for title, raw, hold in (("상승장 (신고가 뒤 3~10일 · −4~−6%)", up_net, 250),
                             ("급락 후 반등장 (코스피 −15% 최저일 · −40~−60%)", down_net, 20)):
        net = (raw & has_theme).fillna(False)
        counts = together(ctx, net)
        factors = {
            "거래대금 500억↑": value >= 500,
            "거래대금 1,000억↑": value >= 1000,
            "거래대금 상위 20%": value.rank(axis=1, pct=True) >= 0.8,
            "최근 11일 −5%↑ 빠짐": recent11 <= -5.0,
            "최근 11일 안 올랐음": recent11 <= 0.0,
            "최근 11일 +5%↑ 오름": recent11 >= 5.0,
            "60일 안 올랐음": gain60 <= 0.0,
            "60일 40%↑ 오름": gain60 >= 40.0,
            "변동성 4% 미만": atr <= 4.0,
            # 기준서 3-3이 쓰는 '6%↑면 0점' 항목. kr_score_new는 뒤집힌 쪽만 쟀다.
            "변동성 6% 미만": atr < 6.0,
            "변동성 6%↑": atr >= 6.0,
            "테마 동반 3개↑": counts >= 3,
            "테마 동반 5개↑": counts >= 5,
            "테마 20일수익률 상위 5%": top_share(ctx, measures["20일 수익률"], 0.05),
            "테마 20일수익률 상위 20%": top_share(ctx, measures["20일 수익률"], 0.20),
            "테마 60일수익률 상위 20%": top_share(ctx, measures["60일 수익률"], 0.20),
            "테마 거래대금늘었나 상위 20%": top_share(
                ctx, theme_frame(ctx, flow), 0.20),
            "테마 덜빠졌나 상위 20%": top_share(ctx, measures["덜 빠졌나(고점 대비)"], 0.20),
            "테마 20일선위비율 상위 20%": top_share(ctx, measures["20일선 위 종목 비율"], 0.20),
            "테마 상승종목비율 상위 20%": top_share(
                ctx, measures["[앱25] 구성종목 상승 비율"], 0.20),
        }
        factors = {k: v.reindex(index=dates, columns=codes).fillna(False)
                   for k, v in factors.items()}
        run_part(f"④ 한국 {title} — 앱 그물 · 보유 {hold}일",
                 net, factors, returns_for(ctx, (hold,)), len(dates))


def main() -> None:
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    ctx = build()
    jobs = {"pullback": part_pullback, "theme": part_theme,
            "top7": part_top7, "old": part_old}
    if which == "all":
        for name in ("pullback", "top7", "theme", "old"):
            jobs[name](ctx)
    elif which in jobs:
        jobs[which](ctx)
    else:
        print(f"쓰는 법: python research/kr_parts.py [{' | '.join(jobs)} | all]")


if __name__ == "__main__":
    main()
