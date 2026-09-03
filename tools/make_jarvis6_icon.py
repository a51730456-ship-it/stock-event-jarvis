"""자비스6 미국테마 홈 화면 아이콘을 그린다 (2026-09-03 상하님 지시).

상하님 — *"어플 디자인까지 해서 만들고, 내가 어플 누르면 자동으로 들어가게."*

폰 홈 화면에 얹을 그림이라 **작게 줄여도 알아볼 수 있어야 한다.** 그래서
글자는 「J6」 둘뿐이고, 뒤에 오르는 선 하나만 둔다. 「JARVIS 6」을 다 적으면
48픽셀에서 뭉개진다.

만든 그림은 `static/` 에 둔다 — 스트림릿이 `/app/static/…` 주소로 내준다.
다시 만들려면 이 파일을 그냥 돌리면 된다:  python tools/make_jarvis6_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static"
BOLD = "C:/Windows/Fonts/malgunbd.ttf"

# 새 디자인의 그 남색이다(_J6_CSS 의 판 색과 같은 계열).
DEEP = (5, 8, 15)
MID = (18, 33, 63)
BLUE = (77, 166, 255)
WHITE = (255, 255, 255)


def _background(size: int) -> Image.Image:
    """위가 옅고 아래가 짙은 남색 바탕."""
    image = Image.new("RGB", (size, size), DEEP)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / max(1, size - 1)
        # 위쪽 3분의 1에 빛이 도는 느낌만 준다.
        glow = max(0.0, 1.0 - ratio * 1.9)
        draw.line(
            [(0, y), (size, y)],
            fill=tuple(int(DEEP[i] + (MID[i] - DEEP[i]) * glow) for i in range(3)),
        )
    return image


def _chart_line(draw: ImageDraw.ImageDraw, size: int) -> None:
    """아래쪽을 가로지르는 오르는 선 하나. 지어낸 모양이라 숫자는 안 적는다."""
    points = []
    steps = 44
    for step in range(steps + 1):
        x = size * (0.08 + 0.84 * step / steps)
        # 글자(J6) 밑을 지나가게 낮게 깐다 — 글자를 가로지르면 둘 다 안 읽힌다.
        base = 0.86 - 0.20 * (step / steps)          # 왼쪽 아래에서 오른쪽 위로
        wobble = 0.022 * math.sin(step / steps * math.pi * 3.2)
        points.append((x, size * (base + wobble)))
    draw.line(points, fill=BLUE, width=max(3, size // 42), joint="curve")
    # 끝점에 밝은 점 하나
    end = points[-1]
    dot = max(4, size // 26)
    draw.ellipse([end[0] - dot, end[1] - dot, end[0] + dot, end[1] + dot], fill=WHITE)


def _mark(draw: ImageDraw.ImageDraw, size: int) -> None:
    """가운데 「J6」 — J 는 흰색, 6 은 파랑."""
    font = ImageFont.truetype(BOLD, int(size * 0.46))
    j_box = draw.textbbox((0, 0), "J", font=font)
    six_box = draw.textbbox((0, 0), "6", font=font)
    gap = int(size * 0.03)
    total = (j_box[2] - j_box[0]) + gap + (six_box[2] - six_box[0])
    left = (size - total) / 2
    top = size * 0.16
    draw.text((left - j_box[0], top - j_box[1]), "J", font=font, fill=WHITE)
    draw.text((left + (j_box[2] - j_box[0]) + gap - six_box[0], top - six_box[1]),
              "6", font=font, fill=BLUE)


def build(size: int) -> Image.Image:
    image = _background(size)
    draw = ImageDraw.Draw(image)
    _chart_line(draw, size)
    _mark(draw, size)
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        build(size).save(OUT / f"jarvis6_icon_{size}.png", optimize=True)
    # 아이폰이 쓰는 크기. 안드로이드는 위 둘을 쓴다.
    build(180).save(OUT / "jarvis6_icon_180.png", optimize=True)
    for name in ("jarvis6_icon_192.png", "jarvis6_icon_512.png", "jarvis6_icon_180.png"):
        path = OUT / name
        print(f"{name}  {path.stat().st_size:,}바이트")


if __name__ == "__main__":
    main()
