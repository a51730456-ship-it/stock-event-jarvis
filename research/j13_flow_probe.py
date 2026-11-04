"""자비스13 종목 수급 「수급 표를 찾지 못했습니다」 까닭 살피기 (2026-11-04 상하님 「로딩 문제 해결하고」).

깃허브 컴퓨터에서 네이버 종목 수급 화면(frgn.naver)과 모바일 자료(trend)를 받아 모양만 적는다. 저장소에는 아무것도 안 쓴다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jarvis4_data as j4  # 얼린 파일 — 부르기만

for code in ("005930", "000660"):
    url = j4._STOCK_FLOW_URL.format(code=code)
    r = requests.get(url, headers=j4._HEADERS, timeout=10)
    r.encoding = "euc-kr"
    html = r.text
    print(f"\n== {code} frgn {r.status_code} · 글자 {len(html)} · 줄 맞음 {len(j4._FLOW_ROW_PATTERN.findall(html))} · 읽힌 줄 {len(j4._parse_stock_flow(html))}")
    for word in ("tah p10 gray03", "외국인", "기관", "순매매"):
        print(f"   「{word}」 {html.count(word)}번")
    at = html.find("순매매")
    print("   앞부분:", re.sub(r"\s+", " ", html[max(0, at - 300): at + 1500])[:1800])
    for tail in ("trend?pageSize=5", "integration"):
        m = requests.get(f"https://m.stock.naver.com/api/stock/{code}/{tail}", headers=j4._HEADERS, timeout=10)
        text = m.text
        print(f"== {code} 모바일 {tail} {m.status_code} · 글자 {len(text)}")
        try:
            data = m.json()
            sample = data[:2] if isinstance(data, list) else {k: data[k] for k in list(data)[:6]}
            print("  ", json.dumps(sample, ensure_ascii=False)[:1500])
        except Exception as exc:
            print("   JSON 아님:", exc, text[:300])
