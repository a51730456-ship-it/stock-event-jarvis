"""시장 현황(미국 업종 지도) 시험 — 2026-08-28 상하님 지시로 넣은 화면.

상하님 — "시장국면·상승여건양호 사이에 세 번째 캡처처럼 시장현황을 미국 자료
찾아서 넣어 줘."

여기서 지키는 것 셋.
  ① 상자 넓이가 업종 몫에 비례하고, 칸을 빈틈·겹침 없이 채운다.
  ② 화면이 자료를 **기다리지 않는다** — 공책에 있는 것만 읽는다.
  ③ 자리는 시장 상황 뒤, 시장 국면 게이지 앞이다.
"""

from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).parent / "pages" / "2_자비스3.py"
DATA = Path(__file__).parent / "jarvis3_data.py"
MOBILE = Path(__file__).parent / "mobile_ui.py"


def _page_namespace() -> dict:
    """지도 그리는 함수만 떼어 내 돌려 본다(스트림릿 없이)."""
    source = PAGE.read_text(encoding="utf-8")
    chunk = source[source.index("_SECTOR_MAP_W = "):source.index("def _sector_map_cell(")]
    namespace: dict = {}
    exec(chunk, namespace)
    return namespace


def test_the_boxes_fill_the_whole_map_without_gaps_or_overlaps():
    """넓이가 몫에 비례하고, 겹치지도 비지도 않는다."""
    namespace = _page_namespace()
    width, height = namespace["_SECTOR_MAP_W"], namespace["_SECTOR_MAP_H"]
    weights = [32.5, 13.7, 10.5, 9.4, 9.3, 8.8, 4.8, 4.3, 2.8, 2.0, 1.9]
    scale = (width * height) / sum(weights)
    boxes: list = []
    namespace["_squarify"]([weight * scale for weight in weights], 0.0, 0.0, width, height, boxes)

    assert len(boxes) == len(weights), "업종 하나가 사라졌다"
    covered = sum(box[2] * box[3] for box in boxes)
    assert abs(covered - width * height) < 0.5, f"칸을 다 못 채웠다: {covered:.1f}"
    for (x, y, box_width, box_height), weight in zip(boxes, weights):
        assert x >= -0.01 and y >= -0.01, "상자가 칸 밖으로 나갔다"
        assert x + box_width <= width + 0.01 and y + box_height <= height + 0.01
        share = (box_width * box_height) / (width * height) * 100
        assert abs(share - weight / sum(weights) * 100) < 0.5, \
            f"넓이가 몫과 다르다: {share:.2f}% vs {weight / sum(weights) * 100:.2f}%"


def test_bigger_share_gets_a_bigger_box():
    """몫이 큰 업종이 더 큰 상자를 받는다."""
    namespace = _page_namespace()
    width, height = namespace["_SECTOR_MAP_W"], namespace["_SECTOR_MAP_H"]
    weights = [40.0, 30.0, 20.0, 10.0]
    scale = (width * height) / sum(weights)
    boxes: list = []
    namespace["_squarify"]([weight * scale for weight in weights], 0.0, 0.0, width, height, boxes)
    areas = [box[2] * box[3] for box in boxes]
    assert areas == sorted(areas, reverse=True), "큰 몫이 더 큰 상자를 못 받았다"


def test_the_colour_follows_the_us_rule():
    """미국 화면 규칙 — 오르면 파랑, 내리면 빨강. 많이 움직일수록 진하다."""
    namespace = _page_namespace()
    tone = namespace["_sector_tone"]
    up_strong, up_weak = tone(3.0), tone(0.2)
    down_strong = tone(-3.0)
    to_rgb = lambda value: tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    assert to_rgb(up_strong)[2] > to_rgb(up_strong)[0], "오름인데 파랑이 아니다"
    assert to_rgb(down_strong)[0] > to_rgb(down_strong)[2], "내림인데 빨강이 아니다"
    assert to_rgb(up_strong)[2] > to_rgb(up_weak)[2], "많이 올랐는데 더 진하지 않다"
    assert tone(None) == "#22304a", "값이 없으면 무채색이어야 한다"


def test_the_screen_never_waits_for_the_sector_data():
    """화면은 공책에 있는 것만 읽는다 (CLAUDE.md 0-0 첫째).

    받는 데 2초가 걸리는 조회다. 화면 그리는 도중에 받으면 첫 화면이 그만큼 밀린다.
    """
    data = DATA.read_text(encoding="utf-8")
    getter = data[data.index("def get_us_sector_map("):]
    getter = getter[:getter.index(chr(10) + "def ", 10)]
    assert "_compute_sector_map()" not in getter, "화면이 부르는 자리에서 직접 받고 있다"
    assert "warm_sector_map()" in getter, "뒤에서 받기를 시작하지 않는다"
    warm = data[data.index("def warm_sector_map("):]
    warm = warm[:warm.index(chr(10) + "def ", 10)]
    assert "threading.Thread" in warm, "뒤 일꾼에게 안 맡긴다"
    # 관심종목 화면이 뉴스를 다 받은 뒤에 미리 챙긴다.
    page = PAGE.read_text(encoding="utf-8")
    after_news = page[page.index("def _warm_after_news("):]
    after_news = after_news[:after_news.index(chr(10) + "def ", 10)]
    assert "warm_sector_map" in after_news, "관심종목 화면이 미리 안 챙긴다"


def test_the_map_sits_between_the_market_state_and_the_gauges():
    """자리 — 시장 상황 바로 뒤, 시장 국면 게이지 앞 (상하님 지시)."""
    page = PAGE.read_text(encoding="utf-8")
    cells = page[page.index("    top_cells = ["):page.index("    # 게이지 스타일은")]
    phase = cells.index("_market_phase_cell(")
    sector = cells.index("_sector_map_cell(")
    fear = cells.index("_fear_greed_box()")
    assert phase < sector < fear, "지도가 시장 상황과 게이지 사이가 아니다"
    # 폰에서는 게이지 둘이 맨 뒤(order 10)로 간다. 그 사이 값을 받아야 한다.
    mobile = MOBILE.read_text(encoding="utf-8")
    gauge_order = int(re.search(r"\.fg-box \{ order: (\d+)", mobile).group(1))
    map_order = int(re.search(r"\.j3-sector-map \{ order: (\d+)", mobile).group(1))
    assert 0 < map_order < gauge_order, f"폰에서 자리가 어긋난다: {map_order} vs {gauge_order}"


def test_the_map_says_what_it_counted():
    """무엇을 셌는지 화면에 적는다 — 미국장 전체인 척하지 않는다."""
    page = PAGE.read_text(encoding="utf-8")
    cell = page[page.index("def _sector_map_cell("):]
    cell = cell[:cell.index(chr(10) + "def ", 10)]
    assert "자비스가 보는 미국 {breadth['total']}종목 기준" in cell, "무엇을 셌는지 안 적었다"
    assert "칸 크기 = 미국 시장에서 차지하는 몫" in cell, "칸 크기가 무엇인지 안 적었다"


def test_the_breadth_count_never_downloads():
    """상승·하락 개수는 **이미 받아 둔 자료로만** 센다."""
    data = DATA.read_text(encoding="utf-8")
    breadth = data[data.index("def _sector_breadth("):]
    breadth = breadth[:breadth.index(chr(10) + "def ", 10)]
    assert "_download_cache_only(" in breadth, "여기서 새로 내려받고 있다"
    assert "_download_cached(" not in breadth
