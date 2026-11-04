"""자비스13 관심종목 — 자비스12 관심종목(홈) 모양 그대로 (2026-11-04 상하님 「관심종목도 미국테마 그대로 따라 만들어라」).

꾸밈은 jarvis13_home_css(자비스12 꾸밈을 글자 그대로 베낀 것 · 이름 j13h)를 쓰고, 여기서는 **같은 짜임의 글(HTML)** 을 한국 자료로 만든다.
  · 맨 위 고양이버스 띠(같은 그림 파일 static/j12asset · 관심종목 로고가 버스 둘레를 돈다) · ↻ · 실시간 · 「🌎 미국테마 →」
  · 🇰🇷 한국시장 한줄 브리핑(네이버 뉴스 「코스피」 최근 셋 · 누르면 크게)
  · ◎ 사용자 선정 종목 + 「종목 검색 후 추가」 칸 + 「+」 단추(찾고 → 맞는지 확인 → 넣기)
  · 두 칸 카드 — 로고 · 이름 · 값 · 등락 · **당일 분봉 그림(전일 종가 점선)** · 종목 뉴스 세 줄 · 꾸밈 그림 · × 빼기 ·
    누르면 크게(일봉 6개월 · 뉴스 원문 · 「🔎 선택종목 세부사항 보기」)
한국과 다른 점(지어내지 않는다)
  · 색은 한국 그대로 — 오름 빨강 · 내림 파랑(자비스12 는 초록 · 빨강).
  · 회사 로고 그림이 앱에 없다 — 이름 첫 글자 표(색은 종목코드로 늘 같게).
  · 뉴스 뜻(좋음 · 나쁨) 표시가 없다 — 모두 ○.
  · 「추가 검색 종목」 칸이 없다 — 한국 관심종목은 한 줄(최대 20)이다.
값 · 점수 · 판정은 안 건드린다. 뉴스는 받은 것만 보이고 못 받으면 「못 받았습니다」라고 적는다.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jarvis13_home_css as C

MODULE_REVISION = 2026110402
ROOT = Path(__file__).resolve().parent
UP_STROKE = "#ff5b5b"          # 한국 — 오름 빨강
DOWN_STROKE = "#5aa9ff"        # 한국 — 내림 파랑
NEWS_KEEP = 1800.0             # 뉴스는 30분 같이 쓴다(손님끼리 · 실패는 안 담는다)
ORBIT_SECONDS = 26.0
DECOR_IMAGES = (
    ("soot", "soot_lamp_cut.webp", "75/72"),
    ("catlamp", "small_cat_lamp_cut.webp", "102/75"),
    ("totoro", "small_totoro_cut.webp", "99/73"),
    ("bunny", "bunny_bench_cut.webp", "133/101"),
)
_NEWS: dict = {}


def asset_uri(filename: str) -> str:
    """자비스12 와 같은 그림 파일(assets/briefing · 내용 도장 붙은 static/j12asset 주소). 없으면 빈 글."""
    asset = ROOT / "assets" / "briefing" / filename
    if not asset.is_file():
        return ""
    try:
        stamp = hashlib.sha1(asset.read_bytes()).hexdigest()[:10]
        served = f"{asset.stem}-{stamp}{asset.suffix}"
        if (ROOT / "static" / "j12asset" / served).is_file():
            return f"app/static/j12asset/{served}"
    except Exception:
        pass
    mime = {".svg": "image/svg+xml", ".webp": "image/webp"}.get(asset.suffix.lower(), "image/png")
    return f"data:{mime};base64,{base64.b64encode(asset.read_bytes()).decode('ascii')}"


def decor_css() -> str:
    rules = [f".j13h-decor-img.{name}{{background-image:url('{asset_uri(filename)}');aspect-ratio:{ratio}}}"
             for name, filename, ratio in DECOR_IMAGES if asset_uri(filename)]
    if not rules:
        return ""
    return ("<style>.j13h-decor-img{background-size:contain;background-repeat:no-repeat;"
            "background-position:bottom right;height:auto!important}" + "".join(rules) + "</style>")


KR_CSS = """<style>
/* 한국 색 — 오름 빨강 · 내림 파랑(자비스12 는 초록 · 빨강) */
.j13h-up{color:#ff5b5b!important}
.j13h-down{color:#5aa9ff!important}
.j13h-note:before{color:#ff6b6b!important}
.j13h-card.decline .j13h-note:before{color:#5aa9ff!important}
/* 세부사항 여는 숨은 단추 묶음 — 눈에 안 보이고 카드의 「🔎 선택종목 세부사항 보기」가 대신 누른다 */
div[class*="st-key-j13h_wdgo_box"]{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;
  opacity:0!important;pointer-events:none!important}
#j13h-wd-wait{position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;
  background:rgba(2,10,28,.72);color:#eaf4ff;font-weight:800;font-size:1rem}
#j13h-wd-wait span{padding:.7rem 1.1rem;border:1px solid #c89550;border-radius:14px;background:#062448}
</style>"""


def _flat(block: str) -> str:
    """줄 앞 들여쓰기를 뗀다 — 덩어리를 한 번에 이어 붙이면 들여쓴 「<style>」 줄을 화면이 코드 글로 읽어 규칙이 글자로
    찍혔다(2026-11-04 깃허브 사진). 자비스12 는 덩어리를 따로따로 넣어 괜찮았다. 꾸밈 값은 한 글자도 안 바뀐다."""
    return "\n".join(line.strip() for line in str(block or "").splitlines() if line.strip())


def css() -> str:
    """관심종목 꾸밈 한 덩어리 — 자비스12 베낌 + 한국 색."""
    return "\n".join(_flat(block) for block in (*C.BRIEFING_CSS, C.BRIEFING_OPEN_CSS, decor_css(), C.BRIEFING_TABLET_CSS,
                                                C.BRIEFING_TOUCH_CSS, KR_CSS) if block)


# ── 그림 ─────────────────────────────────────────────────────────────────────────────────

def _chart_split(values, low: float, span: float, *, base=None) -> str:
    base = values[0] if base is None else float(base)
    step = 100.0 / (len(values) - 1)

    def _y(value):
        return 42 - (value - low) * 38 / span

    base_y = _y(base)
    pieces, current, sign = [], [(0.0, base)], None
    for index in range(len(values) - 1):
        x_now, v_now = index * step, values[index]
        x_next, v_next = (index + 1) * step, values[index + 1]
        sign_now = 1 if v_now >= base else -1
        sign_next = 1 if v_next >= base else -1
        if sign is None:
            sign = sign_now if v_now != base else sign_next
        if sign_next == sign or v_next == base:
            current.append((x_next, v_next))
            continue
        share = (base - v_now) / (v_next - v_now) if v_next != v_now else 0.0
        x_cross = x_now + (x_next - x_now) * share
        current.append((x_cross, base))
        pieces.append((sign, current))
        sign, current = sign_next, [(x_cross, base), (x_next, v_next)]
    pieces.append((sign if sign is not None else 1, current))
    body = []
    for piece_sign, piece in pieces:
        if len(piece) < 2:
            continue
        color = UP_STROKE if piece_sign >= 0 else DOWN_STROKE
        line = " ".join(f"{x:.2f},{_y(v):.2f}" for x, v in piece)
        area = f"{piece[0][0]:.2f},{base_y:.2f} " + line + f" {piece[-1][0]:.2f},{base_y:.2f}"
        body.append(f'<polygon points="{area}" fill="{color}" fill-opacity="0.15"/>')
        body.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.1" '
                    'vector-effect="non-scaling-stroke"/>')
    guide = (f'<line x1="0" y1="{base_y:.2f}" x2="100" y2="{base_y:.2f}" stroke="rgba(255,255,255,.42)" '
             'stroke-width="1" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>')
    return '<svg class="j13h-chart" viewBox="0 0 100 45" preserveAspectRatio="none">' + guide + "".join(body) + "</svg>"


def chart(values, change, *, baseline: bool = False, base=None) -> str:
    """자비스12 _briefing_chart 와 같은 그림 — 기준선(전일 종가 · 6개월은 첫 값) 위 빨강 · 아래 파랑."""
    values = [float(item) for item in (values or []) if item is not None]
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = high - low or 1
    if baseline:
        if base is not None:
            low = min(low, float(base))
            span = (max(high, float(base)) - low) or 1
        return _chart_split(values, low, span, base=base)
    stroke = UP_STROKE if (change or 0) >= 0 else DOWN_STROKE
    points = " ".join(f"{i * 100 / (len(values) - 1):.1f},{42 - (v - low) * 38 / span:.1f}" for i, v in enumerate(values))
    return (f'<svg class="j13h-chart" viewBox="0 0 100 45" preserveAspectRatio="none"><polyline points="{points}" '
            f'fill="none" stroke="{stroke}" stroke-width="2.1" vector-effect="non-scaling-stroke"/></svg>')


def six_month_caption(values) -> str:
    points = [float(v) for v in (values or []) if v is not None]
    if not points or not points[0]:
        return ""
    ratio = (points[-1] / points[0] - 1.0) * 100.0
    tone = "j13h-up" if ratio >= 0 else "j13h-down"
    return f"<div class='j13h-chart-cap'>일봉 6개월 <b class='{tone}'>{ratio:+.1f}%</b></div>"


def logo_face(code: str, name: str) -> tuple[str, str]:
    """이름 첫 글자 표 — 색은 종목코드로 늘 같게(자비스12 의 그림 없는 종목과 같은 방식)."""
    text = (str(name or code).strip() or str(code))[:1]
    hue = sum(ord(ch) for ch in str(code)) * 37 % 360
    return (f'<span class="j13h-logo-text" style="background:linear-gradient(145deg,hsl({hue} 52% 42%),hsl({hue} 60% 20%));'
            f'color:#f4faff;font-size:.62em">{html.escape(text)}</span>'), ""


def orbit_html(stocks: list[dict]) -> str:
    riders = [s for s in (stocks or []) if str(s.get("code") or "").strip()][:5]
    if not riders:
        return ""
    pods = []
    for index, stock in enumerate(riders):
        code, name = str(stock["code"]), str(stock.get("name") or stock["code"])
        face, kind = logo_face(code, name)
        delay = -ORBIT_SECONDS * index / len(riders)
        pods.append(f'<span class="j13h-orbit-arm" style="animation-delay:{delay:.2f}s">'
                    f'<span class="j13h-orbit-pod" style="animation-delay:{delay:.2f}s">'
                    f'<span class="j13h-orbit-logo" style="animation-delay:{delay:.2f}s">'
                    f'<span class="j13h-logo{kind}">{face}</span>'
                    f'<span class="j13h-orbit-tag">{html.escape(name[:6])}</span></span></span></span>')
    return f'<div class="j13h-orbit" aria-hidden="true">{"".join(pods)}</div>'


def hero_html(stocks: list[dict]) -> str:
    scene = asset_uri("hero_scene.webp")
    scene_html = f'<img class="j13h-hero-scene" src="{scene}" alt="">' if scene else ""
    pop = asset_uri("hero_catbus_pop.webp") if scene else ""
    pop_html = (f'<div class="j13h-hero j13h-hero-pop" aria-hidden="true"><div class="j13h-hero-scene">'
                f'<img class="j13h-hero-pop-bus" src="{pop}" alt=""></div></div>') if pop else ""
    return ('<div class="j13h-app j13h-home"></div><div class="j13h-hero"><div class="j13h-head-copy">'
            '<div class="j13h-title">JARVIS <b>13</b></div><div class="j13h-sub">한국테마</div></div>'
            '<div class="j13h-head-actions"><span class="j13h-round">↻</span><span class="j13h-live"><i></i>실시간</span></div>'
            f'{scene_html}{orbit_html(stocks)}</div>{pop_html}'
            + _flat(C.J13H_HOME_CSS) + _flat(C.J13H_CROSS_CSS))


# ── 뉴스 ─────────────────────────────────────────────────────────────────────────────────

def _clean(item: dict) -> dict:
    link = str(item.get("originallink") or item.get("link") or "").strip()
    return {"brief": str(item.get("title") or "").strip(), "headline": str(item.get("title") or "").strip(),
            "url": link if link.lower().startswith(("http://", "https://")) else "",
            "published_at": str(item.get("pub_date") or "")}


def cached_news(query: str):
    """같이 쓰는 뉴스(30분). 없거나 오래됐으면 None."""
    kept = _NEWS.get(str(query))
    if kept and time.time() - kept[0] < NEWS_KEEP:
        return kept[1]
    return None


def fetch_news(queries, client_id, client_secret, *, workers: int = 6, fetch=None) -> int:
    """못 가진 검색어의 뉴스를 한꺼번에 받는다. 받은 것만 담는다(실패는 안 담는다 · 다음에 다시). 새로 담은 수를 돌려준다."""
    todo = [q for q in dict.fromkeys(str(q) for q in queries if q) if cached_news(q) is None]
    if not todo or not client_id or not client_secret:
        return 0
    if fetch is None:
        import news_data

        def fetch(query):
            return news_data.fetch_naver_news(client_id, client_secret, query, display=5, sort="date")

    def one(query):
        try:
            return query, fetch(query)
        except Exception:
            return query, None

    added = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for query, result in pool.map(one, todo):
            if (result or {}).get("status") in ("정상", "데이터 없음"):
                _NEWS[query] = (time.time(), [_clean(item) for item in (result.get("data") or [])][:5])
                added += 1
    return added


def _accordion(items: list[dict]) -> str:
    rows = []
    for item in items[:3]:
        brief = html.escape(str(item.get("brief") or ""))
        parts = []
        if item.get("published_at"):
            parts.append(f'<div class="j13h-open-src">{html.escape(str(item["published_at"])[:16].replace("T", " "))}</div>')
        if item.get("url"):
            parts.append(f'<a class="j13h-open-link" href="{html.escape(item["url"], quote=True)}" target="_blank" '
                         'rel="noopener noreferrer">원문 기사 열기 ↗</a>')
        if not parts:
            parts.append('<div class="j13h-open-src">원문 주소를 받지 못했습니다.</div>')
        rows.append(f'<details class="j13h-open-news"><summary>{brief}</summary>'
                    f'<div class="j13h-open-body">{"".join(parts)}</div></details>')
    return "".join(rows)


def _note_items(items, state: str) -> list[dict]:
    if items:
        return list(items)[:3]
    if state == "pending":
        return [{"brief": "뉴스를 불러오는 중입니다"}]
    if state == "nokey":
        return [{"brief": "네이버 뉴스 열쇠가 없어 뉴스를 못 받습니다"}]
    return [{"brief": "뉴스를 못 받았습니다 · 맨 위 ↻ 를 누르십시오"}]


def market_news_html(items, state: str) -> str:
    """🇰🇷 한국시장 한줄 브리핑 — 세 줄 한 상자 · 누르면 크게(자비스12 와 같은 짜임)."""
    shown = _note_items(items, state)
    rows = "".join(
        f'<div class="j13h-news"><span class="j13h-news-link"><span class="j13h-news-icon">○</span>'
        f'<span>{html.escape(str(item.get("brief") or ""))}</span><span class="j13h-news-dot neutral"></span></span></div>'
        for item in shown)
    return ('<details class="j13h-market-news-shell"><summary class="j13h-market-news-summary">'
            f'<div class="j13h-news-box">{rows}</div></summary>'
            '<div class="j13h-card-open"><div class="j13h-open-card"><span class="j13h-open-close">× 다시 누르면 닫힘</span>'
            '<div class="j13h-market-news-title">한국시장 한줄 브리핑</div>'
            f'<div class="j13h-open-list">{_accordion(shown if items else [])}</div>'
            '<span class="j13h-open-close j13h-open-close-b">✕ 닫기</span></div></div></details>')


# ── 카드 ─────────────────────────────────────────────────────────────────────────────────

def card_html(stock: dict, card: dict, news_items, news_state: str) -> str:
    """카드 한 장 — 자비스12 _render_briefing_card 의 글 그대로(이름 j13h · 한국 자료)."""
    code, name = str(stock["code"]), str(stock.get("name") or stock["code"])
    price, change = card.get("price"), card.get("change_pct")
    tone = "j13h-up" if (change or 0) > 0 else "j13h-down" if (change or 0) < 0 else "j13h-neutral"
    price_text = f"{price:,.0f}원" if isinstance(price, (int, float)) else "시세 준비 중"
    change_text = f"{change:+.2f}%" if isinstance(change, (int, float)) else "—"
    notes = _note_items(news_items, news_state)
    note_html = "".join(f'<div class="j13h-note">{html.escape(str(item.get("brief") or ""))}</div>' for item in notes)
    logo, kind = logo_face(code, name)
    direction = "decline" if (change or 0) < 0 else ""
    decor = DECOR_IMAGES[sum(ord(ch) for ch in code) % len(DECOR_IMAGES)][0]
    decor_html = f'<span class="j13h-decor-img {decor}"></span>'
    today = card.get("chart_today")
    top = (f'<div class="j13h-card-top"><span class="j13h-logo{kind}">{logo}</span><div>'
           f'<span class="j13h-symbol">{html.escape(name)}</span><span class="j13h-name">{html.escape(code)}</span></div></div>'
           f'<div class="j13h-price">{price_text} <span class="{tone}">{change_text}</span></div>')
    body = (f'<div class="j13h-card {direction}">' + top
            + chart(today or card.get("chart"), change, baseline=bool(today), base=card.get("prev_close"))
            + f'<div class="j13h-card-notes">{note_html}</div>{decor_html}</div>')
    six = [float(v) for v in (card.get("chart6m") or []) if v is not None]
    opened = (f'<div class="j13h-open-card {direction}"><span class="j13h-open-close">× 다시 누르면 닫힘</span>' + top
              + chart(six or card.get("chart"), change, baseline=bool(six)) + six_month_caption(six)
              + f'<div class="j13h-open-list">{_accordion(news_items or [])}</div>'
              + f'<span class="j13h-wd-open" data-tk="{html.escape(code)}">🔎 선택종목 세부사항 보기</span>'
              + '<span class="j13h-open-close j13h-open-close-b">✕ 닫기</span>' + decor_html + '</div>')
    return ('<details class="j13h-card-shell"><summary class="j13h-card-summary" title="누르면 크게 보기">'
            f'{body}</summary><div class="j13h-card-open">{opened}</div></details>')


def card_data(frame, intraday) -> dict:
    """값 · 등락 · 그림 — 일봉(마지막 값 · 전일 대비 · 20일 · 6개월)과 당일 분봉(있으면)."""
    out = {}
    try:
        closes = [float(v) for v in frame["Close"].dropna().tolist()] if frame is not None else []
    except Exception:
        closes = []
    if closes:
        out["price"] = closes[-1]
        if len(closes) >= 2 and closes[-2]:
            out["change_pct"] = (closes[-1] / closes[-2] - 1.0) * 100.0
        out["chart"] = closes[-30:]
        out["chart6m"] = closes[-126:]
    if isinstance(intraday, dict) and intraday.get("ok"):
        try:
            minutes = [float(v) for v in intraday["price"]["Close"].tolist()]
        except Exception:
            minutes = []
        prev = intraday.get("prev_close")
        if len(minutes) >= 5:
            out["chart_today"] = minutes
            out["prev_close"] = prev
            out["price"] = minutes[-1]
            if prev:
                out["change_pct"] = (minutes[-1] / float(prev) - 1.0) * 100.0
    return out


def load_intraday(codes, loader, *, workers: int = 6) -> dict:
    def one(code):
        try:
            return code, loader(code)
        except Exception:
            return code, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, list(codes)))


WD_OPEN_JS = """
(function(){
  if (window.__j13hWdOpen) { return; }
  window.__j13hWdOpen = true;
  document.addEventListener('click', function (e) {
    var go = e.target && e.target.closest ? e.target.closest('.j13h-wd-open') : null;
    if (!go) { return; }
    e.preventDefault(); e.stopPropagation();
    var tk = go.getAttribute('data-tk') || '';
    var btn = document.querySelector('div.st-key-j13h_wdgo_' + tk + ' button');
    if (!btn) { return; }
    var shell = go.closest('details'); if (shell) { shell.open = false; }
    var old = document.getElementById('j13h-wd-wait'); if (old) { old.remove(); }
    var wait = document.createElement('div'); wait.id = 'j13h-wd-wait';
    var label = document.createElement('span'); label.textContent = '🔎 세부사항을 여는 중…';
    wait.appendChild(label); document.body.appendChild(wait);
    var started = Date.now();
    function watch() {
      var name = document.querySelector('.j4-stock-name');
      if ((name && !name.closest('[data-stale="true"]')) || Date.now() - started > 15000) { wait.remove(); return; }
      window.setTimeout(watch, 80);
    }
    btn.click(); window.setTimeout(watch, 80);
  }, true);
})();
"""


def scripts_html() -> str:
    """카드 닫는 움직임(자비스12 _J3B_POP_CLOSE 베낌) · 세부사항 여는 단추 — 바깥 문서에 한 번만(id j13h-...)."""
    out = "<script>"
    for ident, code in (("j13h-pop-close", C.J13H_POP_CLOSE), ("j13h-wd-open", WD_OPEN_JS)):
        out += ("(function(){try{var d=window.parent.document;"
                f"if(d.getElementById('{ident}')){{return;}}"
                f"var s=d.createElement('script');s.id='{ident}';"
                f"s.textContent={json.dumps(code)};d.head.appendChild(s);}}catch(e){{}}}})();")
    return out + "</script>"
