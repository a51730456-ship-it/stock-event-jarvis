"""PDF 한 쪽을 화면에 올릴 그림 한 장으로 뽑는다 (2026-09-07 상하님 지시).

상하님이 PDF 를 주시면 「이 테마 설명」 화면에 사진으로 넣는다. 그때 쓰는 도구다.
같은 PDF 를 다시 주시거나 내용을 고치셨을 때, 이 파일을 돌리면 같은 그림이 나온다.

  python tools/pdf_to_asset.py "C:/…/나스닥_매매규칙_가나.pdf" assets/us_method_rules.png

  · 가로 1400px 로 뽑는다 — 폰에서도 글씨가 읽히는 크기다.
  · 사방의 흰 여백은 24px 만 남기고 잘라 낸다.
  · 쪽이 여럿이면 `--page 2` 처럼 골라 준다(기본은 첫 쪽).

**그림을 바꿔도 코드는 안 고쳐도 된다** — method_help.py 는 assets/ 의 같은 이름
파일을 그대로 읽는다.
"""

from __future__ import annotations

import argparse
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 한 쪽 → 그림 한 장")
    parser.add_argument("pdf", help="읽을 PDF 경로")
    parser.add_argument("out", help="저장할 그림 경로 (assets/… .png)")
    parser.add_argument("--page", type=int, default=1, help="몇 쪽인가 (기본 1)")
    parser.add_argument("--width", type=int, default=1400, help="가로 픽셀 (기본 1400)")
    parser.add_argument("--pad", type=int, default=24, help="남길 흰 여백 (기본 24)")
    args = parser.parse_args()

    try:
        import pymupdf
        from PIL import Image, ImageChops
    except ImportError:
        print("pymupdf 와 pillow 가 있어야 합니다:  pip install pymupdf pillow")
        return 1

    source = pathlib.Path(args.pdf)
    if not source.is_file():
        print(f"PDF 를 찾지 못했습니다 — {source}")
        return 1

    document = pymupdf.open(str(source))
    if not 1 <= args.page <= document.page_count:
        print(f"{args.page}쪽은 없습니다 — 이 PDF 는 {document.page_count}쪽입니다")
        return 1

    page = document[args.page - 1]
    zoom = float(args.width) / page.rect.width
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(out))

    # 흰 여백을 잘라 낸다 — A4 는 아래쪽이 많이 비어서, 그대로 두면 화면에서
    # 그림 밑에 빈칸이 한 장 생긴다.
    image = Image.open(out).convert("RGB")
    box = ImageChops.difference(image, Image.new("RGB", image.size, (255, 255, 255))).getbbox()
    if box:
        pad = int(args.pad)
        image = image.crop((
            max(0, box[0] - pad), max(0, box[1] - pad),
            min(image.width, box[2] + pad), min(image.height, box[3] + pad),
        ))
        image.save(out, optimize=True)

    print(f"{out}  {image.width}x{image.height}  {out.stat().st_size:,}바이트")
    return 0


if __name__ == "__main__":
    sys.exit(main())
