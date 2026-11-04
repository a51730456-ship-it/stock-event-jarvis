"""자비스13 「시장 현황」 — 한국 테마 지도 · 테마 상위 5 줄 · 오름/내림 막대 (2026-11-04 상하님 — 미국테마 캡처를 보이시며
「미국테마에는 있는데 한국 테마에는 없다」).

자비스12 「시장 현황」(_sector_map_cell · 칸 자리 셈 squarify · 누르면 크게) 그대로 옮기고 이름표만 j13 이다.
**새로 받는 자료가 없다** — 첫 화면이 이미 받는 테마 순위(jarvis4_data.get_theme_rankings 의 all_scored · 후보 테마 30여 개와
그 구성 종목)만 쓴다. 로딩을 늘리지 않으려고(상하님 「가장 우선은 로딩 문제다」).

미국과 다른 점(한국에는 업종의 「시장 몫」 자료가 앱에 없다 — 지어내지 않는다)
  · 칸 = 테마 · 칸 크기 = 그 테마 구성 종목의 **오늘 거래대금 합** · 색·숫자 = 네이버 테마 등락률(한국 색 — 오름 빨강 · 내림 파랑)
  · 테마 상위 5 = 아래 「오늘의 강한 테마」 순위 위 5개(새로 세지 않는다)
  · 오름/그대로/내림 = 그 테마들에 든 종목(겹치면 한 번)의 오늘 등락
값은 보여 주기만 한다 — 점수·판정에 안 쓴다.
"""

from __future__ import annotations

import html

MODULE_REVISION = 2026110401
MAP_W, MAP_H = 100.0, 58.0
POP_W, POP_H = 100.0, 45.0
MAX_TILES = 30


def _squarify(areas, x, y, width, height, out) -> None:
    """넓이가 값에 비례하는 상자로 칸을 채운다(자비스12 _squarify 그대로)."""
    if not areas:
        return
    if len(areas) == 1 or width <= 0 or height <= 0:
        offset, total = y, sum(areas) or 1.0
        for area in areas:
            share = area / total * height
            out.append((x, offset, width, share))
            offset += share
        return

    def worst(row, side):
        total = sum(row)
        if total <= 0 or side <= 0:
            return float("inf")
        return max(side * side * max(row) / (total * total), (total * total) / (side * side * min(row)))

    side = min(width, height)
    row, index = [areas[0]], 1
    while index < len(areas) and worst(row + [areas[index]], side) <= worst(row, side):
        row.append(areas[index])
        index += 1
    total = sum(row)
    if width >= height:
        band, offset = total / height, y
        for area in row:
            share = area / total * height
            out.append((x, offset, band, share))
            offset += share
        _squarify(areas[index:], x + band, y, width - band, height, out)
    else:
        band, offset = total / width, x
        for area in row:
            share = area / total * width
            out.append((offset, y, share, band))
            offset += share
        _squarify(areas[index:], x, y + band, width, height - band, out)


def tone(change) -> str:
    """한국 색 — 오르면 빨강 · 내리면 파랑 · 많이 움직일수록 진하다(2% 이상이 가장 진함)."""
    try:
        value = float(change)
    except (TypeError, ValueError):
        return "#22304a"
    strength = min(abs(value) / 2.0, 1.0)
    target = (255, 91, 91) if value >= 0 else (77, 166, 255)
    dark = (12, 28, 52)
    mixed = tuple(round(base + (tip - base) * (0.22 + 0.78 * strength)) for base, tip in zip(dark, target))
    return "#%02x%02x%02x" % mixed


def _pct(value) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _label_em(name: str) -> float:
    longest = 0.0
    for part in name.replace("·", "·\n").replace(" ", "\n").replace("/", "/\n").split("\n"):
        longest = max(longest, sum(0.35 if ch == "·" else 0.62 if ch.isascii() else 1.0 for ch in part))
    return max(longest, 2.0)


def tiles_from_ranking(ranking: dict) -> list[dict]:
    """칸 줄 — 이름 · 크기(구성 종목 거래대금 합) · 등락. 거래대금을 못 센 테마는 뺀다(0으로 채우지 않는다)."""
    rows = []
    for theme in (ranking or {}).get("all_scored") or (ranking or {}).get("rows") or []:
        stocks = theme.get("stocks") or []
        weight = sum(float(stock.get("trading_value") or 0) for stock in stocks if stock.get("trading_value"))
        if weight <= 0:
            continue
        rows.append({"name": str(theme.get("name") or ""), "weight": weight, "change": theme.get("change_pct")})
    rows.sort(key=lambda row: row["weight"], reverse=True)
    return rows[:MAX_TILES]


def breadth_from_ranking(ranking: dict) -> dict:
    """그 테마들에 든 종목(겹치면 한 번)의 오늘 오름 · 그대로 · 내림."""
    seen: dict = {}
    for theme in (ranking or {}).get("all_scored") or (ranking or {}).get("rows") or []:
        for stock in theme.get("stocks") or []:
            code = str(stock.get("code") or "")
            if code and code not in seen and stock.get("change_pct") is not None:
                seen[code] = float(stock["change_pct"])
    up = sum(1 for value in seen.values() if value > 0)
    down = sum(1 for value in seen.values() if value < 0)
    return {"up": up, "down": down, "flat": len(seen) - up - down, "total": len(seen)}


def _tiles_html(rows, width, height) -> str:
    total = sum(row["weight"] for row in rows) or 1.0
    scale = width * height / total
    boxes: list = []
    _squarify([row["weight"] * scale for row in rows], 0.0, 0.0, width, height, boxes)
    out = []
    for row, (x, y, w, h) in zip(rows, boxes):
        name = html.escape(row["name"])
        out.append(
            f"<div class='j13-sector-tile' title='{name} · {_pct(row['change'])}' "
            f"style='left:{x / width * 100:.3f}%;top:{y / height * 100:.3f}%;width:{w / width * 100:.3f}%;"
            f"height:{h / height * 100:.3f}%;--n:{_label_em(row['name']):.2f};background:{tone(row['change'])}'>"
            f"<div class='j13-sector-name'>{name.replace('·', '·<wbr>').replace('/', '/<wbr>')}</div>"
            f"<div class='j13-sector-pct'>{_pct(row['change'])}</div></div>")
    return "".join(out)


def _theme_strip(ranking) -> str:
    rows = [row for row in ((ranking or {}).get("rows") or []) if row.get("ok", True)][:5]
    if not rows:
        return ""
    cells = []
    for place, row in enumerate(rows, start=1):
        name = html.escape(str(row.get("name") or ""))
        cells.append(f"<div class='j13-sector-theme' title='{place}위 {name} · {_pct(row.get('change_pct'))}' "
                     f"style='--n:{_label_em(str(row.get('name') or '')):.2f};background:{tone(row.get('change_pct'))}'>"
                     f"<div class='j13-sector-name'><i>{place}</i> {name.replace('·', '·<wbr>')}</div>"
                     f"<div class='j13-sector-pct'>{_pct(row.get('change_pct'))}</div></div>")
    return ("<div class='j13-sector-themes'><div class='j13-sector-themes-label'>자비스 테마 상위 5 · 색 = 테마 등락</div>"
            f"<div class='j13-sector-theme-row'>{''.join(cells)}</div></div>")


def cell_html(ranking) -> str:
    """지도 칸 한 개(시장분석 맨 위 줄에 끼운다). 테마 순위가 아직 없으면 「받는 중」 한 줄(기다리지 않는다)."""
    rows = tiles_from_ranking(ranking)
    if not rows:
        return ("<div class='j4-top-cell j13-sector-map'><div class='j4-top-label'>시장 현황</div>"
                "<div class='j13-sector-wait'>테마 지도를 받는 중입니다 — 잠시 뒤 저절로 채워집니다</div></div>")
    breadth = breadth_from_ranking(ranking)
    foot = ""
    if breadth["total"]:
        total = float(breadth["total"])
        foot = ("<div class='j13-sector-bar'>"
                f"<span style='width:{breadth['up'] / total * 100:.1f}%;background:#ff5b5b'></span>"
                f"<span style='width:{breadth['flat'] / total * 100:.1f}%;background:#7a8494'></span>"
                f"<span style='width:{breadth['down'] / total * 100:.1f}%;background:#4da6ff'></span></div>"
                f"<div class='j13-sector-foot'><span style='color:#ff5b5b'>▲ 오름 {breadth['up']}</span>"
                f"<span style='color:#9aa0aa'>― 그대로 {breadth['flat']}</span>"
                f"<span style='color:#4da6ff'>▼ 내림 {breadth['down']}</span>"
                f"<span class='j13-sector-note'>자비스가 보는 한국 {breadth['total']}종목 기준</span></div>")
    strip = _theme_strip(ranking)
    return (
        "<div class='j4-top-cell j13-sector-map'>"
        "<input type='checkbox' id='j13sm-tap' class='j13sm-tap'>"
        "<label for='j13sm-tap' class='j13sm-cell'>"
        "<div class='j4-top-label'>시장 현황</div>"
        "<div class='j13-sector-sub'>칸 크기 = 테마 오늘 거래대금 · 색 = 테마 등락 · 누르면 크게</div>"
        f"<div class='j13-sector-grid'>{_tiles_html(rows, MAP_W, MAP_H)}</div>"
        + strip + foot + "</label>"
        "<label for='j13sm-tap' class='j13sm-scrim' aria-hidden='true'></label>"
        "<label for='j13sm-tap' class='j13sm-pop'>"
        "<span class='j13sm-title'>시장 현황 · 한국 테마 지도 <small>오늘 등락</small></span>"
        "<span class='j13sm-sub'>칸 크기 = 그 테마 구성 종목의 오늘 거래대금 합 · 색 = 네이버 테마 등락률 · 오름 빨강 · 내림 파랑</span>"
        f"<div class='j13-sector-grid j13sm-grid'>{_tiles_html(rows, POP_W, POP_H)}</div>"
        + strip + foot + "<span class='j13sm-close'>다시 누르면 닫힘</span></label></div>")


CSS = """<style>
.j4-top-row .j4-top-cell.j13-sector-map{flex:1 1 100%!important;width:100%!important;min-width:100%!important;max-width:100%!important;
  font-size:13px;grid-column:1/-1;box-sizing:border-box}
@media (min-width:1201px){.j4-top-row .j4-top-cell.j13-sector-map{min-width:0!important;max-width:640px!important}}
.j13-sector-sub{color:#8f9bb0;font-size:.86em;font-weight:700;margin:.1rem 0 .35rem}
.j13-sector-grid{position:relative;width:100%;aspect-ratio:100/58;border-radius:10px;overflow:hidden;background:rgba(255,255,255,.04)}
.j13-sector-tile{position:absolute;box-sizing:border-box;border:1px solid rgba(2,11,30,.85);border-radius:4px;display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:.1em;overflow:hidden;text-align:center;color:#f4f8ff;padding:2px}
.j13-sector-name{font-weight:600;line-height:1.12;word-break:keep-all}
.j13-sector-pct{font-weight:500;line-height:1.1;opacity:.95}
.j13-sector-tile,.j13-sector-theme{container-type:size}
.j13-sector-grid{--fmax:15px}
.j13sm-pop,.j13sm-pop .j13-sector-grid{--fmax:24px}
.j13-sector-tile .j13-sector-name,.j13-sector-theme .j13-sector-name{
  font-size:clamp(8px,min(calc(92cqw / var(--n,4)),27cqh),var(--fmax,15px))}
.j13-sector-tile .j13-sector-pct,.j13-sector-theme .j13-sector-pct{font-size:clamp(8px,min(calc(92cqw / 3.6),22cqh),calc(var(--fmax,15px)*.88))}
@container (max-height:30px){.j13-sector-tile .j13-sector-pct{display:none}}
@container (max-width:40px){.j13-sector-tile .j13-sector-pct{display:none}}
@container (max-width:20px){.j13-sector-name{display:none}}
@container (max-height:13px){.j13-sector-name{display:none}}
.j13-sector-themes{margin-top:.4rem}
.j13-sector-themes-label{color:#c084fc;font-size:.82em;font-weight:600;margin-bottom:.2rem}
.j13-sector-theme-row{display:flex;gap:3px;height:46px}
.j13-sector-theme{flex:1 1 0;min-width:0;box-sizing:border-box;border-radius:4px;border:1px solid rgba(2,11,30,.85);display:flex;
  flex-direction:column;align-items:center;justify-content:center;text-align:center;overflow:hidden;color:#f4f8ff;padding:2px}
.j13-sector-theme .j13-sector-name i{font-style:normal;color:#ffd166;margin-right:.1em}
.j13-sector-bar{display:flex;height:7px;border-radius:4px;overflow:hidden;margin:.4rem 0 .25rem;background:rgba(255,255,255,.08)}
.j13-sector-bar span{display:block;height:100%}
.j13-sector-foot{display:flex;flex-wrap:wrap;gap:.1rem .7rem;font-size:.86em;font-weight:800}
.j13-sector-note{color:#7d8798;font-weight:700}
.j13-sector-wait{color:#9aa0aa;font-weight:700;padding:.6rem 0}
.j13sm-tap{position:absolute;opacity:0;pointer-events:none;width:0;height:0;margin:0}
label.j13sm-cell{display:block;cursor:zoom-in}
.j13-sector-map:has(> .j13sm-tap:checked){transform:none!important;filter:none!important;z-index:2147483000!important}
.j13sm-scrim{position:fixed;inset:0;z-index:2147483646;cursor:zoom-out;background:rgba(1,8,22,.84);opacity:0;visibility:hidden;
  transition:opacity .3s ease,visibility 0s linear .56s}
.j13sm-pop{position:fixed;left:50%;top:50%;z-index:2147483647;cursor:zoom-out;width:min(calc(100vw - 16px),1280px);
  height:min(calc(100dvh - 16px),860px);box-sizing:border-box;padding:14px 14px 10px;border-radius:22px;background:#0d2344;
  border:1px solid rgba(157,204,255,.45);box-shadow:0 18px 50px rgba(0,0,0,.6);display:flex;flex-direction:column;gap:6px;
  font-size:clamp(12px,1.45vmax,18px);color:#f4f8ff;opacity:0;visibility:hidden;pointer-events:none;transform:translate(-50%,-50%) scale(.55);
  transition:transform .56s cubic-bezier(.5,-.18,.72,.18),opacity .56s cubic-bezier(.7,0,.84,0),visibility 0s linear .56s}
.j13sm-tap:checked ~ .j13sm-scrim{opacity:1;visibility:visible;transition:opacity .3s ease,visibility 0s}
.j13sm-tap:checked ~ .j13sm-pop{opacity:1;visibility:visible;pointer-events:auto;transform:translate(-50%,-50%) scale(1);
  transition:transform .9s cubic-bezier(.34,1.56,.64,1),opacity .36s ease,visibility 0s}
.j13sm-title{color:#9dccff;font-size:1.05em;font-weight:700}
.j13sm-title small{color:#8fb4de;font-size:.72em;font-weight:500;margin-left:.4em}
.j13sm-sub{color:#8f9bb0;font-size:.7em;font-weight:500;line-height:1.3}
.j13sm-close{align-self:center;font-size:.74em;color:#8fb4de}
.j13sm-pop .j13sm-grid{flex:1 1 auto;min-height:0;aspect-ratio:auto}
.j13sm-pop .j13-sector-themes{margin-top:0;flex:0 0 auto}
.j13sm-pop .j13-sector-theme-row{height:clamp(40px,11vmin,84px)}
.j13sm-pop .j13-sector-bar{flex:0 0 auto;margin:.15rem 0 0}
.j13sm-pop .j13-sector-foot{font-size:.74em}
body:has(.j13sm-tap:checked) .j13b-bottom-nav{visibility:hidden!important}
@media (orientation: portrait){
  .j13sm-pop{width:calc(100dvh - 76px);height:calc(100vw - 16px);top:calc(50% - 30px);transform:translate(-50%,-50%) rotate(90deg) scale(.55)}
  .j13sm-tap:checked ~ .j13sm-pop{transform:translate(-50%,-50%) rotate(90deg) scale(1)}
}
@media (prefers-reduced-motion: reduce){.j13sm-pop,.j13sm-scrim{transition:none!important}}
</style>"""
