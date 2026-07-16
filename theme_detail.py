"""theme_detail.py — 네이버 sise_group_detail 페이지 파싱.

기존 theme_data.py(테마 목록 조회)는 수정하지 않는다. 이 모듈은 테마 목록에서
얻지 못하는 구성종목별 현재가/등락률/거래대금을 추가로 가져오는 역할만 한다.
읽기 전용. 모든 함수는 실패 시 예외 대신 {"ok": False, "error": "..."} 반환.
"""

import logging
import re
import time

import requests

from theme_data import KR_THEME_NAVER_MAPPING

_log = logging.getLogger(__name__)

_DETAIL_URL = "https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={no}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQUEST_INTERVAL = 0.3  # 기존 스크래핑 관행: 요청 간 최소 0.3초

_FETCH_CACHE: dict = {}   # {테마명: (timestamp, result)}
_FETCH_TTL_SEC = 60.0


# ── HTML 파싱 ────────────────────────────────────────────────────────────────


# 종목명+코드를 포함하는 TR 블록 추출
_TR_SPLIT = re.compile(r"<tr(?:\s[^>]*)?>", re.I)

# name td 안의 code와 이름
_NAME_PATTERN = re.compile(
    r'/item/main\.naver\?code=(\d{6})">([^<]+)</a>', re.S
)

# number td 값 (태그 제거 후 숫자)
_NUM_TD = re.compile(r'<td class="number"[^>]*>([\s\S]*?)</td>', re.S)

# 등락률 — 색상 클래스(red01/blue01/nv01 등)에 의존하지 않고 텍스트에 이미
# 포함된 부호(-)를 그대로 읽는다. 네이버가 클래스명을 바꿔도 안전하다.
_PCT_NUM = re.compile(r"([+-]?[\d]+\.?[\d]*)\s*%")

_COMMA_NUM = re.compile(r"[\d,]+")


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _parse_stocks(html: str) -> list[dict]:
    """TR 행별로 종목 정보를 파싱한다.

    컬럼 순서(thead 확인): 현재가[0] / 전일비[1] / 등락률[2] /
    매수호가[3] / 매도호가[4] / 거래량[5] / 거래대금[6] / 전일거래량[7]
    거래대금 단위: 백만원(네이버 표기 기준)
    """
    stocks = []
    # TR 분리
    parts = _TR_SPLIT.split(html)
    for part in parts:
        name_m = _NAME_PATTERN.search(part)
        if not name_m:
            continue

        code = name_m.group(1)
        name = name_m.group(2).strip()

        num_tds = _NUM_TD.findall(part)
        if len(num_tds) < 7:
            continue

        # 현재가
        try:
            price_str = _COMMA_NUM.search(_strip_tags(num_tds[0]))
            price = int(price_str.group().replace(",", "")) if price_str else None
        except Exception:
            price = None

        # 등락률 (index 2: 텍스트에 이미 포함된 부호를 그대로 사용)
        pct_m = _PCT_NUM.search(_strip_tags(num_tds[2]))
        change_pct = None
        if pct_m:
            try:
                change_pct = round(float(pct_m.group(1)), 2)
            except Exception:
                pass

        # 거래량 (index 5)
        try:
            vol_m = _COMMA_NUM.search(_strip_tags(num_tds[5]))
            volume = int(vol_m.group().replace(",", "")) if vol_m else None
        except Exception:
            volume = None

        # 거래대금 (index 6, 단위: 백만원)
        try:
            tv_m = _COMMA_NUM.search(_strip_tags(num_tds[6]))
            turnover_mil = int(tv_m.group().replace(",", "")) if tv_m else None
        except Exception:
            turnover_mil = None

        if price is None:
            continue

        stocks.append(
            {
                "code": code,
                "name": name,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "turnover_mil": turnover_mil,
            }
        )
    return stocks


def _fetch_one(no: int) -> list[dict]:
    """네이버 테마 상세(no)에서 구성종목 목록을 가져온다. 실패 시 빈 리스트."""
    url = _DETAIL_URL.format(no=no)
    try:
        resp = requests.get(url, timeout=10, headers=_HEADERS)
        resp.raise_for_status()
        resp.encoding = "euc-kr"
        return _parse_stocks(resp.text)
    except Exception as e:
        _log.warning("theme_detail fetch failed no=%s: %s", no, e)
        return []


# ── 공개 API ─────────────────────────────────────────────────────────────────


def fetch_theme_stocks(theme_name: str) -> dict:
    """테마 구성종목별 현재가/등락률/거래대금을 반환한다.

    KR_THEME_NAVER_MAPPING에 등록된 테마만 지원한다.
    여러 네이버 ID가 매핑된 경우 모두 조회해 중복 없이 합산한다.

    반환:
    {
      "ok": True,
      "stocks": [
        {"code": "006050", "name": "국영지앤엠", "price": 523,
         "change_pct": 5.66, "volume": 356401, "turnover_mil": 185},
        ...
      ],
      "error": None
    }
    거래대금 단위: 백만원(네이버 표기 기준).
    실패 시 {"ok": False, "error": "...", "stocks": []}
    """
    naver_ids = KR_THEME_NAVER_MAPPING.get(theme_name)
    if not naver_ids:
        return {"ok": False, "error": f"등록되지 않은 테마: {theme_name}", "stocks": []}

    # 신호 확인 한 번에 이 함수가 3회 호출되는 구조(theme_signals/직접/find_leader)라
    # 60초 TTL 캐시로 중복 스크래핑을 제거한다. 성공 결과만 캐시.
    now = time.time()
    hit = _FETCH_CACHE.get(theme_name)
    if hit and now - hit[0] < _FETCH_TTL_SEC:
        return hit[1]

    all_stocks: list[dict] = []
    seen_codes: set[str] = set()

    for i, no in enumerate(naver_ids):
        if i > 0:
            time.sleep(_REQUEST_INTERVAL)
        stocks = _fetch_one(no)
        for s in stocks:
            if s["code"] not in seen_codes:
                seen_codes.add(s["code"])
                all_stocks.append(s)

    if not all_stocks:
        return {"ok": False, "error": "구성종목 파싱 실패 (0종목)", "stocks": []}

    result = {"ok": True, "stocks": all_stocks, "error": None}
    _FETCH_CACHE[theme_name] = (now, result)
    return result
