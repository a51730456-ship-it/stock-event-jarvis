"""자비스13 관심종목 카드 — 현재가 · 등락 · 20일 선 · 「넣은 날부터 성적」(코스피와 나란히) (2026-10-30).

상하님 「자비스13 관심종목(5단계) — 다해라」 · 「다 넣어라」(자비스에 넣을 기능 ② 관심종목 「넣은 날부터 성적」).
셈 — 넣은 그 순간의 값(저장고 added_price)에서 지금 값까지. 같은 사이 코스피(kospi_at_add → 지금)를 나란히 둔다.
넣은 값이 비었으면(넣을 때 시세를 못 받음) 넣은 날 종가로 센다. 보여 주기만 한다 — 점수·판정에 안 쓴다.
화면은 이 파일의 계산만 부르고 받아 오는 일은 jarvis4_data 가 한다(얼린 파일 — 부르기만 한다).
"""

from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

MODULE_REVISION = 2026110301
SPARK_DAYS = 20


def load_frames(codes, loader, *, workers: int = 6) -> dict:
    """종목 일봉을 한꺼번에 나눠 받는다 — 하나가 실패해도 나머지는 그대로(그 종목만 None)."""
    codes = [str(code) for code in codes]
    if not codes:
        return {}

    def _one(code):
        try:
            frame = loader(code)
        except Exception:
            return code, None
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            return code, None
        return code, frame

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(codes)))) as pool:
        return dict(pool.map(_one, codes))


def _added_day(stock: dict) -> date | None:
    try:
        return pd.Timestamp(str(stock.get("added_at") or "")[:10]).date()
    except Exception:
        return None


def _close_on(frame, day: date | None):
    """그날(없으면 그 뒤 첫 장) 종가."""
    if frame is None or day is None:
        return None
    closes = frame["Close"].dropna()
    for stamp, value in closes.items():
        if pd.Timestamp(stamp).date() >= day:
            return float(value)
    return None


def card(stock: dict, frame, kospi) -> dict:
    """카드 한 장에 쓸 값. 못 받으면 ok=False(그 카드만 「시세를 못 받았습니다」)."""
    out = {"code": stock.get("code"), "name": stock.get("name") or stock.get("code"),
           "added_at": stock.get("added_at"), "added_day": _added_day(stock),
           "target_price": stock.get("target_price"), "ok": False}
    if frame is None or getattr(frame, "empty", True):
        return out
    closes = frame["Close"].dropna()
    if closes.empty:
        return out
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else None
    out.update({"ok": True, "last": last, "last_day": pd.Timestamp(closes.index[-1]).date(),
                "change_pct": (last / prev - 1.0) * 100.0 if prev else None,
                "spark": [float(value) for value in closes.iloc[-SPARK_DAYS:]]})
    day = out["added_day"]
    base = stock.get("added_price") or _close_on(frame, day)
    out["base"] = base
    out["since_pct"] = (last / base - 1.0) * 100.0 if base else None
    out["days"] = int(sum(1 for stamp in closes.index if day and pd.Timestamp(stamp).date() > day)) if day else None
    k_last = k_base = None
    if kospi is not None and not getattr(kospi, "empty", True) and "Close" in kospi:
        k_closes = kospi["Close"].dropna()
        if not k_closes.empty:
            k_last = float(k_closes.iloc[-1])
            k_base = stock.get("kospi_at_add") or _close_on(kospi, day)
    out["kospi_pct"] = (k_last / k_base - 1.0) * 100.0 if (k_last and k_base) else None
    out["beat_pp"] = (out["since_pct"] - out["kospi_pct"]
                      if out["since_pct"] is not None and out["kospi_pct"] is not None else None)
    return out


def _sign(value) -> str:
    if value is None:
        return "j4-muted"
    return "j4-up" if value > 0 else ("j4-down" if value < 0 else "j4-muted")


def _pct(value, unit: str = "%") -> str:
    return "—" if value is None else f"{value:+.1f}{unit}"


def _won(value) -> str:
    return "—" if value is None else f"{value:,.0f}원"


def spark_svg(values, *, width: int = 220, height: int = 44) -> str:
    """20일 종가 선 — 오른 기간이면 빨강, 내린 기간이면 파랑(한국장 색)."""
    values = [float(v) for v in (values or []) if v == v]
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    step = width / (len(values) - 1)
    points = " ".join(f"{i * step:.1f},{height - 3 - (v - low) / span * (height - 6):.1f}" for i, v in enumerate(values))
    color = "#ff5b5b" if values[-1] >= values[0] else "#4da6ff"
    return (f"<svg class='j13w-spark' viewBox='0 0 {width} {height}' preserveAspectRatio='none' aria-hidden='true'>"
            f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{points}'/></svg>")


def card_html(item: dict) -> str:
    name = html.escape(str(item.get("name") or ""))
    code = html.escape(str(item.get("code") or ""))
    # 자비스12 카드처럼 왼쪽 위에 둥근 네모 표(2026-11-03 화면 옷) — 한국 종목은 로고 그림이 없어 이름 첫 글자를 쓴다.
    badge_colors = ("#216eab", "#7a3fd1", "#0f8a74", "#b5532a", "#9a2d5c", "#3f6f1f")
    badge_color = badge_colors[sum(map(ord, code)) % len(badge_colors)] if code else badge_colors[0]
    badge = f"<span class='j13w-badge' style='background:{badge_color}'>{html.escape(str(item.get('name') or '?')[:1])}</span>"
    head = (f"<div class='j13w-top'>{badge}<div class='j13w-id'><span class='j13w-name'>{name}</span>"
            f"<span class='j13w-code'>{code}</span></div></div>")
    if not item.get("ok"):
        return (f"<div class='j13w-card'>{head}"
                "<div class='j13w-miss'>시세를 못 받았습니다 — 잠시 뒤 다시 엽니다.</div></div>")
    price = (f"<div class='j13w-price'><b>{_won(item['last'])}</b> "
             f"<span class='{_sign(item.get('change_pct'))}'>{_pct(item.get('change_pct'))}</span></div>")
    day = item.get("added_day")
    when = f"{day.month}월 {day.day}일" if day else "—"
    held = f" · {item['days']}거래일째" if item.get("days") else (" · 오늘 넣음" if item.get("days") == 0 else "")
    # 세 값은 칸 셋에 나눠 둔다 — 한 줄로 이으면 폰·PC 모두 「코스피보다」 값만 다음 줄로 밀렸다(2026-10-30 화면 확인).
    cells = "".join(
        f"<div><span>{label}</span><b class='{_sign(value)}'>{_pct(value, unit)}</b></div>"
        for label, value, unit in (("지금까지", item.get("since_pct"), "%"),
                                   ("같은 사이 코스피", item.get("kospi_pct"), "%"),
                                   ("코스피보다", item.get("beat_pp"), "%p")))
    since = (f"<div class='j13w-since'><div class='j13w-when'>넣은 날 {when} · {_won(item.get('base'))}{held}</div>"
             f"<div class='j13w-grid'>{cells}</div></div>")
    target = ""
    if item.get("target_price"):
        target = f"<div class='j13w-target j4-muted'>알림 값 {_won(item['target_price'])}</div>"
    return f"<div class='j13w-card'>{head}{price}{spark_svg(item.get('spark'))}{since}{target}</div>"


CSS = """<style>
.j13w-card{background:linear-gradient(145deg,#06345f 0%,#03264a 58%,#001d3c 100%);border:1px solid #bf9254a8;border-radius:17px;
  padding:11px 12px 10px;display:grid;gap:6px;min-width:0;color:#e7edf2;box-shadow:inset 0 1px #7bc9ff35,0 6px 16px #0006}
.j13w-card:hover{border-color:#d8ab68}
.j13w-top{display:flex;align-items:center;gap:8px;min-width:0}
.j13w-badge{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;flex:0 0 auto;color:#fff;font-weight:900;
  font-size:1.05rem;box-shadow:inset 0 1px #ffffff44,0 2px 5px #0008}
.j13w-id{display:grid;min-width:0}
.j13w-name{color:#f4faff;font-size:1.12rem;font-weight:900;letter-spacing:-.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.j13w-code{color:#9fb6c8;font-size:.78rem;font-variant-numeric:tabular-nums}
.j13w-price{font-size:1.3rem;font-weight:850;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.j13w-price b{color:#f4faff}
.j13w-spark{width:100%;height:44px;display:block}
.j13w-since{font-size:.9rem;line-height:1.45;font-variant-numeric:tabular-nums;display:grid;gap:5px;border-top:1px solid #94b5c52a;padding-top:6px}
.j13w-when{color:#9fb6c8;font-size:.8rem}
.j13w-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}
.j13w-grid > div{background:#04213f;border:1px solid #22324a;border-radius:9px;padding:4px 6px;display:grid;gap:1px;min-width:0}
.j13w-grid span{color:#9fb6c8;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.j13w-grid b{font-size:.95rem}
.j13w-miss{color:#9aa0aa;font-size:.95rem}
.j13w-target{font-size:.82rem}
.j13w-empty{border:1px dashed #7091af99;border-radius:14px;padding:18px;text-align:center;color:#c3d7e7;line-height:1.7}
.j13w-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:.2rem 0 .6rem}
.j13w-title{font-size:1.55rem;font-weight:900;color:#ffc94f;letter-spacing:-.02em}
.j13w-count{color:#9fb6c8;font-size:.95rem}
/* 카드 묶음 — 자비스12 처럼 한 통에 넣고 자리는 CSS 가 잡는다(PC 세 칸 · 폰 두 칸) */
div[class*="st-key-j13w_cards"]{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;column-gap:10px!important;
  row-gap:16px!important;align-items:start!important}
div[class*="st-key-j13w_cards"]>*{min-width:0!important;width:auto!important}
div[class*="st-key-j13w_item_"] .stButton button{min-height:30px!important;padding:2px 10px!important;font-size:.82rem!important;
  border-radius:15px!important;border:1px solid #b9965c!important;background:#062448!important;color:#eaf5ff!important}
@media (max-width: 600px){
  div[class*="st-key-j13w_cards"]{grid-template-columns:repeat(2,minmax(0,1fr))!important;column-gap:7px!important}
  .j13w-name{font-size:.98rem}.j13w-price{font-size:1.05rem}.j13w-badge{width:30px;height:30px;font-size:.9rem}
  .j13w-grid{grid-template-columns:1fr}.j13w-grid > div{display:flex;justify-content:space-between;gap:4px}
}
</style>"""
