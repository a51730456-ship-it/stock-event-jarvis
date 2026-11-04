"""자비스13 종목 수급(외국인 · 기관) — 네이버 모바일 자료로 받기 · 점수에는 안 씀 (2026-11-04 상하님 「고쳐라」 → 「1 · 값만 보이게」).

까닭 — 네이버 PC 수급 화면(frgn.naver)이 새 모양이 되어 표가 없어졌다(깃허브 살핌 41759276328). 그래서 얼린 jarvis4_data 의
get_stock_flow 가 늘 「수급 표를 찾지 못했습니다」였고, 표의 수급 · 동반 칸이 「확인 필요」였다. 같은 값(날짜 · 종가 · 거래량 ·
외국인 · 기관 순매수 주수)이 모바일 자료(m.stock.naver.com/api/stock/{코드}/trend)에 그대로 있다.

**얼린 jarvis4_data 파일은 한 글자도 안 고친다**(CLAUDE.md 0-3). 그 모듈이 실행 중에 찾아 부르는 이름 몇 개만 바꿔 끼운다(install).
  · 받는 곳 — _STOCK_FLOW_URL 을 「j13trend:{code}」 로, _get_text 는 그 표시가 붙은 주소만 모바일 자료로 받는다(나머지는 원래대로).
  · 읽는 법 — _parse_stock_flow 는 모바일 자료(JSON 배열)면 같은 모양의 줄로 바꾸고, 아니면 원래 읽는 법 그대로.
  · 요약(5일 순매수 · 동반 일수 등)은 원래 get_stock_flow 가 그대로 센다 — 셈을 베끼지 않는다.

**점수에는 안 쓴다**(docs/KR_THEME_SPEC.md 3-5 · 「0점 · 값만 보여줌」 확정 · 상하님 「1」). 수급이 들어가던 넷을 0으로 둔다 —
그동안 자료를 못 받아 실제로도 0이었으니 점수 · 순위 · 판정은 그대로다.
  · 종목 조건점수 수급 20 · 눌림 점수 수급 15 — 점수는 「자료 없음」으로 세고, 화면용 값(net5_ratio)만 원래 자리에 남긴다.
  · 시장 점수 「외국인·기관 5일 수급」 15 · 어제 시장 국면 15 — 점수에는 「자료 없음」을 넘기고, 실제 값은 j13_display 에 실어
    화면(for_display)만 읽는다.

자비스13 화면 · 날짜별 목록 저장(picklist_collector 한국) · 상위 테마 5개 저장이 같이 부른다 — 화면과 저장 목록이 갈라지지 않게.
"""

from __future__ import annotations

import json
import time

MODULE_REVISION = 2026110402
# 지수 분 단위 꼬리(네이버 sise_index_time) — 2026-11-04 깃허브 재기(41777142345)에서 410(닫힌 주소)으로 지수 둘 × 세 번 = 6초를 버렸다.
# 없어도 그림은 9시~15시 분봉으로 그대로 그려지는 보탬 자료다. 한 번만(다시 시도 없이) 묻고, 실패하면 이만큼 건너뛴다.
INDEX_TAIL_MARK = "sise_index_time.naver"
INDEX_TAIL_SKIP_SECONDS = 6 * 3600
_TAIL_OFF_UNTIL = {"t": 0.0}
TREND_URL = "https://m.stock.naver.com/api/stock/{code}/trend?pageSize=20"
MARK = "j13trend:"


def _number(text):
    """「+1,289,652」 · 「-953,731」 · 「222,000」 → 숫자. 못 읽으면 None(0으로 채우지 않는다)."""
    try:
        return float(str(text).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def parse_trend(text: str) -> list[dict]:
    """모바일 자료 → 옛 수급 표와 같은 줄(최근 날이 앞 · 날짜 「2026.11.03」 · 기관/외국인 순매수 주수)."""
    try:
        items = json.loads(text)
    except (TypeError, ValueError):
        return []
    rows = []
    for item in items if isinstance(items, list) else []:
        day = str(item.get("bizdate") or "")
        close = _number(item.get("closePrice"))
        foreign = _number(item.get("foreignerPureBuyQuant"))
        institution = _number(item.get("organPureBuyQuant"))
        if len(day) != 8 or close is None or foreign is None or institution is None:
            continue
        rows.append({"date": f"{day[:4]}.{day[4:6]}.{day[6:]}", "close": close,
                     "volume": _number(item.get("accumulatedTradingVolume")),
                     "institution_net": institution, "foreign_net": foreign})
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows


def for_display(foreign):
    """시장 카드가 읽는 대표종목 수급 — 점수용(ok 아님) 안에 실어 둔 실제 값이 있으면 그것."""
    foreign = foreign or {}
    shown = foreign.get("j13_display")
    return shown if isinstance(shown, dict) and shown.get("ok") else foreign


def install(data) -> None:
    """얼린 jarvis4_data 가 부르는 이름을 바꿔 끼운다. 여러 번 불러도 한 번만 끼운다(모듈을 다시 읽으면 다시 끼운다)."""
    if int(getattr(data, "_j13_flow_installed", 0) or 0) >= MODULE_REVISION:
        return
    original_get = getattr(data, "_j13_original_get_text", None) or data._get_text
    original_parse = getattr(data, "_j13_original_parse_flow", None) or data._parse_stock_flow
    original_score = getattr(data, "_j13_original_stock_score", None) or data._stock_score
    original_pullback = getattr(data, "_j13_original_pullback_quality", None) or data._pullback_quality
    original_market_flow = getattr(data, "_j13_original_market_foreign_flow", None) or data._market_foreign_flow

    def get_text(url, *, timeout: float = 8, retries: int = 2) -> str:
        if INDEX_TAIL_MARK in str(url):
            if time.time() < _TAIL_OFF_UNTIL["t"]:
                raise RuntimeError("지수 꼬리 주소가 닫혀 있어 잠시 건너뜁니다")
            try:
                return original_get(url, timeout=min(float(timeout), 4.0), retries=0)
            except Exception:
                _TAIL_OFF_UNTIL["t"] = time.time() + INDEX_TAIL_SKIP_SECONDS
                raise
        if not str(url).startswith(MARK):
            return original_get(url, timeout=timeout, retries=retries)
        code = str(url)[len(MARK):]
        last = None
        for attempt in range(retries + 1):
            try:
                response = data._http_session().get(TREND_URL.format(code=code), timeout=timeout)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response.text
            except Exception as exc:
                last = exc
                if attempt < retries:
                    time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"네이버 모바일 수급 조회 실패: {last}")

    def parse(text: str) -> list[dict]:
        if str(text or "").lstrip().startswith("["):
            return parse_trend(text)
        return original_parse(text)

    def stock_score(metrics, flow, theme_ret20):
        if not (flow or {}).get("ok"):
            return original_score(metrics, flow, theme_ret20)
        original_score(metrics, flow, theme_ret20)            # 화면용 net5_ratio 를 원래 자리(flow)에 남긴다 — 점수는 버린다
        return original_score(metrics, {**flow, "ok": False}, theme_ret20)   # 점수는 수급 없이(지금까지와 같은 값)

    def pullback_quality(metrics, flow):
        if not (flow or {}).get("ok"):
            return original_pullback(metrics, flow)
        return original_pullback(metrics, {**flow, "ok": False})

    def market_foreign_flow():
        real = original_market_flow()
        # 점수(시장 15 · 어제 국면 15)에는 「자료 없음」 — 화면은 j13_display 를 읽는다(for_display).
        return {"ok": False, "previous_net5_amount": None, "j13_display": real}

    data._j13_original_get_text = original_get
    data._j13_original_parse_flow = original_parse
    data._j13_original_stock_score = original_score
    data._j13_original_pullback_quality = original_pullback
    data._j13_original_market_foreign_flow = original_market_flow
    data._get_text = get_text
    data._parse_stock_flow = parse
    data._stock_score = stock_score
    data._pullback_quality = pullback_quality
    data._market_foreign_flow = market_foreign_flow
    data._STOCK_FLOW_URL = MARK + "{code}"
    data._j13_flow_installed = MODULE_REVISION


def mark_display_only(overview):
    """시장 점수 풀이에서 수급 항목 이름에 「점수 안 씀」을 붙인 사본 — 값은 카드에 보이는데 「자료부족」처럼 읽히지 않게."""
    if not isinstance(overview, dict) or not isinstance((overview.get("foreign") or {}).get("j13_display"), dict):
        return overview
    rows = []
    for item in overview.get("score_breakdown") or []:
        if str(item.get("label") or "").startswith("외국인·기관 5일 수급") and not item.get("earned"):
            item = {**item, "label": "외국인·기관 5일 수급(점수 안 씀 · 값만 보여줌)", "state": "값만 보여줌"}
        rows.append(item)
    return {**overview, "score_breakdown": rows}


def uninstall(data) -> None:
    """바꿔 끼운 것을 원래대로 — 시험이 같은 곳에서 얼린 자비스4 시험을 이어 돌릴 때 섞이지 않게(앱에서는 안 부른다)."""
    for name, saved in (("_get_text", "_j13_original_get_text"), ("_parse_stock_flow", "_j13_original_parse_flow"),
                        ("_stock_score", "_j13_original_stock_score"),
                        ("_pullback_quality", "_j13_original_pullback_quality"),
                        ("_market_foreign_flow", "_j13_original_market_foreign_flow")):
        original = getattr(data, saved, None)
        if original is not None:
            setattr(data, name, original)
    if getattr(data, "_j13_flow_installed", 0):
        data._STOCK_FLOW_URL = "https://finance.naver.com/item/frgn.naver?code={code}"
        data._j13_flow_installed = 0
