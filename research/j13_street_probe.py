# -*- coding: utf-8 -*-
"""한국 종목의 「실적 발표 · 애널리스트 의견·목표주가 · 공매도 · 배당」 자료가 어디 있나 살핀다 (2026-11-04 상하님 — 자비스12
세부사항 캡처를 보이시며 「한국테마에서 3번째 캡쳐 빠졌고」).

보기만 한다(아무것도 안 쓴다 · 결과는 J13_OUT 폴더). 주소마다 응답 코드 · 길이 · 앞부분 · JSON 이면 키를 적는다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

OUT = Path(os.environ.get("J13_OUT") or "j13street")
CODES = ("005930", "096770")
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Referer": "https://m.stock.naver.com/"}
URLS = (
    "https://m.stock.naver.com/api/stock/{code}/integration",
    "https://m.stock.naver.com/api/stock/{code}/basic",
    "https://m.stock.naver.com/api/stock/{code}/finance/annual",
    "https://m.stock.naver.com/api/stock/{code}/shortSelling",
    "https://m.stock.naver.com/api/stock/{code}/short-selling",
    "https://m.stock.naver.com/api/stock/{code}/consensus",
    "https://m.stock.naver.com/api/stock/{code}/research",
    "https://m.stock.naver.com/api/stock/{code}/dividend",
    "https://m.stock.naver.com/api/stock/{code}/disclosure?page=1&pageSize=5",
    "https://m.stock.naver.com/api/research/stock/{code}?page=1&pageSize=5",
    "https://finance.naver.com/item/main.naver?code={code}",
    "https://finance.naver.com/item/coinfo.naver?code={code}",
    "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}",
)


def _shape(value, depth=0):
    if depth > 2:
        return "…"
    if isinstance(value, dict):
        return {k: _shape(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [_shape(value[0], depth + 1), f"(줄 {len(value)})"] if value else []
    return value if not isinstance(value, str) else value[:80]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = []
    for code in CODES:
        for url in URLS:
            target = url.format(code=code)
            try:
                response = requests.get(target, headers=HEAD, timeout=12)
                text = response.content.decode(response.apparent_encoding or "utf-8", errors="replace")
                lines.append(f"\n=== {target} · {response.status_code} · {len(text)}자")
                try:
                    lines.append(json.dumps(_shape(json.loads(text)), ensure_ascii=False)[:6000])
                except ValueError:
                    for word in ("투자의견", "목표주가", "공매도", "컨센서스", "실적발표", "배당", "추정기관"):
                        at = text.find(word)
                        if at >= 0:
                            snippet = " ".join(text[max(0, at - 200):at + 600].split())
                            lines.append(f"[{word}] {snippet[:900]}")
            except Exception as exc:
                lines.append(f"\n=== {target} · 실패 {exc}")
    text = "\n".join(lines) + "\n"
    (OUT / "result.txt").write_text(text, encoding="utf-8")
    print(text[:20000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
