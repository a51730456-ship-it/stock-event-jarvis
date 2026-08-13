"""정해진 기준으로 **10년을 처음부터 다시** 꼼꼼히 검증한다 (2026-08-13).

상하님 지시 — *"기준이 정해졌으니 다시 기준대로 꼼꼼히 10년치 검토 다시 하고
생각하고 이야기해봐라."*

## 검증할 기준 (정해진 것)

  관문   나스닥 200일선 위 **하나만** (고점 -10% 안은 뺀다)
  그물   52주 신고가 뒤 3~10일 · 그 고점보다 4~15% 아래 · 테마 있는 종목
  배점   40 테마 2개↑ 걸침 / 30 같은 테마 4개↑ 동반 /
        20 빅50 안 / 10 뚫기 전 60일 50%↑ 올랐다

## 무엇을 확인하나 — 여섯 가지

  ① **앞 5년 · 뒤 5년** 둘 다에서 통하나 (제일 중요)
  ② **해마다** 통하나 — 한두 해가 전체를 끌고 가는 것 아닌가
  ③ **점수 계단이 단조로운가** — 점수 높을수록 정말 나은가, 네 보유기간 다
  ④ **항목끼리 겹치나** — 40점과 30점이 같은 종목을 가리키면 중복이다
  ⑤ **표본이 충분한가** — 70점 이상이 몇 자리뿐인가
  ⑥ **관문에서 '고점 -10% 안'을 빼면** 목록과 성적이 어떻게 바뀌나

쓰는 법:  python research/us_pullback_verify.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))


def stat(values):
    values = values[~np.isnan(values)]
    if values.size < 100:
        return None
    return values.size, (values > 0).mean() * 100, float(np.median(values))


def main() -> None:
    import jarvis3_data as j3
    from us_shares import load as load_shares
    from us_yearly import fetch

    wide = fetch()
    stocks = [c for c in wide["close"].columns if c != "QQQ"]
    close, high = wide["close"][stocks], wide["high"][stocks]
    opens, qqq = wide["open"][stocks], wide["close"]["QQQ"]
    dates = close.index

    high52 = high.rolling(252, min_periods=252).max()
    order = pd.DataFrame(np.arange(len(dates))[:, None].repeat(close.shape[1], axis=1),
                         index=dates, columns=close.columns)
    is_new_high = high >= high52.shift(1)
    peak = high.where(is_new_high).ffill()
    days_since = order - order.where(is_new_high).ffill()
    from_peak = (close / peak - 1.0) * 100.0
    gain60_at_peak = ((close / close.shift(60) - 1.0) * 100.0).where(is_new_high).ffill()
    shares = load_shares().reindex(close.columns)
    cap_rank = close.mul(shares, axis=1).rank(axis=1, ascending=False, method="min")

    themes_of: dict[str, set] = {}
    for theme in j3.US_THEMES:
        for stock in theme["stocks"]:
            if stock in close.columns:
                themes_of.setdefault(stock, set()).add(theme["name"])
    has_theme = pd.DataFrame(
        np.repeat(np.array([[s in themes_of for s in close.columns]]), len(dates), axis=0),
        index=dates, columns=close.columns)
    theme_count = pd.DataFrame(
        np.repeat(np.array([[len(themes_of.get(s, ())) for s in close.columns]]),
                  len(dates), axis=0), index=dates, columns=close.columns)

    ma200_up = qqq > qqq.rolling(200, min_periods=200).mean()
    qdrop = (qqq / qqq.rolling(252, min_periods=252).max() - 1.0) * 100.0
    wait_lo, wait_hi = j3.BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_lo, drop_hi = j3.BREAKOUT_PULLBACK_RULE["drop_band"]
    shape = (has_theme & (days_since >= wait_lo) & (days_since <= wait_hi)
             & (from_peak <= drop_hi) & (from_peak >= drop_lo)).fillna(False)

    def widen(series):
        return pd.DataFrame(np.repeat(series.fillna(False).to_numpy()[:, None],
                                      close.shape[1], axis=1),
                            index=dates, columns=close.columns)

    net_new = (shape & widen(ma200_up)).fillna(False)              # 정한 관문
    net_old = (shape & widen(ma200_up & (qdrop > -10.0))).fillna(False)  # 지금 앱

    def together_of(net):
        out = pd.DataFrame(0, index=dates, columns=close.columns)
        for theme in j3.US_THEMES:
            members = [s for s in theme["stocks"] if s in close.columns]
            if not members:
                continue
            count = net[members].sum(axis=1)
            for stock in members:
                out[stock] = np.maximum(out[stock], count)
        return out

    rets = {hold: (close.shift(-hold) / opens.shift(-1) - 1.0) * 100.0
            for hold, _ in HOLDS}

    def parts_of(net):
        return {
            "40 테마 2개↑ 걸침": theme_count >= 2,
            "30 같은 테마 4개↑": together_of(net) >= 4,
            "20 빅50 안": (cap_rank <= 50).fillna(False),
            "10 뚫기 전 60일 50%↑": (gain60_at_peak > 50.0).fillna(False),
        }

    def score_of(net):
        parts = parts_of(net)
        return (40 * parts["40 테마 2개↑ 걸침"].astype(float)
                + 30 * parts["30 같은 테마 4개↑"].astype(float)
                + 20 * parts["20 빅50 안"].astype(float)
                + 10 * parts["10 뚫기 전 60일 50%↑"].astype(float)), parts

    score, parts = score_of(net_new)
    total = int(net_new.to_numpy().sum())
    base = (widen(ma200_up) & close.notna()).fillna(False)

    print(f"\n{'=' * 116}\n### 정해진 기준으로 10년 재검증"
          f"\n### 관문 나스닥 200일선 위 · 그물 신고가 뒤 {wait_lo}~{wait_hi}일 · "
          f"고점보다 {abs(drop_hi):.0f}~{abs(drop_lo):.0f}% 아래\n{'=' * 116}")

    # ── ⑥ 관문을 바꾸면 ────────────────────────────────────────────────
    print("\n[⑥] 관문에서 '고점 -10% 안'을 빼면")
    for label, net in (("지금 앱 (200일선 위 + 고점 -10% 안)", net_old),
                       ("정한 것 (200일선 위만)", net_new)):
        cells = ""
        for hold, _n in HOLDS:
            got = stat(rets[hold].where(net).to_numpy().ravel())
            cells += "        —      " if not got else f"  {got[1]:>2.0f}번 {got[2]:>+6.1f}%"
        print(f"  {label:<34}{int(net.to_numpy().sum()):>7,}자리{cells}")

    # ── ① 앞 5년 · 뒤 5년 ──────────────────────────────────────────────
    mid = dates[len(dates) // 2]
    halves = (("앞 5년", dates < mid), ("뒤 5년", dates >= mid))
    print(f"\n[①] 앞 5년 · 뒤 5년 둘 다에서 통하나 (가른 날 {mid.date()})")
    print(f"  {'':<26}" + "".join(f"{n:>17}" for _h, n in HOLDS))
    for half, when in halves:
        window = pd.Series(when, index=dates)
        print(f"\n  ── {half} ──")
        for name, mask in (("아무 종목이나", base), ("그물 전체", net_new),
                           *((f"{k}", net_new & v.reindex_like(net_new).fillna(False))
                             for k, v in parts.items()),
                           ("70점 이상", net_new & (score >= 70))):
            sel = mask.loc[window.to_numpy()]
            cells = ""
            for hold, _n in HOLDS:
                got = stat(rets[hold].loc[window.to_numpy()].where(sel).to_numpy().ravel())
                cells += "       —      " if not got else f" {got[1]:>2.0f}번 {got[2]:>+6.1f}%"
            print(f"  {name:<26}{cells}")

    # ── ② 해마다 ──────────────────────────────────────────────────────
    print(f"\n[②] 해마다 (1년 보유 · 승률 / 수익 가운데값)")
    years = sorted({d.year for d in dates})
    print(f"  {'':<26}" + "".join(f"{y:>12}" for y in years))
    for name, mask in (("아무 종목이나", base), ("그물 전체", net_new),
                       ("40점 항목", net_new & (theme_count >= 2)),
                       ("70점 이상", net_new & (score >= 70))):
        cells = ""
        for year in years:
            window = np.array([d.year == year for d in dates])
            got = stat(rets[250][window].where(mask[window]).to_numpy().ravel())
            cells += f"{'—':>12}" if not got else f"{got[1]:>4.0f}번{got[2]:>+7.1f}"
        print(f"  {name:<26}{cells}")

    # ── ③ 계단이 단조로운가 ─────────────────────────────────────────────
    print(f"\n[③] 점수 계단이 네 보유기간 다 단조로운가")
    print(f"  {'':<26}{'자리':>8}{'몫':>5}" + "".join(f"{n:>17}" for _h, n in HOLDS))
    for lo, hi, label in ((70, 101, "70점 이상"), (40, 70, "40~60점"),
                          (10, 40, "10~30점"), (0, 10, "0점")):
        mask = net_new & (score >= lo) & (score < hi)
        count = int(mask.to_numpy().sum())
        cells = ""
        for hold, _n in HOLDS:
            got = stat(rets[hold].where(mask).to_numpy().ravel())
            cells += "       —      " if not got else f" {got[1]:>2.0f}번 {got[2]:>+6.1f}%"
        print(f"  {label:<26}{count:>8,}{count / max(total, 1) * 100:>4.0f}%{cells}")

    # ── ④ 항목끼리 겹치나 ──────────────────────────────────────────────
    print(f"\n[④] 항목끼리 겹치나 (그물 안에서 둘 다 붙는 비율)")
    names = list(parts)
    print(f"  {'':<26}" + "".join(f"{n[:14]:>16}" for n in names))
    for a in names:
        cells = ""
        mask_a = net_new & parts[a].reindex_like(net_new).fillna(False)
        for b in names:
            mask_b = net_new & parts[b].reindex_like(net_new).fillna(False)
            both = (mask_a.to_numpy() & mask_b.to_numpy()).sum()
            cells += f"{both / max(int(mask_a.to_numpy().sum()), 1) * 100:>15.0f}%"
        print(f"  {a:<26}{cells}")
    print("  (가로줄이 '이 항목이 붙은 자리 중 세로 항목도 붙은 비율')")

    # ── ⑤ 표본 ────────────────────────────────────────────────────────
    print(f"\n[⑤] 표본 — 그물 {total:,}자리 · "
          f"70점 이상 {int((net_new & (score >= 70)).to_numpy().sum()):,}자리")
    print("  ※ 지금 살아 있는 회사만 봤다. 망한 회사는 빠져 있어 실제보다 좋게 나온다.")


if __name__ == "__main__":
    main()
