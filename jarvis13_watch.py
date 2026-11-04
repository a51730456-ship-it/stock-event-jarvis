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

MODULE_REVISION = 2026110402
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
    """자비스12 관심종목 카드 모양(2026-11-04 상하님 「왠만한 것 다 찾아서 미국테마 형식을 따라」) — 작은 카드 한 장.
    위 — 둥근 네모 표 · 이름 · 코드 / 가운데 — 왼쪽 값·등락 · 오른쪽 20일 선 / 아래 — 「•」 두 줄(넣은 날 · 넣은 날부터 성적).
    자세한 성적(기준 값 · 지금 · 같은 사이 코스피)은 카드 밑 「📈 넣은 날부터 성적」 표가 말한다(since_table_html)."""
    name = html.escape(str(item.get("name") or ""))
    code = html.escape(str(item.get("code") or ""))
    # 한국 종목은 로고 그림이 없어 이름 첫 글자를 쓴다(2026-11-03 화면 옷).
    badge_colors = ("#216eab", "#7a3fd1", "#0f8a74", "#b5532a", "#9a2d5c", "#3f6f1f")
    badge_color = badge_colors[sum(map(ord, code)) % len(badge_colors)] if code else badge_colors[0]
    badge = f"<span class='j13w-badge' style='background:{badge_color}'>{html.escape(str(item.get('name') or '?')[:1])}</span>"
    head = (f"<div class='j13w-top'>{badge}<div class='j13w-id'><span class='j13w-name'>{name}</span>"
            f"<span class='j13w-code'>{code}</span></div></div>")
    if not item.get("ok"):
        return (f"<div class='j13w-card'>{head}"
                "<div class='j13w-miss'>시세를 못 받았습니다 — 잠시 뒤 다시 엽니다.</div></div>")
    price = (f"<div class='j13w-price'><b>{_won(item['last'])}</b>"
             f"<span class='{_sign(item.get('change_pct'))}'>{_pct(item.get('change_pct'))}</span></div>")
    day = item.get("added_day")
    when = f"{day.month}월 {day.day}일" if day else "—"
    held = f" · {item['days']}거래일째" if item.get("days") else (" · 오늘 넣음" if item.get("days") == 0 else "")
    notes = (f"<div class='j13w-notes'><div class='j13w-note'>넣은 날 {when} · {_won(item.get('base'))}{held}</div>"
             f"<div class='j13w-note'>지금까지 <b class='{_sign(item.get('since_pct'))}'>{_pct(item.get('since_pct'))}</b>"
             f" · 코스피보다 <b class='{_sign(item.get('beat_pp'))}'>{_pct(item.get('beat_pp'), '%p')}</b></div>")
    if item.get("target_price"):
        notes += f"<div class='j13w-note j4-muted'>알림 값 {_won(item['target_price'])}</div>"
    notes += "</div>"
    return (f"<div class='j13w-card'>{head}<div class='j13w-mid'>{price}"
            f"<div class='j13w-chart'>{spark_svg(item.get('spark'), width=120, height=40)}</div></div>{notes}</div>")


def since_table_html(items: list) -> str:
    """카드 밑 「📈 넣은 날부터 성적」 표 — 자비스12 관심종목(jarvis12_watch_since)과 같은 칸. 코스피와 나란히 · 한국장 색.
    시세를 못 받은 종목은 줄을 그리되 값은 「—」(없는 것을 있는 것처럼 적지 않는다)."""
    rows = []
    for item in items:
        name = html.escape(str(item.get("name") or ""))
        code = html.escape(str(item.get("code") or ""))
        day = item.get("added_day")
        when = f"{day.month}월 {day.day}일" if day else "—"
        held = (f"{item['days']}거래일째" if item.get("days") else ("오늘 넣음" if item.get("days") == 0 else ""))
        ok = bool(item.get("ok"))
        cells = [
            f"<td class='j13ws-name'><b>{name}</b><small>{code}</small></td>",
            f"<td class='j13ws-name'><b>{when}</b><small>{held}</small></td>",
            f"<td>{_won(item.get('base')) if ok else '—'}</td>",
            f"<td>{_won(item.get('last')) if ok else '—'}</td>",
            f"<td class='{_sign(item.get('since_pct'))}'>{_pct(item.get('since_pct')) if ok else '—'}</td>",
            f"<td class='{_sign(item.get('kospi_pct'))}'>{_pct(item.get('kospi_pct')) if ok else '—'}</td>",
            f"<td class='{_sign(item.get('beat_pp'))}'>{_pct(item.get('beat_pp'), '%p') if ok else '—'}</td>",
        ]
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = ("<tr><th>종목</th><th>넣은 날</th><th>기준 값</th><th>지금</th><th>지금까지</th><th>같은 사이 코스피</th>"
            "<th>코스피보다</th></tr>")
    return ("<div class='j13ws'><div class='j13ws-title'>📈 넣은 날부터 성적</div><div class='j13ws-scroll'>"
            f"<table class='j13ws-t'>{head}{''.join(rows)}</table></div></div>")


CSS = """<style>
.j13w-card{position:relative;height:auto;min-height:150px;box-sizing:border-box;background:linear-gradient(145deg,#06345f 0%,#03264a 58%,#001d3c 100%);
  border:1px solid #bf9254a8;border-radius:17px;padding:10px 10px 9px;min-width:0;color:#e7edf2;box-shadow:inset 0 1px #7bc9ff35,0 6px 16px #0006;
  overflow:hidden;transition:transform .12s ease-out,filter .12s ease-out,border-color .12s ease-out}
.j13w-card:after{content:"";position:absolute;right:-28px;bottom:-55px;width:130px;height:96px;border-radius:50%;
  background:radial-gradient(ellipse at 32% 24%,#0e5a843d,transparent 70%);pointer-events:none}
div[class*="st-key-j13w_item_"]:hover .j13w-card{transform:translateY(-4px);filter:brightness(1.12);border-color:rgba(150,220,255,.95)}
.j13w-top{display:flex;align-items:center;gap:8px;min-width:0;padding-right:28px}
.j13w-badge{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;flex:0 0 auto;color:#fff;font-weight:900;
  font-size:1.05rem;box-shadow:inset 0 1px #ffffff44,0 2px 5px #0008}
.j13w-id{display:grid;min-width:0}
.j13w-name{color:#f4faff;font-size:1.08rem;font-weight:900;letter-spacing:-.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.j13w-code{color:#9fb6c8;font-size:.76rem;font-variant-numeric:tabular-nums}
.j13w-mid{display:flex;align-items:center;gap:6px;margin:8px 0 6px;min-width:0}
.j13w-price{flex:1 1 auto;min-width:0;display:grid;font-size:1.12rem;font-weight:850;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.2}
.j13w-price b{color:#fff9eb;white-space:nowrap;font-size:clamp(.85rem,3.6vw,1.12rem)}
.j13w-price span{font-size:.88rem}
.j13w-chart{flex:0 0 42%;min-width:0}
.j13w-spark{width:100%;height:40px;display:block}
.j13w-notes{border-top:1px solid #94b5c52a;padding-top:5px;display:grid;gap:1px}
.j13w-note{font-size:.74rem;color:#e7edf2;line-height:1.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.j13w-note:before{content:"•";color:#7ee24b;margin-right:5px}
.j13w-miss{color:#9aa0aa;font-size:.92rem;margin-top:10px}
.j13w-empty{border:1px dashed #7091af99;border-radius:14px;padding:18px;text-align:center;color:#c3d7e7;line-height:1.7}
.j13w-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:.2rem 0 .6rem}
.j13w-title{font-size:1.55rem;font-weight:900;color:#ffc94f;letter-spacing:-.02em}
.j13w-count{color:#9fb6c8;font-size:.95rem}
/* 카드 묶음 — 자비스12 처럼 한 통에 넣고 자리는 CSS 가 잡는다(넓으면 셋 넘게 · 폰 두 칸 · auto-fill 165px) */
div[class*="st-key-j13w_cards"]{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(165px,1fr))!important;column-gap:9px!important;
  row-gap:14px!important;align-items:start!important}
div[class*="st-key-j13w_cards"]>*{min-width:0!important;width:auto!important}
/* 카드 어디를 눌러도 세부사항 — 속이 비치는 단추를 카드 위에 통째로 겹친다(자비스12 카드를 누르면 크게 뜨는 것과 같은 자리) */
div[class*="st-key-j13w_item_"]{position:relative!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_open_"]{position:absolute!important;inset:0!important;z-index:5!important;margin:0!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_open_"] *{width:100%!important;height:100%!important;max-width:none!important;margin:0!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_open_"] button{min-height:0!important;padding:0!important;border:0!important;border-radius:17px!important;
  background:transparent!important;box-shadow:none!important;color:transparent!important;cursor:zoom-in!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_open_"] button p{color:transparent!important}
/* ✕ 빼기 — 자비스12 처럼 카드 오른쪽 위 동그라미(주인만) */
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_remove_"]{position:absolute!important;right:7px!important;top:7px!important;z-index:8!important;
  width:26px!important;height:26px!important;margin:0!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_remove_"] button{min-height:26px!important;width:26px!important;height:26px!important;padding:0!important;
  border-radius:50%!important;border:1px solid #a9c7df!important;background:#062448!important;color:#fff!important;font-size:15px!important;line-height:1!important}
div[class*="st-key-j13w_item_"] div[class*="st-key-j13w_remove_"] button p{font-size:14px!important;color:#fff!important}
/* 「📈 넣은 날부터 성적」 표 — 자비스12 와 같은 판 */
.j13ws{margin:14px 0 6px;background:linear-gradient(145deg,#06345f 0%,#03264a 58%,#001d3c 100%);border:1px solid #bf9254a8;border-radius:17px;
  padding:12px 12px 6px;box-shadow:inset 0 1px #7bc9ff35,0 6px 16px #0006}
.j13ws-title{color:#ffc94f;font-size:1.15rem;font-weight:900;margin:0 0 6px}
.j13ws-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.j13ws-t{width:100%;min-width:560px;border-collapse:collapse;font-size:.86rem;font-variant-numeric:tabular-nums}
.j13ws-t th{color:#9fb6c8;font-weight:700;text-align:right;padding:6px 6px;border-bottom:1px solid #94b5c52a;white-space:nowrap}
.j13ws-t th:first-child,.j13ws-t th:nth-child(2){text-align:left}
.j13ws-t td{text-align:right;padding:7px 6px;border-bottom:1px solid #94b5c51a;color:#e7edf2;white-space:nowrap}
.j13ws-t td.j13ws-name{text-align:left}
.j13ws-name b{display:block;color:#f4faff}
.j13ws-name small{display:block;color:#9fb6c8;font-size:.72rem}
</style>"""
