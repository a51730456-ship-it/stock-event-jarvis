# -*- coding: utf-8 -*-
"""한국 종목의 「📅 실적 발표 · 👥 애널리스트 의견 · 🔍 공매도·내부자·배당」 자료가 어디 있나 살핀다
(2026-11-04 상하님 — 자비스12 세부사항 캡처 「한국테마에서 3번째 캡쳐 빠졌고」 · 밤 「왜 이거 안 넣냐 말 좀 들어라」).

보기만 한다(아무것도 안 쓴다 · 결과는 J13_OUT 폴더). DART 열쇠는 깃허브 비밀 칸(DART_API_KEY)에서만 읽고 찍지 않는다.
  · DART — 잠정실적 공시(발표일) · 임원·주요주주 소유보고(내부자) · 배당에 관한 사항
  · 네이버 모바일 재무 — 증권사 예상(E) 칸
  · 와이즈리포트(네이버 기업정보) — 투자의견 · 목표주가 · 추정기관 수 · 증권사별 목표가
  · 공매도 — 한국거래소 · 네이버 몇 군데
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT = Path(os.environ.get("J13_OUT") or "j13street")
CODES = ("005930", "096770")
HEAD = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Referer": "https://m.stock.naver.com/"}
LINES: list[str] = []


def say(text: str) -> None:
    LINES.append(text)


def shape(value, depth=0):
    if depth > 3:
        return "…"
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [shape(value[0], depth + 1), f"(줄 {len(value)})"] if value else []
    return value if not isinstance(value, str) else value[:90]


def get(url, **kw):
    try:
        r = requests.get(url, headers=HEAD, timeout=15, **kw)
        return r.status_code, r.content.decode(r.apparent_encoding or "utf-8", errors="replace")
    except Exception as exc:
        return None, f"실패 {exc}"


def text_near(html_text: str, word: str, width: int = 900) -> str:
    at = html_text.find(word)
    if at < 0:
        return "(없음)"
    plain = re.sub(r"<[^>]+>", " ", html_text[max(0, at - 300):at + width])
    return " ".join(plain.split())[:width]


def dart(code: str) -> None:
    key = (os.environ.get("DART_API_KEY") or "").strip()
    if not key:
        say("DART 열쇠 없음")
        return
    import disclosure_data

    mapping = disclosure_data.fetch_dart_corp_code_map(key)
    table = (mapping or {}).get("data") if isinstance(mapping, dict) else None
    corp = ((table or {}).get(code) or {}).get("corp_code") if isinstance(table, dict) else None
    say(f"DART 회사번호 {code} → {corp} · 표 상태 {(mapping or {}).get('status')}")
    if not corp:
        return
    base = "https://opendart.fss.or.kr/api/"
    end = date.today()
    start = end - timedelta(days=720)
    for kind in ("I", "B"):
        status, body = get(base + "list.json", params={"crtfc_key": key, "corp_code": corp, "bgn_de": start.strftime("%Y%m%d"),
                                                       "end_de": end.strftime("%Y%m%d"), "pblntf_ty": kind, "page_count": 100})
        try:
            data = json.loads(body)
            items = data.get("list") or []
            hits = [f"{i.get('rcept_dt')} {i.get('report_nm')}" for i in items
                    if re.search(r"잠정|실적|배당|기업설명회|IR", str(i.get("report_nm")))]
            say(f"DART 공시({kind}) {status} · {data.get('status')} · 전체 {len(items)} · 실적/배당/IR {len(hits)}: {hits[:14]}")
        except ValueError:
            say(f"DART 공시({kind}) {status} 읽기 실패 {body[:200]}")
    status, body = get(base + "elestock.json", params={"crtfc_key": key, "corp_code": corp})
    try:
        data = json.loads(body)
        items = data.get("list") or []
        say(f"DART 임원·주요주주 소유보고 {status} · {data.get('status')} · {len(items)}건 · 모양 {shape(items[:1])}")
        say("   최근: " + " | ".join(f"{i.get('rcept_dt')} {i.get('repror')} {i.get('isu_exctv_ofcps')} "
                                       f"증감 {i.get('sp_stock_lmp_irds_cnt')} 비율 {i.get('sp_stock_lmp_rate')}" for i in items[-6:]))
    except ValueError:
        say(f"DART 소유보고 {status} 읽기 실패 {body[:200]}")
    for year in (end.year - 1, end.year - 2):
        status, body = get(base + "alotMatter.json", params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(year),
                                                             "reprt_code": "11011"})
        try:
            data = json.loads(body)
            items = data.get("list") or []
            say(f"DART 배당({year}) {status} · {data.get('status')} · " + " | ".join(
                f"{i.get('se')}={i.get('thstrm')}" for i in items[:12]))
        except ValueError:
            say(f"DART 배당 {status} 읽기 실패 {body[:200]}")


def naver(code: str) -> None:
    for group in ("quarter", "annual"):
        status, body = get(f"https://m.stock.naver.com/api/stock/{code}/finance/{group}")
        try:
            info = json.loads(body).get("financeInfo") or {}
            heads = [(h.get("key"), h.get("title"), h.get("isConsensus")) for h in info.get("trTitleList") or []]
            say(f"네이버 재무 {group} {status} 칸 {heads}")
            for row in info.get("rowList") or []:
                if re.sub(r"\s", "", str(row.get("title"))) in ("매출액", "영업이익", "EPS"):
                    cols = row.get("columns") or {}
                    say(f"   {row.get('title')}: " + " · ".join(f"{k}={(v or {}).get('value')}" for k, v in cols.items()))
        except ValueError:
            say(f"네이버 재무 {group} {status} 읽기 실패")


def wise(code: str) -> None:
    status, body = get(f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}")
    say(f"와이즈 기업개요 {status} · 투자의견표: {text_near(body, 'cTB15', 1200)}")
    status, body = get(f"https://navercomp.wisereport.co.kr/v2/company/c1050001.aspx?cmp_cd={code}")
    say(f"와이즈 컨센서스 {status} · {len(body)}자 · 목표주가: {text_near(body, '목표주가', 900)}")
    for word in ("추정기관", "투자의견", "증권사", "제시일"):
        say(f"   [{word}] {text_near(body, word, 500)}")
    for path in ("/v2/company/ajax/cF9001.aspx", "/v2/company/ajax/cF5001.aspx"):
        status, body = get("https://navercomp.wisereport.co.kr" + path, params={"cmp_cd": code, "data_typ": "1"})
        say(f"와이즈 {path} {status} · {len(body)}자 · {' '.join(re.sub(r'<[^>]+>', ' ', body).split())[:600]}")


def short(code: str) -> None:
    for url in (f"https://m.stock.naver.com/api/stock/{code}/shortSelling/trend",
                f"https://m.stock.naver.com/api/stock/{code}/short",
                f"https://finance.naver.com/item/short_trade.naver?code={code}",
                f"https://m.stock.naver.com/api/stock/{code}/integration/short"):
        status, body = get(url)
        say(f"공매도 시도 {url} → {status} · {len(body)}자 · {' '.join(re.sub(r'<[^>]+>', ' ', body).split())[:200]}")
    end = date.today()
    form = {"bld": "dbms/MDC/STAT/srt/MDCSTAT30102", "searchType": "1", "mktId": "STK", "isuCd": code,
            "strtDd": (end - timedelta(days=14)).strftime("%Y%m%d"), "endDd": end.strftime("%Y%m%d")}
    try:
        r = requests.post("https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", data=form, timeout=15,
                          headers={**HEAD, "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"})
        say(f"한국거래소 공매도 {r.status_code} · {r.text[:400]}")
    except Exception as exc:
        say(f"한국거래소 공매도 실패 {exc}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for code in CODES:
        say(f"\n================ {code}")
        for step in (dart, naver, wise, short):
            try:
                step(code)
            except Exception as exc:
                say(f"{step.__name__} 오류 {exc}")
    text = "\n".join(LINES) + "\n"
    (OUT / "result.txt").write_text(text, encoding="utf-8")
    print(text[:30000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
