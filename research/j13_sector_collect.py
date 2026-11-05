"""한국 「시장 현황」(업종 지도) 자료 모으기 — 업종 목록 · 업종마다 구성 종목 · 업종 시가총액 (2026-11-05 상하님 「미국테마처럼 하라고
한국테마도 배치도」 · docs/JARVIS13.md 4-1).

자비스12 「시장 현황」은 칸 크기 = 그 업종이 시장에서 차지하는 몫이다. 한국 자료(KR.json · kr_roster.json)에는 업종 칸이 없어 여기서 모은다.
  · 업종 목록 — 네이버 모바일 증권(테마와 같은 꼴의 주소 · 안 되면 PC 「업종별 시세」 표)
  · 업종마다 구성 종목 — 종목 코드 · 시가총액(응답에 있으면 그 값, 없으면 data/fundamentals/KR.json 의 mcap · 둘 다 없으면 빈칸)
data/kr_sectors.json 에 쓴다(지우지 않고 덮어씀 · 못 받은 업종은 옛 값을 둔다). 점수 · 판정에 안 쓴다(보여 주기만).
깃허브 「자비스13 업종 자료 모으기」가 돌린다. 작업 갈래에서는 쓰지 않고 첫 응답의 칸 이름 · 위 10업종만 찍는다(J13_SECTOR_DRY=1).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("J13_SECTOR_OUT") or ROOT / "data" / "kr_sectors.json")
KR_FILE = ROOT / "data" / "fundamentals" / "KR.json"
SEOUL = ZoneInfo("Asia/Seoul")
LIST_API = "https://m.stock.naver.com/api/stocks/industry?page={page}&pageSize=100"
DETAIL_API = "https://m.stock.naver.com/api/stocks/industry/{no}?page={page}&pageSize=100"
LIST_PAGE = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
DETAIL_PAGE = "https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no={no}"
HEADERS = {"User-Agent": "Mozilla/5.0 (jarvis13 sector collector)", "Referer": "https://m.stock.naver.com/"}
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)


def _get(url: str, *, as_json: bool = True, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            response = _SESSION.get(url, timeout=10)
            response.raise_for_status()
            if as_json:
                return response.json()
            response.encoding = "euc-kr"
            return response.text
        except Exception as exc:          # 잠깐 막힌 것 — 조금 쉬고 다시
            last = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"{url} — {last}")


def _num(text):
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def sector_list() -> tuple[list, str, list]:
    """업종 목록 [{no, name, change_pct}] · 어디서 받았나 · 첫 응답의 칸 이름(모양 확인용)."""
    rows, keys = [], []
    try:
        for page in range(1, 4):
            payload = _get(LIST_API.format(page=page))
            groups = payload.get("groups") or []
            if groups and not keys:
                keys = sorted(groups[0].keys())
            for group in groups:
                no = str(group.get("no") or "").strip()
                if no:
                    rows.append({"no": no, "name": str(group.get("name") or "").strip(),
                                 "change_pct": _num(group.get("changeRate"))})
            if len(groups) < 100:
                break
        if rows:
            return rows, "mobile", keys
    except Exception as exc:
        print(f"모바일 업종 목록 실패 — {exc}"[:200], flush=True)
    html = _get(LIST_PAGE, as_json=False)
    pattern = re.compile(r'sise_group_detail\.naver\?type=upjong&no=(\d+)">([^<]+)</a>.*?([+-]?\d+\.\d+)%', re.S)
    for no, name, pct in pattern.findall(html):
        rows.append({"no": no, "name": name.strip(), "change_pct": _num(pct)})
    return rows, "pc", keys


def sector_members(no: str, source: str) -> tuple[list, list]:
    """업종 구성 종목 [{code, name, mcap(억 원 · 없으면 None)}] · 첫 종목 칸 이름."""
    members, keys = [], []
    if source == "mobile":
        for page in range(1, 11):
            payload = _get(DETAIL_API.format(no=no, page=page))
            stocks = payload.get("stocks") or []
            if stocks and not keys:
                keys = sorted(stocks[0].keys())
            for item in stocks:
                code = str(item.get("itemCode") or "").strip()
                if re.fullmatch(r"\d{6}|\d{5}[A-Z]|\d{4}[A-Z]\d", code or ""):
                    members.append({"code": code, "name": str(item.get("stockName") or "").strip(),
                                    "mcap": _num(item.get("marketValue"))})
            total = payload.get("totalCount")
            if not stocks or (total is not None and len(members) >= int(total)):
                break
        return members, keys
    html = _get(DETAIL_PAGE.format(no=no), as_json=False)
    for code, name in re.findall(r'/item/main\.naver\?code=(\d{6})">([^<]+)</a>', html):
        members.append({"code": code, "name": name.strip(), "mcap": None})
    return members, keys


def main() -> int:
    dry = os.environ.get("J13_SECTOR_DRY") == "1"
    try:
        fundamentals = (json.loads(KR_FILE.read_text(encoding="utf-8")).get("stocks") or {})
    except (OSError, ValueError):
        fundamentals = {}
    old = {}
    try:
        old = {str(s.get("no")): s for s in json.loads(OUT.read_text(encoding="utf-8")).get("sectors") or []}
    except (OSError, ValueError):
        pass
    groups, source, list_keys = sector_list()
    print(f"업종 {len(groups)}개 · 받은 곳 {source} · 목록 칸 {list_keys}", flush=True)
    sectors, member_keys, missed = [], [], []
    for group in groups:
        try:
            members, keys = sector_members(group["no"], source)
            member_keys = member_keys or keys
        except Exception as exc:
            missed.append(f"{group['name']}: {exc}"[:120])
            if group["no"] in old:                       # 못 받은 업종은 옛 값을 둔다
                sectors.append(old[group["no"]])
            continue
        mcap, counted = 0.0, 0
        for member in members:
            value = member["mcap"]
            if value is None:
                value = _num((fundamentals.get(member["code"]) or {}).get("mcap"))
            if value:
                mcap += value
                counted += 1
        sectors.append({"no": group["no"], "name": group["name"], "codes": [m["code"] for m in members],
                        "count": len(members), "mcap": round(mcap, 1) if counted else None, "mcap_counted": counted})
        time.sleep(0.15)
    print(f"종목 칸 {member_keys}", flush=True)
    ranked = sorted((s for s in sectors if s.get("mcap")), key=lambda s: s["mcap"], reverse=True)
    for s in ranked[:10]:
        print(f"  {s['name']} · 종목 {s['count']} · 시가총액 {s['mcap']:,.0f} (센 종목 {s['mcap_counted']})", flush=True)
    for line in missed[:10]:
        print(f"  못 받음 — {line}", flush=True)
    if dry:
        print("작업 갈래 시험 — 파일은 쓰지 않습니다", flush=True)
        return 0 if ranked else 1
    if not ranked:
        print("업종 시가총액을 하나도 못 셌습니다 — 옛 파일을 그대로 둡니다", flush=True)
        return 1
    OUT.write_text(json.dumps({"at": datetime.now(SEOUL).isoformat(timespec="seconds"), "source": source,
                               "unit": "억 원", "sectors": sectors}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"썼습니다 — {OUT} · 업종 {len(sectors)}개", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
