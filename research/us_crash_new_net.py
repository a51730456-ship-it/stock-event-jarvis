"""급락 후 반등 — **새 그물**에서 배점 항목을 다시 잰다 (2026-08-12).

왜 다시 재나. 그물이 바뀌면 배점도 다시 재야 한다. 그물이 좁을 때 값을 하던 항목이
넓은 그물에서는 아무것도 안 가르는 일이 실제로 있다(테마 동반이 그 예다 — 하루에
몇 개 안 걸릴 때는 '함께 걸렸다'가 뜻이 있지만, 하루에 수십 개가 걸리면 거의 전부가
'동반 2개 이상'이 되어 순위를 못 가른다).

**옛 그물** — 나스닥이 고점 대비 −10~−20%인 **구간의 최저일 하루** · 종목 −20~−30% · 250일
**새 그물** — 나스닥이 고점 대비 **−6% 아래인 날 전부**(구간에 있는 동안 매일)
             · 종목 **−20~−50%**(−20~−30% 칸과 −30~−50% 칸 둘 다)
             · 보유는 안 정한다 → **60·120·250거래일 셋 다 따로** 잰다

보유를 셋 다 따로 재는 이유. 같은 항목이 보유기간에 따라 뜻이 뒤집힌다(실제로 겪었다).
'덜 빠진 종목'은 짧게 들면 유리하고 길게 들면 불리해질 수 있다. 하나로 뭉뚱그리면
어느 쪽 얘기인지 모르게 된다.

**잣대는 `us_verify.py`에 못박힌 것 그대로 쓴다. 여기서 바꾸지 않는다.**
  · 창 2년·3년·4년을 한 달(21거래일)에 한 번씩 민다
  · 견주는 상대는 **같은 그물 안의 나머지**다 (아무 종목이 아니다)
  · 승률로 이긴 창 비율과 수익률로 이긴 창 비율이 **둘 다 65% 이상**이어야 합격
  · 두 무리 각 30건 미만인 창은 버리고, 남은 창이 20개 미만이면 판정하지 않는다

**해당 비율 85% 초과 또는 10% 미만이면 합격이어도 '못 가름'으로 적는다.**
거의 전부가 해당하거나 거의 아무도 해당 안 하면, 합격이든 아니든 순위를 못 가른다.

지표 만드는 방식은 앱(`jarvis3_data._series_metrics`)과 맞춘 `us_parts.py`를 그대로 베꼈다.
  high52 = 최근 252일 High의 최대값 · from_high = (종가/high52 − 1)×100
  atr_pct = 14일 평균 진폭 / 종가 × 100 · dollar = 50일 평균 거래대금
명부는 `US_THEMES`에 속한 종목만 쓴다(테마 없는 종목은 테마 항목이 늘 거짓이라 뺀다).

쓰는 법:  PYTHONIOENCODING=utf-8 python research/us_crash_new_net.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from us_verify import MIN_SIDE, MIN_WINDOWS, PASS_MARK, WINDOWS, score, verdict  # noqa: E402
from us_theme_rank import per_theme, top_rank  # noqa: E402

HOLDS = (60, 120, 250)
HOLD_NAME = {60: "3개월(60일)", 120: "6개월(120일)", 250: "1년(250일)"}

QQQ_GATE = -6.0                 # 나스닥이 이보다 더 빠진 날이 새 그물이다
STOCK_BAND = (-50.0, -20.0)     # 종목 낙폭 두 칸을 합친 범위
SHARE_HIGH = 85.0               # 이보다 많이 해당하면 못 가름
SHARE_LOW = 10.0                # 이보다 적게 해당해도 못 가름

STEPS = (40, 30, 20, 10)        # 배점 계단


def mark_of(result: dict, share: float) -> str:
    """us_verify의 판정에 '못 가름' 한 겹을 더 얹는다."""
    base = verdict(result)
    if base == "○ 합격" and not (SHARE_LOW <= share <= SHARE_HIGH):
        return "✎ 못 가름"
    return base


def worst_of(result: dict) -> float | None:
    values = [item["win_worst"] for item in result.values() if item]
    return min(values) if values else None


def show(name: str, share: float, result: dict, mark: str) -> None:
    cells = ""
    for years in WINDOWS:
        item = result.get(years)
        cells += (f"{'—':^16}" if not item else
                  f"{item['win_share']:>4.0f}/{item['median_share']:>3.0f}%({item['n']:>3})")
    worst = worst_of(result)
    tail = "     —" if worst is None else f"{worst:+6.1f}p"
    print(f"  {name:<30}{share:>5.0f}%  {cells}  {mark:<10} 최악 {tail}")


def build(wide: dict) -> dict:
    """앱과 같은 방식으로 지표를 만든다."""
    import jarvis3_data as j3

    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close = wide["close"][stocks]
    high = wide["high"][stocks]
    low = wide["low"][stocks]
    volume = wide["volume"][stocks]
    opens = wide["open"][stocks]
    qqq = wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    from_high = (close / high52 - 1.0) * 100.0
    sma20 = close.rolling(20, min_periods=20).mean()

    prev = close.shift(1)
    true_range = pd.concat([(high - low).stack(), (high - prev).abs().stack(),
                            (low - prev).abs().stack()], axis=1).max(axis=1).unstack()
    atr_pct = true_range.rolling(14, min_periods=14).mean() / close * 100.0
    turnover = close * volume
    dollar = turnover.rolling(50, min_periods=20).mean()
    recent11 = (close / close.shift(11) - 1.0) * 100.0
    gain60 = (close / close.shift(60) - 1.0) * 100.0
    qqq_drop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)

    measures = {
        "테마 덜 빠졌나": per_theme(from_high, j3.US_THEMES),
        "테마 5일 오른 비율": per_theme(
            (close.pct_change(5) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 20일 오른 비율": per_theme(
            (close.pct_change(20) > 0).astype(float) * 100, j3.US_THEMES),
        "테마 20일선 위 비율": per_theme(
            (close > sma20).astype(float) * 100, j3.US_THEMES),
        "테마 20일 수익률": per_theme(close.pct_change(20) * 100, j3.US_THEMES),
        "테마 60일 수익률": per_theme(close.pct_change(60) * 100, j3.US_THEMES),
        "테마 거래대금 늘었나": per_theme(
            turnover.rolling(5, min_periods=3).mean()
            / turnover.rolling(60, min_periods=30).mean() * 100, j3.US_THEMES),
    }

    return {
        "j3": j3, "stocks": stocks, "close": close, "opens": opens, "qqq": qqq,
        "dates": dates, "high52": high52, "from_high": from_high, "atr_pct": atr_pct,
        "dollar": dollar, "recent11": recent11, "gain60": gain60, "qqq_drop": qqq_drop,
        "themes_of": themes_of, "has_theme": has_theme, "measures": measures,
        "valid": close.notna() & high52.notna(),
    }


def together(net: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    """같은 테마에서 함께 걸린 종목 수 (앱의 _attach_theme_together와 같은 뜻)."""
    close = ctx["close"]
    counts = pd.DataFrame(0, index=ctx["dates"], columns=close.columns)
    for theme in ctx["j3"].US_THEMES:
        members = [s for s in theme["stocks"] if s in close.columns]
        if not members:
            continue
        n = net[members].sum(axis=1)
        for stock in members:
            counts[stock] = np.maximum(counts[stock], n)
    return counts


def candidates(net: pd.DataFrame, ctx: dict, *, with_bands: bool) -> dict:
    """잴 후보를 모은다. 그물이 달라지면 '테마 동반'도 달라지니 그물마다 다시 만든다."""
    counts = together(net, ctx)
    from_high, atr, dollar = ctx["from_high"], ctx["atr_pct"], ctx["dollar"]
    out = {
        "같은 테마 동반 2개↑": counts >= 2,
        "같은 테마 동반 3개↑": counts >= 3,
        "같은 테마 동반 4개↑": counts >= 4,
        "같은 테마 동반 5개↑": counts >= 5,
        "최근 11일 안 올랐음": ctx["recent11"] <= 0,
        "최근 11일 -5%↑ 빠짐": ctx["recent11"] <= -5,
        "최근 11일 -10%↑ 빠짐": ctx["recent11"] <= -10,
        "60일 안 올랐음": ctx["gain60"] <= 0,
        "60일 40%↑ 오름": ctx["gain60"] >= 40,
        "변동성 3% 미만": atr < 3,
        "변동성 4% 미만": atr < 4,
        "변동성 6%↑": atr >= 6,
        "거래대금 5억달러↑": dollar >= 5e8,
        "거래대금 상위 절반": dollar.rank(axis=1, pct=True, ascending=False) <= 0.5,
        "종목 낙폭 -20~-30%": from_high >= -30.0,
        "종목 낙폭 -30~-50%": from_high < -30.0,
    }
    for label, values in ctx["measures"].items():
        for top in (3, 5):
            out[f"{label} 상위 {top}등"] = top_rank(
                values, ctx["themes_of"], ctx["close"].columns, top)
    if with_bands:
        drop = ctx["qqq_drop"]
        for lo, hi, name in ((-12.0, -6.0, "6~12%"), (-18.0, -12.0, "12~18%"),
                             (-24.0, -18.0, "18~24%"), (-30.0, -24.0, "24~30%"),
                             (-1e9, -30.0, "30% 아래")):
            flag = (drop <= hi) & (drop > lo)
            out[f"[날] 나스닥 {name}"] = pd.DataFrame(
                np.repeat(flag.to_numpy()[:, None], ctx["close"].shape[1], axis=1),
                index=ctx["dates"], columns=ctx["close"].columns)
    return out


def run(title: str, net: pd.DataFrame, rets: pd.DataFrame, ctx: dict,
        factors: dict) -> dict:
    dates, close = ctx["dates"], ctx["close"]
    net = net.fillna(False)
    inside = net.to_numpy()
    total = int(inside.sum())
    days = int(net.any(axis=1).sum())
    print(f"\n{'=' * 118}\n### {title}"
          f"\n### 그물 안 {total:,}자리 · 신호 난 날 {days:,}일\n{'=' * 118}")
    print(f"  {'후보':<30}{'해당':>5}  " + "".join(f"{y:>6}년        " for y in WINDOWS)
          + "  판정        가장 나쁜 창")

    found: dict[str, dict] = {}
    for name, factor in factors.items():
        factor = factor.reindex(index=dates, columns=close.columns).fillna(False)
        share = (factor.to_numpy() & inside).sum() / max(total, 1) * 100
        result = score(rets, net, factor)
        mark = mark_of(result, share)
        show(name, share, result, mark)
        found[name] = {"mark": mark, "share": share, "worst": worst_of(result),
                       "result": result}

    # '[날] ~'은 그날 모든 종목에 똑같이 붙는다. 같은 날 안에서 종목을 못 가르니
    # 배점 계단에 얹지 않는다. 잰 값은 아래 참고 칸에 따로 적는다.
    passed = [(v["worst"], k, v["share"]) for k, v in found.items()
              if v["mark"] == "○ 합격" and not k.startswith("[날]")]
    passed.sort(key=lambda item: -item[0])
    print()
    if passed:
        print(f"  ▶ 합격 {len(passed)}개 — 가장 나쁜 창이 좋은 순")
        for rank, (worst, name, share) in enumerate(passed, 1):
            print(f"     {rank}. {name}  (가장 나쁜 창 {worst:+.1f}p · 해당 {share:.0f}%)")
        print("\n  ▶ 배점표 (상위 넷을 40·30·20·10에 얹는다)")
        for step, (worst, name, share) in zip(STEPS, passed):
            print(f"     {step:>3}점  {name:<28} 가장 나쁜 창 {worst:+.1f}p · 해당 {share:.0f}%")
        if len(passed) < len(STEPS):
            print(f"     ※ 합격이 {len(passed)}개뿐이라 계단 {len(STEPS) - len(passed)}칸이 빈다.")
    else:
        print("  ▶ 합격 0개 — 이 보유기간에서는 얹을 항목이 없다.")

    blocked = [(k, v["share"], v["worst"]) for k, v in found.items()
               if v["mark"] == "✎ 못 가름"]
    if blocked:
        print(f"\n  ▶ 잣대는 넘었지만 못 가름 {len(blocked)}개 (해당 비율이 "
              f"{SHARE_HIGH:.0f}% 초과 또는 {SHARE_LOW:.0f}% 미만)")
        for name, share, worst in sorted(blocked, key=lambda x: -x[1]):
            tail = "  —  " if worst is None else f"{worst:+.1f}p"
            print(f"     · {name}  (해당 {share:.0f}% · 가장 나쁜 창 {tail})")

    day_level = [(k, v) for k, v in found.items()
                 if k.startswith("[날]") and v["mark"] == "○ 합격"]
    if day_level:
        print("\n  ▶ 참고 · 잣대는 넘었지만 계단에 안 얹는 '그날' 항목"
              " (같은 날 안에서는 종목을 못 가른다)")
        for name, item in day_level:
            print(f"     · {name}  (가장 나쁜 창 {item['worst']:+.1f}p"
                  f" · 해당 {item['share']:.0f}%)")
    return found


def main() -> None:
    from us_yearly import fetch

    wide = fetch()
    ctx = build(wide)
    close, opens, dates = ctx["close"], ctx["opens"], ctx["dates"]
    valid, has_theme, from_high = ctx["valid"], ctx["has_theme"], ctx["from_high"]
    qqq_drop = ctx["qqq_drop"]

    def spread(flag: pd.Series) -> pd.DataFrame:
        return pd.DataFrame(np.repeat(flag.to_numpy()[:, None], close.shape[1], axis=1),
                            index=dates, columns=close.columns)

    rets = {h: (close.shift(-h) / opens.shift(-1) - 1.0) * 100.0 for h in HOLDS}

    stock_lo, stock_hi = STOCK_BAND
    new_net = (spread((qqq_drop <= QQQ_GATE).fillna(False)) & valid & has_theme
               & (from_high <= stock_hi) & (from_high >= stock_lo)).fillna(False)

    print(f"명부 {len(ctx['stocks'])}종목 중 테마 있는 것 {len(ctx['themes_of'])}개만 쓴다"
          f"  ·  {dates[0].date()} ~ {dates[-1].date()} {len(dates):,}거래일")
    print(f"잣대(us_verify 고정): 창 {WINDOWS[0]}·{WINDOWS[1]}·{WINDOWS[2]}년 · 한 달에 한 번 밀기"
          f" · 두 무리 각 {MIN_SIDE}건↑ · 창 {MIN_WINDOWS}개↑ · 합격선 {PASS_MARK:.0f}%")
    print("칸은 '승률로 이긴 창% / 수익률로 이긴 창%(창 개수)'. 견주는 상대는 같은 그물 안의 나머지다.")
    gate_days = int((qqq_drop <= QQQ_GATE).fillna(False).sum())
    print(f"새 그물의 날: 나스닥이 고점 대비 {QQQ_GATE:.0f}% 아래인 날 {gate_days:,}일"
          f" ({gate_days / len(dates) * 100:.0f}%)")

    factors = candidates(new_net, ctx, with_bands=True)
    per_hold: dict[int, dict] = {}
    for hold in HOLDS:
        per_hold[hold] = run(
            f"새 그물 · 보유 {HOLD_NAME[hold]} — 나스닥 -6% 아래 아무 날 · 종목 -20~-50%",
            new_net, rets[hold], ctx, factors)

    # ── 보유기간 셋 사이에서 순서가 뒤집히는가 ──────────────────────────────
    print(f"\n\n{'=' * 118}\n### 보유기간 셋을 나란히 — 순서가 뒤집히는 항목 찾기\n{'=' * 118}")
    ranks: dict[int, dict[str, int]] = {}
    for hold in HOLDS:
        ordered = sorted(((v["worst"], k) for k, v in per_hold[hold].items()
                          if v["mark"] == "○ 합격" and not k.startswith("[날]")),
                         key=lambda x: -x[0])
        ranks[hold] = {name: i + 1 for i, (_, name) in enumerate(ordered)}

    names = list(factors)
    print(f"  {'후보':<30}" + "".join(f"{HOLD_NAME[h]:<22}" for h in HOLDS))
    for name in names:
        cells = ""
        for hold in HOLDS:
            item = per_hold[hold][name]
            rank = ranks[hold].get(name)
            tag = f"{rank}등" if rank else "  "
            worst = item["worst"]
            worst_text = "  —  " if worst is None else f"{worst:+5.1f}p"
            cells += f"{item['mark']:<10}{worst_text} {tag:<4}"
        print(f"  {name:<30}{cells}")

    print("\n  ── 뒤집힘 ──")
    flipped = []
    for name in names:
        marks = {per_hold[h][name]["mark"] for h in HOLDS}
        if "○ 합격" in marks and ("✗ 거꾸로" in marks or "△ 안 됨" in marks):
            detail = " / ".join(f"{HOLD_NAME[h]} {per_hold[h][name]['mark']}" for h in HOLDS)
            flipped.append(f"     · {name}: {detail}")
    print("\n".join(flipped) if flipped else "     (합격↔불합격이 뒤집히는 항목 없음)")

    print("\n  ── 등수가 두 계단 넘게 움직인 항목 ──")
    moved = []
    for name in names:
        got = [ranks[h][name] for h in HOLDS if name in ranks[h]]
        if len(got) >= 2 and max(got) - min(got) >= 2:
            detail = " / ".join(
                f"{HOLD_NAME[h]} {ranks[h].get(name, '-')}등" for h in HOLDS)
            moved.append(f"     · {name}: {detail}")
    print("\n".join(moved) if moved else "     (없음)")

    # ── 옛 그물 — 무엇이 떨어졌나 ──────────────────────────────────────────
    band_lo, band_hi = ctx["j3"].CRASH_MARKET_BAND
    in_band = ((qqq_drop <= band_hi) & (qqq_drop >= band_lo)).fillna(False)
    episode = (in_band & ~in_band.shift(1, fill_value=False)).cumsum().where(in_band)
    deepest = pd.Series(False, index=dates)
    for _, group in pd.DataFrame({"e": episode, "d": qqq_drop}).dropna().groupby("e"):
        deepest.loc[group["d"].idxmin()] = True
    old_lo, old_hi = ctx["j3"].CRASH_REBOUND_RULES[0]["band"]
    old_hold = int(ctx["j3"].CRASH_REBOUND_RULES[0]["hold_days"])
    old_net = (spread(deepest) & valid & has_theme
               & (from_high <= old_hi) & (from_high >= old_lo)).fillna(False)
    old_rets = (close.shift(-old_hold) / opens.shift(-1) - 1.0) * 100.0
    old_factors = candidates(old_net, ctx, with_bands=False)
    old = run(f"옛 그물 · 보유 {old_hold}거래일 — 나스닥 -10~-20% 구간 최저일 · 종목 -20~-30%",
              old_net, old_rets, ctx, old_factors)

    print(f"\n\n{'=' * 118}\n### 옛 그물에서 합격이던 항목이 새 그물에서 어떻게 됐나\n{'=' * 118}")
    old_pass = [k for k, v in old.items() if v["mark"] == "○ 합격"]
    if not old_pass:
        print("  옛 그물에서 합격한 항목이 없다.")
    for name in old_pass:
        cells = "".join(f"{HOLD_NAME[h]} {per_hold[h][name]['mark']}   " for h in HOLDS)
        keeps = any(per_hold[h][name]["mark"] == "○ 합격" for h in HOLDS)
        print(f"  {'유지' if keeps else '탈락'}  {name:<30}{cells}")

    dropped = [n for n in old_pass
               if all(per_hold[h][n]["mark"] != "○ 합격" for h in HOLDS)]
    print(f"\n  ▶ 옛 그물 합격 {len(old_pass)}개 중 새 그물에서 **완전히 떨어진 것** "
          f"{len(dropped)}개")
    for name in dropped:
        detail = " / ".join(
            f"{HOLD_NAME[h]} {per_hold[h][name]['mark']}(해당 {per_hold[h][name]['share']:.0f}%)"
            for h in HOLDS)
        print(f"     · {name}: {detail}")

    print("\n※ 사는 것은 신호 다음 거래일 시가, 파는 것은 정해진 거래일 뒤 종가.")
    print("※ '못 가름'은 잣대는 넘었지만 해당 비율이 치우쳐 순위를 못 가르는 항목이다.")
    print("※ '[날] 나스닥 ~%'는 그날 모든 종목에 똑같이 붙는 값이라 같은 날 안에서는 "
          "순위를 못 가른다. 참고용이다.")


if __name__ == "__main__":
    main()
