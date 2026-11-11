# -*- coding: utf-8 -*-
"""한국 목표주가 최저 · 최고를 어디서 받을 수 있는지 살펴보는 시험(2026-11-11 상하님 「미국테마 캡처처럼 지금 · 금액이 나와야지」).

자비스12 목표주가 막대는 최저 · 평균 · 최고가 있어야 그린다. 한국 재무 파일(KR.json)에는 평균(네이버 consensusInfo)만 있다.
1차(90c060c): 와이즈리포트 기업현황(c1010001 — 매주 이미 받는 화면)에 「제공처별 투자의견 및 목표주가」 표(cTB24)가 있다.
2차: 그 표 전체와 투자의견 표(cTB15 · 추정기관수) · 네이버 평균을 나란히 찍어, 어느 기간의 제공처가 평균 · 기관 수와 맞는지 본다.
찍기만 한다 — 파일은 안 쓴다 · 화면 · 점수와 무관.
"""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta

import requests

HEAD = {"User-Agent": "Mozilla/5.0 (jarvis13 probe)", "Referer": "https://finance.naver.com/"}


def cells_of(html_text: str, table_id: str) -> list:
    at = html_text.find(f'id="{table_id}"')
    if at < 0:
        return []
    table = html_text[at:html_text.find("</table>", at)]
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S):
        cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
        if cells:
            rows.append(cells)
    return rows


def num(text):
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


def main() -> int:
    for code in sys.argv[1:] or ["005930"]:
        print(f"######## {code}")
        whole = requests.get(f"https://m.stock.naver.com/api/stock/{code}/integration", headers=HEAD, timeout=20).json()
        print("네이버 consensusInfo:", whole.get("consensusInfo"))
        page = requests.get(f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}", headers=HEAD, timeout=20)
        text = page.content.decode("utf-8", errors="replace")
        print("cTB15:", cells_of(text, "cTB15"))
        rows = cells_of(text, "cTB24")
        print(f"cTB24 줄 {len(rows)}개")
        for row in rows:
            print("   ", row)
        today = date.today()
        picked = []
        for row in rows:
            if len(row) < 3:
                continue
            day = re.match(r"(\d{2,4})[./-](\d{1,2})[./-](\d{1,2})", row[1])
            target = num(row[2])
            if not day or not target:
                continue
            y = int(day.group(1))
            y = y + 2000 if y < 100 else y
            picked.append((date(y, int(day.group(2)), int(day.group(3))), target, row[0]))
        for months in (1, 3, 6, 12, 120):
            near = [t for d, t, _ in picked if d >= today - timedelta(days=31 * months)]
            if near:
                print(f"   {months}개월 안: {len(near)}곳 · 평균 {sum(near) / len(near):,.0f} · 최저 {min(near):,.0f} · 최고 {max(near):,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
