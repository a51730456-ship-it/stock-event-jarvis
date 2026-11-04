# -*- coding: utf-8 -*-
"""한국테마 머리 띠 배경 — 여의도 밤 · 코스피 캔들 (2026-11-05 상하님 「한국테마에 동그라미 친 배경 동영상을 한국 주식 배경
동영상을 찾아 넣든지 만들든지 해서 넣어줘 · 미국테마와 구분하자」).

미국테마(자비스12)는 눈밭 영상(hero_snow_camp.mp4 · 2.8MB)과 고양이 버스 그림을 쓴다. 한국테마는 **처음부터 그린** 장면으로 바꾼다.
  · 여의도 밤 — 금빛 63빌딩 · 유리 빛 고층 셋 · 붉은 기둥 쌍둥이 빌딩 · 남산 위 서울타워(꼭대기 빨간 불이 깜빡) · 롯데타워(넓은 화면)
  · 하늘에 코스피 캔들이 흐른다 — **오름 빨강 · 내림 파랑**(한국 색) · 금빛 이동평균선
  · 한강 — 빌딩 불빛이 물에 비쳐 일렁이고, 다리 위로 차 불빛(흰 불 · 빨간 불)이 오간다
남의 그림 · 사진 · 캐릭터를 쓰지 않는다(저장소가 공개라 저작권 걱정이 없게). 동영상 파일 대신 SVG + CSS 움직임이라 가볍고
(몇십 KB) 폰에서도 선명하다. 움직임은 transform · opacity 만 쓴다(폰이 덜 힘들다) · 「움직임 줄이기」를 켠 폰에서는 멈춘다.
장식이다 — 캔들은 실제 시세가 아니다(숫자를 적지 않는다).
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

MODULE_REVISION = 2026110501

W, H = 1600, 300                 # 그림 판 — 폰은 가운데(x 560~1040 쯤)만 보이고 PC 는 거의 다 보인다
WATER = 226                      # 강물 높이(빌딩 밑동)
UP, DOWN = "#ff4d5e", "#3d8bff"   # 한국 색 — 오름 빨강 · 내림 파랑
GOLD = "#f3c76b"
# 이름난 건물 자리(폰은 x 560~1040 쯤이 보인다 — 왼쪽 위 「JARVIS 13」 글자 밑은 비워 둔다)
TOWER_X, SIXTY3_X, IFC_X, PARC_X, LOTTE_X = 640, 772, 806, 912, 1330


def _f(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


# ── 하늘의 코스피 캔들 — 끝과 처음이 이어지는 값(한 바퀴 흘러도 끊김 없이) ──────────────────────────────────────

def _series(count: int, seed: int) -> list[tuple[float, float, float, float]]:
    """(시가, 고가, 저가, 종가) — 한 바퀴의 8할은 오르고(빨간 캔들 7할쯤) 2할은 조정(파란 캔들). 끝과 처음 값이 같아
    두 띠를 이어 붙여 흘려도 끊김이 없다."""
    rng = random.Random(seed)
    rise_n = round(count * .85)

    def steps(n: int, up_odds: float, up_size: tuple, down_size: tuple, total: float) -> list[float]:
        raw = [rng.uniform(*up_size) if rng.random() < up_odds else -rng.uniform(*down_size) for _ in range(n)]
        scale = total / sum(raw)
        return [value * scale for value in raw]

    # 오를 때도 위아래로 출렁여야 캔들이 굵다(한 바퀴에 오르는 높이는 정해져 있다) — 빨강 6할 남짓 · 몸통 큼
    moves = steps(rise_n, .62, (10, 18), (8, 14), 1.0) + steps(count - rise_n, .15, (3, 6), (8, 16), -1.0)
    closes, level = [], 0.0
    for move in moves:
        level += move
        closes.append(level)
    rows = []
    for i, close in enumerate(closes):
        opened = closes[i - 1]
        size = abs(close - opened)
        top, bottom = max(opened, close), min(opened, close)
        rows.append((opened, top + size * rng.uniform(.15, .7) + .004, bottom - size * rng.uniform(.15, .7) - .004, close))
    return rows


def _chart(seed: int = 211) -> str:
    """하늘 띠(y 52~178)의 캔들 · 이동평균선. 같은 띠 둘을 이어 붙여 왼쪽으로 흘린다(.j13k-flow)."""
    rows = _series(56, seed)
    step, body = 31.5, 16.0
    lows = min(r[2] for r in rows)
    highs = max(r[1] for r in rows)
    top_y, bottom_y = 18.0, 156.0

    def y_of(value: float) -> float:
        return bottom_y - (value - lows) / (highs - lows) * (bottom_y - top_y)

    strip = step * len(rows)
    parts = {"ub": [], "db": [], "uw": [], "dw": []}
    for copy in (0, 1):
        for i, (opened, high, low, close) in enumerate(rows):
            x = copy * strip + i * step + step / 2
            up = close >= opened
            y1, y2 = y_of(max(opened, close)), y_of(min(opened, close))
            height = max(y2 - y1, 1.2)
            parts["ub" if up else "db"].append(f"M{_f(x - body / 2)} {_f(y1)}h{_f(body)}v{_f(height)}h-{_f(body)}z")
            parts["uw" if up else "dw"].append(f"M{_f(x)} {_f(y_of(high))}V{_f(y_of(low))}")
    # 이동평균(8개 · 처음과 끝이 이어지게 감아서 잰다)
    closes = [r[3] for r in rows]
    span = 8
    averages = [sum(closes[(i - k) % len(closes)] for k in range(span)) / span for i in range(len(closes))]
    points = []
    for copy in (0, 1):
        for i, value in enumerate(averages):
            points.append(f"{_f(copy * strip + i * step + step / 2)},{_f(y_of(value))}")
    line = " ".join(points)
    area = f"{_f(step / 2)},{_f(bottom_y + 14)} " + line + f" {_f(2 * strip - step / 2)},{_f(bottom_y + 14)}"
    return (
        f'<g class="j13k-flow" style="--j13k-strip:-{_f(strip)}px">'
        f'<polygon points="{area}" fill="url(#j13karea)"/>'
        f'<path d="{"".join(parts["uw"])}" stroke="{UP}" stroke-width="1.6" opacity=".85"/>'
        f'<path d="{"".join(parts["dw"])}" stroke="{DOWN}" stroke-width="1.6" opacity=".85"/>'
        f'<path d="{"".join(parts["ub"])}" fill="{UP}"/>'
        f'<path d="{"".join(parts["db"])}" fill="{DOWN}"/>'
        f'<polyline points="{line}" fill="none" stroke="{GOLD}" stroke-width="7" opacity=".16" stroke-linejoin="round"/>'
        f'<polyline points="{line}" fill="none" stroke="#ffe39a" stroke-width="2.2" opacity=".95" stroke-linejoin="round"/>'
        "</g>"
    )


# ── 별 · 달 ─────────────────────────────────────────────────────────────────────────────────────────────

def _stars(seed: int = 5) -> str:
    rng = random.Random(seed)
    groups = {1: [], 2: [], 3: []}
    for _ in range(54):
        x, y = rng.uniform(0, W), rng.uniform(6, 118)
        r = rng.choice((.7, .9, 1.1, 1.4))
        groups[rng.choice((1, 2, 3))].append(f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{r}"/>')
    return "".join(f'<g class="j13k-tw j13k-tw{k}" fill="#fff6dc">{"".join(v)}</g>' for k, v in groups.items())


# ── 빌딩 ────────────────────────────────────────────────────────────────────────────────────────────────

# 눈에 띄는 건물 자리(가운데 쪽 — 폰에서도 보이게)
_LANDMARKS = (TOWER_X - 30, PARC_X + 64)


def _generic_buildings(seed: int, layer: str) -> str:
    """이름 없는 빌딩들. layer 'far'(뒤 · 어둡게) · 'near'(앞 · 창 불빛)."""
    rng = random.Random(seed)
    shapes, windows = [], {1: [], 2: [], 3: []}
    x = -10.0
    while x < W + 10:
        width = rng.uniform(22, 48) if layer == "near" else rng.uniform(30, 70)
        if layer == "near" and _LANDMARKS[0] - 20 < x < _LANDMARKS[1] + 10:
            # 이름난 건물 자리 앞은 낮은 건물만(가리지 않게)
            height = rng.uniform(16, 34)
        elif layer == "near":
            height = rng.uniform(28, 92)
        else:
            height = rng.uniform(40, 110)
        top = WATER - height
        color = rng.choice(("#0f1d3d", "#13234a", "#0c1934", "#152a55")) if layer == "near" else \
            rng.choice(("#0a1531", "#0c1838", "#0b1634"))
        shapes.append(f'<rect x="{_f(x)}" y="{_f(top)}" width="{_f(width)}" height="{_f(height + 1)}" fill="{color}"/>')
        if rng.random() < .25 and height > 50:
            # 꼭대기 안테나 · 붉은 항공 장애등
            shapes.append(f'<rect x="{_f(x + width / 2 - .6)}" y="{_f(top - 9)}" width="1.2" height="9" fill="{color}"/>')
            shapes.append(f'<circle class="j13k-blink" cx="{_f(x + width / 2)}" cy="{_f(top - 9)}" r="1.3" fill="#ff5a4e"/>')
        if layer == "near" and height > 26:
            pattern = rng.choice(("j13kwa", "j13kwb", "j13kwc"))
            windows[rng.choice((1, 2, 3))].append(
                f'<rect x="{_f(x + 2)}" y="{_f(top + 4)}" width="{_f(width - 4)}" height="{_f(height - 6)}" '
                f'fill="url(#{pattern})"/>')
        x += width + rng.uniform(1, 6)
    lights = "".join(f'<g class="j13k-tw j13k-tw{k}">{"".join(v)}</g>' for k, v in windows.items() if v)
    return "".join(shapes) + lights


def _sixty_three(x: float) -> str:
    """금빛 63빌딩 — 위가 비스듬한 금빛 유리 탑."""
    left, right, top = x - 23, x + 23, 82
    shape = (f"M{_f(left)} {WATER}V{_f(top + 20)}L{_f(left + 13)} {_f(top + 2)}L{_f(right - 9)} {_f(top - 4)}"
             f"L{_f(right)} {_f(top + 14)}V{WATER}z")
    return (
        f'<clipPath id="j13k63"><path d="{shape}"/></clipPath>'
        f'<path d="{shape}" fill="url(#j13kgold)"/>'
        f'<rect x="{_f(left)}" y="{_f(top - 6)}" width="46" height="{_f(WATER - top + 6)}" fill="url(#j13kfloor)" '
        'clip-path="url(#j13k63)"/>'
        # 금빛 유리에 빛이 위로 훑고 지나간다
        f'<g clip-path="url(#j13k63)"><rect class="j13k-shine" x="{_f(left - 4)}" y="{WATER}" width="54" height="26" '
        'fill="url(#j13kshine)"/></g>'
        f'<path d="M{_f(left + 13)} {_f(top + 2)}L{_f(right - 9)} {_f(top - 4)}" stroke="#fff3c4" stroke-width="1.2" opacity=".8"/>'
    )


def _ifc(x: float) -> str:
    """유리 빛 고층 셋(IFC 쯤) — 키가 다른 푸른 유리 탑."""
    out = []
    for dx, width, top in ((0, 30, 104), (34, 24, 130), (62, 22, 150)):
        left = x + dx
        out.append(f'<rect x="{_f(left)}" y="{top}" width="{width}" height="{WATER - top + 1}" fill="url(#j13kglass)"/>')
        out.append(f'<rect x="{_f(left)}" y="{top}" width="{width}" height="{WATER - top}" fill="url(#j13kmull)"/>')
        out.append(f'<rect x="{_f(left)}" y="{top}" width="{width}" height="2" fill="#bfe0ff" opacity=".7"/>')
    return "".join(out)


def _parc_one(x: float) -> str:
    """붉은 기둥 쌍둥이 빌딩 — 모서리에 빨간 띠가 선다(오름 빨강과 맞는 색)."""
    out = []
    for dx, top in ((0, 92), (38, 106)):
        left = x + dx
        out.append(f'<rect x="{_f(left)}" y="{top}" width="30" height="{WATER - top + 1}" fill="#17213f"/>')
        out.append(f'<rect x="{_f(left + 3)}" y="{top + 6}" width="24" height="{WATER - top - 8}" fill="url(#j13kwb)" opacity=".85"/>')
        for edge in (left - 1.5, left + 29.5):
            out.append(f'<rect x="{_f(edge)}" y="{top - 8}" width="2.2" height="{WATER - top + 8}" fill="{UP}" opacity=".9"/>')
    return "".join(out)


def _lotte(x: float) -> str:
    """롯데타워 쯤 — 가늘게 솟는 바늘 탑(넓은 화면 오른쪽)."""
    return (f'<path d="M{_f(x - 14)} {WATER}L{_f(x - 6)} 120L{_f(x)} 58L{_f(x + 6)} 120L{_f(x + 14)} {WATER}z" '
            'fill="url(#j13ksilver)"/>'
            f'<path d="M{_f(x)} 58V{WATER}" stroke="#d9ecff" stroke-width=".8" opacity=".5"/>'
            f'<circle class="j13k-blink" cx="{_f(x)}" cy="57" r="1.6" fill="#ff5a4e"/>')


def _namsan(x: float) -> str:
    """남산과 서울타워 — 꼭대기 빨간 불이 깜빡인다."""
    hill = f"M{_f(x - 120)} {WATER}Q{_f(x - 60)} 168 {_f(x)} 166Q{_f(x + 60)} 168 {_f(x + 120)} {WATER}z"
    return (
        f'<path d="{hill}" fill="#0a1a33"/>'
        f'<ellipse cx="{_f(x)}" cy="113" rx="26" ry="16" fill="url(#j13kglow)"/>'
        f'<rect x="{_f(x - 2.5)}" y="118" width="5" height="49" fill="url(#j13ktower)"/>'
        f'<rect x="{_f(x - 10)}" y="107" width="20" height="10" rx="3" fill="#e8eef8"/>'
        f'<rect x="{_f(x - 10)}" y="111" width="20" height="1.6" fill="{GOLD}"/>'
        f'<rect x="{_f(x - 1)}" y="84" width="2" height="23" fill="#d6e3f5"/>'
        f'<circle class="j13k-blink" cx="{_f(x)}" cy="83" r="2.2" fill="#ff4040"/>'
    )


# ── 한강 · 다리 · 차 불빛 ───────────────────────────────────────────────────────────────────────────────

def _river(seed: int = 21) -> str:
    rng = random.Random(seed)
    streaks = []
    # 이름난 건물 불빛이 물에 비친 줄(금빛 · 푸른빛 · 붉은빛) + 이름 없는 빌딩 불빛
    for x0, width, color, alpha in ((SIXTY3_X - 23, 46, GOLD, .7), (IFC_X, 30, "#7fb6ff", .55), (IFC_X + 34, 24, "#7fb6ff", .45),
                                    (IFC_X + 62, 22, "#7fb6ff", .35),
                                    (PARC_X - 1.5, 3, UP, .75), (PARC_X + 29.5, 3, UP, .75), (PARC_X + 36.5, 3, UP, .6),
                                    (PARC_X + 67.5, 3, UP, .6), (TOWER_X - 4, 8, "#ffe2a8", .5)):
        streaks.append(f'<rect x="{_f(x0)}" y="{WATER + 2}" width="{width}" height="62" fill="{color}" '
                       f'opacity="{alpha}" mask="url(#j13kfade)"/>')
    for _ in range(46):
        x = rng.uniform(0, W)
        streaks.append(f'<rect x="{_f(x)}" y="{WATER + 2}" width="{_f(rng.uniform(1.2, 3.4))}" '
                       f'height="{_f(rng.uniform(18, 44))}" fill="#ffd98a" opacity="{_f(rng.uniform(.15, .4))}" '
                       'mask="url(#j13kfade)"/>')
    ripples = "".join(f'<rect x="0" y="{_f(WATER + 6 + k * 6.5)}" width="{W * 2}" height=".8" fill="url(#j13kripple)"/>'
                      for k in range(11))
    return (f'<rect x="0" y="{WATER}" width="{W}" height="{H - WATER}" fill="url(#j13kwater)"/>'
            f'<g class="j13k-shimmer">{"".join(streaks)}</g>'
            f'<g class="j13k-ripples">{ripples}</g>')


def _bridge(seed: int = 34) -> str:
    rng = random.Random(seed)
    deck = 252
    arches = "".join(f"M{x} {deck}Q{x + 50} {deck - 22} {x + 100} {deck}" for x in range(-40, W + 40, 100))
    hangers = "".join(f"M{x + k} {deck - 22 + abs(50 - k) * .36 + .5}V{deck}"
                      for x in range(-40, W + 40, 100) for k in range(10, 100, 10) if 10 < k < 90)
    lamps = "".join(f'<circle cx="{x}" cy="{deck - 1.5}" r=".9"/>' for x in range(0, W, 25))

    def lane(color: str, y: float, seed_add: int) -> str:
        local = random.Random(seed + seed_add)
        cars = []
        for copy in (0, 1):
            x = 0.0
            while x < W:
                cars.append(f"M{_f(copy * W + x)} {_f(y)}h3.2v1.3h-3.2z")
                x += local.uniform(18, 70)
        return f'<path d="{"".join(cars)}" fill="{color}"/>'

    return (
        f'<path d="{arches}" fill="none" stroke="#2c4f93" stroke-width="2" opacity=".9"/>'
        f'<path d="{hangers}" stroke="#2c4f93" stroke-width=".7" opacity=".7"/>'
        f'<rect x="0" y="{deck}" width="{W}" height="5" fill="#16213f"/>'
        f'<rect x="0" y="{deck}" width="{W}" height="1" fill="#7f9ee6" opacity=".55"/>'
        f'<g fill="#ffe7b0" opacity=".8">{lamps}</g>'
        f'<g class="j13k-cars-l" style="--j13k-run:-{W}px">{lane("#fff3d1", deck - 2.6, 1)}</g>'
        f'<g class="j13k-cars-r" style="--j13k-run:{W}px" transform="translate(-{W} 0)">{lane("#ff4a4a", deck + 1.6, 2)}</g>'
    )


# ── 무늬(창 불빛 · 유리) ────────────────────────────────────────────────────────────────────────────────

def _defs() -> str:
    def windows(pid: str, lit: list[tuple[int, int]], color: str) -> str:
        cells = "".join(f'<rect x="{1 + c * 6}" y="{1 + r * 7}" width="2.6" height="3" fill="{color}"/>' for r, c in lit)
        return f'<pattern id="{pid}" width="18" height="21" patternUnits="userSpaceOnUse">{cells}</pattern>'

    return (
        "<defs>"
        '<linearGradient id="j13ksky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#030b22"/><stop offset=".5" stop-color="#0e2560"/>'
        '<stop offset=".74" stop-color="#26408e"/><stop offset="1" stop-color="#3b3486"/></linearGradient>'
        '<linearGradient id="j13karea" x1="0" y1="18" x2="0" y2="170" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#ffd27a" stop-opacity=".22"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></linearGradient>'
        '<radialGradient id="j13kbloom" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ffd27a" stop-opacity=".45"/>'
        '<stop offset="1" stop-color="#ffd27a" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="j13kbloomb" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#8ec5ff" stop-opacity=".4"/>'
        '<stop offset="1" stop-color="#8ec5ff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="j13kbloomr" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#ff6b6b" stop-opacity=".35"/>'
        '<stop offset="1" stop-color="#ff6b6b" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="j13khaze" cx=".5" cy="1" r=".6"><stop offset="0" stop-color="#8a6cff" stop-opacity=".6"/>'
        '<stop offset=".45" stop-color="#4f55c9" stop-opacity=".3"/><stop offset="1" stop-color="#1b2a66" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="j13kmoon" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff6d8" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#fff6d8" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="j13kgold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8a5f1d"/>'
        '<stop offset=".35" stop-color="#f6d27a"/><stop offset=".6" stop-color="#d9a441"/><stop offset="1" stop-color="#6b4716"/></linearGradient>'
        '<pattern id="j13kfloor" width="46" height="3.6" patternUnits="userSpaceOnUse">'
        '<rect width="46" height=".9" fill="#5c3d10" opacity=".55"/></pattern>'
        '<linearGradient id="j13kshine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff8dc" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="j13kglass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1b3b78"/>'
        '<stop offset=".45" stop-color="#4f86d6"/><stop offset="1" stop-color="#142c5c"/></linearGradient>'
        '<pattern id="j13kmull" width="5" height="5" patternUnits="userSpaceOnUse">'
        '<rect width=".7" height="5" fill="#0d1f45" opacity=".55"/><rect x="2" y="1" width="1.8" height="2" fill="#cfe6ff" opacity=".35"/></pattern>'
        '<linearGradient id="j13ksilver" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4e6a98"/>'
        '<stop offset=".5" stop-color="#c7dbf5"/><stop offset="1" stop-color="#3d5785"/></linearGradient>'
        '<linearGradient id="j13ktower" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9fb4d6"/>'
        '<stop offset=".5" stop-color="#eef4ff"/><stop offset="1" stop-color="#8aa0c4"/></linearGradient>'
        '<radialGradient id="j13kglow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#aee0ff" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#aee0ff" stop-opacity="0"/></radialGradient>'
        '<linearGradient id="j13kwater" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1a42"/>'
        '<stop offset="1" stop-color="#020815"/></linearGradient>'
        '<linearGradient id="j13kfadeg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="j13kfade" maskContentUnits="userSpaceOnUse"><rect x="0" y="{WATER}" width="{W}" height="70" fill="url(#j13kfadeg)"/></mask>'
        '<linearGradient id="j13kripple" x1="0" y1="0" x2="60" y2="0" spreadMethod="repeat" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#9fc4ff" stop-opacity="0"/><stop offset=".5" stop-color="#9fc4ff" stop-opacity=".22"/>'
        '<stop offset="1" stop-color="#9fc4ff" stop-opacity="0"/></linearGradient>'
        + windows("j13kwa", [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)], "#ffd98a")
        + windows("j13kwb", [(0, 1), (1, 0), (1, 2), (2, 1)], "#ffe7b0")
        + windows("j13kwc", [(0, 0), (1, 1), (1, 2), (2, 0)], "#cfe3ff")
        + "</defs>"
    )


@lru_cache(maxsize=4)
def scene_svg(variant: str = "market") -> str:
    """장면 한 장(SVG). 폰은 가운데가, PC 는 거의 다 보인다(xMidYMax slice — 아래를 맞추고 넘치는 위·옆을 자른다)."""
    # 시장분석 띠(236px)는 아래(강 · 다리)를 맞추고, 낮고 넓은 관심종목 띠는 위아래를 고르게 자른다(PC 에서 빌딩 꼭대기가 안 깎이게)
    fit = "xMidYMid slice" if variant == "watch" else "xMidYMax slice"
    return (
        f'<svg class="j13k-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="{fit}" aria-hidden="true" '
        'xmlns="http://www.w3.org/2000/svg">'
        + _defs()
        + f'<rect width="{W}" height="{H}" fill="url(#j13ksky)"/>'
        + _stars()
        # 초승달 — 가림 원 대신 가면(하늘색이 높이마다 달라 원 자국이 남지 않게)
        + '<mask id="j13kcres"><circle cx="1210" cy="44" r="11" fill="#fff"/><circle cx="1216" cy="40" r="10" fill="#000"/></mask>'
        + '<circle cx="1210" cy="44" r="30" fill="url(#j13kmoon)"/>'
        + '<circle cx="1210" cy="44" r="11" fill="#fff4cf" mask="url(#j13kcres)"/>'
        # 하늘을 천천히 가로지르는 비행기 불빛(흰 불 · 빨간 불 깜빡)
        + '<g class="j13k-plane"><circle cx="0" cy="0" r="1.5" fill="#ffffff"/>'
          '<circle class="j13k-blink" cx="-4" cy=".6" r="1.2" fill="#ff4a4a"/></g>'
        # 하늘 눈금 · 캔들(빌딩 뒤로 흐른다)
        + "".join(f'<rect x="0" y="{y}" width="{W}" height=".7" fill="#8fb4ff" opacity=".07"/>' for y in (70, 100, 130, 160))
        + f'<g class="j13k-chart" opacity=".88">{_chart()}</g>'
        # 먼 산 · 도시 빛 안개
        + f'<path d="M0 196Q120 170 240 186T480 178T720 190T960 172T1200 184T1440 176T1600 182V{WATER}H0z" fill="#0b1736"/>'
        + f'<rect x="0" y="150" width="{W}" height="{WATER - 150}" fill="url(#j13khaze)"/>'
        + _generic_buildings(7, "far")
        + _namsan(TOWER_X)
        + _lotte(LOTTE_X)
        + _generic_buildings(11, "near")
        # 꼭대기 빛 번짐(금 · 푸른 · 붉은)
        + f'<ellipse cx="{SIXTY3_X}" cy="96" rx="58" ry="44" fill="url(#j13kbloom)"/>'
        + f'<ellipse cx="{IFC_X + 30}" cy="120" rx="60" ry="40" fill="url(#j13kbloomb)"/>'
        + f'<ellipse cx="{PARC_X + 34}" cy="104" rx="56" ry="40" fill="url(#j13kbloomr)"/>'
        + _sixty_three(SIXTY3_X)
        + _ifc(IFC_X)
        + _parc_one(PARC_X)
        + _river()
        + _bridge()
        + "</svg>"
    )


# 움직임(이름 j13k — 자비스12(j3 · j12) 와 안 섞인다). transform · opacity 만.
CSS = """<style>
.j13k-scene{position:absolute;inset:0;z-index:0;overflow:hidden;pointer-events:none;background:#030b22}
.j13k-svg{position:absolute;inset:0;width:100%;height:100%;display:block}
.j13k-flow{animation:j13k-flow 70s linear infinite;will-change:transform}
@keyframes j13k-flow{from{transform:translateX(0)}to{transform:translateX(var(--j13k-strip))}}
.j13k-tw{animation:j13k-twinkle 5s ease-in-out infinite alternate}
.j13k-tw2{animation-duration:6.5s;animation-delay:-2s}
.j13k-tw3{animation-duration:8s;animation-delay:-4s}
@keyframes j13k-twinkle{from{opacity:1}to{opacity:.35}}
.j13k-blink{animation:j13k-blink 1.8s steps(2,jump-none) infinite}
@keyframes j13k-blink{0%{opacity:1}100%{opacity:.15}}
.j13k-shine{animation:j13k-shine 7s ease-in-out infinite}
@keyframes j13k-shine{0%{transform:translateY(0)}55%,100%{transform:translateY(-170px)}}
.j13k-shimmer{animation:j13k-shimmer 3.4s ease-in-out infinite alternate}
@keyframes j13k-shimmer{from{opacity:1}to{opacity:.62}}
.j13k-ripples{animation:j13k-ripple 9s linear infinite}
@keyframes j13k-ripple{from{transform:translateX(0)}to{transform:translateX(-60px)}}
.j13k-cars-l{animation:j13k-cars 26s linear infinite}
.j13k-cars-r{animation:j13k-cars-r 32s linear infinite}
@keyframes j13k-cars{from{transform:translateX(0)}to{transform:translateX(var(--j13k-run))}}
@keyframes j13k-cars-r{from{transform:translateX(-1600px)}to{transform:translateX(0)}}
.j13k-plane{animation:j13k-plane 46s linear infinite}
@keyframes j13k-plane{from{transform:translate(-80px,64px)}to{transform:translate(1700px,26px)}}
@media (prefers-reduced-motion:reduce){.j13k-scene *{animation:none!important}.j13k-plane{display:none}}
</style>"""


def scene_html(variant: str = "market") -> str:
    """머리 띠 안에 까는 배경 한 덩이(꾸밈은 CSS 를 따로 한 번 싣는다)."""
    return f'<div class="j13k-scene j13k-{variant}">{scene_svg(variant)}</div>'
