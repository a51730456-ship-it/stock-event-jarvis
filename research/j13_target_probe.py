# -*- coding: utf-8 -*-
"""한국 목표주가 최저 · 최고를 어디서 받을 수 있는지 살펴보는 시험(2026-11-11 상하님 「미국테마 캡처처럼 지금 · 금액이 나와야지」).

자비스12 목표주가 막대는 최저 · 평균 · 최고가 있어야 그린다. 한국 재무 파일(KR.json)에는 평균(네이버 consensusInfo)만 있다.
깃허브 컴퓨터에서 몇 곳을 열어 「목표가」 글자 둘레만 찍는다 — 파일은 안 쓴다 · 화면 · 점수와 무관.
"""
from __future__ import annotations

import json
import re
import sys

import requests

CODE = sys.argv[1] if len(sys.argv) > 1 else "005930"
HEAD = {"User-Agent": "Mozilla/5.0 (jarvis13 probe)", "Referer": "https://finance.naver.com/"}
KEYS = ("목표가", "목표주가", "TARGET", "제공처", "최고", "최저", "goal", "Goal")


def show(name: str, url: str, *, js: bool = False) -> str:
    try:
        res = requests.get(url, headers=HEAD, timeout=20)
    except Exception as exc:
        print(f"== {name}: 실패 {type(exc).__name__}")
        return ""
    text = res.content.decode(res.encoding or "utf-8", errors="replace")
    if "euc-kr" in (res.headers.get("content-type") or "").lower():
        text = res.content.decode("euc-kr", errors="replace")
    print(f"== {name}: {res.status_code} · {len(text):,}자 · {url}")
    if js:
        try:
            data = json.loads(text)
            print("   열쇠:", list(data)[:30] if isinstance(data, dict) else type(data).__name__)
            return text
        except ValueError:
            pass
    shown = 0
    for key in KEYS:
        for hit in re.finditer(re.escape(key), text):
            piece = " ".join(re.sub(r"<[^>]+>", " ", text[max(0, hit.start() - 160):hit.end() + 220]).split())
            print(f"   [{key}] {piece[:300]}")
            shown += 1
            if shown >= 10:
                break
        if shown >= 10:
            break
    links = sorted(set(re.findall(r"[\"']([^\"']*(?:json|ajax|_data|cF\d+)[^\"']*)[\"']", text)))[:25]
    if links:
        print("   불러오는 주소:", links)
    return text


def main() -> int:
    whole = show("네이버 모바일 integration", f"https://m.stock.naver.com/api/stock/{CODE}/integration", js=True)
    try:
        data = json.loads(whole)
        print("   consensusInfo:", data.get("consensusInfo"))
        print("   researches[0] 열쇠:", list((data.get("researches") or [{}])[0]))
        print("   researches 수:", len(data.get("researches") or []))
    except Exception as exc:
        print("   읽기 실패", type(exc).__name__)
    show("와이즈리포트 컨센서스 c1050001", f"https://navercomp.wisereport.co.kr/v2/company/c1050001.aspx?cmp_cd={CODE}")
    show("와이즈리포트 c1080001", f"https://navercomp.wisereport.co.kr/v2/company/c1080001.aspx?cmp_cd={CODE}")
    show("와이즈리포트 c1010001", f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={CODE}")
    show("FnGuide 컨센서스", f"https://comp.fnguide.com/SVO2/ASP/SVD_Consensus.asp?pGB=1&gicode=A{CODE}")
    for part in ("01", "02", "03", "04"):
        show(f"FnGuide json 01_06/{part}", f"https://comp.fnguide.com/SVO2/json/data/01_06/{part}_A{CODE}.json", js=True)
    listing = show("네이버 리서치 종목 목록", f"https://finance.naver.com/research/company_list.naver?searchType=itemCode&itemCode={CODE}")
    nids = re.findall(r"company_read\.naver\?nid=(\d+)", listing)
    print("   리포트 번호:", nids[:8])
    if nids:
        show("네이버 리서치 한 건", f"https://finance.naver.com/research/company_read.naver?nid={nids[0]}&searchType=itemCode&itemCode={CODE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
