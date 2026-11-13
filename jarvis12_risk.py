"""자비스12 기능 ④ — 목록이 한쪽으로 쏠렸나(흔들림 · 테마 쏠림) (2026-11-13 상하님 「너의 추천 차례로 다 해라」).

본뜬 곳 — Interactive Brokers 「Risk Navigator」(베타 = 2년 일간 수익률 · 업종별 위험). **보여 주기만 한다** — 점수 · 판정 ·
차례 · 성적표는 안 바꾼다.

  흔들림(베타) — 최근 2년(최대 504 거래일) 날마다 수익률로 잰 「QQQ 가 1 움직일 때 이 종목이 몇 움직였나」.
                 목록 값은 종목 베타의 단순 평균. 겹치는 날이 120일 안 되는 종목은 빼고(빈칸) 센다 — 0 으로 채우지 않는다.
  테마 쏠림    — 목록 종목의 첫째 소속 테마(표의 「소속 테마」와 같은 것)를 세어 많은 차례로.

자료는 화면이 이미 받아 둔 200종목 2년 일봉(jarvis3_data._universe_daily · QQQ 포함)만 읽는다 — 새로 받으러 가지 않는다.
"""
from __future__ import annotations

import math
import threading
import time

import jarvis3_data as j3

MODULE_REVISION = 2026111301

WINDOW = 504                 # 2년
MIN_OVERLAP = 120            # 이보다 적게 겹치면 못 잼
MARKET = "QQQ"
_MEMO: dict = {}
_LOCK = threading.Lock()
_MEMO_SECONDS = 1800.0


def _returns(frame):
    try:
        close = frame["Close"].astype(float).dropna()
    except Exception:
        return None
    if len(close) < 3:
        return None
    return close.pct_change().dropna().tail(WINDOW)


def beta_of(stock_frame, market_frame) -> float | None:
    """QQQ 대비 베타(공분산 ÷ 분산). 겹치는 날이 MIN_OVERLAP 보다 적거나 값이 이상하면 None."""
    left, right = _returns(stock_frame), _returns(market_frame)
    if left is None or right is None:
        return None
    try:
        joined = left.to_frame("s").join(right.to_frame("m"), how="inner").dropna()
    except Exception:
        return None
    if len(joined) < MIN_OVERLAP:
        return None
    var = float(joined["m"].var())
    if not var or not math.isfinite(var):
        return None
    value = float(joined["s"].cov(joined["m"])) / var
    return round(value, 2) if math.isfinite(value) else None


def theme_of(row: dict) -> str:
    """표의 「소속 테마」 첫째 이름(상승장 줄은 theme_id). 없으면 「테마 없음」."""
    themes = row.get("themes") or ()
    if isinstance(themes, str):
        themes = [part for part in themes.replace("·", ",").split(",") if part.strip()]
    first = (themes[0] if themes else None) or row.get("theme_id")
    return str(first).strip() if first else "테마 없음"


def summarize(rows: list, daily: dict | None = None) -> dict:
    """목록 줄들의 흔들림 · 테마 쏠림. daily 를 안 주면 받아 둔 일봉을 읽는다(새로 받지 않음)."""
    rows = [row for row in (rows or []) if isinstance(row, dict) and row.get("ticker")]
    out = {"ok": bool(rows), "count": len(rows), "beta": None, "measured": 0, "betas": [], "themes": [],
           "top_theme": None, "top_share": None}
    if not rows:
        return out
    if daily is None:
        try:
            daily, _meta, _members = j3._universe_daily(True)
        except Exception:
            daily = {}
    daily = daily or {}
    market = daily.get(MARKET)
    betas = []
    for row in rows:
        ticker = str(row.get("ticker")).upper()
        value = beta_of(daily.get(ticker), market) if market is not None else None
        betas.append((ticker, value))
    known = [value for _ticker, value in betas if value is not None]
    if known:
        out["beta"] = round(sum(known) / len(known), 2)
    out["measured"] = len(known)
    out["betas"] = sorted(((t, v) for t, v in betas if v is not None), key=lambda item: -item[1])
    counts: dict[str, int] = {}
    for row in rows:
        name = theme_of(row)
        counts[name] = counts.get(name, 0) + 1
    themes = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    out["themes"] = themes
    if themes:
        out["top_theme"], top = themes[0]
        out["top_share"] = round(top / len(rows) * 100)
    return out


def cached_summary(rows: list) -> dict:
    """같은 종목 묶음이면 30분 동안 다시 세지 않는다(화면이 다시 그릴 때마다 계산하지 않게)."""
    key = tuple(sorted(str(row.get("ticker")) for row in rows or [] if isinstance(row, dict)))
    now = time.time()
    with _LOCK:
        hit = _MEMO.get(key)
        if hit and now - hit[0] < _MEMO_SECONDS:
            return hit[1]
    value = summarize(rows)
    with _LOCK:
        _MEMO[key] = (now, value)
    return value


_PALETTE = ("#b48cff", "#4cc3ff", "#ffcf5c", "#3ddc97", "#ff9f5c")


def html(summary: dict, label: str) -> str:
    """표 위 한 덩이 — 흔들림 막대 + 테마 쏠림 막대 + (접힌) 종목별 값. 그릴 것이 없으면 빈 글."""
    if not summary or not summary.get("ok"):
        return ""
    count = int(summary.get("count") or 0)
    beta = summary.get("beta")
    parts = []
    if beta is not None:
        # 0.5 ~ 2.0 막대 위에 시장(1.0)과 이 목록 표시
        def at(value):
            return max(0.0, min(100.0, (float(value) - 0.5) / 1.5 * 100.0))
        move = round(float(beta) * 10)
        tone = "#3ddc97" if beta < 1.1 else "#ffcf5c" if beta < 1.5 else "#ff6b6b"
        parts.append(
            "<div class='j12rk-row'><span class='j12rk-k'>흔들림</span>"
            f"<b style='color:{tone}'>{float(beta):.2f}</b>"
            f"<span class='j12rk-d'>QQQ 가 10% 움직이면 이 목록은 약 {move}%</span></div>"
            "<div class='j12rk-gauge'><div class='j12rk-grad'></div>"
            f"<span class='j12rk-mk j12rk-mk1' style='left:{at(1.0):.1f}%'>시장 1.0</span>"
            f"<span class='j12rk-mk j12rk-mk2' style='left:{at(beta):.1f}%;color:{tone}'>이 목록</span></div>")
    themes = summary.get("themes") or []
    if themes:
        shown = themes[:4]
        rest = count - sum(n for _name, n in shown)
        bars, keys = [], []
        for index, (name, n) in enumerate(shown):
            color = _PALETTE[index % len(_PALETTE)]
            bars.append(f"<span style='flex:{n};background:{color}'></span>")
            keys.append(f"<span><i style='background:{color}'></i>{name} {n}</span>")
        if rest > 0:
            bars.append(f"<span style='flex:{rest};background:#3a5578'></span>")
            keys.append(f"<span><i style='background:#3a5578'></i>그 밖 {rest}</span>")
        share = summary.get("top_share")
        warn = share is not None and share >= 40
        parts.append(
            "<div class='j12rk-row'><span class='j12rk-k'>테마 쏠림</span>"
            f"<b style='color:{'#ffcf5c' if warn else '#e8f0fb'}'>{summary.get('top_theme')} {share}%</b>"
            + ("<span class='j12rk-d'>이 테마가 빠지면 목록이 같이 빠집니다</span>" if warn else "")
            + "</div>"
            f"<div class='j12rk-bar'>{''.join(bars)}</div><div class='j12rk-keys'>{''.join(keys)}</div>")
    if not parts:
        return ""
    measured = summary.get("measured")
    note = (f"{label} {count}종목 · 흔들림은 {measured}종목을 최근 2년 날마다 값으로 잼 · 보여 주기만(점수 · 차례 안 바꿈)"
            if beta is not None else f"{label} {count}종목 · 보여 주기만(점수 · 차례 안 바꿈)")
    top = summary.get("betas") or []
    detail = ""
    if top:
        cells = " · ".join(f"{t} {v:.2f}" for t, v in top[:5])
        detail = (f"<details class='j12rk-more'><summary>가장 크게 흔들리는 종목</summary>"
                  f"<div class='j12rk-d'>{cells}</div></details>")
    return (
        "<div class='j12rk-box'>"
        "<div class='j12rk-title'>📏 이 목록이 한쪽으로 쏠렸나</div>"
        + "".join(parts)
        + f"<div class='j12rk-note'>{note}</div>{detail}</div>"
    )


CSS = (
    "<style>"
    ".j12rk-box{background:#0d2340;border:1px solid #1f3a5f;border-radius:12px;padding:.55rem .75rem;margin:.35rem 0 .55rem;}"
    ".j12rk-title{font-weight:900;font-size:.92rem;color:#e8f0fb;margin-bottom:.25rem;}"
    ".j12rk-row{display:flex;flex-wrap:wrap;align-items:baseline;gap:.45rem;font-size:.86rem;margin-top:.2rem;}"
    ".j12rk-k{color:#8fa6c4;min-width:4.2rem;}"
    ".j12rk-d{color:#8fa6c4;font-size:.78rem;}"
    ".j12rk-gauge{position:relative;height:1.55rem;margin:.15rem 0 .1rem;}"
    ".j12rk-grad{position:absolute;left:0;right:0;top:.95rem;height:.42rem;border-radius:4px;"
    "background:linear-gradient(90deg,#3ddc97,#ffcf5c 50%,#ff6b6b);}"
    ".j12rk-mk{position:absolute;top:0;transform:translateX(-50%);font-size:.68rem;white-space:nowrap;}"
    ".j12rk-mk::after{content:'';position:absolute;left:50%;top:.85rem;width:2px;height:.75rem;background:currentColor;}"
    ".j12rk-mk1{color:#e8f0fb;}.j12rk-mk2{font-weight:800;}"
    ".j12rk-bar{display:flex;height:.62rem;border-radius:5px;overflow:hidden;margin:.25rem 0 .2rem;gap:2px;}"
    ".j12rk-keys{display:flex;flex-wrap:wrap;gap:.2rem .7rem;font-size:.74rem;color:#8fa6c4;}"
    ".j12rk-keys i{display:inline-block;width:.6rem;height:.6rem;border-radius:2px;margin-right:.25rem;vertical-align:-1px;}"
    ".j12rk-note{color:#6f86a4;font-size:.72rem;margin-top:.3rem;}"
    ".j12rk-more summary{cursor:pointer;color:#4cc3ff;font-size:.78rem;margin-top:.2rem;}"
    "</style>"
)
