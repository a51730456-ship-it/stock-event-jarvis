"""Independent JARVIS 7 presentation. No imports of any existing page renderer."""
from __future__ import annotations

import base64
import html
import json
import math
import re
from functools import lru_cache
from pathlib import Path


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def number(value, digits=2, signed=False):
    try:
        value = float(value)
        if not math.isfinite(value):
            return "—"
        return f"{value:+,.{digits}f}" if signed else f"{value:,.{digits}f}"
    except (ValueError, TypeError):
        return "—"


def pct(value):
    text = number(value, signed=True)
    return text + "%" if text != "—" else text


def tone(value):
    try:
        return "up" if float(value) >= 0 else "down"
    except (ValueError, TypeError):
        return "muted"


ICONS = {
    "home": '<path d="m3 10 9-7 9 7v10H15v-7H9v7H3z"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
    "market": '<path d="M4 20V12h3v8m4 0V4h3v16m4 0V8h3v12"/>',
    "records": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M8 10l2 2 5-5m-7 9h8"/>',
    "more": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "search": '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
    "bell": '<path d="M6 10a6 6 0 0 1 12 0v5l2 3H4l2-3zm4 11h4"/>',
    "arrow": '<path d="m9 5 7 7-7 7"/>',
    "shield": '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zm-4 9 3 3 5-6"/>',
    "chip": '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3M9 9h6v6H9z"/>',
    "cloud": '<path d="M6 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 6 6 0 0 1 0 11z"/>',
    "bolt": '<path d="m14 2-10 12h7l-1 8L21 9h-8z"/>',
    "rise": '<path d="m3 18 6-7 4 4 8-12m-7 0h7v7"/>',
    "rebound": '<path d="m2 4 8 16 5-10 3 4 4-10m-5 0h5v5"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 10v7m0-11v1"/>',
    "warning": '<path d="M10 4a2 2 0 0 1 4 0l8 15a2 2 0 0 1-2 3H4a2 2 0 0 1-2-3zM12 8v6m0 3v1"/>',
    "refresh": '<path d="M20 9a8 8 0 1 0 0 6M20 3v6h-6"/>',
    "plus": '<path d="M12 4v16M4 12h16"/>',
}


def icon(name):
    return f'<svg class="j7-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(name, ICONS["bolt"])}</svg>'


def button(body, view=None, *, cls="", label="", **event):
    if view:
        event = {"action": "nav", "view": view, **event}
    accessible=label or html.unescape(re.sub(r'<[^>]+>', ' ',body)).strip() or "선택"
    return f'<button type="button" class="j7-button {cls}" data-event="{esc(json.dumps(event, ensure_ascii=False))}" aria-label="{esc(accessible)}">{body}</button>'


def heading(title, caption="", symbol="bolt"):
    return f'<div class="j7-section-head"><h2>{icon(symbol)}{esc(title)}</h2><span>{esc(caption)}</span></div>'


def banner(title, subtitle, symbol="market"):
    return f'<section class="j7-banner j7-panel"><div><div class="j7-eyebrow">JARVIS 7 / US THEMES</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div><div class="j7-banner-art">{icon(symbol)}</div></section>'


def notice(text, warning=False):
    return f'<div class="j7-notice {"warning" if warning else ""}">{icon("warning" if warning else "info")}<span>{esc(text)}</span></div>'


def waiting(label="자료를 불러오고 있습니다", failed=False):
    return f'<div class="j7-wait {"failed" if failed else ""}"><span class="j7-dot"></span>{esc("조회하지 못했습니다. 잠시 후 다시 시도합니다." if failed else label)}</div>'


def ring(score, label="시장 국면", small=False):
    n = max(0, min(100, float(score))) if number(score) != "—" else 0
    return f'<div class="j7-gauge {"small" if small else ""}" role="img" aria-label="{esc(label)} {number(score,0)}점"><svg viewBox="0 0 240 240"><circle class="j7-orbit" cx="120" cy="120" r="113"/><circle class="j7-track" cx="120" cy="120" r="99"/><circle class="j7-arc" cx="120" cy="120" r="99" pathLength="100" stroke-dasharray="{n} 100" transform="rotate(-90 120 120)"/><circle class="j7-inner" cx="120" cy="120" r="87"/></svg><div class="j7-gauge-text"><strong>{number(score,0)}</strong><span>/ 100</span><b>{esc(label)}</b></div></div>'


def spark(values, change=None, *, large=False, labels=None, base=None):
    values = list(values or [])
    if len(values) < 2:
        return '<div class="j7-chart-empty">차트 자료 없음</div>'
    values = [float(v) for v in values if number(v) != "—"]
    if len(values) < 2:
        return '<div class="j7-chart-empty">차트 자료 없음</div>'
    w, h, pad = (900, 290, 32) if large else (240, 74, 6)
    low, high = min(values), max(values)
    if base is not None and number(base) != "—":
        low, high = min(low, float(base)), max(high, float(base))
    span = high - low or max(abs(high) * .01, 1)
    points = [(pad+i*(w-2*pad)/(len(values)-1), h-pad-(v-low)/span*(h-2*pad)) for i,v in enumerate(values)]
    path = " ".join(f'{"M" if i == 0 else "L"}{x:.1f},{y:.1f}' for i,(x,y) in enumerate(points))
    color = "#27e8a7" if (change if change is not None else values[-1]-values[0]) >= 0 else "#ff636e"
    grid = ""
    if large:
        for ratio in (0, .5, 1):
            y = pad + (h-2*pad)*ratio
            grid += f'<path d="M{pad},{y}H{w-pad}" stroke="#23415e" stroke-width="1"/><text x="{w-pad}" y="{y-6}" text-anchor="end" fill="#9eb2cb" font-size="13">{number(high-span*ratio)}</text>'
        if base is not None and number(base) != "—":
            y = h-pad-(float(base)-low)/span*(h-2*pad)
            grid += f'<path d="M{pad},{y}H{w-pad}" stroke="#aab8cb" stroke-dasharray="5 6"/><text x="{pad}" y="{y-7}" fill="#bac8dc" font-size="13">전일 종가 {number(base)}</text>'
    return f'<svg class="j7-spark {"large" if large else ""}" viewBox="0 0 {w} {h}" role="img" aria-label="가격 흐름">{grid}<path d="{path} L{points[-1][0]},{h-pad} L{pad},{h-pad}Z" fill="{color}" opacity=".07"/><path d="{path}" stroke="{color}" stroke-width="{2.2 if large else 2}" fill="none" stroke-linejoin="round"/><circle cx="{points[-1][0]}" cy="{points[-1][1]}" r="{4 if large else 2}" fill="{color}"/></svg>'


def logo(ticker):
    # Local cached logos only: a missing logo never blocks quotes or the page.
    safe = "".join(c for c in str(ticker) if c.isalnum() or c in ".-_")
    path = Path(__file__).parent / "cache" / "logos" / f"{safe}.webp"
    if path.is_file():
        return '<img alt="" src="data:image/webp;base64,' + _logo_bytes(str(path)) + '">'
    return f'<span>{esc(str(ticker)[:2])}</span>'


@lru_cache(maxsize=128)
def _logo_bytes(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def stock_tiles(stocks, cards, *, compact=False):
    items = []
    for stock in stocks:
        t = stock.get("ticker", "")
        card = cards.get(t) or {}
        chart = card.get("chart_today") or []
        body = f'<div class="j7-stock-id"><div class="j7-logo">{logo(t)}</div><div><b>{esc(t)}</b><small>{esc(stock.get("name",t))}</small></div></div><strong class="j7-price">{number(card.get("price"))}</strong><span class="{tone(card.get("change_pct"))}">{pct(card.get("change_pct"))}</span>{spark(chart,card.get("change_pct"))}<small class="j7-card-note">정규장 흐름{" · 이전 자료" if card.get("stale") else ""}</small>'
        items.append(button(body, "stock", ticker=t, cls="j7-stock-tile", label=f"{t} 종목 상세"))
    return '<div class="j7-stock-strip">' + ''.join(items) + '</div>' if items else waiting("등록한 종목이 없습니다")


def theme_icon(name):
    if any(s in name for s in ("반도체", "AI", "양자")):
        return "chip"
    if "보안" in name:
        return "shield"
    if any(s in name for s in ("클라우드", "소프트", "SaaS")):
        return "cloud"
    return "bolt"


def theme_rows(rows, limit=10):
    items = []
    for i,row in enumerate(rows[:limit], 1):
        score = row.get("score") if row.get("ok", True) else None
        width = max(0,min(100,float(score))) if score is not None else 0
        body = f'<span class="j7-rank">{i:02}</span><span class="j7-theme-icon">{icon(theme_icon(row.get("name","")))}</span><b>{esc(row.get("name"))}</b><span class="j7-bar"><i style="width:{width}%"></i></span><strong>{number(score,1)}</strong>{icon("arrow")}'
        items.append(button(body,"theme",theme=row.get("name"),cls="j7-theme-row",label=f'{row.get("name")} 테마 상세'))
    return ''.join(items) or waiting("테마 순위를 불러오고 있습니다")


def strategy_cards():
    return '<div class="j7-strategies">' + button(f'<div><small>STRATEGY 01</small><h2>상승장</h2><h3>신고가 눌림매수</h3><p>강한 추세 속 눌림 구간의<br>조건 충족 종목을 확인하세요.</p><span>후보 보기 {icon("arrow")}</span></div>{icon("rise")}',"breakout",cls="j7-strategy green") + button(f'<div><small>STRATEGY 02</small><h2>급락 후 반등장</h2><h3>낙폭종목</h3><p>기존 낙폭·반등 조건에 따른<br>종목과 선정 근거를 확인하세요.</p><span>후보 보기 {icon("arrow")}</span></div>{icon("rebound")}',"crash",cls="j7-strategy purple") + '</div>'


def metric(label, value, sub="", color="", help_text=""):
    return f'<div class="j7-metric" title="{esc(help_text)}"><small>{esc(label)}</small><strong class="{color}">{esc(value)}</strong><span>{esc(sub)}</span></div>'


def evidence(title, lines, symbol="info", badge=""):
    return f'<section class="j7-panel j7-evidence">{heading(title,badge,symbol)}<ul>' + ''.join(f'<li>{esc(line)}</li>' for line in lines if line) + '</ul></section>'


def stock_rows(rows, *, theme="", strategy="", guest=False):
    out = []
    for row in rows:
        t = row.get("ticker") or row.get("code") or ""
        m = row.get("metrics") or {}
        plan = row.get("plan") or {}
        score = row.get("final_score", row.get("score"))
        sub = plan.get("state") or row.get("status_text") or row.get("verdict") or row.get("decision") or "상세 보기"
        body = f'<div class="j7-logo">{logo(t)}</div><div class="j7-list-name"><b>{"★ " if row.get("both_theme_and_breakout") else ""}{esc(t)}</b><small>{esc(row.get("name") or row.get("stock_name") or t)}</small></div><div><b>{number(m.get("current",row.get("price")))}</b><small class="{tone(m.get("change_pct"))}">{pct(m.get("change_pct"))}</small></div>'
        if not guest:
            body += f'<div><b class="gold">{number(score,1)}점</b><small>{esc(sub)}</small></div>'
        body += icon("arrow")
        origin = row.get("top7_origin", "")
        out.append(button(body,"stock",ticker=t,theme=theme,strategy=strategy,origin=origin,cls="j7-list-row",label=f"{t} {origin+' ' if origin else ''}종목 상세"))
    return ''.join(out) or notice("현재 조건을 충족한 종목이 없습니다.")


CSS = """
.j7-shell{--navy:#041226;--line:#254563;--muted:#95abc8;--blue:#27baff;--gold:#f8cc70;font-family:Inter,'Segoe UI','Malgun Gothic',sans-serif;color:#edf5ff;font-size:15px;line-height:1.55;max-width:1140px;margin:0 auto;padding:8px 2px 110px;box-sizing:border-box;color-scheme:dark}
.j7-shell *{box-sizing:border-box}.j7-shell h1,.j7-shell h2,.j7-shell h3,.j7-shell p{margin:0}.j7-shell h1{font-size:46px;line-height:1.22;letter-spacing:-2px}.j7-shell h2{font-size:20px;letter-spacing:-.5px}.j7-shell h3{font-size:18px;font-weight:500}.j7-shell p{color:#b4c9e0}.j7-shell small{display:block;color:var(--muted);font-size:12px}.j7-shell .up{color:#2be1a7}.j7-shell .down{color:#ff6b76}.j7-shell .gold{color:var(--gold)}.j7-shell .muted{color:var(--muted)}
.j7-icon{width:24px;height:24px;flex-shrink:0;vertical-align:middle}.j7-button{font:inherit;color:inherit;border:0;cursor:pointer;text-align:left;background:none;padding:0}.j7-button:hover{filter:brightness(1.18);border-color:#45bfff}.j7-button:active{transform:scale(.99)}.j7-button:focus-visible,.j7-shell input:focus-visible,.j7-shell select:focus-visible{outline:2px solid #7ddfff;outline-offset:4px}.j7-button{transition:filter .12s,border-color .12s,transform .12s}.j7-shell a{color:#80d5ff}
.j7-header{display:flex;align-items:center;gap:14px;margin:8px 0 24px}.j7-brand{font-size:32px;font-weight:850;letter-spacing:-1.5px;white-space:nowrap}.j7-brand b{color:#3bc6ff}.j7-tag{font-size:12px;border:1px solid #31587d;border-radius:6px;padding:3px 9px;color:#c0d2e9}.j7-header-spacer{flex:1}.j7-status{display:flex;gap:7px;align-items:center;border:1px solid #245375;border-radius:30px;padding:6px 12px;font-size:12px;background:#071d32;white-space:nowrap}.j7-dot{width:7px;height:7px;display:inline-block;border-radius:50%;background:#35dcb0;box-shadow:0 0 12px #24baff55;flex-shrink:0}.j7-circle{display:grid;place-items:center;width:40px;height:40px;border:1px solid #284b6d;border-radius:50%;background:linear-gradient(145deg,#102e50,#051021)}
.j7-panel{border:1px solid var(--line);border-radius:22px;background:radial-gradient(ellipse at 15% 0,#0c2b514d,transparent 70%),linear-gradient(135deg,#091a32e6,#030e1fee);box-shadow:inset 0 1px 0 #8bbef21c,0 10px 24px #00000022;padding:22px;margin-bottom:18px;overflow:hidden}
.j7-hero{position:relative;display:grid;grid-template-columns:1.25fr 1fr;align-items:center;min-height:310px;padding:32px 40px;border-color:#287fd0;background:radial-gradient(ellipse at 95% 0,#1556a67d,transparent 55%),radial-gradient(ellipse at 20% 100%,#073e7288,transparent 60%),linear-gradient(120deg,#071d3b,#021126 65%);box-shadow:inset 0 1px 2px #80dcff88,0 0 22px #0775fc22}
.j7-hero:after,.j7-banner:after{content:'';position:absolute;pointer-events:none;width:75%;height:100px;bottom:-52px;right:-8%;border-radius:50%;border:1px solid #29bfff70;box-shadow:0 -8px 0 #29bfff19,0 -16px 0 #29bfff16,0 -24px 0 #29bfff13,0 -32px 0 #29bfff10,0 -40px 0 #29bfff0d;transform:rotate(-12deg)}
.j7-hero h1{font-size:44px;max-width:540px;margin:14px 0 20px;word-break:keep-all}.j7-hero h1 em{font-style:normal;color:var(--gold)}.j7-eyebrow{display:flex;align-items:center;gap:8px;color:#84cdfa;font-size:13px;letter-spacing:1px;font-weight:650}.j7-hero p{font-size:15px;max-width:470px;margin:0 0 20px}.j7-hero .j7-gauge{justify-self:center}.j7-footnote{font-size:12px;color:#8da9c9}.j7-gauge{width:260px;height:260px;position:relative;display:grid;place-items:center}.j7-gauge svg{position:absolute;width:100%;height:100%;overflow:visible}.j7-orbit{fill:none;stroke:#126fbb;stroke-width:1}.j7-track{fill:#08224a44;stroke:#123255;stroke-width:8}.j7-inner{fill:none;stroke:#19619655;stroke-width:1;stroke-dasharray:1 5}.j7-arc{fill:none;stroke:#f4d17f;stroke-width:8;filter:drop-shadow(0 0 6px #dcb36266)}.j7-gauge-text{text-align:center;z-index:1}.j7-gauge-text strong{display:block;font-size:72px;font-weight:750;line-height:1.1;letter-spacing:-3px}.j7-gauge-text span{color:#91aac9;font-size:16px}.j7-gauge-text b{display:block;color:#f6ce7a;font-size:16px;margin-top:8px}.j7-gauge.small{width:170px;height:170px}.j7-gauge.small strong{font-size:48px}.j7-gauge.small b{font-size:13px}
.j7-index-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.j7-index{padding:15px 18px;margin:0;border-radius:17px}.j7-index .j7-index-name{display:flex;justify-content:space-between;color:#c7d8ec;font-size:13px;margin-bottom:7px}.j7-index .j7-index-price{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.j7-index b{font-size:21px;letter-spacing:-.5px}.j7-index .j7-icon{width:17px;height:17px;color:#629dc7}.j7-index span{font-size:12px}.j7-spark{width:100%;height:60px;display:block;margin-top:6px}.j7-chart-empty{height:60px;display:grid;place-items:center;font-size:11px;color:#7890ad}.j7-spark.large{height:auto;max-height:320px}.j7-chart-labels{display:flex;justify-content:space-between;color:#8fa9c6;font-size:12px;padding:0 3%}
.j7-section-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:15px}.j7-section-head h2{display:flex;align-items:center;gap:9px}.j7-section-head h2 .j7-icon{color:#3ec5ff}.j7-section-head>span{font-size:12px;color:#9cafcb}.j7-section-link{font-size:12px;color:#a8cee9}.j7-theme-row{display:grid;grid-template-columns:28px 34px minmax(110px,1.05fr) minmax(45px,1.3fr) 48px 14px;align-items:center;gap:12px;width:100%;padding:10px 0;border-bottom:1px solid #21406066}.j7-theme-row:last-child{border:0}.j7-theme-row .j7-rank{color:#7895ba;font-size:15px;font-variant-numeric:tabular-nums}.j7-theme-row .j7-theme-icon{display:grid;place-items:center;width:32px;height:32px;border-radius:9px;background:linear-gradient(145deg,#1450a3,#072452);border:1px solid #2876bc;color:#b6e8ff}.j7-theme-row b{font-size:15px;font-weight:550}.j7-theme-row strong{font-size:19px;text-align:right;color:#e8d29c;font-variant-numeric:tabular-nums}.j7-theme-row>.j7-icon{width:14px;color:#7f9fbf}.j7-bar{height:7px;border-radius:3px;background:#122740;overflow:hidden}.j7-bar i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,#0860eb,#42caff);box-shadow:0 0 12px #28b4ff55}
.j7-stock-strip{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(140px,1fr);gap:10px;overflow-x:auto;padding:3px 1px 8px;scrollbar-width:thin;scrollbar-color:#346187 #07162c}.j7-stock-tile{min-width:0;border:1px solid #2e4c70;border-radius:16px;padding:14px 12px;background:linear-gradient(145deg,#102e50bb,#041325);overflow:hidden}.j7-stock-id{display:flex;align-items:center;gap:8px;margin-bottom:12px;min-width:0}.j7-stock-id b{font-size:17px;letter-spacing:-.3px}.j7-stock-id>div:last-child{min-width:0}.j7-stock-id small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px}.j7-logo{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:linear-gradient(145deg,#21446b,#092039);border:1px solid #466d9355;flex-shrink:0;overflow:hidden;color:#d5ebff;font-weight:800;font-size:13px}.j7-logo img{width:100%;height:100%;object-fit:contain}.j7-price{display:block;font-size:23px;letter-spacing:-.6px}.j7-stock-tile>.up,.j7-stock-tile>.down{font-size:13px}.j7-card-note{font-size:10px!important}.j7-stock-tile .j7-spark{height:52px}
.j7-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}.j7-two>.j7-panel{min-width:0}.j7-quick{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.j7-quick-item{padding:16px;border:1px solid #244968;border-radius:14px;background:linear-gradient(140deg,#0c2847,#05152a)}.j7-quick-item b{font-size:17px}.j7-quick-item strong{display:block;font-size:23px;margin:5px 0}.j7-notice{display:flex;align-items:center;gap:14px;border:1px solid #266495;border-radius:17px;background:linear-gradient(110deg,#062646,#061528);padding:18px 22px;margin-bottom:18px;font-size:14px;color:#c4d8ed}.j7-notice>.j7-icon{width:30px;height:30px;color:#42c3ff}.j7-notice.warning{border-color:#a38346;background:linear-gradient(110deg,#322b1c55,#091427);color:#e8cf95}.j7-notice.warning>.j7-icon{color:#ffcf6f}.j7-wait{padding:30px 16px;border:1px dashed #2a4663;border-radius:14px;margin-bottom:14px;color:#94abc7;font-size:13px;display:flex;align-items:center;gap:12px}.j7-wait.failed .j7-dot{background:#f8bd70}
.j7-banner{position:relative;display:flex;align-items:center;justify-content:space-between;padding:30px 34px;min-height:180px;border-color:#2669a9;background:radial-gradient(ellipse at 95% 60%,#09539e66,transparent 60%),linear-gradient(110deg,#082447,#021226)}.j7-banner h1{margin:10px 0 12px}.j7-banner-art>.j7-icon{width:112px;height:112px;color:#26baff;filter:drop-shadow(0 0 15px #058fff88);stroke-width:1}.j7-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:18px}.j7-summary-card{display:flex;align-items:center;flex-direction:column;justify-content:center;text-align:center;margin:0;padding:20px 10px}.j7-summary-card h3{font-size:15px;color:#c2d5ec}.j7-summary-card>strong{font-size:48px;color:#f0c577;margin:20px 0 8px}.j7-summary-card small{margin-top:6px}
.j7-strategies{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}.j7-strategy{position:relative;padding:25px 26px;border:1px solid #23756f;border-radius:20px;overflow:hidden;background:radial-gradient(ellipse at 100% 100%,#08645d55,transparent 70%),linear-gradient(140deg,#072b37,#021625)}.j7-strategy>div{position:relative;z-index:1}.j7-strategy h2{font-size:28px;color:#48e6be;margin:6px 0 0}.j7-strategy h3{color:#a0c9d6}.j7-strategy p{margin:12px 0 20px;font-size:13px}.j7-strategy span{display:inline-flex;align-items:center;gap:16px;border:1px solid #3a8776;border-radius:30px;padding:6px 13px;color:#8fe8d2;font-size:13px}.j7-strategy>svg{position:absolute;right:15px;top:52px;width:120px;height:120px;opacity:.25;color:#3becbd;stroke-width:1.1;filter:drop-shadow(0 0 10px #17bba2)}.j7-strategy.purple{border-color:#6651a8;background:radial-gradient(ellipse at 100% 100%,#6230ad44,transparent 70%),linear-gradient(140deg,#141c42,#071329)}.j7-strategy.purple h2,.j7-strategy.purple>svg{color:#b38bff}.j7-strategy.purple span{border-color:#66528c;color:#c9b2fc}
.j7-nav{position:fixed;z-index:90;bottom:16px;left:50%;transform:translateX(-50%);width:min(780px,calc(100% - 32px));display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #31628a;border-radius:26px;background:linear-gradient(180deg,#0c2c4ef5,#031022f5);box-shadow:0 -4px 28px #0007,inset 0 1px 0 #b3d5ed40;backdrop-filter:blur(18px);padding:10px 8px}.j7-nav button{display:flex;align-items:center;flex-direction:column;gap:5px;padding:5px 0;color:#8fa4bf;font-size:12px;text-align:center;min-height:51px}.j7-nav .j7-icon{width:25px;height:25px}.j7-nav button.active{color:#29c7ff;text-shadow:0 0 14px #2ec3ff55}.j7-nav button.active>.j7-icon{filter:drop-shadow(0 0 7px #22b8ff88)}
.j7-search{display:flex;gap:12px;margin-bottom:22px}.j7-shell input,.j7-shell select{font:inherit;color:#e4efff;background:#071b32;border:1px solid #365d83;border-radius:12px;padding:12px 14px;min-width:0}.j7-search input{flex:1;border-color:#2c9eee;box-shadow:0 0 15px #0776e92a}.j7-submit{padding:11px 20px;background:linear-gradient(135deg,#147dd4,#125091);border:1px solid #46b9fc;border-radius:12px;font:inherit;color:white;cursor:pointer}.j7-search input::placeholder{color:#829bbb}.j7-list-row{display:flex;align-items:center;gap:14px;width:100%;padding:13px 15px;margin-bottom:8px;border:1px solid #234866;border-radius:14px;background:linear-gradient(120deg,#0d2c4c77,#051326)}.j7-list-name{flex:1;min-width:0}.j7-list-name small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:270px}.j7-list-row>div:not(.j7-logo){min-width:0}.j7-list-row>div:nth-last-child(2){text-align:right}.j7-list-row>div:nth-last-child(3){min-width:90px}.j7-list-row>.j7-icon{width:16px;color:#91bad8}.j7-search-row{display:flex;gap:9px;align-items:center}.j7-search-row>.j7-list-row{flex:1}.j7-search-row>.j7-circle{margin-bottom:8px}
.j7-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px;margin:20px 0}.j7-metric{border:1px solid #2b4e70;background:linear-gradient(145deg,#0b284777,#031023);border-radius:15px;padding:17px 12px;min-width:0;text-align:center}.j7-metric strong{display:block;font-size:24px;margin:8px 0 4px;letter-spacing:-.5px}.j7-metric>span{display:block;color:#9aafc9;font-size:12px}.j7-detail-title{display:flex;align-items:center;gap:14px;margin:12px 0}.j7-detail-title>.j7-logo{width:58px;height:58px;font-size:23px}.j7-detail-title h1{font-size:40px}.j7-decision{border-color:#9b814f;padding:24px 28px;background:radial-gradient(ellipse at 0 100%,#72592333,transparent 75%),#071427}.j7-decision.danger{border-color:#bd4556;background:radial-gradient(ellipse at 0 0,#861f3333,transparent 70%),#081122}.j7-decision h2{font-size:28px;color:#f6c26c;margin-bottom:8px}.j7-decision.danger h2{color:#ff6876}.j7-decision p{font-size:14px}.j7-chart-tabs{display:flex;gap:4px;background:#02101f;border:1px solid #263e5a;border-radius:12px;padding:5px;margin-bottom:14px}.j7-chart-tabs button{flex:1;text-align:center;padding:8px;border-radius:9px;color:#93abc7;font-size:14px}.j7-chart-tabs button.active{background:#124172;color:#e8f8ff}.j7-evidence ul{padding:0 0 0 18px;margin:12px 0 0;color:#b3c7e0}.j7-evidence li{margin:7px 0;font-size:14px}.j7-evidence .j7-section-head{margin-bottom:8px}.j7-shell details{border:1px solid #294765;border-radius:13px;padding:13px 17px;margin-bottom:16px;background:#07182c}.j7-shell summary{cursor:pointer;color:#b4d6f2}.j7-shell table{width:100%;border-collapse:collapse;font-size:13px}.j7-shell td,.j7-shell th{padding:11px 8px;border-bottom:1px solid #254362;text-align:left}.j7-table-scroll{overflow-x:auto}.j7-shell th{color:#88afd0;white-space:nowrap}.j7-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}.j7-toolbar button{padding:7px 14px;border:1px solid #345572;border-radius:20px;font-size:13px;color:#b5cce4}.j7-empty{padding:24px;color:#9cafc9}.j7-manage-form{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.j7-manage-form input{flex:1;min-width:120px}.j7-footer{color:#7590b0;font-size:11px;margin:20px 0}.j7-section-footer{display:flex;justify-content:flex-end;margin-top:12px}.j7-shell button[disabled]{opacity:.4;cursor:not-allowed}
"""


JS = """
export default function(component) {
  const {data, parentElement, setTriggerValue} = component;
  let root = parentElement.querySelector('.j7-mount');
  if (!root) {root = document.createElement('div'); root.className='j7-mount'; parentElement.appendChild(root);}
  root.dataset.embedded=window.self!==window.top?'true':'false';
  const before = root.dataset.route;
  if (root._markup !== data.html) {
    const open = [...root.querySelectorAll('details[open]')].map(d=>d.id);
    const drafts=[...root.querySelectorAll('form[data-action]')].map(f=>({action:f.dataset.action,fields:[...f.querySelectorAll('input,select')].map(x=>({name:x.name,value:x.value}))}));
    const focused = root.contains(document.activeElement) ? document.activeElement : null;
    const fieldName = focused?.name;
    const value = focused?.value;
    root.innerHTML = data.html;
    root._markup = data.html;
    for(const id of open) {const d=root.querySelector('#'+id); if(d)d.open=true;}
    if(before===data.route)for(const draft of drafts){const form=[...root.querySelectorAll('form[data-action]')].find(f=>f.dataset.action===draft.action);if(form)for(const field of draft.fields){const el=[...form.elements].find(x=>x.name===field.name);if(el)el.value=field.value;}}
    if(fieldName && before===data.route){const f=[...root.querySelectorAll('input')].find(x=>x.name===fieldName);if(f){f.value=value;f.focus({preventScroll:true});}}
  }
  root.dataset.route = data.route;
  if(performance.getEntriesByName('j7:interaction:start').length){root.dataset.responseMs=Math.round(performance.measure('j7:interaction','j7:interaction:start').duration);performance.clearMarks('j7:interaction:start');}
  if(before && before!==data.route) window.scrollTo({top:0,behavior:'instant'});
  const track = () => {performance.clearMarks('j7:interaction:start');performance.clearMeasures('j7:interaction');performance.mark('j7:interaction:start');};
  const click = (e) => {const el=e.target.closest('[data-event]');if(!el || el.disabled)return;e.preventDefault();track();setTriggerValue('event',JSON.parse(el.dataset.event));};
  const submit = (e) => {const form=e.target.closest('form[data-action]');if(!form)return;e.preventDefault();track();const fields=Object.fromEntries(new FormData(form));setTriggerValue('event',{action:form.dataset.action,...fields});};
  root.addEventListener('click',click);root.addEventListener('submit',submit);
  const timer = setTimeout(()=>{if(!document.hidden)setTriggerValue('event',{action:'poll'});}, data.pending?1600:120000);
  const visible=()=>{if(!document.hidden)setTriggerValue('event',{action:'poll'});};
  document.addEventListener('visibilitychange',visible);
  return ()=>{clearTimeout(timer);root.removeEventListener('click',click);root.removeEventListener('submit',submit);document.removeEventListener('visibilitychange',visible);};
}
"""
