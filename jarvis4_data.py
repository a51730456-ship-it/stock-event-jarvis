"""자비스4 한국 테마 레이더용 시세·수급·판정 엔진.

기존 자비스1/2/3의 ``price_data.py``·``performance.py``·``jarvis3_data.py``는 사용하거나
수정하지 않는다. 이 모듈의 점수는 확률 예측이 아니라 조건 충족도다.

데이터 경로 (2026-07-22 실조회 검증):
- 테마 목록·구성종목·당일 등락률 : 네이버 금융 테마별 시세(무료, 스크래핑)
- 종목 일봉(추세·신고가·ATR)      : FinanceDataReader
- 종목별 외국인·기관 순매매        : 네이버 종목별 투자자 매매동향
- KOSPI/KOSDAQ 지수               : naver_market_data + FinanceDataReader
- 원/달러                          : FinanceDataReader

pykrx는 쓰지 않는다 — KRX가 로그인(KRX_ID/KRX_PW)을 요구하도록 바뀌어 빈 결과만 온다.
네트워크 실패는 예외 대신 구조화된 오류로 반환하며, 확인되지 않은 값을 0으로 만들지 않는다.
"""

from __future__ import annotations

import io
import logging
import math
import pickle
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

_log = logging.getLogger(__name__)
_SEOUL = ZoneInfo("Asia/Seoul")
_NY = ZoneInfo("America/New_York")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}

_THEME_LIST_URL = "https://finance.naver.com/sise/theme.naver"
_THEME_DETAIL_URL = "https://finance.naver.com/sise/sise_group_detail.naver?type=theme&no={no}"
_STOCK_FLOW_URL = "https://finance.naver.com/item/frgn.naver?code={code}"
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# 화면에 보여줄 테마 수와, 그 후보로 상세 조회할 테마 수.
# 미국테마(자비스3)가 20개를 보여주므로 한국도 20개로 맞춘다(2026-07-25 사용자 지시).
# 화면에서는 1~10위만 펼치고 11위부터는 '더 보기'로 접힌다.
DISPLAY_THEME_COUNT = 20
# 후보 테마 수. 표에는 20개만 보이지만, 눌림목·통과 종목 심사는 이 범위 전체를 훑는다 —
# 30개로 자르면 '은행'(당일 49위) 같은 테마의 좋은 눌림목을 통째로 놓친다(2026-07-22).
CANDIDATE_THEME_COUNT = 40
# 테마당 심사할 구성종목 수 (거래대금 상위부터).
THEME_STOCK_LIMIT = 8
# 이 점수를 넘는 종목은 테마 점수가 낮아도 후보로 인정한다(테마 게이트 면제).
STRONG_STOCK_OVERRIDE = 85.0
THEME_DETAIL_PARSER_VERSION = 2

# 종목 조건점수 100점의 배분 — 2026-08-07에 실측으로 다시 짰다.
# 자세한 숫자와 이유는 `_stock_score`의 설명글에 있다. 한 줄로 줄이면:
# 검증에 통과한 둘(신고가 근접·낮은 변동성)로 무게를 옮기고, 거꾸로였던
# 둘(이동평균 추세·20일 상대강도)은 0점으로 뺐다.
SCORE_WEIGHTS = {
    "high": 35.0,        # 신고가에 가까운가 — 창 88 / 95 / 100% 합격
    "risk": 25.0,        # 변동성이 낮은가 — 창 86 / 73 / 77% 합격
    "liquidity": 20.0,   # 거래대금 — 합격선은 못 넘었지만 거꾸로도 아니다
    "flow": 20.0,        # 외국인·기관 수급 — 아직 못 쟀다(과거 자료 없음)
    "trend": 0.0,        # 이동평균 위 — 거꾸로였다
    "relative": 0.0,     # 20일 상대강도 — 거꾸로였다
}
# 화면에 '검증됐다'고 적어도 되는 항목만 추린 것. 설명글이 이 목록을 읽는다.
SCORE_VERIFIED_KEYS = ("high", "risk")

# 눌림 점수(`pullback_score`)의 '장기 추세' 배점. 같은 날 같은 이유로 0이 됐다 —
# 50일선 위·200일선 위는 `_stock_score`의 추세 항목과 같은 것을 재는데 거꾸로였다.
# 이 값이 0이면 눌림 점수 만점은 110점이 아니라 90점이다.
PULLBACK_TREND_POINTS = 0.0
PULLBACK_SCORE_MAX = 25.0 + 25.0 + PULLBACK_TREND_POINTS + 25.0 + 15.0
# 실행 중인 프로세스에 옛 모듈이 남아 있는지 화면이 스스로 알아채기 위한 표식이다.
# 스트림릿은 페이지 파일만 다시 읽고 import된 모듈은 그대로 두는 경우가 있어,
# 화면은 새 코드인데 계산은 옛 코드인 상태가 생긴다(2026-07-24 실제 발생:
# 눌림목 깔때기의 전체·유동성·수급 확인 개수가 전부 0으로 표시됐다).
# 계산 결과나 반환 키를 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026080920

_CACHE_LOCK = threading.Lock()
_CACHE: dict = {}
_HTTP_LOCK = threading.Lock()
_HTTP_SESSION: "requests.Session | None" = None
# 한꺼번에 열어 둘 연결 수. 테마 6갈래 × 종목 8갈래 = 최대 48이라 그보다 넉넉히 둔다.
_HTTP_POOL_SIZE = 64


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------
def clear_runtime_cache() -> None:
    """사용자가 새로고침을 눌렀을 때 자비스4 메모리 캐시만 비운다.

    직전 테마 순위(previous_theme_names)는 남긴다 — 새로고침은 자료를 다시 받으려는
    것이지 '어제 뭐가 강했는지'를 잊으라는 뜻이 아니다. 이 기억이 사라지면 신규 진입·
    탈락 표시와, 오늘 하루 쉰 강세 테마의 이월 심사가 함께 끊긴다.
    """
    with _CACHE_LOCK:
        keep = _CACHE.get("previous_theme_names")
        _CACHE.clear()
        if keep is not None:
            _CACHE["previous_theme_names"] = keep


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_number(text) -> float | None:
    if text is None:
        return None
    cleaned = str(text).replace(",", "").replace("+", "").strip()
    if not cleaned or cleaned in {"-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── 공책(파일) 캐시 ─────────────────────────────────────────────────────────
# 2026-07-30 사용자 지시. 앱이 잠들면 메모리 캐시가 통째로 비워져 깨어날 때마다
# 처음부터 다시 받는다(사용자 실측: 순위 7이 15초, 다시 누르면 0.2초).
# 그래서 **느리게 변하는 값만** 파일에도 적어 두고, 깨어날 때 그걸 먼저 읽는다.
#
# 적어 두는 것은 두 가지뿐이다.
#   daily — 일봉. 화면의 현재가는 여기서 오지 않는다(테마 표에서 따로 받는다).
#           일봉이 만드는 것은 이동평균·52주 고가·20일 수익률이라 하루 안에서는
#           거의 안 움직인다.
#   flow  — 외국인·기관 수급. 애초에 하루 한 번 지연 공개되는 값이다.
# 현재가·지수·분봉처럼 지금 이 순간을 나타내는 값은 절대 적지 않는다.
#
# 날짜가 바뀌면 안 쓴다 — 어제 이동평균을 오늘 값인 척 보여주지 않기 위해서다.
# 파일이 깨졌거나 못 읽어도 그냥 넘어간다. 캐시 때문에 화면이 죽으면 안 된다.
_DISK_CACHE_DIR = Path("cache") / "jarvis4"
_DISK_CACHE_KINDS = ("daily", "flow")


def _disk_cache_path(key) -> Path | None:
    if not (isinstance(key, tuple) and len(key) == 2 and key[0] in _DISK_CACHE_KINDS):
        return None
    kind, name = key[0], re.sub(r"[^0-9A-Za-z_-]", "", str(key[1]))
    if not name:
        return None
    return _DISK_CACHE_DIR / f"{kind}__{name}.pkl"


def _disk_cache_read(key):
    """오늘 적어 둔 값이면 돌려준다. 아니면 None."""
    path = _disk_cache_path(key)
    if path is None or not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            saved = pickle.load(handle)
        if saved.get("day") != datetime.now(_SEOUL).strftime("%Y-%m-%d"):
            return None
        return saved["value"]
    except Exception:  # 깨진 파일은 없는 셈 친다.
        return None


def _disk_cache_write(key, value) -> None:
    path = _disk_cache_path(key)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 쓰다 만 파일을 남기지 않으려고 임시 이름으로 쓴 뒤 바꿔치기한다.
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            pickle.dump(
                {"day": datetime.now(_SEOUL).strftime("%Y-%m-%d"), "value": value},
                handle, protocol=pickle.HIGHEST_PROTOCOL,
            )
        temporary.replace(path)
    except Exception:  # 못 적어도 그냥 넘어간다.
        pass


def _cached(key, ttl_seconds, producer):
    """키별 TTL 캐시. 실패하면 마지막 정상값을 stale로 돌려준다."""
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and now - entry["at"] < ttl_seconds:
            return entry["value"], False
    if entry is None:
        # 메모리에 아무것도 없다 = 앱이 방금 깨어났다. 공책을 먼저 펴 본다.
        saved = _disk_cache_read(key)
        if saved is not None:
            with _CACHE_LOCK:
                _CACHE[key] = {"at": now, "value": saved}
            return saved, False
    try:
        value = producer()
    except Exception as exc:
        _log.warning("jarvis4 fetch failed key=%s: %s", key, exc)
        with _CACHE_LOCK:
            entry = _CACHE.get(key)
        if entry:
            return entry["value"], True
        raise
    with _CACHE_LOCK:
        _CACHE[key] = {"at": now, "value": value}
    _disk_cache_write(key, value)
    return value, False


def _http_session() -> requests.Session:
    """모든 워커가 함께 쓰는 연결 하나. HTTPS 악수를 한 번만 한다.

    2026-07-30 실측 — 워커 스레드마다 세션을 따로 두던 방식은 '매수심사결과 높은
    순위 7' 한 번에 **새 세션 114개**를 만들었다. 테마마다 ThreadPoolExecutor를
    새로 만들어 스레드가 매번 죽고, 스레드에 딸린 세션도 같이 죽기 때문이다.
    세션 하나당 TLS 악수 한 번이라, 지연이 큰 회선(클라우드→네이버)에서는
    그 악수가 그대로 대기 시간이 된다(사용자 실측 15초).

    연결을 함께 쓰면 악수는 한 번이고, 그 뒤로는 이미 열린 연결을 돌려 쓴다.
    requests의 연결 풀은 여러 스레드가 같이 써도 안전하다. 다만 기본 풀이
    호스트당 10개라 그대로 두면 워커가 줄을 서므로 넉넉히 늘린다.
    """
    global _HTTP_SESSION
    session = _HTTP_SESSION
    if session is not None:
        return session
    with _HTTP_LOCK:
        if _HTTP_SESSION is None:
            session = requests.Session()
            session.headers.update(_HEADERS)
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=8, pool_maxsize=_HTTP_POOL_SIZE, max_retries=0
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            _HTTP_SESSION = session
    return _HTTP_SESSION


def _get_text(url: str, *, timeout: float = 8, retries: int = 2) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = _http_session().get(url, timeout=timeout)
            response.raise_for_status()
            response.encoding = "euc-kr"
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"네이버 조회 실패: {last_error}")


def market_phase(now: datetime | None = None) -> dict:
    """한국장 세션 단계."""
    now_seoul = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    if now_seoul.weekday() >= 5:
        label = "주말 휴장"
    elif now_seoul.time() < dt_time(8, 30):
        label = "장 시작 전"
    elif now_seoul.time() < dt_time(9, 0):
        label = "장전 동시호가"
    elif now_seoul.time() <= dt_time(15, 20):
        label = "정규장"
    elif now_seoul.time() <= dt_time(15, 30):
        label = "장 마감 동시호가"
    elif now_seoul.time() <= dt_time(18, 0):
        label = "시간외 거래"
    else:
        label = "장 마감"
    return {"label": label, "seoul_time": now_seoul.isoformat(timespec="seconds")}


def is_regular_session(now: datetime | None = None) -> bool:
    now_seoul = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    return now_seoul.weekday() < 5 and dt_time(9, 0) <= now_seoul.time() <= dt_time(15, 30)


# ---------------------------------------------------------------------------
# 종목 일봉 (FinanceDataReader)
# ---------------------------------------------------------------------------
def _read_daily_naver(code: str, days: int) -> pd.DataFrame | None:
    """네이버 일봉을 공용 연결로 직접 받는다. FinanceDataReader와 같은 주소·같은 계산.

    2026-07-30 실측 — FinanceDataReader는 종목마다 ``count=6000``(약 24년치)을 받아
    파싱한 뒤 우리가 쓸 400일만 잘라 버렸다. 269줄을 쓰려고 6000줄을 파싱한 것이다.
    게다가 자기 안에서 맨 ``requests.get``을 불러 종목마다 새 연결·새 SSL 준비를
    했다 — 이 앱이 `_http_session`으로 이미 없앤 낭비를 그대로 되살렸다.

    같이 돌릴 때 종목당 CPU가 0.34초 → 1.12초로 세 배가 됐다(일꾼 1개 대 12개).
    코어가 10개인 노트북은 이걸 감추지만, 코어 1~2개인 온라인은 실제시간이 CPU
    시간을 따라간다 — 50종목이면 50초대다.

    주소·파싱·`Change` 계산은 FinanceDataReader가 하던 것과 같게 둔다. 다만 필요한
    만큼만 받고(``count``), 연결은 공용 세션을 쓴다. 자르기 전 여유분을 두어 창의
    첫날 ``Change``도 전날 대비로 제대로 나오게 한다.
    """
    end = datetime.now(_SEOUL).date()
    start = end - timedelta(days=days)
    # 400 달력일 ≈ 275 거래일. 두 배 가까이 받아 두면 앞쪽 여유분이 넉넉하다.
    count = max(600, int(days * 1.5))
    url = (
        "https://fchart.stock.naver.com/sise.nhn"
        f"?timeframe=day&count={count}&requestType=0&symbol={code}"
    )
    response = _http_session().get(url, timeout=10)
    response.raise_for_status()
    rows = re.findall(r'<item data=\"(.*?)\" />', response.text, re.DOTALL)
    if not rows:
        return None
    frame = pd.read_csv(
        io.StringIO("\n".join(rows)), delimiter="|", header=None, dtype={0: str}
    )
    frame.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    frame["Date"] = pd.to_datetime(frame["Date"], format="%Y%m%d")
    frame.set_index("Date", inplace=True)
    frame.sort_index(inplace=True)
    frame["Change"] = frame["Close"].pct_change()
    return frame.loc[start.isoformat():end.isoformat()]


def _read_daily(code: str, days: int = 400) -> pd.DataFrame | None:
    code = str(code)
    frame = None
    try:
        frame = _read_daily_naver(code, days)
    except Exception as exc:
        # 조용히 예전 방식으로 넘어간다 — 네이버 응답 모양이 바뀌어도 화면이 비지 않게.
        _log.warning("jarvis4 naver daily failed code=%s: %s", code, exc)
    if frame is None or frame.empty or "Close" not in frame.columns:
        import FinanceDataReader as fdr

        end = datetime.now(_SEOUL).date()
        start = end - timedelta(days=days)
        frame = fdr.DataReader(code, start.isoformat(), end.isoformat())
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame


def get_daily_frame(code: str, *, ttl_seconds: float = 300) -> pd.DataFrame | None:
    code = str(code).strip()
    try:
        frame, _stale = _cached(("daily", code), ttl_seconds, lambda: _read_daily(code))
    except Exception:
        return None
    return None if frame is None else frame.copy()


# 추세·신고가 지표를 내려면 최소한 이만큼의 거래일이 쌓여야 한다.
# 신규상장 종목은 한동안 이 줄에 걸린다 — 20일선을 12일치로 그릴 수는 없다.
MIN_HISTORY_BARS = 25


def _series_metrics(daily: pd.DataFrame | None, live_price: float | None = None) -> dict:
    """추세·신고가·변동성 지표. 자비스3 _series_metrics의 한국판이다.

    이력이 MIN_HISTORY_BARS에 못 미치면 긴 창이 필요한 값(20일선·52주 고가 등)만
    None으로 두고 partial=True로 표시한다. 예전에는 통째로 실패로 돌려보내 그
    종목이 목록에서 사라졌고, 신규상장 테마처럼 구성종목이 전부 짧으면 화면 전체가
    안 나왔다(2026-07-29 사용자 지적: "그런 김에 화면은 나오게 해줘야지").
    """
    if daily is None or len(daily) < 2:
        return {"ok": False}
    closes = daily["Close"].dropna().astype(float)
    if len(closes) < 2:
        return {"ok": False}
    partial = len(closes) < MIN_HISTORY_BARS
    live_current = _finite(live_price)
    current = live_current or _finite(closes.iloc[-1])
    if not current:
        return {"ok": False}

    today = datetime.now(_SEOUL).date()
    last_date = pd.Timestamp(closes.index[-1]).date()
    if live_current is not None:
        # 장중 현재가를 따로 넣었으면 일봉의 마지막 값이 오늘 행인지에 따라
        # 전일 종가 위치가 달라진다.
        prev_close = _finite(closes.iloc[-2] if last_date == today and len(closes) >= 2 else closes.iloc[-1])
    else:
        # 종가 일봉 자체를 현재가로 쓸 때는 바로 앞 거래일이 비교 기준이다.
        # 예전 코드는 마지막 종가를 자기 자신과 비교해 등락률이 항상 0%가 됐다.
        prev_close = _finite(closes.iloc[-2]) if len(closes) >= 2 else None

    def ret(days: int):
        # 이력이 모자라면 가장 오래된 값으로 때우지 않는다 — 12일치를 '20일
        # 수익률'이라고 적으면 그건 지어낸 값이다.
        if len(closes) < days + 1:
            return None
        base = _finite(closes.iloc[-(days + 1)])
        return (current / base - 1) * 100 if base else None

    sma20 = _finite(closes.tail(20).mean())
    sma50 = _finite(closes.tail(50).mean()) if len(closes) >= 50 else None
    sma200 = _finite(closes.tail(200).mean()) if len(closes) >= 200 else None
    # 52주 신고가와 '그 고점을 며칠 전에 찍었나'. 눌림목 판별의 핵심 재료다 —
    # 최근에 신고가를 찍고 지금 눌린 종목이 곧 '올라가던 종목의 조정'이다
    # (2026-07-22 사용자 제안: 복잡한 전체 스캔 대신 이 한 가지만 보면 된다).
    high52 = None
    high52_days_ago = None
    window = daily.tail(248)
    if "High" in daily.columns:
        highs = window["High"].dropna().astype(float)
        if not highs.empty:
            high52 = _finite(highs.max())
            high52_days_ago = int(len(highs) - 1 - highs.values.argmax())
    if high52 is None:
        window_closes = closes.tail(248)
        high52 = _finite(window_closes.max())
        if high52 is not None and not window_closes.empty:
            high52_days_ago = int(len(window_closes) - 1 - window_closes.values.argmax())

    volume_ratio = None
    avg_trading_value = None
    if "Volume" in daily.columns:
        volumes = daily["Volume"].dropna().astype(float)
        if not volumes.empty:
            avg_volume = _finite(volumes.tail(20).mean())
            latest_volume = _finite(volumes.iloc[-1])
            if avg_volume and latest_volume is not None:
                volume_ratio = latest_volume / avg_volume
                avg_trading_value = avg_volume * current  # 원 단위 일평균 거래대금

    atr = atr_pct = None
    if {"High", "Low", "Close"}.issubset(daily.columns) and len(daily) >= 15:
        high = daily["High"].astype(float)
        low = daily["Low"].astype(float)
        prev = daily["Close"].shift(1).astype(float)
        true_range = pd.concat(
            [(high - low), (high - prev).abs(), (low - prev).abs()], axis=1
        ).max(axis=1)
        atr = _finite(true_range.tail(14).mean())
        if atr:
            atr_pct = atr / current * 100

    metrics = {
        "ok": True,
        "bars": int(len(closes)),
        "partial": partial,
        "current": current,
        "prev_close": prev_close,
        "change_pct": ((current / prev_close - 1) * 100) if prev_close else None,
        "ret5": ret(5),
        "ret20": ret(20),
        "ret60": ret(60) if len(closes) >= 61 else None,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "high52": high52,
        "high52_days_ago": high52_days_ago,
        "from_high_pct": ((current / high52 - 1) * 100) if high52 else None,
        "volume_ratio": volume_ratio,
        "avg_trading_value": avg_trading_value,
        "atr": atr,
        "atr_pct": atr_pct,
        "last_date": last_date.isoformat(),
        # 당일 시가·고가·저가·종가 (2026-07-24 사용자 요청: 상세에 당일 가격을 함께 본다).
        # 장중에는 일봉 마지막 행이 오늘 행이라 '진행 중인 값'이고, 오늘 행이 아직
        # 없으면 마지막 거래일 값이므로 day_is_today로 구분해 화면에서 알려준다.
        **_day_prices(daily, last_date == today),
    }
    if partial:
        # 20일선을 12일치로 그리거나 12일 최고가를 '52주 고가'라고 부르지 않는다.
        # 값을 비워 두면 화면이 '-'로 적고, 그 칸이 왜 비었는지는 따로 안내한다.
        for key in ("ret20", "ret60", "sma20", "sma50", "sma200",
                    "high52", "high52_days_ago", "from_high_pct"):
            metrics[key] = None
    return metrics


def _day_prices(daily: pd.DataFrame, is_today: bool) -> dict:
    """일봉 마지막 행의 시가·고가·저가·종가를 꺼낸다."""
    values = {"day_open": None, "day_high": None, "day_low": None,
              "day_close": None, "day_is_today": bool(is_today)}
    try:
        last = daily.iloc[-1]
    except Exception:
        return values
    for key, column in (("day_open", "Open"), ("day_high", "High"),
                        ("day_low", "Low"), ("day_close", "Close")):
        if column in daily.columns:
            values[key] = _finite(last[column])
    return values


# ---------------------------------------------------------------------------
# 종목별 외국인·기관 수급 (네이버 종목별 투자자 매매동향)
# ---------------------------------------------------------------------------
_FLOW_ROW_PATTERN = re.compile(
    r'<span class="tah p10 gray03">([\d.]+)</span>(.*?)</tr>', re.S
)
_FLOW_NUMBER_PATTERN = re.compile(r'>([+-]?[\d,]+)<')


def _parse_stock_flow(html: str) -> list[dict]:
    """표 열 순서: 날짜 | 종가 | 전일비 | 등락률 | 거래량 | 기관 순매매량 | 외국인 순매매량 | 보유주수 | 보유율."""
    rows = []
    for date_text, body in _FLOW_ROW_PATTERN.findall(html):
        numbers = _FLOW_NUMBER_PATTERN.findall(body)
        if len(numbers) < 4:
            continue
        close = _parse_number(numbers[0])
        volume = _parse_number(numbers[1])
        institution = _parse_number(numbers[2])
        foreign = _parse_number(numbers[3])
        if close is None or institution is None or foreign is None:
            continue
        rows.append({
            "date": date_text.strip(),
            "close": close,
            "volume": volume,
            "institution_net": institution,
            "foreign_net": foreign,
        })
    return rows


# 하루 수급을 네 가지로 나눈다 (2026-07-25 사용자 요청).
#   both_buy  외국인·기관이 둘 다 순매수 = '동반'
#   both_sell 둘 다 순매도
#   one       한쪽만 움직였거나 서로 엇갈림
#   flat      둘 다 거의 0
# 외국인과 기관을 합치지 않는다. 합치면 외국인 +500억 / 기관 −480억인 날이
# '순매수'로 둔갑한다. 한국 증권사 화면(키움 0785·미래에셋 0228 등)도 둘을 합치지
# 않고 따로 보여주며, '동반 순매수'를 별도 개념으로 쓴다. 그 방식을 따른다.
#
# 부호 자체는 주수로 재나 금액으로 재나 같다 — 같은 종목·같은 날이면 종가가 양쪽에
# 똑같이 곱해지기 때문이다. 그래서 여기서 중요한 것은 '얼마나 작으면 무시할까'이고,
# 그 기준을 그날 거래량 대비 비율로 둔다. 큰 종목의 자잘한 매매를 신호로 치지 않는다.
_FLAT_RATIO = 0.0005  # 그날 거래량의 0.05% 미만은 '보합'으로 본다(임의 기준, 화면에 밝힌다)


def _day_flow_mark(row: dict) -> str:
    close = row.get("close") or 0
    volume = row.get("volume") or 0
    flat = abs(volume * close) * _FLAT_RATIO
    foreign = (row.get("foreign_net") or 0) * close
    institution = (row.get("institution_net") or 0) * close
    foreign_buy, foreign_sell = foreign > flat, foreign < -flat
    institution_buy, institution_sell = institution > flat, institution < -flat
    if foreign_buy and institution_buy:
        return "both_buy"
    if foreign_sell and institution_sell:
        return "both_sell"
    # 화면은 동그라미의 왼쪽 반을 외국인, 오른쪽 반을 기관으로 그린다. 그래서 '엇갈렸다'로
    # 뭉치지 않고 누가 사고 누가 팔았는지까지 나눈다(2026-07-25 사용자 선택).
    # 뭉쳐 두면 실제 자료의 절반 이상(8종목 160일 중 101일)이 한 색으로 묻힌다.
    if foreign_buy and institution_sell:
        return "f_buy_i_sell"
    if foreign_sell and institution_buy:
        return "f_sell_i_buy"
    if foreign_buy:
        return "f_buy"
    if foreign_sell:
        return "f_sell"
    if institution_buy:
        return "i_buy"
    if institution_sell:
        return "i_sell"
    return "flat"


def get_stock_flow(code: str, *, ttl_seconds: float = 300) -> dict:
    """종목별 외국인·기관 순매매(주 단위, 최근 20거래일)와 요약 지표."""
    code = str(code).strip()

    def _produce():
        html = _get_text(_STOCK_FLOW_URL.format(code=code))
        rows = _parse_stock_flow(html)
        if not rows:
            raise RuntimeError("수급 표를 찾지 못했습니다")
        return rows

    try:
        rows, stale = _cached(("flow", code), ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}

    recent5 = rows[:5]
    recent20 = rows[:20]
    combined = [row["foreign_net"] + row["institution_net"] for row in rows]

    def _amount(subset):
        # 순매매 '금액' 근사 = 순매매 주수 × 그날 종가.
        return sum(
            (row["foreign_net"] + row["institution_net"]) * row["close"] for row in subset
        )

    streak = 0
    for value in combined:
        if value > 0:
            streak += 1
        else:
            break

    marks = [_day_flow_mark(row) for row in rows[:20]]   # 최근 날짜가 앞
    return {
        "ok": True,
        "stale": stale,
        "rows": rows,
        # 동반(둘 다 순매수) 일수 — 5일은 세부, 20일은 긴 흐름. 실무에서 5일·20일
        # 두 창을 같이 보라는 권고를 따른다.
        "day_marks": marks,
        "both_buy_days5": sum(1 for mark in marks[:5] if mark == "both_buy"),
        "both_buy_days20": sum(1 for mark in marks if mark == "both_buy"),
        # 20일은 점을 20개 찍을 수 없어 '동반매도 일수'를 숫자로 따로 준다 —
        # 그래야 '꾸준히 매집'과 '사고팔고 반복'이 갈린다(2026-07-25).
        "both_sell_days20": sum(1 for mark in marks if mark == "both_sell"),
        "window5": len(marks[:5]),
        "window20": len(marks),
        "net5_amount": _amount(recent5),
        # 금액만으로는 큰 종목인지 작은 종목인지 감이 안 온다(2026-07-25 사용자 지적).
        # 그날그날 거래대금 합으로 나눠 '거래대금의 몇 %를 사갔나'를 같이 준다.
        # 실무에서도 금액보다 거래대금 대비 비중으로 보라고 권한다.
        "turnover5_amount": sum((row.get("volume") or 0) * (row.get("close") or 0) for row in recent5),
        "net5_ratio_pct": (
            _amount(recent5) / turnover5 * 100
            if (turnover5 := sum((row.get("volume") or 0) * (row.get("close") or 0) for row in recent5))
            else None
        ),
        "net20_amount": _amount(recent20),
        "net5_shares": sum(combined[:5]),
        "buy_streak_days": streak,
        "foreign_net5": sum(row["foreign_net"] for row in recent5),
        "institution_net5": sum(row["institution_net"] for row in recent5),
        "latest_date": rows[0]["date"] if rows else None,
    }


# ---------------------------------------------------------------------------
# 테마 목록·구성종목 (네이버)
# ---------------------------------------------------------------------------
_THEME_ROW_PATTERN = re.compile(
    r'no=(\d+)">([^<]+)</a>.*?col_type2">\s*<span[^>]*>\s*([+-]?[\d.]+)%',
    re.S,
)
_DETAIL_ROW_PATTERN = re.compile(
    r'<td class="name">.*?code=(\d{6})[^>]*>([^<]+)</a>(.*?)</tr>', re.S
)
_DETAIL_PCT_PATTERN = re.compile(r'([+-]?\d+\.\d+)%')


def _parse_theme_detail_numbers(numbers: list[str] | tuple[str, ...]) -> dict:
    """가변 숫자 열을 뒤에서 읽어 현재량·거래대금·전일량을 분리한다.

    전일비가 보합이면 평문 ``0``이 하나 더 잡혀 앞쪽 인덱스가 밀린다.
    마지막 세 열은 현재 거래량, 거래대금(백만원), 전일 거래량 순서다.
    """
    values = list(numbers or [])
    price = _parse_number(values[0]) if values else None
    if len(values) < 4:
        return {
            "price": price,
            "volume": None,
            "trading_value_million": None,
            "trading_value": None,
            "previous_volume": None,
        }

    volume = _parse_number(values[-3])
    trading_value_million = _parse_number(values[-2])
    previous_volume = _parse_number(values[-1])
    if volume is not None and volume < 0:
        volume = None
    if trading_value_million is not None and trading_value_million < 0:
        trading_value_million = None
    if previous_volume is not None and previous_volume < 0:
        previous_volume = None
    return {
        "price": price,
        "volume": volume,
        "trading_value_million": trading_value_million,
        "trading_value": (
            trading_value_million * 1_000_000
            if trading_value_million is not None
            else None
        ),
        "previous_volume": previous_volume,
    }


def _fetch_theme_page(page: int) -> dict:
    url = _THEME_LIST_URL if page == 1 else f"{_THEME_LIST_URL}?page={page}"
    html = _get_text(url)
    found = {}
    for theme_no, name, pct in _THEME_ROW_PATTERN.findall(html):
        found[int(theme_no)] = {
            "no": int(theme_no),
            "name": name.strip(),
            "change_pct": float(pct),
        }
    return found


def get_all_themes(*, ttl_seconds: float = 300) -> dict:
    """네이버 테마별 시세 전체(약 260개)를 당일 평균 등락률과 함께 가져온다."""

    def _produce():
        themes = {}
        # 첫 장으로 연결을 먼저 데운 뒤 나머지를 받는 방식도 해 봤다. 이 여덟 장만
        # 따로 재면 CPU 6.81 → 4.52초로 줄지만, 눌림목 전체로 돌리면 CPU는 그대로고
        # 실제시간만 0.5초 늘었다 — 값이 없어 안 넣었다(2026-07-30 실측).
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fetch_theme_page, page): page for page in range(1, 9)}
            for future in as_completed(futures):
                try:
                    themes.update(future.result())
                except Exception:
                    continue
        if not themes:
            raise RuntimeError("테마 목록을 찾지 못했습니다 (페이지 구조 변경 가능성)")
        return themes

    try:
        themes, stale = _cached("theme_list", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "themes": {}}
    return {"ok": True, "stale": stale, "themes": themes}


def _fetch_theme_detail(theme_no: int) -> list[dict]:
    html = _get_text(_THEME_DETAIL_URL.format(no=theme_no))
    stocks = []
    for code, name, body in _DETAIL_ROW_PATTERN.findall(html):
        numbers = _FLOW_NUMBER_PATTERN.findall(body)
        parsed = _parse_theme_detail_numbers(numbers)
        percents = _DETAIL_PCT_PATTERN.findall(body)
        change_pct = float(percents[0]) if percents else None
        if parsed["price"] is None:
            continue
        stocks.append({
            "code": code,
            "name": name.strip(),
            "price": parsed["price"],
            "change_pct": change_pct,
            "volume": parsed["volume"],
            "trading_value_million": parsed["trading_value_million"],
            "trading_value": parsed["trading_value"],
            "previous_volume": parsed["previous_volume"],
            "parser_version": THEME_DETAIL_PARSER_VERSION,
        })
    return stocks


def get_theme_stocks(theme_no: int, *, ttl_seconds: float = 300) -> dict:
    """테마 구성종목 전체(현재가·등락률·거래량)."""

    def _produce():
        stocks = _fetch_theme_detail(int(theme_no))
        if not stocks:
            raise RuntimeError("테마 구성종목을 찾지 못했습니다")
        return stocks

    try:
        stocks, stale = _cached(("theme_detail", int(theme_no)), ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stocks": []}
    return {"ok": True, "stale": stale, "stocks": stocks}


# ---------------------------------------------------------------------------
# 시장 판단 (KOSPI·KOSDAQ·환율·미국 전일·외국인 수급)
# ---------------------------------------------------------------------------
_NAVER_INDEX_SYMBOLS = {"KS11": "KOSPI", "KQ11": "KOSDAQ"}


def _index_frame(symbol: str) -> pd.DataFrame | None:
    """지수 일봉. 코스피·코스닥은 네이버에서 한 번에 받는다.

    2026-07-30 실측 — FinanceDataReader로 지수 하나를 받으면 그 안에서 URL을 **82번**
    따로 열고, 그 82번이 pandas 경로라 공용 연결을 못 타서 인증서 저장소를 82번
    새로 읽었다(CPU 1.9초). 눌림목 첫 클릭에서 `_index_frame` 호출은 딱 한 번인데도
    그랬다. 네이버 fchart는 같은 자료를 요청 한 번으로 준다(600줄 0.38초).

    값 대조(2026-07-30, 269거래일): 시가·고가·저가·종가가 269일 전부 똑같다.
    거래량만 네이버가 **천 주 단위**라 1000을 곱해 예전과 같은 단위로 맞춘다.
    이렇게 하면 `_series_metrics`가 내놓는 25개 값이 전부 같아진다.

    환율(USD/KRW)은 네이버 fchart에 없어 예전 방식을 그대로 쓴다.
    """
    naver_symbol = _NAVER_INDEX_SYMBOLS.get(str(symbol))
    if naver_symbol:
        try:
            frame = _read_index_naver(naver_symbol)
            if frame is not None and not frame.empty and "Close" in frame.columns:
                return frame
        except Exception as exc:
            # 조용히 예전 방식으로 넘어간다 — 응답 모양이 바뀌어도 화면이 비지 않게.
            _log.warning("jarvis4 naver index failed symbol=%s: %s", symbol, exc)

    import FinanceDataReader as fdr

    end = datetime.now(_SEOUL).date()
    start = end - timedelta(days=400)
    frame = fdr.DataReader(symbol, start.isoformat(), end.isoformat())
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    return frame.sort_index()


def _read_index_naver(naver_symbol: str, days: int = 400) -> pd.DataFrame | None:
    end = datetime.now(_SEOUL).date()
    start = end - timedelta(days=days)
    count = max(600, int(days * 1.5))
    url = (
        "https://fchart.stock.naver.com/sise.nhn"
        f"?timeframe=day&count={count}&requestType=0&symbol={naver_symbol}"
    )
    response = _http_session().get(url, timeout=10)
    response.raise_for_status()
    rows = re.findall(r'<item data=\"(.*?)\" />', response.text, re.DOTALL)
    if not rows:
        return None
    frame = pd.read_csv(
        io.StringIO("\n".join(rows)), delimiter="|", header=None, dtype={0: str}
    )
    frame.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    frame["Date"] = pd.to_datetime(frame["Date"], format="%Y%m%d")
    frame.set_index("Date", inplace=True)
    frame.sort_index(inplace=True)
    # 네이버 지수 거래량은 천 주 단위다. 예전(FinanceDataReader)과 같은 단위로 맞춘다 —
    # 안 맞추면 avg_trading_value가 1000배 작아진다(2026-07-30 대조로 확인).
    frame["Volume"] = frame["Volume"].astype("float64") * 1000.0
    frame["Change"] = frame["Close"].pct_change()
    return frame.loc[start.isoformat():end.isoformat()].sort_index()



def get_index_sparkline(symbol: str, days: int = 30) -> list:
    """지수의 최근 종가 흐름 — 상단 KOSPI·KOSDAQ 칸에 작은 선을 그린다(2026-07-25).

    이미 받아 둔 일봉(_index_metrics와 같은 캐시)을 그대로 쓴다. 실패하면 빈 목록.
    """
    try:
        frame, _stale = _cached(("index", symbol), 300, lambda: _index_frame(symbol))
    except Exception:
        return []
    if frame is None or frame.empty or "Close" not in frame.columns:
        return []
    return [float(v) for v in frame["Close"].dropna().tail(days).tolist()]


# ---------------------------------------------------------------------------
# 지수 분봉 (2026-07-25) — 왜 두 곳을 이어 붙이는가
#
# 종목에 쓰는 네이버 siseJson은 'KOSPI'·'KPI200'을 받지 않는다(머리줄만 오고 값이
# 없다). 네이버 JSON 차트 api.stock.naver.com은 day·week·month뿐이라 분봉이 없다.
# 둘 다 실제로 불러 확인했다. 그래서 지수 분봉은 두 곳을 이어 붙인다.
#   ① 야후 ^KS11·^KQ11 1분봉 — 09:00~15:00을 한 번에 받는다. 다만 야후가 아는
#      한국장은 15:00에 끝나 마감 30분이 통째로 없고, 장중에는 값이 늦다.
#   ② 네이버 '시간별 시세'(HTML) — 분 단위로 정확하고 15:30까지 있다. 한 쪽에 6줄뿐이라
#      하루를 다 받으려면 66번을 불러야 해서 꼬리(최근 48분)만 받는다.
# 겹치는 구간은 네이버 값을 쓴다. 야후의 지연분과 마감 30분을 이 꼬리가 덮는다.
# ---------------------------------------------------------------------------
_INDEX_YAHOO = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}
_INDEX_DAILY = {"KOSPI": "KS11", "KOSDAQ": "KQ11"}
_INDEX_TIME_URL = (
    "https://finance.naver.com/sise/sise_index_time.naver"
    "?code={code}&thistime={stamp}&page={page}"
)
_INDEX_TIME_ROW = re.compile(
    r'class="date">(\d{2}):(\d{2})</td>\s*<td class="number_1">([\d,]+\.\d+)')
# 한 쪽이 6줄이므로 8쪽 = 48분. 야후 지연분과 마감 30분을 함께 덮을 만큼만 받는다.
_INDEX_TAIL_PAGES = 8


def _yahoo_index_minutes(symbol: str) -> list:
    """야후 1분봉에서 마지막으로 열린 장 하루치만 뽑는다. [(시각, 값)]."""
    import warnings

    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = yf.download(
            _INDEX_YAHOO[symbol], period="5d", interval="1m",
            auto_adjust=False, progress=False, threads=False, timeout=15,
        )
    if raw is None or raw.empty or "Close" not in raw:
        raise RuntimeError("야후 지수 분봉이 비어 있습니다")
    closes = raw["Close"]
    if isinstance(closes, pd.DataFrame):
        closes = closes.iloc[:, 0]
    closes = closes.dropna()
    stamps = closes.index
    try:
        stamps = stamps.tz_convert(_SEOUL)
    except (TypeError, AttributeError):
        pass
    if len(closes) < 5:
        raise RuntimeError("야후 지수 분봉이 부족합니다")
    last_day = stamps[-1].date()
    rows = [
        (datetime(stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute), float(value))
        for stamp, value in zip(stamps, closes.tolist()) if stamp.date() == last_day
    ]
    # 장 시작 직후에는 오늘 분봉이 두세 개뿐이다. 5개를 요구하면 09:00~09:04에
    # 조회가 실패하고, 그 사이 캐시에 남은 **어제 자료**가 그려진다
    # (2026-07-31 09:09 실측: 코스피 +12.71%인데 그림은 어제 모양).
    if len(rows) < 2:
        raise RuntimeError("야후 지수 분봉이 부족합니다")
    return rows


def _index_tail_stamp(day) -> str:
    """네이버 '시간별 시세'의 기준 시각. 지난 장은 15:30, 오늘 장중이면 지금."""
    now = datetime.now(_SEOUL)
    if day < now.date() or now.time() > dt_time(15, 30):
        return f"{day:%Y%m%d}153000"
    return now.strftime("%Y%m%d%H%M00")


def _naver_index_tail(symbol: str, day) -> list:
    """네이버 '시간별 시세'의 마지막 몇 분. [(시각, 값)]."""
    stamp = _index_tail_stamp(day)
    anchor = datetime.strptime(stamp, "%Y%m%d%H%M%S")
    rows = []
    for page in range(1, _INDEX_TAIL_PAGES + 1):
        text = _get_text(_INDEX_TIME_URL.format(code=symbol, stamp=stamp, page=page), timeout=8)
        found = _INDEX_TIME_ROW.findall(text)
        if not found:
            break
        for hour, minute, price in found:
            # 코스피는 천 단위 쉼표가 붙는다("6,690.02") — _parse_number로 벗겨야 한다.
            value = _parse_number(price)
            if value is None:
                continue
            when = datetime.combine(day, dt_time(int(hour), int(minute)))
            # 기준 시각보다 뒤인 줄은 버린다. 장 초반(09:03 같은 때)에 쪽을 넘기면
            # 전날 마감 줄이 딸려 올 수 있는데, 그걸 오늘 것으로 찍으면 하루 그림의
            # 맨 앞에 15:30 값이 박힌다.
            if when <= anchor:
                rows.append((when, value))
    return rows


def _index_prev_close(symbol: str, day) -> float | None:
    """그 세션 '전날' 종가 — 그림의 기준선이다. 같은 날 종가를 쓰면 선이 어긋난다."""
    daily_symbol = _INDEX_DAILY[symbol]
    try:
        frame, _stale = _cached(("index", daily_symbol), 300, lambda: _index_frame(daily_symbol))
    except Exception:
        return None
    if frame is None or frame.empty or "Close" not in frame.columns:
        return None
    closes = frame["Close"].dropna()
    prior = [v for stamp, v in closes.items() if pd.Timestamp(stamp).date() < day]
    return _finite(prior[-1]) if prior else None


def get_index_intraday(symbol: str, *, ttl_seconds: float = 60,
                       expect_session: str | None = None) -> dict:
    """KOSPI·KOSDAQ 하루치 분봉과 그 전날 종가. 실패하면 빈 dict.

    돌려주는 값은 {"points": 분봉 종가들, "base": 전일 종가, "session": 날짜,
    "last_time": 마지막 시각}이다. 자료가 없으면 그리지 않는다 — 일봉으로 대신
    그렸다가 '기준선 위로 간 적이 없는데 빨간 구간이 있다'는 지적을 받았다(2026-07-25).

    expect_session을 주면 그 날짜의 분봉만 돌려준다. 2026-07-31 09:09에 코스피가
    +12.71%인데 그림은 어제(07-30) 모양이 떴다 — 장 시작 직후에는 야후 분봉이
    아직 몇 개 없어 조회가 실패하고, 그때 캐시에 남아 있던 **어제 자료**가
    그대로 그려졌기 때문이다. 오늘 숫자 옆에 어제 그림을 붙이면 거짓말이 된다.
    """
    symbol = str(symbol).strip().upper()
    if symbol not in _INDEX_YAHOO:
        return {}

    def _produce():
        body = _yahoo_index_minutes(symbol)
        day = body[-1][0].date()
        merged = dict(body)
        try:
            # 꼬리를 못 받아도 그림은 그린다 — 09:00~15:00만으로도 하루 흐름은 맞다.
            merged.update(_naver_index_tail(symbol, day))
        except Exception as exc:
            _log.warning("jarvis4 지수 꼬리 조회 실패 %s: %s", symbol, exc)
        return [(stamp, merged[stamp]) for stamp in sorted(merged)]

    try:
        rows, _stale = _cached(("index_intraday", symbol), ttl_seconds, _produce)
    except Exception:
        return {}
    # 장 시작 직후에는 분봉이 두세 개뿐이다. 그것만으로도 선은 그린다 —
    # 예전 기준(5개)이면 09:00~09:04에 그림이 통째로 사라졌다(2026-07-31 실측).
    if len(rows) < 2:
        return {}
    day = rows[-1][0].date()
    # 부르는 쪽이 '오늘 것'을 기대했는데 캐시에 어제 것이 남아 있으면 그리지 않는다.
    if expect_session and day.isoformat() != str(expect_session):
        return {}
    base = _index_prev_close(symbol, day)
    if base is None:
        return {}
    return {
        "points": _thin_points([value for _stamp, value in rows]),
        "base": base,
        "session": day.isoformat(),
        "last_time": rows[-1][0].strftime("%H:%M"),
    }


# 그림은 가로 120px이라 391분을 다 그리면 한 점이 0.3px이다 — 눈에는 똑같은데
# HTML만 지수 한 칸에 45KB가 된다. 폰에서 쓸데없이 무거워지므로 솎아 낸다.
_INDEX_POINT_LIMIT = 180


def _thin_points(points: list) -> list:
    """점이 너무 많으면 일정 간격으로 솎는다. 마지막 값(종가)은 반드시 남긴다."""
    if len(points) <= _INDEX_POINT_LIMIT:
        return points
    step = len(points) // _INDEX_POINT_LIMIT + 1
    thinned = points[::step]
    if (len(points) - 1) % step:
        thinned.append(points[-1])
    return thinned


def kr_crash_market_state(*, ttl_seconds: float = 600) -> dict:
    """코스피가 지금 '급락 후 반등장' 국면인가 (2026-08-07).

    새 규칙의 핵심은 **코스피가 고점 대비 15% 넘게 빠진 국면**이다. 그런데 화면은
    코스피를 전혀 안 보고 종목 낙폭만 보고 있었다 — '급락 후 반등장'이라고 써 놓고
    실제로는 '많이 빠진 종목 목록'이었다(상하님 지적으로 확인).

    **막지는 않고 알려만 준다.** 미국(jarvis3.crash_market_state)과 같은 결정이다 —
    막았더니 화면이 통째로 비는 일이 있었고, 국면을 지나 올라가도 그때 걸렸던 종목은
    볼 값어치가 있다는 판단이다.
    """

    def _produce():
        frame = _index_frame("KS11")
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            raise RuntimeError("코스피 일봉 없음")
        closes = frame["Close"].dropna()
        if len(closes) < 60:
            raise RuntimeError("코스피 일봉이 너무 짧다")
        current = float(closes.iloc[-1])
        peak = float(closes.tail(252).max())
        drop = (current / peak - 1.0) * 100.0 if peak else None
        armed = drop is not None and drop <= CRASH_MARKET_DROP
        # 이번 국면에서 **가장 깊었던 날**이 신호일이다. 국면에 들어선 뒤부터
        # 오늘까지 중 코스피 낙폭이 가장 컸던 날을 찾는다. 갈래와 점수는 원래
        # 그날 낙폭으로 정해야 한다(오늘 값으로 정하면 이미 반등한 종목이
        # 목록에서 사라진다). 지금 화면은 오늘 값을 쓰고 있어 그 사실을 밝혀 둔다.
        reference_date = None
        reference_drop = None
        if armed:
            window = closes.tail(252)
            running = window.cummax()
            series = (window / running - 1.0) * 100.0
            inside = series[series <= CRASH_MARKET_DROP]
            if len(inside):
                # 마지막으로 국면에 들어선 뒤 구간만 본다.
                start = inside.index[0]
                for stamp in inside.index:
                    if series.loc[:stamp].iloc[-2:].min() > CRASH_MARKET_DROP:
                        start = stamp
                episode = series.loc[start:]
                reference_date = str(pd.Timestamp(episode.idxmin()).date())
                reference_drop = float(episode.min())
        return {
            "current": current, "peak": peak, "drop_pct": drop, "armed": bool(armed),
            "threshold": CRASH_MARKET_DROP,
            "reference_date": reference_date, "reference_drop": reference_drop,
            "reason": (
                f"코스피가 52주 고점에서 {drop:.1f}% 내려와 있습니다 — "
                f"이 규칙이 보는 국면({CRASH_MARKET_DROP:.0f}% 아래)입니다."
                if armed else
                f"코스피가 52주 고점에서 {drop:.1f}%입니다 — 이 규칙이 보는 국면"
                f"({CRASH_MARKET_DROP:.0f}% 아래)이 아닙니다. 아래 목록은 참고로만 보십시오."
            ) if drop is not None else "코스피 낙폭을 못 읽었습니다",
        }

    try:
        value, stale = _cached("kr_crash_market_state", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "armed": False}
    return {"ok": True, "stale": stale, **value}


def kr_market_traded_today(now: datetime | None = None,
                           *, ttl_seconds: float = 600) -> bool | None:
    """오늘 한국장이 **열렸나**. 모르면 None (2026-08-19 상하님 지시로 넣었다).

    **왜 달력을 안 쓰나** — 설·추석이 음력이라 규칙으로 셀 수 없다. 미국 휴장일은
    규칙으로 세어 `picklist_store.us_market_holidays`에 넣었지만 한국은 그 방법이
    안 통한다. 달력을 손으로 채워 두면 해마다 누가 고쳐 넣어야 하고, 잊으면
    그해부터 조용히 틀린다.

    **그래서 자료에 물어본다** — 코스피 일봉에 오늘 날짜 봉이 있으면 장이 열린
    것이고, 없으면 휴장이다. 달력을 채울 필요가 없다.

    **조회에 실패하면 None을 준다.** 부르는 쪽은 None일 때 막지 않는다 —
    인터넷이 잠깐 끊겼다고 그날 목록이 통째로 비면 안 된다.
    """
    today = (now or datetime.now(_SEOUL)).astimezone(_SEOUL).date()
    if today.weekday() >= 5:
        return False

    def _produce():
        frame = _index_frame("KS11")
        if frame is None or getattr(frame, "empty", True):
            raise RuntimeError("코스피 일봉 없음")
        last = pd.Timestamp(frame.index[-1])
        return last.date().isoformat()

    try:
        last_date, _stale = _cached("kr_last_trade_date", ttl_seconds, _produce)
    except Exception:
        return None
    return str(last_date) == today.isoformat()


def get_index_daily_spark(symbol: str, *, days: int = 126,
                          ttl_seconds: float = 600) -> dict:
    """지수의 **일봉 6개월** 종가 — 손톱그림에서 '당일'과 바꿔 보여 준다.

    미국테마(자비스3)의 지수 칸은 손을 올리거나 손가락으로 누르면 '당일'에서
    '일봉 6개월'로 바뀐다. 한국에도 같게 하려면 그 자료가 있어야 하는데 지금은
    당일 분봉만 있었다(2026-08-07).

    symbol은 야후 표기(^KS11 · ^KQ11 · ^GSPC …)나 _INDEX_DAILY의 값(KS11 …)
    둘 다 받는다. 실패하면 빈 dict — 그러면 화면은 '당일' 그림만 그린다.
    """
    daily = _INDEX_DAILY.get(symbol, symbol).lstrip("^")

    def _produce():
        frame = _index_frame(daily)
        if frame is None or getattr(frame, "empty", True) or "Close" not in frame:
            raise RuntimeError("일봉 없음")
        closes = [float(v) for v in frame["Close"].dropna().tolist()[-int(days):]]
        if len(closes) < 2:
            raise RuntimeError("일봉이 너무 짧다")
        return {"points": closes, "base": closes[0]}

    try:
        value, _stale = _cached(("index_daily_spark", daily, int(days)),
                                ttl_seconds, _produce)
    except Exception:
        return {}
    return value


def _index_metrics(symbol: str, live_price: float | None = None) -> dict:
    try:
        frame, _stale = _cached(("index", symbol), 300, lambda: _index_frame(symbol))
    except Exception:
        return {"ok": False}
    return _series_metrics(frame, live_price)


def _live_index(ticker: str) -> float | None:
    """장중이면 네이버 현재지수, 아니면 None(일봉 종가를 쓴다)."""
    try:
        import naver_market_data

        snapshot = naver_market_data.get_index_snapshot(ticker)
        if snapshot.get("ok"):
            return _finite(snapshot.get("current"))
    except Exception:
        return None
    return None


# 지수선물·환율은 거의 24시간 돈다. 그런데 Yahoo의 range=1d는 이 종목들에서
# '뉴욕 자정' 이후만 돌려준다. 한국시각 13시가 지나면 차트가 한두 시간짜리
# 토막으로 줄어든다 — 2026-07-29 14:26 KST에 79봉(1.3시간)만 왔다. 네이버는
# 세션 전체를 그리므로 같은 시각에 모양이 전혀 달라 보였다(사용자 지적).
# 그래서 이틀치를 받아 '이번 세션'만 남긴다. CME 지수선물의 하루는 뉴욕
# 18시에 시작해 다음 날 17시에 끝난다.
_NEW_YORK = ZoneInfo("America/New_York")
_SESSION_OPEN_HOUR_ET = 18


def _session_start_stamp(last_stamp: int) -> float:
    """마지막 봉이 속한 세션이 시작한 시각(epoch).

    주말도 알아서 맞는다 — 금요일 17시 마감 뒤에는 목요일 18시가 아니라
    그 봉이 속한 금요일 세션(목 18시~금 17시)의 시작을 돌려준다.
    """
    moment = datetime.fromtimestamp(last_stamp, tz=_NEW_YORK)
    start = moment.replace(
        hour=_SESSION_OPEN_HOUR_ET, minute=0, second=0, microsecond=0
    )
    if moment < start:
        start -= timedelta(days=1)
    return start.timestamp()


def _parse_yahoo_1m_chart(payload: dict, *, symbol: str, label: str) -> dict:
    """Yahoo 단일 1분봉 응답을 화면 값으로 바꾼다.

    현재가, 차트 마지막 값, 전일 기준가를 서로 다른 요청에서 섞지 않는다.
    Yahoo 응답의 ``previousClose``는 선물의 직전 정산가이므로 화면 등락률 기준도
    같은 응답 안에서 완결된다.
    """
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"{label} 조회 오류: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"{label} 1분봉 응답이 비었습니다")

    result = results[0] or {}
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []

    rows = []
    for raw_stamp, raw_close in zip(timestamps, closes):
        stamp = _finite(raw_stamp)
        close = _finite(raw_close)
        if stamp is not None and close is not None:
            rows.append((int(stamp), close))
    if len(rows) < 2:
        raise RuntimeError(f"{label} 1분봉 자료가 부족합니다")

    prev_close = _finite(meta.get("previousClose"))
    if prev_close is None:
        prev_close = _finite(meta.get("chartPreviousClose"))
    if prev_close is None or prev_close <= 0:
        raise RuntimeError(f"{label} 전일 기준가가 없습니다")

    last_stamp, current = rows[-1]
    # 이번 세션만 그린다. 세션 경계를 못 찾거나 자료가 너무 적으면 받은 걸 다 쓴다.
    session_rows = [row for row in rows if row[0] >= _session_start_stamp(last_stamp)]
    if len(session_rows) >= 2:
        rows = session_rows
    points = [value for _stamp, value in rows]
    as_of = datetime.fromtimestamp(last_stamp, tz=_SEOUL).strftime("%m.%d %H:%M")
    delay = _finite(meta.get("exchangeDataDelayedBy"))
    return {
        "label": label,
        "symbol": symbol,
        "contract": meta.get("shortName"),
        # 표시 숫자와 차트 끝값은 반드시 이 한 값이다.
        "current": current,
        "prev_close": prev_close,
        "change_pct": (current / prev_close - 1) * 100,
        "chart": {"points": _thin_points(points), "base": prev_close},
        "as_of": as_of,
        "interval": meta.get("dataGranularity") or "1m",
        "delay_minutes": delay,
        "source": "Yahoo Finance Chart",
    }


def _fetch_yahoo_1m_chart(symbol: str, label: str, interval: str = "1m") -> dict:
    """Yahoo Chart API의 단일 분봉 응답을 가져온다.

    `interval`은 2026-08-21에 붙였다(상하님 지시 — 미국테마의 나스닥100 선물을
    5분봉으로). **기본값은 1분봉 그대로**라 한국테마 화면은 하나도 안 바뀐다.
    """
    encoded_symbol = requests.utils.quote(symbol, safe="")
    url = _YAHOO_CHART_URL.format(symbol=encoded_symbol)
    last_error = None
    for attempt in range(3):
        try:
            response = _http_session().get(
                url,
                params={
                    "interval": str(interval or "1m"),
                    # 1d로 받으면 뉴욕 자정 이후만 온다. 세션 전체를 그리려면
                    # 이틀치를 받아 위 _session_start_stamp로 잘라야 한다.
                    "range": "2d",
                    "includePrePost": "true",
                    "events": "div,splits",
                },
                headers={"Referer": "https://finance.yahoo.com/"},
                timeout=12,
            )
            response.raise_for_status()
            return _parse_yahoo_1m_chart(response.json(), symbol=symbol, label=label)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"{label} 1분봉 조회 실패: {last_error}")


def get_us_futures_live(*, ttl_seconds: float = 60, interval: str = "1m") -> dict:
    """나스닥100·S&P500 선물의 동일 응답 기반 최신 분봉 값과 당일 차트.

    `interval`과 `ttl_seconds`는 부르는 쪽이 정한다. **기본값은 1분봉·60초라
    한국테마는 지금까지와 똑같다.** 미국테마는 2026-08-21부터 5분봉으로 부른다
    (상하님 — "1분마다 로딩하니 너무 자주 로딩하는듯하다").
    """

    def _produce():
        out = {}
        for symbol, label in (("NQ=F", "나스닥100 선물"), ("ES=F", "S&P500 선물")):
            out[symbol] = _fetch_yahoo_1m_chart(symbol, label, interval=interval)
        return out

    try:
        values, stale = _cached(f"us_futures_{interval}", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "stale": stale, "values": values}


def get_fx_intraday(*, ttl_seconds: float = 60) -> dict:
    """원/달러의 동일 응답 기반 최신 1분봉 값과 당일 차트."""

    try:
        value, stale = _cached(
            "fx_intraday",
            ttl_seconds,
            lambda: _fetch_yahoo_1m_chart("KRW=X", "원/달러 환율"),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "stale": stale, **value}


# 한국테마의 '미국 전일' 칸은 jarvis3_data의 계산을 그대로 쓴다(아래 함수).
# 그 계산이 바뀌면 이 숫자를 jarvis3_data.MODULE_REVISION과 같게 올리고,
# **재적재는 pages/3_자비스4.py가 한다**(규칙 11, 이 프로젝트 방식).
# 여기서 importlib.reload를 부르면 시험이 갈아 끼운 가짜 모듈까지 날아간다
# (2026-08-06 실제로 test_jarvis4_data 두 건이 깨졌다).
# 2026-08-20 — 상승장(신고가 눌림매수)이 US_SWING_V1으로 바뀌면서 jarvis3_data의
# MODULE_REVISION이 올라갔다. **여기 계산은 하나도 안 바뀌었다** — 이 숫자는
# 옛 모듈이 프로세스에 남았는지 알아채는 표식일 뿐이라, 규칙 11대로 같이 올린다.
_REQUIRED_J3_REVISION = 2026082960


def _us_previous_session() -> dict:
    """미국 전일 결과 — 한국장은 미국 전일과 갭 상관이 높아 게이트에 넣는다."""
    try:
        import jarvis3_data as j3

        # 옛 jarvis3_data가 프로세스에 남으면 이 칸만 옛 계산으로 돈다(규칙 11).
        # 재적재는 보통 페이지가 하지만, 자비스4 페이지는 자비스3 모듈을 건드리지
        # 않기로 되어 있어(test_jarvis4_page) 여기서 한다.
        # **리비전이 진짜 숫자일 때만** 다시 읽는다 — 시험이 갈아 끼운 가짜 모듈에는
        # 그 숫자가 없어서, 그냥 재적재하면 가짜가 날아간다(2026-08-06 실제로 겪었다).
        revision = getattr(j3, "MODULE_REVISION", None)
        if isinstance(revision, int) and revision < _REQUIRED_J3_REVISION:
            import importlib

            j3 = importlib.reload(j3)

        overview = j3.get_market_overview()
        if not overview.get("ok"):
            return {"ok": False}
        rows = overview.get("rows", {})
        # '미국 전일'은 끝난 정규장을 묻는 자리다. change_pct는 지금 값(프리마켓·
        # 시간외 포함) 기준이라 한국 저녁에 보면 전일 -1.2%가 프리마켓 +0.2%로
        # 뒤집혀 보였고, 조건점수 15점까지 잘못 붙었다(2026-07-24 실측 수정).
        #
        # 값은 ETF가 아니라 지수를 쓴다 — 화면에 'S&P500'이라고 적으므로 지수와
        # 같아야 한다(SPY는 -1.23%, 지수는 -1.21%로 조금 어긋난다).
        def _session_change(index_symbol, etf_symbol):
            value = rows.get(index_symbol, {}).get("last_session_change_pct")
            if value is None:
                value = rows.get(etf_symbol, {}).get("last_session_change_pct")
            return value

        spy = _session_change("^GSPC", "SPY")
        qqq = _session_change("^NDX", "QQQ")
        fear_greed = j3.get_fear_greed()
        previous_market = overview.get("previous_market") or {}
        return {
            "ok": spy is not None and qqq is not None,
            "spy_change": spy,
            "qqq_change": qqq,
            # 한국 화면에서는 '미국 전일 등락률' 대신 전일 미국 시장국면을 보여 준다.
            "regime": previous_market.get("regime"),
            "score": previous_market.get("score"),
            "posture": previous_market.get("posture"),
            # 한국테마에도 미국테마의 시장국면 카드를 그대로 그리기 위한 원본이다.
            # score만 따로 옮기면 '전일 시장국면' 행이 빠져 두 화면이 달라진다.
            "market_overview": dict(overview),
            "fear_greed": fear_greed.get("score") if fear_greed.get("ok") else None,
            "fear_greed_label": fear_greed.get("rating_kr") if fear_greed.get("ok") else None,
            # 게이지 그림에는 지난 값(전일·1주·1개월·1년)까지 필요하다. 자비스4 화면은
            # 규칙상 jarvis3_data를 직접 import하지 않으므로 여기서 통째로 넘긴다.
            "fear_greed_detail": dict(fear_greed) if fear_greed.get("ok") else None,
        }
    except Exception:
        return {"ok": False}


def _market_foreign_flow() -> dict:
    """시장 전체 외국인 수급 — 삼성전자·SK하이닉스 수급을 대표 지표로 쓴다.

    시장 전체 투자자 매매동향은 KIS 키가 있어야 하고 온라인에서만 되므로,
    키 없이도 항상 되는 대표종목 수급을 시장 수급의 근사로 쓴다(대체 신호로 표기).
    """
    codes = (("005930", "삼성전자"), ("000660", "SK하이닉스"))
    try:
        import naver_stock_quote

        def _live_quotes():
            payload = naver_stock_quote.get_quotes([code for code, _label in codes])
            if any(
                not (payload.get(code) or {}).get("price")
                for code, _label in codes
            ):
                raise RuntimeError("대표종목 현재가 일부 누락")
            return payload

        quotes, quotes_stale = _cached("market_representative_live_quotes", 55, _live_quotes)
    except Exception:
        quotes, quotes_stale = {}, False

    total5 = 0.0
    live_total5 = 0.0
    live_foreign5 = 0.0
    live_institution5 = 0.0
    live_count = 0
    quote_times = []
    previous_total5 = 0.0
    ok_any = False
    previous_ok_any = False
    details = []
    stocks = []
    for code, label in codes:
        flow = get_stock_flow(code)
        if flow.get("ok"):
            ok_any = True
            total5 += flow["net5_amount"]
            previous_rows = (flow.get("rows") or [])[1:6]
            if previous_rows:
                previous_ok_any = True
                previous_total5 += sum(
                    ((row.get("foreign_net") or 0) + (row.get("institution_net") or 0))
                    * (row.get("close") or 0) for row in previous_rows
                )
            details.append(f"{label} 5일 {flow['net5_amount'] / 1e8:+,.0f}억")
            # 합계만 주면 화면이 종목별 동반 그림을 못 그린다(2026-07-25 사용자 요청).
            quote = quotes.get(code) or {}
            current_price = _finite(quote.get("price"))
            live_amount = None
            if current_price is not None:
                live_count += 1
                live_amount = (flow.get("net5_shares") or 0) * current_price
                live_total5 += live_amount
                live_foreign5 += (flow.get("foreign_net5") or 0) * current_price
                live_institution5 += (flow.get("institution_net5") or 0) * current_price
                if quote.get("traded_at"):
                    quote_times.append(str(quote["traded_at"]))
            # 하루치(가장 최근 완료 거래일)도 따로 낸다. 5일 합계만 보여 주면
            # "그래서 어제는 팔았나 샀나"를 알 수 없다(2026-07-29 사용자 요청).
            # 오늘치는 장중에 공개되지 않으므로 **그 행의 날짜를 같이** 돌려주고
            # 화면이 며칠 것인지 밝힌다.
            # 완료 거래일과 당일을 **따로** 돌려준다(2026-07-29 사용자 요청 형식).
            # 당일 줄은 네이버가 종목별 수급을 올리기 전까지 비어 있다.
            day_rows = flow.get("rows") or []
            today_text = datetime.now(_SEOUL).strftime("%Y.%m.%d")

            def _amount_of(row):
                if not row:
                    return None
                shares = (row.get("foreign_net") or 0) + (row.get("institution_net") or 0)
                base = current_price if current_price is not None else _finite(row.get("close"))
                return shares * base if base is not None else None

            today_row = next(
                (r for r in day_rows if str(r.get("date") or "").strip() == today_text), None
            )
            prev_row = next(
                (r for r in day_rows if str(r.get("date") or "").strip() != today_text), None
            )
            stocks.append({
                "code": code,
                "label": label,
                "flow": flow,
                "quote": quote,
                "live_net5_amount": live_amount,
                # 가장 최근 '완료' 거래일 — 오늘 것이 올라와도 이 줄은 어제 것을 지킨다.
                "day_net_amount": _amount_of(prev_row),
                "day_date": str((prev_row or {}).get("date") or "").strip() or None,
                # 당일. 아직 공개 전이면 None이고 화면이 그렇게 밝힌다.
                "today_net_amount": _amount_of(today_row),
                "today_date": today_text if today_row else None,
            })
    if not ok_any:
        return {"ok": False}
    return {
        "ok": True, "net5_amount": total5,
        "previous_net5_amount": previous_total5 if previous_ok_any else None,
        "detail": " · ".join(details), "stocks": stocks,
        # 최근 5거래일 수급수량 자체는 완료 거래일 확정치다. 금액만 두 종목의
        # 장중 현재가로 1분마다 다시 환산한다. 이를 오늘 신규 수급으로 표시하지 않는다.
        "live_ok": live_count == len(codes),
        "live_net5_amount": live_total5 if live_count == len(codes) else None,
        "live_foreign_net5_amount": live_foreign5 if live_count == len(codes) else None,
        "live_institution_net5_amount": live_institution5 if live_count == len(codes) else None,
        "live_as_of": max(quote_times) if quote_times else None,
        "live_stale": bool(quotes_stale),
        "live_source": "네이버 현재가 1분 자동조회",
    }


def _market_intraday_investor_flow(*, ttl_seconds: float = 55) -> dict:
    """KOSPI 당일 외국인+기관 시간별 누적 수급(네이버 지연 공개치).

    종목별 5일 수급을 현재가로 재평가하면 오늘 수급처럼 보이는 잘못된 값이 된다.
    따라서 장중 카드에는 시장 전체 시간별 표를 별도 값으로 제공한다.
    """
    import naver_market_data

    def _produce():
        result = naver_market_data.get_market_investor_flow_intraday("KOSPI")
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "KOSPI 장중 수급 조회 실패")
        values = result.get("values") or {}
        foreign = _finite(values.get("foreign"))
        institution = _finite(values.get("institution"))
        if foreign is None or institution is None:
            raise RuntimeError("KOSPI 장중 수급 주요 열 없음")
        return {
            "ok": True,
            "foreign_eok": foreign,
            "institution_eok": institution,
            "net_amount": (foreign + institution) * 1e8,
            "as_of": (
                result.get("as_of").isoformat()
                if isinstance(result.get("as_of"), datetime)
                else result.get("as_of")
            ),
            "as_of_time": result.get("as_of_time"),
            "trade_date": result.get("trade_date"),
            "source": result.get("source") or "네이버 시간별 투자자매매동향(지연 가능)",
            "realtime": False,
        }

    try:
        value, stale = _cached("market_intraday_investor_flow", ttl_seconds, _produce)
    except Exception:
        return {"ok": False}
    return {**value, "stale": bool(stale)}


def _previous_index_metrics(symbol: str) -> dict:
    """오늘 일봉이 있으면 제외하고, 직전 완료 한국장의 지표를 다시 계산한다."""
    try:
        frame, _stale = _cached(("index", symbol), 300, lambda: _index_frame(symbol))
    except Exception:
        return {"ok": False}
    if frame is None or frame.empty:
        return {"ok": False}
    last_date = pd.Timestamp(frame.index[-1]).date()
    completed = frame if last_date < datetime.now(_SEOUL).date() else frame.iloc[:-1]
    return _series_metrics(completed)


def _market_regime_label(score: int) -> tuple[str, str]:
    # 다섯 칸 — regime_gauge_ui.ZONES·jarvis3_data와 끊는 자리가 같아야 한다(2026-08-05 지시).
    if score >= 80:
        return "상승 여건 양호", "조건 충족 종목만 매수 심사"
    if score >= 65:
        return "상승 신호 우세", "확인된 대장주만 분할 진입"
    if score >= 50:
        return "방향 엇갈림", "비중 축소·확인 후 진입"
    if score >= 30:
        return "약세 신호 우세", "신규 매수 보류"
    return "하락 압력 큼", "신규 매수 보류·손절 관리 먼저"


def _us_session_change_before(offset: int = 1) -> dict:
    """한국장 하루치를 더 거슬러 올라간 미국 정규장 등락.

    offset=1이면 '어제 한국장이 열리기 전 밤'의 미국장이다.
    """
    try:
        import FinanceDataReader as fdr

        out = {}
        for key, symbol in (("spy_change", "US500"), ("qqq_change", "IXIC")):
            frame = fdr.DataReader(symbol, (datetime.now(_SEOUL).date()
                                            - timedelta(days=20)).isoformat())
            closes = frame["Close"].astype(float).dropna()
            if len(closes) < offset + 2:
                return {"ok": False}
            index = -(offset + 1)
            out[key] = float(closes.iloc[index] / closes.iloc[index - 1] - 1) * 100
        out["ok"] = True
        return out
    except Exception:
        return {"ok": False}


def _previous_korean_market_regime(foreign: dict, us_prev: dict) -> dict | None:
    """직전 완료 한국장 기준의 시장국면.

    가격·환율은 그날 종가로 다시 계산하고, 수급은 대표종목 5일 묶음을 하루
    뒤로 밀어 같은 기준일로 맞춘다. 자료가 모자라면 표시하지 않는다.

    '미국 전일'도 하루 더 거슬러 올라가야 한다(2026-07-31 사용자 지적).
    예전에는 오늘 화면이 쓰는 us_prev를 그대로 넘겨받아, 어제 한국장 점수를
    **오늘 새벽 미국장**으로 매겼다. 실제로 이 탓에 15점이 30점으로 보였다 —
    7/29 밤 미국장은 S&P −1.52%·나스닥 −1.74%라 0점이어야 하는데,
    7/30 밤(+1.66%·+2.78%)을 가져다 15점을 준 것이다.
    """
    kospi = _previous_index_metrics("KS11")
    kosdaq = _previous_index_metrics("KQ11")
    usdkrw = _previous_index_metrics("USD/KRW")
    if not kospi.get("ok"):
        return None
    # 어제 한국장 기준이므로 미국장도 하루 뒤로 민다. 못 구하면 그 항목은 0점이
    # 되게 두고(빈 dict) 점수를 지어내지 않는다.
    us_prev = _us_session_change_before(1)
    score = 0
    checks = (
        (bool(kospi.get("sma50") and kospi["current"] > kospi["sma50"]), 20),
        (bool(kospi.get("sma20") and kospi["current"] > kospi["sma20"]), 10),
        (bool(kosdaq.get("ok") and kosdaq.get("sma50") and kosdaq["current"] > kosdaq["sma50"]), 15),
        (bool(kosdaq.get("ok") and kosdaq.get("sma20") and kosdaq["current"] > kosdaq["sma20"]), 10),
        (bool(us_prev.get("ok") and (us_prev.get("spy_change") or 0) >= 0
              and (us_prev.get("qqq_change") or 0) >= 0), 15),
        (bool(foreign.get("previous_net5_amount") is not None
              and foreign.get("previous_net5_amount") > 0), 15),
        (bool(usdkrw.get("ok") and usdkrw.get("sma20") and usdkrw["current"] <= usdkrw["sma20"]), 15),
    )
    score = sum(points for passed, points in checks if passed)
    regime, posture = _market_regime_label(score)
    return {"ok": True, "score": score, "regime": regime, "posture": posture,
            "as_of": "직전 완료 한국장"}


def get_market_overview() -> dict:
    """한국 전체시장 판단 — 조건점수 100점."""
    # 여섯 조회는 서로 기다릴 이유가 없다. 차례차례 돌리면 합계가 그대로 대기가 된다
    # (2026-07-30 실측: 미국전일 2.09 + KOSPI 0.81 + 원달러 0.56 + 외국인 0.36 + 나머지
    # = 약 4.1초). 같이 돌리면 가장 긴 것만 기다린다. 받는 자료·계산·점수는 그대로다.
    # 캐시는 잠금(_CACHE_LOCK)으로 지켜지고 HTTP 연결도 여러 스레드가 함께 쓰도록
    # 만들어 둔 것이라(_http_session) 나눠 돌려도 안전하다.
    with ThreadPoolExecutor(max_workers=6) as executor:
        f_kospi = executor.submit(lambda: _index_metrics("KS11", _live_index("^KS11")))
        f_kosdaq = executor.submit(lambda: _index_metrics("KQ11", _live_index("^KQ11")))
        f_usdkrw = executor.submit(_index_metrics, "USD/KRW")
        f_us_prev = executor.submit(_us_previous_session)
        f_foreign = executor.submit(_market_foreign_flow)
        f_intraday = executor.submit(_market_intraday_investor_flow)
        kospi = f_kospi.result()
        kosdaq = f_kosdaq.result()
        usdkrw = f_usdkrw.result()
        us_prev = f_us_prev.result()
        foreign = f_foreign.result()
        intraday_flow = f_intraday.result()

    if not kospi.get("ok"):
        return {
            "ok": False,
            "error": "KOSPI 지수 자료를 가져오지 못했습니다",
            "phase": market_phase(),
            "rows": {"KOSPI": kospi, "KOSDAQ": kosdaq, "USDKRW": usdkrw},
        }

    score = 0
    reasons = []
    breakdown = []

    def add_check(label: str, passed: bool, points: int, reason: str, *, state=None):
        nonlocal score
        earned = points if passed else 0
        score += earned
        if passed:
            reasons.append(reason)
        breakdown.append({
            "label": label,
            "earned": earned,
            "max": points,
            "state": state or ("충족" if passed else "미충족"),
        })

    add_check(
        "KOSPI 50일선", bool(kospi.get("sma50") and kospi["current"] > kospi["sma50"]),
        20, "KOSPI 50일선 위",
    )
    add_check(
        "KOSPI 20일선", bool(kospi.get("sma20") and kospi["current"] > kospi["sma20"]),
        10, "KOSPI 단기추세 양호",
    )
    add_check(
        "KOSDAQ 50일선", bool(kosdaq.get("ok") and kosdaq.get("sma50") and kosdaq["current"] > kosdaq["sma50"]),
        15, "KOSDAQ 50일선 위",
    )
    add_check(
        "KOSDAQ 20일선", bool(kosdaq.get("ok") and kosdaq.get("sma20") and kosdaq["current"] > kosdaq["sma20"]),
        10, "KOSDAQ 단기추세 양호",
    )

    # 미국 시장국면(전일) — 한국장 갭 상관이 높아 15점.
    if us_prev.get("ok"):
        us_ok = (us_prev.get("spy_change") or 0) >= 0 and (us_prev.get("qqq_change") or 0) >= 0
        add_check("미국 시장국면(전일)", us_ok, 15, "미국 전일 상승 마감")
    else:
        breakdown.append({"label": "미국 시장국면(전일)", "earned": 0, "max": 15, "state": "자료부족"})

    # 외국인·기관 수급 (대표종목 근사) 15점.
    if foreign.get("ok"):
        add_check("외국인·기관 5일 수급", foreign["net5_amount"] > 0, 15, "대표종목 5일 순매수")
    else:
        breakdown.append({"label": "외국인·기관 5일 수급", "earned": 0, "max": 15, "state": "자료부족"})

    # 원/달러 — 하락(원화 강세)이면 외국인 자금에 우호적.
    if usdkrw.get("ok"):
        stable = bool(usdkrw.get("sma20") and usdkrw["current"] <= usdkrw["sma20"])
        add_check("원/달러 안정", stable, 15, "원/달러 20일선 아래(원화 강세)")
    else:
        breakdown.append({"label": "원/달러 안정", "earned": 0, "max": 15, "state": "자료부족"})

    regime, posture = _market_regime_label(score)

    return {
        "ok": True,
        "score": score,
        "regime": regime,
        "posture": posture,
        "reasons": reasons,
        "score_breakdown": breakdown,
        "rows": {"KOSPI": kospi, "KOSDAQ": kosdaq, "USDKRW": usdkrw},
        "us_prev": us_prev,
        "previous_market": _previous_korean_market_regime(foreign, us_prev),
        "foreign": foreign,
        "intraday_flow": intraday_flow,
        "phase": market_phase(),
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 테마 순위 — 매일 동적 선정, 약한 테마는 자동 탈락
# ---------------------------------------------------------------------------
def _scale(value: float | None, low: float, high: float, points: float) -> float:
    if value is None or high <= low:
        return 0.0
    return max(0.0, min(points, (value - low) / (high - low) * points))


def _theme_score(detail_stocks: list[dict], theme_change: float, kospi_change: float) -> dict:
    """테마 조건점수 100점.

    당일 등락률만 쓰지 않는다 — 구성종목 확산도와 거래대금 집중도를 함께 본다.
    20일 상대강도는 선택된 테마에서만 계산한다(전체 테마에 다 계산하면 너무 느리다).
    """
    stocks = [s for s in detail_stocks if s.get("change_pct") is not None]
    if not stocks:
        return {"ok": False}

    up_ratio = sum(1 for s in stocks if s["change_pct"] > 0) / len(stocks) * 100
    strong_ratio = sum(1 for s in stocks if s["change_pct"] >= 3.0) / len(stocks) * 100
    relative = theme_change - kospi_change
    values = [s["trading_value"] for s in stocks if s.get("trading_value")]
    total_value = sum(values) if values else None

    # 스케일 상단은 실측(2026-07-22 강세장)에서 만점이 여러 개 나와 변별이 안 되던 것을
    # 보고 넓혔다. 상위권끼리도 순위가 갈리게 한다.
    score = round(
        _scale(relative, -2.0, 9.0, 35)          # KOSPI 대비 당일 상대강도
        + _scale(up_ratio, 30, 98, 25)           # 구성종목 확산
        + _scale(strong_ratio, 0, 65, 20)        # 3%↑ 종목 비중
        + _scale(math.log10(total_value / 1e8) if total_value else None, 1.0, 4.2, 20),
        1,
    )
    status = "주도" if score >= 70 else "관찰" if score >= 50 else "약함"
    return {
        "ok": True,
        "score": score,
        "status": status,
        "up_ratio": up_ratio,
        "strong_ratio": strong_ratio,
        "relative": relative,
        "total_trading_value": total_value,
        "stock_count": len(stocks),
    }


def get_theme_rankings(force_names: tuple[str, ...] | list[str] = ()) -> dict:
    """네이버 전체 테마에서 오늘 강한 테마 20개를 자동 선정한다.

    force_names에 이름을 주면 그 테마는 점수·순위와 무관하게 반드시 심사해서 목록에
    넣는다(사용자가 직접 찾아본 테마용, 2026-07-22 추가).
    """
    listing = get_all_themes()
    if not listing.get("ok"):
        return {"ok": False, "error": listing.get("error"), "rows": []}

    themes = listing["themes"]
    kospi = _index_metrics("KS11", _live_index("^KS11"))
    kospi_change = kospi.get("change_pct") or 0.0

    # 1차: 네이버가 주는 당일 평균 등락률로 후보를 좁힌다(무료·빠름).
    ordered = sorted(themes.values(), key=lambda t: t["change_pct"], reverse=True)
    candidates = ordered[:CANDIDATE_THEME_COUNT]

    # 당일 등락률만으로 자르면 '꾸준히 강했는데 오늘 하루 쉰' 테마가 통째로 사라진다
    # (2026-07-22 사용자 지적: 금융주가 얼마 전까지 좋았는데 목록에서 빠졌다 —
    # 실측 결과 금융 최고 테마가 당일 49위라 후보 30에 못 들었다).
    # 그래서 직전 조회에서 상위권이었던 테마는 오늘 등락률이 낮아도 계속 심사한다.
    # 계속 약하면 점수가 낮아 자연히 20위 밖으로 밀려나므로 '자동 탈락' 원칙은 유지된다.
    previous_entry = _CACHE.get("previous_theme_names")
    previous_names = set(previous_entry["value"]) if previous_entry else set()
    forced = {str(name) for name in (force_names or ())}
    keep_names = previous_names | forced
    if keep_names:
        picked = {theme["name"] for theme in candidates}
        for theme in ordered:
            if theme["name"] in keep_names and theme["name"] not in picked:
                candidates.append(theme)
                picked.add(theme["name"])

    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_theme_stocks, theme["no"]): theme for theme in candidates
        }
        for future in as_completed(futures):
            theme = futures[future]
            try:
                detail = future.result()
            except Exception:
                continue
            if not detail.get("ok"):
                continue
            stocks = detail["stocks"]
            scored = _theme_score(stocks, theme["change_pct"], kospi_change)
            if not scored.get("ok"):
                continue
            rows.append({
                "no": theme["no"],
                "name": theme["name"],
                "ok": True,
                "change_pct": theme["change_pct"],
                "stocks": stocks,
                **scored,
                "basis": (
                    f"KOSPI 대비 {scored['relative']:+.2f}%p · 구성종목 상승 {scored['up_ratio']:.0f}% · "
                    f"3%↑ 종목 {scored['strong_ratio']:.0f}%"
                ),
            })

    rows.sort(key=lambda row: row["score"], reverse=True)
    # 표에는 20개만 보이지만, 눌림목·통과 종목 심사가 쓸 수 있도록 전체 심사 결과를 남긴다.
    all_scored = list(rows)
    # 21위 밖으로 밀린 테마도 이름·점수만 남겨 둔다 — "왜 그 테마가 빠졌나"를
    # 화면에서 확인할 수 있어야 한다(2026-07-22 사용자 지적).
    next_rows = [
        {"name": row["name"], "score": row["score"], "change_pct": row["change_pct"],
         "status": row["status"]}
        for row in rows[DISPLAY_THEME_COUNT:DISPLAY_THEME_COUNT + 10]
    ]
    # 사용자가 직접 찾아본 테마는 점수가 낮아도 목록에 남긴다(순위는 실제 점수 순).
    forced_rows = [row for row in rows[DISPLAY_THEME_COUNT:] if row["name"] in forced]
    rows = rows[:DISPLAY_THEME_COUNT] + forced_rows
    rows.sort(key=lambda row: row["score"], reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        row["is_forced"] = row["name"] in forced

    # 어제 대비 신규 진입·탈락 표시 (세션이 아니라 모듈 캐시에 보관).
    previous = _CACHE.get("previous_theme_names", {}).get("value") if _CACHE.get("previous_theme_names") else None
    current_names = [row["name"] for row in rows]
    entered = [name for name in current_names if previous and name not in previous]
    dropped = [name for name in (previous or []) if name not in current_names]
    with _CACHE_LOCK:
        _CACHE["previous_theme_names"] = {"at": time.time(), "value": current_names}
    for row in rows:
        row["is_new"] = row["name"] in entered

    return {
        "ok": bool(rows),
        "rows": rows,
        "all_scored": all_scored,
        "next_rows": next_rows,
        "entered": entered,
        "dropped": dropped,
        "total_scanned": len(themes),
        "kospi_change": kospi_change,
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
        "stale": listing.get("stale", False),
        "error": None if rows else "테마 점수를 계산하지 못했습니다",
    }


# ---------------------------------------------------------------------------
# 종목 심사 — 수급 20점을 포함한 한국형 6개 항목
# ---------------------------------------------------------------------------
# 제외 대상: 관리종목·투자경고 등은 종목명에 표기되거나 우선주·스팩인 경우를 거른다.
_EXCLUDE_PATTERNS = ("스팩", "SPAC", "리츠")


def _is_excluded(name: str, code: str) -> bool:
    if any(token in name for token in _EXCLUDE_PATTERNS):
        return True
    # 우선주는 종목코드가 0/5/7 등으로 끝나는 경우가 많아 이름 기준으로만 거른다.
    return name.endswith("우") or name.endswith("우B") or name.endswith("3우B")


def _stock_score(metrics: dict, flow: dict, theme_ret20: float | None) -> tuple[float, list[float]]:
    """종목 조건점수 100점 = 상대강도0 + 신고가35 + 추세0 + 유동성20 + 변동성25 + 수급20.

    **2026-08-07에 배점을 다시 짰다.** 상승장·급락 그물은 격자로 다 쟀는데 이 조건점수만
    한 번도 같은 잣대로 재 본 적이 없었다. `research/kr_cond_check.py`로 12년치
    2,272종목을 창 2·3·4년씩 한 달 간격으로 밀며 그물(거래대금 50억↑ ·
    고점 대비 -45~0%) 안에서 재 봤더니 옛 배점 100점 중 40점이 **거꾸로**였다.

      · 신고가에 가까운가  88 / 95 / 100%  ○  → 15점에서 **35점**으로 올림
      · 변동성 4% 미만     86 / 73 /  77%  ○  → 10점에서 **25점**으로 올림
      · 거래대금 500억↑    69 / 64 /  57%  △  → 합격선(65%)은 못 넘었지만 거꾸로도
                                                아니라 15점에서 20점으로만 손봄
      · 20일선 위          17 / 17 /   6%  ✗  ┐ 이동평균 위에 있다고 점수를 주면
      · 50일선 위           9 / 11 /   0%  ✗  ├ 오히려 손해였다. 추세 20점 → **0점**
      · 200일선 위         19 / 26 /  31%  ✗  ┘
      · 20일 수익률 상위    5 / 10 /   0%  ✗    상대강도 20점 → **0점**

    수급 20점은 오늘 재지 못했다 — 외국인·기관 순매수는 과거치를 12년어치 받아 둔 데가
    없다. 재기 전까지 배점은 그대로 두되, 검증된 항목이 아니라는 것을 잊으면 안 된다.

    **0점짜리 두 항목의 계산은 남겨 둔다.** 화면이 여섯 칸을 그리고 있고, 나중에 다시
    재서 되살릴 수도 있어서다. 배점만 0으로 두면 점수에 섞이지 않는다.

    (옛 주석) 미국판 배점을 그대로 쓰면 안 된다(2026-07-22 실측): 국내 대형주 상당수가
    52주 고가 대비 -30~-45% 구간이라 미국 기준(-25%~0)에서는 전 종목이 0점이 된다.
    그래서 신고가 항목의 범위는 지금도 -45~0이다.
    """
    relative = None
    if metrics.get("ret20") is not None and theme_ret20 is not None:
        relative = metrics["ret20"] - theme_ret20
    rs_points = _scale(relative, -8, 8, SCORE_WEIGHTS["relative"])

    high_points = _scale(metrics.get("from_high_pct"), -45, 0, SCORE_WEIGHTS["high"])

    trend_full = SCORE_WEIGHTS["trend"]
    trend_points = 0.0
    for average_key, share in (("sma20", 0.40), ("sma50", 0.35), ("sma200", 0.25)):
        value = metrics.get(average_key)
        if value and metrics.get("current") and metrics["current"] > value:
            trend_points += trend_full * share

    liquidity_full = SCORE_WEIGHTS["liquidity"]
    trading_value = metrics.get("avg_trading_value")
    if trading_value is None:
        liquidity_points = 0.0
    elif trading_value >= 5e10:      # 500억 이상
        liquidity_points = liquidity_full
    elif trading_value >= 2e10:      # 200억
        liquidity_points = liquidity_full * 0.87
    elif trading_value >= 1e10:      # 100억
        liquidity_points = liquidity_full * 0.67
    elif trading_value >= 3e9:       # 30억
        liquidity_points = liquidity_full * 0.40
    else:
        liquidity_points = liquidity_full * 0.13

    risk_full = SCORE_WEIGHTS["risk"]
    atr_pct = metrics.get("atr_pct")
    if atr_pct is None:
        risk_points = 0.0
    elif atr_pct <= 4:
        risk_points = risk_full
    elif atr_pct <= 6:
        risk_points = risk_full * 0.80
    elif atr_pct <= 9:
        risk_points = risk_full * 0.50
    elif atr_pct <= 13:
        risk_points = risk_full * 0.20
    else:
        risk_points = 0.0

    # 수급 20점 — 자비스3에 없던 한국판 핵심 항목.
    # 순매수 '금액'을 그대로 쓰면 대형주가 항상 만점이 된다(삼성전자·하이닉스 실측).
    # 그래서 그 종목의 5일 거래대금 대비 몇 %를 순매수했는지로 정규화한다 —
    # 종목 규모와 무관하게 "얼마나 강하게 담았나"를 본다.
    if not flow.get("ok"):
        flow_points = 0.0
        flow_ratio = None
    else:
        net5 = flow.get("net5_amount") or 0
        base = (trading_value or 0) * 5
        flow_ratio = (net5 / base) if base > 0 else None
        flow_full = SCORE_WEIGHTS["flow"]
        amount_points = _scale(flow_ratio, 0.0, 0.12, flow_full * 0.70)  # 12%면 만점
        # 2026-07-25: '연속'(외국인+기관을 합쳐서 센 연속일)에서 '동반'(둘 다 순매수한
        # 날 수)으로 바꿨다. 합산은 외국인 +500억·기관 −480억을 순매수로 둔갑시켜
        # 화면에서 이미 버린 기준이라, 점수도 같은 자를 쓰게 맞췄다(사용자 지시).
        # 5일 중 3일이면 만점 6점. 동반이 더 엄격해 점수는 전보다 낮게 나온다.
        partner_cap = flow_full * 0.30
        partner_points = min(partner_cap, (flow.get("both_buy_days5") or 0)
                             * partner_cap / 3.0)
        flow_points = amount_points + partner_points
    flow["net5_ratio"] = flow_ratio if flow.get("ok") else None

    score = rs_points + high_points + trend_points + liquidity_points + risk_points + flow_points
    # 국내형 추격 금지 감점 (상한가 30% 제도 반영).
    if metrics.get("ret5") is not None and metrics["ret5"] >= 25:
        score -= 12
    if metrics.get("change_pct") is not None and metrics["change_pct"] >= 20:
        score -= 12
    return round(max(0.0, min(100.0, score)), 1), [
        round(rs_points, 1), round(high_points, 1), round(trend_points, 1),
        round(liquidity_points, 1), round(risk_points, 1), round(flow_points, 1),
    ]


def tick_size(price: float) -> int:
    """KRX 호가단위(2023년 개편 기준)."""
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1_000


def round_to_tick(price: float | None) -> float | None:
    """실제 주문 가능한 가격으로 반올림한다."""
    if not price or price <= 0:
        return None
    unit = tick_size(price)
    return float(round(price / unit) * unit)


def _entry_plan(metrics: dict, score: float, market_score: float, theme_score: float) -> dict:
    """매수 심사 — 돌파 확인 / 눌림목 대기 / 추격 금지. 가격은 호가단위로 반올림한다."""
    current = metrics.get("current")
    if not current:
        return {"state": "자료 부족", "recommendation": "추천 불가"}

    atr = metrics.get("atr")
    sma20 = metrics.get("sma20")
    from_high = metrics.get("from_high_pct")
    ret5 = metrics.get("ret5")
    change_pct = metrics.get("change_pct")
    atr_pct = metrics.get("atr_pct")

    chase_block = (
        (ret5 is not None and ret5 >= 25)
        or (change_pct is not None and change_pct >= 20)
        or (atr_pct is not None and atr_pct >= 15)
    )

    # 눌림목 조건도 국내 현실에 맞춘다(2026-07-22): 미국판의 '50일선 위' 단독 조건은
    # 고점 대비 크게 눌린 국내 종목을 전부 제외시켜 후보가 하나도 남지 않았다.
    # 단기 추세(20일선)가 살아 있으면서 중기 회복 신호(50일선 위 또는 20일 수익률 양수)가
    # 있는 경우까지 눌림목으로 본다.
    sma50 = metrics.get("sma50")
    above_sma20 = bool(sma20 and current >= sma20 * 0.98)
    mid_term_ok = bool((sma50 and current > sma50) or (metrics.get("ret20") or 0) > 0)

    if chase_block:
        state = "추격 금지"
        trigger = zone_high = invalidation = target = None
    elif from_high is not None and from_high >= -3.0 and (metrics.get("volume_ratio") or 0) >= 1.3:
        state = "돌파 확인"
        trigger = current * 1.003
        invalidation = current - max((atr or current * 0.04) * 2, current * 0.04)
        zone_high = trigger * 1.01
        target = trigger + 2 * (trigger - invalidation)
    elif above_sma20 and mid_term_ok and abs(current / sma20 - 1) <= 0.07:
        state = "눌림목 대기"
        trigger = max(current, sma20 * 1.005)
        invalidation = current - max((atr or current * 0.04) * 2, current * 0.04)
        zone_high = trigger * 1.01
        target = trigger + 2 * (trigger - invalidation)
    elif score >= 65:
        state = "관찰"
        trigger = zone_high = invalidation = target = None
    else:
        state = "제외"
        trigger = zone_high = invalidation = target = None

    # 테마 게이트는 종목 점수로 면제될 수 있다(2026-07-22 사용자 지적으로 수정).
    # 미국판은 테마=ETF라 테마가 약하면 구성종목도 대체로 약했지만, 국내 네이버 테마는
    # 성격이 섞여 있어 테마 평균이 종목 품질을 대표하지 못한다 — 실측: '은행' 테마는
    # 22.1점(약함)인데 하나금융지주는 95.0점이었다. 압도적으로 강한 종목을 테마 평균
    # 때문에 버리지 않는다.
    theme_ok = theme_score >= 60 or score >= STRONG_STOCK_OVERRIDE
    gates_ok = market_score >= 50 and theme_ok and score >= 70
    if gates_ok and state in {"돌파 확인", "눌림목 대기"}:
        recommendation = "조건부 후보"
    elif state in {"추격 금지", "제외"}:
        recommendation = "추천 제외"
    else:
        recommendation = "관찰"

    if market_score < 50:
        buy_reason = "시장 국면이 약세 구간이라 신규 매수를 보류합니다."
    elif not theme_ok:
        buy_reason = (
            f"테마 강도가 기준 미달입니다(종목 점수가 {STRONG_STOCK_OVERRIDE:.0f}점을 넘으면 "
            "테마와 무관하게 후보로 봅니다)."
        )
    elif score < 70:
        buy_reason = "종목 조건점수가 기준 미달입니다."
    elif state == "돌파 확인":
        buy_reason = "52주 신고가 부근에서 거래량이 증가해 종가 돌파 확인 후 진입합니다."
    elif state == "눌림목 대기":
        buy_reason = "상승 추세 안의 20일선 눌림으로 기준가 회복 후에만 진입합니다."
    elif state == "추격 금지":
        buy_reason = "단기 급등·상한가 인접 또는 고변동으로 추격 매수를 금지합니다."
    else:
        buy_reason = "가격 셋업이 완성되지 않아 관찰합니다."

    return {
        "state": state,
        "recommendation": recommendation,
        "trigger": round_to_tick(trigger),
        "zone_high": round_to_tick(zone_high),
        "invalidation": round_to_tick(invalidation),
        "target": round_to_tick(target),
        "buy_reason": buy_reason,
    }


def _analyze_stock(stock: dict, theme_ret20: float | None) -> dict | None:
    code, name = stock["code"], stock["name"]
    if _is_excluded(name, code):
        return None
    daily = get_daily_frame(code)
    metrics = _series_metrics(daily, stock.get("price"))
    if not metrics.get("ok"):
        return None
    flow = get_stock_flow(code)
    score, parts = _stock_score(metrics, flow, theme_ret20)
    return {
        "code": code,
        "name": name,
        "metrics": metrics,
        "flow": flow,
        "score": score,
        "score_parts": parts,
        "daily": daily,
        # 이력이 짧아 일부 지표가 빈 종목. 점수를 다른 종목과 나란히 비교하면
        # 안 된다 — 빈 항목이 0점으로 잡혀 실제보다 낮게 나온다.
        "partial": bool(metrics.get("partial")),
        "bars": metrics.get("bars"),
    }


def _krx_listing() -> list[tuple[str, str, str]]:
    """상장 종목 (코드, 이름, 시장) 전체. 하루 한 번만 받아 캐시에 둔다."""
    def _produce():
        import FinanceDataReader as fdr

        frame = fdr.StockListing("KRX")
        out = []
        for _, row in frame.iterrows():
            code = str(row.get("Code") or "").strip()
            name = str(row.get("Name") or "").strip()
            if len(code) == 6 and name:
                out.append((code, name, str(row.get("Market") or "").strip()))
        if not out:
            raise RuntimeError("상장 종목 목록이 비었습니다")
        return out

    listing, _stale = _cached("krx_listing", 6 * 3600, _produce)
    return listing


def search_stocks(query: str, *, limit: int = 12) -> dict:
    """이름 일부나 종목코드로 종목을 찾는다. 오타에도 비슷한 이름을 같이 준다.

    사용자가 들고 있는 종목을 직접 쳐서 상세를 보려는 용도라, 테마 목록에 없는
    종목도 찾아야 한다(2026-07-29 요청 '내 종목 현재상황').
    """
    text = str(query or "").strip()
    if len(text) < 1:
        return {"ok": True, "rows": []}
    try:
        listing = _krx_listing()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}

    if text.isdigit():
        rows = [item for item in listing if item[0].startswith(text)]
        return {"ok": True, "rows": [
            {"code": c, "name": n, "market": m} for c, n, m in rows[:limit]
        ]}

    lowered = text.lower().replace(" ", "")

    def _key(name):
        return name.lower().replace(" ", "")

    starts = [i for i in listing if _key(i[1]).startswith(lowered)]
    contains = [i for i in listing if lowered in _key(i[1]) and i not in starts]
    picked = starts + contains
    if len(picked) < limit:
        # 오타까지 받아 준다 — '비슷하게라도 치면' 나와야 한다.
        import difflib

        already = {i[0] for i in picked}
        similar = difflib.get_close_matches(
            lowered, [_key(i[1]) for i in listing], n=limit, cutoff=0.6
        )
        for target in similar:
            for item in listing:
                if _key(item[1]) == target and item[0] not in already:
                    picked.append(item)
                    already.add(item[0])
    return {"ok": True, "rows": [
        {"code": c, "name": n, "market": m} for c, n, m in picked[:limit]
    ]}


def analyze_one_stock(code: str, name: str, *, market_score: float = 0,
                      theme_score: float = 0) -> dict:
    """종목 하나만 대장주와 똑같은 방식으로 심사한다.

    테마 안에서 재는 상대강도(theme_ret20)는 비교할 테마가 없으므로 뺀다 —
    그 항목은 0점이 되고, 그래서 점수를 테마 대장주 점수와 나란히 견주면 안 된다.
    """
    code = str(code or "").strip()
    if len(code) != 6:
        return {"ok": False, "error": "종목코드가 6자리가 아닙니다"}
    daily = get_daily_frame(code)
    metrics = _series_metrics(daily, None)
    if not metrics.get("ok"):
        return {"ok": False, "error": f"{name or code} 시세를 가져오지 못했습니다"}
    flow = get_stock_flow(code)
    score, parts = _stock_score(metrics, flow, None)
    row = {
        "code": code,
        "name": name or code,
        "metrics": metrics,
        "flow": flow,
        "score": score,
        "score_parts": parts,
        "plan": _entry_plan(metrics, score, market_score, theme_score),
        "daily": daily,
        "rank": 0,
        "partial": bool(metrics.get("partial")),
        "bars": metrics.get("bars"),
        "from_search": True,
    }
    from_high = metrics.get("from_high_pct")
    flow_text = (
        f" · 외국인+기관 5일 {flow['net5_amount'] / 1e8:+,.0f}억"
        if flow.get("ok") else " · 수급 확인 필요"
    )
    row["stock_reason"] = (
        f"직접 찾은 종목 · 52주 고가 대비 {from_high:.1f}%{flow_text}"
        if from_high is not None else f"직접 찾은 종목{flow_text}"
    )
    return {"ok": True, "row": row}


def _leaders_failure(stocks: list) -> dict:
    """대장주를 한 종목도 못 남겼을 때, 이유를 종목별로 밝혀서 돌려준다.

    일봉을 다시 부르지만 캐시가 걸려 있어 새로 조회하지는 않는다.
    """
    short, missing = [], []
    for stock in stocks or []:
        code, name = stock.get("code"), stock.get("name")
        if _is_excluded(name, code):
            continue
        try:
            daily = get_daily_frame(code)
        except Exception:
            daily = None
        bars = 0 if daily is None else len(daily)
        entry = {"code": code, "name": name, "bars": bars, "price": stock.get("price")}
        (short if 0 < bars < MIN_HISTORY_BARS else missing).append(entry)

    if short and not missing:
        days = " · ".join(f"{s['name']} {s['bars']}일" for s in short)
        return {
            "ok": False,
            "reason": "too_new",
            "error": (
                f"상장한 지 얼마 안 된 종목들이라 추세 지표를 낼 수 없습니다 "
                f"({days}). 20일선·신고가는 {MIN_HISTORY_BARS}거래일이 쌓여야 나옵니다."
            ),
            "rows": [],
            "skipped": short,
        }
    return {
        "ok": False,
        "reason": "no_quote",
        "error": "구성종목 시세를 가져오지 못했습니다",
        "rows": [],
        "skipped": short + missing,
    }


def get_theme_leaders(theme_row: dict, market_score: float = 0, theme_score: float = 0,
                      stock_limit: int | None = None) -> dict:
    """선택한 테마의 대장주 순위. 거래대금 상위 종목만 심사한다.

    stock_limit — 몇 종목까지 심사할지. 기본은 THEME_STOCK_LIMIT(8)이다.
    '매수심사결과 높은 순위 7'은 테마 20개를 한꺼번에 돌아 종목 수가 8배로 불어나므로
    더 적은 수를 넘겨 받는다(2026-07-30 사용자 지적: 15초는 너무 느리다).
    """
    limit = int(stock_limit or THEME_STOCK_LIMIT)
    stocks = theme_row.get("stocks") or []
    if not stocks:
        detail = get_theme_stocks(theme_row.get("no"))
        if not detail.get("ok"):
            return {"ok": False, "error": detail.get("error"), "rows": []}
        stocks = detail["stocks"]

    ranked_by_value = sorted(
        [s for s in stocks if s.get("trading_value")],
        key=lambda s: s["trading_value"],
        reverse=True,
    )[:limit]
    if not ranked_by_value:
        ranked_by_value = stocks[:limit]

    # 테마 20일 수익률 = 구성종목 20일 수익률의 중앙값(테마 ETF가 없는 국내 사정).
    theme_ret20 = None
    rows = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_analyze_stock, stock, None) for stock in ranked_by_value]
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                rows.append(result)

    if not rows:
        # 왜 한 종목도 못 남겼는지 구별해서 알려준다. '시세를 못 가져왔다'로
        # 뭉뚱그리면 신규상장 테마처럼 시세는 멀쩡히 오는데 이력이 짧아 지표만
        # 못 내는 경우에 엉뚱한 원인을 찾게 된다(2026-07-29 '2026 하반기
        # 신규상장' 테마에서 실제로 발생: 레몬헬스케어 17일·레메디 12일치뿐).
        return _leaders_failure(ranked_by_value)

    ret20_values = [r["metrics"]["ret20"] for r in rows if r["metrics"].get("ret20") is not None]
    if ret20_values:
        theme_ret20 = float(pd.Series(ret20_values).median())

    # 테마 상대강도가 정해졌으니 점수를 다시 매긴다.
    for row in rows:
        row["score"], row["score_parts"] = _stock_score(row["metrics"], row["flow"], theme_ret20)
        row["plan"] = _entry_plan(row["metrics"], row["score"], market_score, theme_score)

    rows.sort(key=lambda row: row["score"], reverse=True)
    for index, row in enumerate(rows, 1):
        row["rank"] = index
        from_high = row["metrics"].get("from_high_pct")
        flow = row["flow"]
        flow_text = (
            f" · 외국인+기관 5일 {flow['net5_amount'] / 1e8:+,.0f}억"
            if flow.get("ok") else " · 수급 확인 필요"
        )
        row["stock_reason"] = (
            f"테마 내 종합 {index}위 · 52주 고가 대비 {from_high:.1f}%{flow_text}"
            if from_high is not None else f"테마 내 종합 {index}위{flow_text}"
        )

    return {
        "ok": True,
        "rows": rows,
        "theme_ret20": theme_ret20,
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


TOP_REVIEW_LIMIT = 7

# 순위 7을 뽑을 때 테마마다 몇 종목까지 볼지.
# 3으로 줄여 봤더니 1.0초 빨라지는 대신 상위 7 중 2개가 바뀌었다
# (2026-07-30 실측: 코리안리·오리온이 빠지고 현대해상·S-Oil이 들어왔다).
# 속도는 연결 재사용으로 잡는 쪽이 낫다고 보고 정확도를 지킨다 — 기본값 그대로 8이다.
TOP_REVIEW_STOCKS_PER_THEME = THEME_STOCK_LIMIT

# 결과를 따로 캐시하지는 않는다 — 일봉·수급이 이미 300초 캐시라 다시 누르면
# 그물망 조회가 거의 다 걸린다(2026-07-30 실측: 두 번째 누름 0.2초).


def _keep_better(picked: dict, row: dict, *, source: str) -> None:
    """같은 종목이 여러 테마에 겹치면 점수가 높은 쪽만 남긴다."""
    code = str(row.get("code") or "").strip()
    if not code:
        return
    kept = picked.get(code)
    if kept is not None:
        kept.setdefault("sources", [])
        if source and source not in kept["sources"]:
            kept["sources"].append(source)
        if float(row.get("score") or 0) <= float(kept.get("score") or 0):
            return
        row = dict(row)
        row["sources"] = kept["sources"]
    else:
        row = dict(row)
        row["sources"] = [source] if source else []
    picked[code] = row


def find_top_reviewed_stocks(
    theme_rows,
    *,
    market_score: float = 0,
    extra_rows=None,
    limit: int = TOP_REVIEW_LIMIT,
) -> dict:
    """'매수 심사 결과' 종목 조건점수 상위 N개 (2026-07-30 사용자 지시).

    전수 검색을 새로 돌리지 않는다. **이미 화면에 떠 있는 테마의 대장주(각 1~6위)**와
    **사용자가 이미 돌려 둔 눌림목 결과**만 한 자루에 담아 줄 세운다.
    사용자 지시: "테마20개 대장주 + 눌림목 상위 몇 개, 그 안에서 하면 가벼울 것".

    순위 기준은 **종목 조건점수 하나뿐**이다(사용자 선택). 상태·판정은 화면에 같이
    보여 주되 순위는 바꾸지 않는다 — 순위 기준이 둘이면 표를 못 읽는다.
    """
    picked: dict[str, dict] = {}
    errors: list[str] = []
    scanned_themes = 0
    theme_scores = {
        str(row.get("name") or ""): float(row.get("score") or 0)
        for row in (theme_rows or [])
    }

    # 테마를 하나씩 돌면 20개에 한참 걸린다(2026-07-30 사용자 지적: 로딩이 너무 길다).
    # 테마끼리는 서로를 안 기다리므로 한꺼번에 돌린다. 안쪽 종목 조회도 이미 병렬이라
    # 너무 많이 벌리면 네이버 쪽이 막으므로 6갈래로만 나눈다.
    def _one(theme_row):
        # 예외는 여기서 잡아 테마 이름과 함께 돌려준다 — 밖에서 잡으면 어느 테마가
        # 실패했는지 알 수 없다.
        name = str(theme_row.get("name") or "")
        try:
            return name, get_theme_leaders(
                theme_row,
                market_score=market_score,
                theme_score=float(theme_row.get("score") or 0),
                stock_limit=TOP_REVIEW_STOCKS_PER_THEME,
            )
        except Exception as exc:
            return name, {"ok": False, "error": str(exc), "rows": []}

    themes = list(theme_rows or [])
    if themes:
        with ThreadPoolExecutor(max_workers=6) as executor:
            for future in [executor.submit(_one, row) for row in themes]:
                name, result = future.result()
                if not result.get("ok"):
                    errors.append(f"{name}: {result.get('error') or '조회 실패'}")
                    continue
                scanned_themes += 1
                for row in result["rows"]:
                    _keep_better(picked, row, source=name)

    for row in extra_rows or []:
        if not row.get("metrics"):
            continue
        # 눌림목 결과는 게이트를 열어 둔 채(시장·테마 100점) 계산돼 있다.
        # 여기서는 오늘 실제 시장 점수로 다시 판정해야 화면 값과 어긋나지 않는다.
        themes = row.get("themes") or []
        theme_score = max((theme_scores.get(str(t), 0.0) for t in themes), default=0.0)
        merged = dict(row)
        merged["plan"] = _entry_plan(
            row["metrics"], float(row.get("score") or 0), market_score, theme_score
        )
        _keep_better(picked, merged, source=(str(themes[0]) if themes else "눌림목"))

    rows = sorted(
        picked.values(), key=lambda item: float(item.get("score") or 0), reverse=True
    )[: max(1, int(limit))]
    for index, row in enumerate(rows, 1):
        row["pick_rank"] = index

    return {
        "ok": bool(rows),
        "rows": rows,
        "scanned_themes": scanned_themes,
        "candidate_count": len(picked),
        "errors": errors,
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


_MINUTE_URL = (
    "https://api.finance.naver.com/siseJson.naver"
    "?symbol={code}&requestType=1&startTime={day}&endTime={day}&timeframe=minute"
)
_MINUTE_ROW_PATTERN = re.compile(r'\["(\d{12})",[^,]*,[^,]*,[^,]*,\s*([\d.]+)')


def get_last_session_intraday(code: str, back_days: int = 5) -> dict | None:
    """마지막으로 열린 장의 분봉. 주말·휴장이면 하루씩 거슬러 올라가며 찾는다.

    2026-07-25: 주말에 분봉이 없다고 30일 일봉으로 대신 그렸더니 '코스피가 기준가
    위로 간 적이 없는데 빨간 구간이 있다'는 지적을 받았다. 그림은 언제나 '하루치
    분봉 + 그 전날 종가'여야 한다. 자료가 없으면 그리지 않는다(틀린 그림보다 낫다).
    """
    for back in range(back_days + 1):
        day = (datetime.now(_SEOUL) - timedelta(days=back)).strftime("%Y%m%d")
        payload = get_intraday_chart(code, day=day)
        if isinstance(payload, dict) and payload.get("ok"):
            return payload
    return None


def get_intraday_chart(code: str, *, ttl_seconds: float = 60, day: str | None = None) -> dict | None:
    """당일 분봉 흐름(네이버 siseJson). 자비스3의 당일 차트와 같은 역할이다.

    FinanceDataReader는 분봉을 주지 않아서 네이버 차트 API를 쓴다. 응답은 JSON이 아니라
    파이썬 리터럴 형식이고 시가·고가·저가는 null이라 종가만 뽑아 쓴다.
    """
    code = str(code).strip()
    day = day or datetime.now(_SEOUL).strftime("%Y%m%d")

    def _produce():
        text = _get_text(_MINUTE_URL.format(code=code, day=day), timeout=8)
        pairs = _MINUTE_ROW_PATTERN.findall(text)
        if len(pairs) < 5:
            raise RuntimeError("분봉 데이터가 부족합니다")
        rows = []
        for stamp, close in pairs:
            value = _finite(close)
            if value is None:
                continue
            rows.append((datetime.strptime(stamp, "%Y%m%d%H%M"), value))
        if len(rows) < 5:
            raise RuntimeError("분봉 데이터가 부족합니다")
        rows.sort(key=lambda item: item[0])
        return rows

    try:
        rows, _stale = _cached(("minute", code, day), ttl_seconds, _produce)
    except Exception:
        return None

    frame = pd.DataFrame({"Close": [value for _stamp, value in rows]},
                         index=[stamp for stamp, _value in rows])
    daily = get_daily_frame(code)
    prev_close = None
    if daily is not None and len(daily) >= 2:
        last_date = pd.Timestamp(daily.index[-1]).date()
        today = datetime.now(_SEOUL).date()
        prev_close = _finite(daily["Close"].iloc[-2] if last_date == today else daily["Close"].iloc[-1])
    return {
        "ok": True,
        "price": frame,
        "prev_close": prev_close,
        "source_time": rows[-1][0].strftime("%Y-%m-%d %H:%M"),
    }


def _pullback_quality(metrics: dict, flow: dict) -> dict | None:
    """눌림목 품질 100점 — '올라가던 종목이 얼마나 좋은 자리까지 눌렸나'를 잰다.

    매수 심사 통과 여부(게이트)와는 다른 관점이다. 지금 시장이 나빠 못 사더라도,
    시장이 돌아섰을 때 먼저 볼 관찰 목록을 만드는 것이 목적이다(2026-07-22 사용자 제안).

    보는 것 다섯 가지:
    - 신고가 시점 : 52주 신고가를 최근에 찍었을수록 좋다. '올라가던 종목'인지 가리는
                    가장 단순하고 확실한 기준이다(2026-07-22 사용자 제안).
    - 20일선 이격 : 20일선에 붙어 있을수록 좋은 자리(멀면 아직 안 눌렸거나 이미 이탈)
    - 장기 추세   : **2026-08-07에 0점이 됐다.** 200·50일선 위가 실측에서 거꾸로였다.
                    위/아래 표시는 화면에 그대로 남지만 점수에는 섞지 않는다.
    - 눌림 깊이   : 고점 대비 -5~-20%가 건강한 조정. 너무 얕으면 조정 전, 깊으면 추세 훼손
    - 수급        : 눌리는 동안 외국인·기관이 담고 있으면 반등 확률이 높다
    """
    current, sma20 = metrics.get("current"), metrics.get("sma20")
    if not current or not sma20:
        return None

    gap_pct = (current / sma20 - 1) * 100          # 20일선 이격도
    from_high = metrics.get("from_high_pct")

    # 신고가를 며칠 전에 찍었나 — 20거래일(약 한 달) 이내면 만점, 120일 넘으면 0점.
    days_ago = metrics.get("high52_days_ago")
    if days_ago is None:
        recency = 0.0
    elif days_ago <= 20:
        recency = 25.0
    elif days_ago >= 120:
        recency = 0.0
    else:
        recency = 25.0 * (1 - (days_ago - 20) / 100.0)

    # 20일선에 붙을수록 만점(±2% 이내 25점 → ±8% 0점)
    proximity = max(0.0, 25.0 * (1 - max(0.0, abs(gap_pct) - 2.0) / 6.0))

    # 2026-08-07: 이 20점도 뺐다. `_stock_score`의 추세 항목과 **같은 것을 재는데**
    # (50일선 위·200일선 위) 실측에서 거꾸로로 나왔다 — 50일선 위는 창 107개 중
    # 11개, 200일선 위는 3~31%에서만 이겼다. 한쪽만 고치면 같은 화면 안에서 같은
    # 조건에 서로 다른 값을 매기게 된다. 계산은 남겨 둔다(되살릴 수 있게).
    trend = 0.0
    if PULLBACK_TREND_POINTS:
        half = PULLBACK_TREND_POINTS / 2.0
        if metrics.get("sma50") and current > metrics["sma50"]:
            trend += half
        if metrics.get("sma200") and current > metrics["sma200"]:
            trend += half

    # 고점 대비 -5~-20%를 건강한 눌림으로 본다.
    if from_high is None:
        depth = 0.0
    elif -20.0 <= from_high <= -5.0:
        depth = 25.0
    elif -30.0 <= from_high < -20.0 or -5.0 < from_high <= -2.0:
        depth = 15.0
    elif from_high < -30.0:
        depth = 5.0
    else:
        depth = 10.0

    if flow.get("ok"):
        net5 = flow.get("net5_amount") or 0
        # 위 조건점수와 같은 이유로 '연속' 대신 '동반'을 쓴다(2026-07-25).
        partner = flow.get("both_buy_days5") or 0
        supply = min(15.0, (8.0 if net5 > 0 else 0.0) + min(7.0, partner * 2.0))
    else:
        supply = 0.0

    score = round(recency + proximity + trend + depth + supply, 1)
    return {
        "score": score,
        "gap_pct": gap_pct,
        "from_high_pct": from_high,
        "high52_days_ago": days_ago,
        "above_sma200": bool(metrics.get("sma200") and current > metrics["sma200"]),
        "parts": [round(recency, 1), round(proximity, 1), round(trend, 1),
                  round(depth, 1), round(supply, 1)],
    }


def get_theme_universe(*, ttl_seconds: float = 90) -> dict:
    """전체 테마의 구성종목을 한 번 모아 '종목별 소속 테마 목록'을 만든다.

    구성관계는 천천히 변하지만 거래대금은 장중 계속 변한다. 예전 30분 캐시는 장전
    0원 스냅샷을 오전 내내 재사용할 수 있어 90초로 줄인다. 화면은 수동 실행이므로
    사용자가 조회하지 않는 동안에는 네이버 요청이 발생하지 않는다.
    """

    def _produce():
        listing = get_all_themes()
        if not listing.get("ok"):
            raise RuntimeError(listing.get("error") or "테마 목록 조회 실패")
        seen: dict[str, dict] = {}
        themes = list(listing["themes"].values())
        # 테마가 266개다. 한 번에 10개씩 받으면 27번을 기다려야 한다.
        #
        # 이 숫자는 같은 날 두 번 고쳤다. 처음엔 실제시간만 보고 20개로 올렸는데,
        # 스레드별로 CPU를 재 보니 그게 잘못이었다 — 눌림목 첫 클릭(차가움) 실측:
        #   일꾼 20개 → 실제 4.43초 / CPU 28.58초
        #   일꾼 12개 → 실제 4.57초 / CPU 18.08초
        #   일꾼  8개 → 실제 5.20초 / CPU 17.55초
        # 실제시간은 거의 같은데 CPU가 10초 넘게 차이난다. 연결을 그만큼 새로 열어
        # SSL 준비를 반복하고, 스레드가 서로 GIL을 다투는 값이다.
        # 코어가 1~2개인 온라인에서는 실제시간이 CPU를 따라가므로 12개가 낫다.
        # 받는 자료·계산·신선도는 하나도 바뀌지 않는다(2026-07-30).
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {
                executor.submit(
                    get_theme_stocks, theme["no"], ttl_seconds=ttl_seconds
                ): theme for theme in themes
            }
            for future in as_completed(futures):
                theme = futures[future]
                try:
                    detail = future.result()
                except Exception:
                    continue
                if not detail.get("ok"):
                    continue
                for stock in detail["stocks"]:
                    if _is_excluded(stock["name"], stock["code"]):
                        continue
                    entry = seen.get(stock["code"])
                    if entry is None:
                        seen[stock["code"]] = {
                            **stock, "themes": [theme["name"]], "theme_name": theme["name"]
                        }
                    elif theme["name"] not in entry["themes"]:
                        entry["themes"].append(theme["name"])
        if not seen:
            raise RuntimeError("구성종목을 모으지 못했습니다")
        return {"stocks": seen, "theme_count": len(themes)}

    try:
        value, stale = _cached("theme_universe", ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stocks": {}}
    return {"ok": True, "stale": stale, **value}


def clear_pullback_cache() -> None:
    """눌림목을 다시 찾을 때 결과와 종목→테마 지도를 새로 만든다.

    테마 상세(theme_detail) 266장은 지우지 않는다. 지우면 단추를 누를 때마다
    네이버 페이지 266장을 처음부터 다시 받는다 — 2026-07-31 사용자 실측으로
    이것이 눌림목 12초·다시 눌러도 9초의 몸통임이 확인됐다. 90초 캐시를 그대로
    살려 두면 그 안에 다시 누를 때는 받아 둔 것을 쓴다(90초가 지나면 예전처럼
    새로 받는다). 값·점수·판정은 바뀌지 않는다 — 90초 안에는 90초 전 거래대금을
    쓸 뿐이고, 화면 안내는 이미 눌림목을 30분 캐시라고 적고 있다.
    """
    # 설명서 두 갈래(2026-08-01)도 같이 지운다 — 안 지우면 '새로 찾기'를 눌러도
    # 옛 결과가 그대로 나온다.
    stale_prefixes = ("pullback_stocks", "kr_breakout_pullback", "kr_crash_rebound")
    with _CACHE_LOCK:
        for key in list(_CACHE):
            if key == "theme_universe" or key == "theme_list":
                _CACHE.pop(key, None)
            elif isinstance(key, tuple) and key and key[0] in stale_prefixes:
                _CACHE.pop(key, None)


def score_at_past(
    daily: pd.DataFrame | None,
    flow: dict,
    market_ret20,
    days_ago: int,
    *,
    market_daily: pd.DataFrame | None = None,
):
    """며칠 전 시점의 가격·기술 조건점수를 100점으로 환산한다.

    눌림목은 '그때 좋았던 종목이 지금 눌린 것'이다. 지금 점수로 자르면 눌렸다는
    이유로 탈락한다 — 신고가를 찍던 날은 신고가 위치가 만점이었을 테니 그때 점수를
    봐야 한다(2026-07-22 사용자 지적).

    일봉을 그 시점까지 자르고, KOSPI도 같은 날짜까지 잘라 당시 20일 상대강도를
    복원한다. 과거 외국인·기관 수급은 현재 데이터로 복원할 수 없으므로 절대 섞지
    않는다. 종목점수의 가격·기술 80점을 100점으로 환산해 서로 비교한다.

    ``flow`` 인자는 기존 호출 호환을 위해 남기되 과거점수에는 사용하지 않는다.
    ``market_daily``가 없을 때만 전달받은 market_ret20을 대체 기준으로 쓴다.
    """
    # 역산이 실패해도 종목이 통째로 빠지면 안 된다 — None을 돌려주면 호출부가
    # 현재 점수로 대신 판단한다.
    try:
        if daily is None or days_ago is None or days_ago <= 0:
            return None
        if len(daily) <= days_ago + 25:
            return None
        past = daily.iloc[: len(daily) - days_ago]
        metrics = _series_metrics(past)
        if not metrics.get("ok"):
            return None
        past_market_ret20 = market_ret20
        market_basis = "현재 KOSPI 대체"
        if isinstance(market_daily, pd.DataFrame) and not market_daily.empty:
            cutoff = pd.Timestamp(past.index[-1])
            aligned_market = market_daily.loc[:cutoff]
            market_metrics = _series_metrics(aligned_market)
            if market_metrics.get("ok") and market_metrics.get("ret20") is not None:
                past_market_ret20 = market_metrics["ret20"]
                market_basis = "신고가 당시 KOSPI"

        # 과거 수급을 현재 수급으로 위장하지 않는다. 가격·기술 80점만 계산한 뒤
        # 100점으로 환산한다. 추격 감점은 _stock_score 안에서 그대로 반영된다.
        raw_score, parts = _stock_score(metrics, {"ok": False}, past_market_ret20)
        technical_score = round(min(100.0, max(0.0, raw_score / 80.0 * 100.0)), 1)
        return {
            "score": technical_score,
            "raw_score": raw_score,
            "parts": parts[:5],
            "metrics": metrics,
            "as_of": pd.Timestamp(past.index[-1]).date().isoformat(),
            "basis": f"과거 가격·기술(수급 제외) · {market_basis}",
        }
    except Exception:
        return None


# ── 설명서 두 갈래의 한국판 (2026-08-01 사용자 지시) ──────────────────────────
# 규칙(며칠 기다리고 몇 % 눌린 것을 보는지)은 미국장 눌림목 매매 설명서 그대로다.
# 숫자는 2026-08-01에 **한국 자료로 직접 쟀다**(그전에는 미국 값이라 안 적었다).
#
# 어떻게 쟀나 — 한국 대형주 197종목(오늘 시총 상위 200 중 자료가 있는 것),
# 2014-05 ~ 2026-07(12년) 일봉. 신호는 그날까지의 자료로만 만들고, 매수는 다음
# 거래일 시가, 매도는 정해진 거래일 뒤 종가다. 자세한 것은 docs/KR_RULE_BACKTEST.md.
#
# **baseline은 반드시 같이 보여 준다.** '아무 날이나 사서 같은 기간 들고 있었을 때'의
# 성적이다. 규칙 성적만 적으면 좋아 보이지만, 기준선과 견줘야 규칙이 값을 했는지
# 알 수 있다 — 실제로 낙폭 얕은 갈래는 기준선보다 못했다.
# ── 2026-08-07 전면 재측정 ──────────────────────────────────────────────────
# **그물과 배점을 통째로 다시 잡았다.** 그전 값은 두 가지가 어긋나 있었다.
#   ① 시총 상위 197종목으로 쟀는데 화면이 실제로 뒤지는 것은 **테마 2,272종목**이다.
#   ② 12년을 통째로 한 번만 쟀다. 이번에는 **3년짜리 창을 한 달씩 밀며 100번 넘게**
#      재고, 창 2·3·4년 모두에서 승률·수익률 둘 다 이겨야 인정했다.
#      (자르는 날 하나에 기대면 안 된다 — 2026-08-07 상하님 지적.)
# 격자로 상승 192조합·급락 240조합을 다 재서 고른 것이다.
# 측정 코드: research/kr_net_grid.py · research/kr_score_new.py
#
# **거래대금 50억 문턱이 새로 들어갔다.** 그 아래에서는 규칙이 앞 시기에 졌다.
KR_LIQUIDITY_FLOOR = 50e8          # 그물에 넣을 최소 50일 평균 거래대금(50억)

BREAKOUT_PULLBACK_RULE = {
    "wait_days": (3, 10),       # 52주 신고가 돌파 뒤 기다리는 거래일
    "drop_band": (-6.0, -4.0),  # 그 고점에서 눌린 폭
    "hold_days": 250,           # 약 1년. 120일보다 세 창 모두에서 나았다.
    "liquidity_floor": KR_LIQUIDITY_FLOOR,
    "verified_in_korea": True,
    # 테마 명부 2,272종목 3,000거래일. 자리 7,410건 · 신호 난 날 2,310일.
    "win_rate": 43.4, "sample": 7410, "median_return": -6.6,
    "base_win_rate": 35.1, "base_median_return": -14.0,
    "years_better": 9, "years_total": 11,
    # 창 2·3·4년 전부에서 이겼다(가운데 +8.7%p · 가장 나쁜 창 +0.0%p).
    "windows_won": "321/321",
}
CRASH_REBOUND_RULES = (
    {"key": "deep", "band": (-60.0, -40.0), "hold_days": 20, "label": "고점 대비 -40~-60%",
     "win_rate": 66.6, "sample": 3739, "median_return": 6.1,
     "base_win_rate": 62.1, "base_median_return": 4.1, "beats_baseline": True,
     "windows_won": "306/306"},
)
# 코스피가 고점 대비 -15% 아래로 내려간 국면에서 **가장 깊었던 날**이 신호다.
# 12년에 스물아홉 번 났다(옛 규칙 '첫 반등일'은 여덟 번뿐이었다 — 기회가 세 배 넘게
# 늘었고 성적은 더 좋았다). 그래도 사실상 스물아홉 번의 사건이라, 승률을 앞으로의
# 확률로 읽으면 안 된다.
CRASH_MARKET_DROP = -15.0
CRASH_REBOUND_EVENTS = 29
KR_BACKTEST_SPAN = "2014-05 ~ 2026-08(12년) · 테마 명부 2,272종목"

# 낙폭 종목의 순위 기준 (2026-08-01 사용자 지시). 두 가지를 순서대로 본다.
#
#   1순위 — **외국인+기관이 5일 동안 함께 산 날 수**(동그라미 다섯 개, 0~5).
#           가장 큰 비중이다. 둘이 같이 사는 종목이 반등에서 먼저 간다.
#   2순위 — **같은 테마에서 같이 오른 종목 수**. 2개·3개·4개 이상으로 나누고
#           4개 이상이 가장 높다. 한 종목만 튀는 것과 테마가 통째로 살아나는
#           것은 다르다는 뜻이다.
#
# 여기서 '테마 개수'는 그 종목이 **몇 개 테마에 이름을 올렸는지**가 아니라,
# **같은 테마 안에서 오늘 같이 오른 종목이 몇 개인지**다(2026-08-01 사용자 정정).
TOGETHER_TIERS = ((4, 3, "4개 이상"), (3, 2, "3개"), (2, 1, "2개"))


def together_tier(count: int) -> tuple[int, str]:
    """같은 테마에서 같이 오른 종목 수 → (순위 점수, 화면에 적을 말)."""
    for least, points, label in TOGETHER_TIERS:
        if count >= least:
            return points, label
    return 0, f"{max(int(count), 0)}개"


# '밸류업 지수 편입' 같은 것은 업종 테마가 아니라 **명단**이다. 서로 상관없는 대형주
# 100개가 한 이름 아래 묶여 있어서, 같이 움직였는지를 보는 데는 쓸 수 없다
# (2026-08-01 실측: 이것 때문에 대부분의 종목이 똑같이 '21개'로 나왔다).
# 크기로는 못 가른다 — 자동차부품 145개·2차전지 141개는 진짜 업종이다.
_BASKET_THEME_WORDS = ("밸류업", "지수 편입", "Value-up")


def _is_basket_theme(name: str) -> bool:
    return any(word in str(name) for word in _BASKET_THEME_WORDS)


# ── 급락 후 반등장 전용 배점 (2026-08-01) ────────────────────────────────────
# 왜 따로 만드나 — 기존 조건점수는 '신고가에 얼마나 가까운가'와 '이동평균 위인가'로
# 절반을 준다. 고점 대비 -40% 종목은 그 조건을 정의상 하나도 못 맞춘다. 그대로 두면
# 찾아 놓고 '제외'라고 하는 화면이 된다.
#
# **미국(jarvis3)과 배점이 다르다.** 같은 자로 재면 안 된다 — 시장도, 있는 자료도,
# 재 본 결과도 다르다. 한국 80~197종목 12년치(2014-05~2026-07)로 잰 결과다.
#
#   40점 같은 테마 동반 — 낙폭 구간 111,012개. 100번 중 이긴 횟수
#                        0~1개 49번 / 2개 50번 / 3개 52번 / 4개 이상 55번.
#                        혼자 빠진 종목은 오히려 손해(가운데 -0.38%)였다.
#   25점 낙폭 갈래     — -40~-50%(20일 보유)는 100번 중 69번으로 기준선(59번)을
#                        이겼고, -30~-40%(60일)는 기준선과 같았다. 그래서 깊은
#                        갈래만 만점을 준다.
#   20점 거래대금 연속 — 0일 52번 / 4~10일 54번 / 11일 이상 61번(가운데 +4.96%).
#                        미국(15점)보다 높게 준다 — 한국이 더 뚜렷했다.
#                        다만 **이미 오른 종목은 깎는다**(아래 설명).
#   15점 유동성       — 성적 예측이 아니라 '실제로 사고팔 수 있는가'.
#    0점 외국인+기관 동반 5일 — **재 보니 거꾸로였다.** 187,632개 표본에서
#                        0일 52번 / 3일 51번 / 5일 46번으로 내려갔고, 낙폭
#                        구간에서 더 뚜렷했다(3일 이상 53.0번 vs 1일 이하 54.9번).
#                        둘이 사는 동안 값이 이미 올라 따라 들어가면 늦기 때문이다.
#                        **표에는 그대로 보여 주되 점수와 순위에서는 뺀다.**
#
# ── 2026-08-07 다시 잼 — 위 주석의 옛 배점은 **버린다** ──────────────────────
# 새 그물(코스피 -15% 국면 가장 깊은 날 · 거래대금 50억↑ · 종목 -40~-60% · 20거래일)
# 위에서 후보 17개를 창 2·3·4년으로 다시 쟀다. 그물 안 3,907자리.
# 칸은 '승률로 이긴 창% / 수익률로 이긴 창%'.
#
#   30점 최근 11일에 안 올랐나 — 100/100 · 99/99 · 99/99 (가운데 +16.0%p)
#                              **+5% 넘게 오른 종목은 0/0 · 0/2 · 0/1로 최악**
#                              (가운데 -20.9%p · 가장 나쁜 창 -43.7%p). 이미 반등을
#                              시작한 종목을 사면 안 된다는 뜻이다.
#   25점 60일에 안 올랐나     — 100/100 · 100/100 · 100/100, 가장 나쁜 창 +2.8%p.
#   25점 같은 테마 동반       — 3개↑가 100/100 세 창 전부. **미국과 정반대다** —
#                              미국 급락 후 반등장에서는 동반 개수가 안 붙었는데
#                              (68%가 해당돼 못 가름) 한국은 붙는다. 한국 테마가
#                              266개로 잘게 쪼개져 있어서로 보인다.
#   20점 사고팔기 쉬운가      — 성적 예측이 아니라 '실제로 살 수 있는가'.
#
# **뺀 것** — 낙폭 갈래(그물로 이미 한 번 썼다) · 거래대금 연속(새 그물에서 안 붙음)
#            · 외국인+기관 동반(2026-08-01에 거꾸로로 확인, 그대로 0점)
# 2026-08-07: '테마 등수' 25점을 넣고 나머지를 비례해 줄였다(30/25/25/20 → 22.5/18.75/18.75/15).
# 급락 그물에서는 **테마가 덜 빠졌나 상위 20%**가 통과했다(창 86 / 88 / 86%, 최악 -2.0p).
# 같은 그물에서 테마 60일 수익률은 통과하지 못했다(49 / 60 / 67%) — 급하게 반등을
# 노릴 때는 '이미 오르던 테마'가 아니라 '덜 다친 테마'였다(research/kr_score_new.py).
CRASH_SCORE_WEIGHTS = {
    "recent11": 22.5, "gain60": 18.75, "together": 18.75, "liquidity": 15.0,
    "theme_rank": 25.0,
}
# 최근 11일 / 60일 등락 → 점수. 빠졌으면 만점, 오를수록 깎고, 많이 올랐으면 0점.
CRASH_RECENT_FULL, CRASH_RECENT_ZERO = -5.0, 5.0
CRASH_GAIN60_FULL, CRASH_GAIN60_ZERO = 0.0, 40.0


def _fade(value, full: float, zero: float, points: float) -> float:
    """full이면 만점, zero면 0점, 그 사이는 비례. 모르면 절반."""
    if value is None:
        return points * 0.5
    number = float(value)
    if (zero - full) == 0:
        return points
    ratio = (zero - number) / (zero - full)
    return float(points) * max(0.0, min(1.0, ratio))

# 거래대금 연속을 그냥 주면 안 된다(2026-08-01 사용자 지적: "이미 오른 상황 아닌가?").
# 한국 낙폭 구간에서 최근 11일 오름폭을 같게 맞춰 놓고 견준 결과
# (연속 0~3일 → 연속 4일 이상, 가운데 값·100번 중 이긴 횟수):
#     이미 -5% 넘게 빠짐  +1.65% 55번 → +4.08% 62번   ← 가장 좋다
#     0~+5%             +0.42% 51번 → +1.92% 54번
#     +15% 넘게 오름      +1.45% 53번 → -0.77% 48번   ← 손해다
# 값을 하는 것은 '거래대금이 많다'가 아니라 **'값은 아직 안 올랐는데 돈만 붙어 있다'**다.
VOLUME_STREAK_LOOKBACK = 11
VOLUME_STREAK_GATES = ((0.0, 1.0), (15.0, 0.5))


def volume_streak_weight(recent_gain_pct: float | None) -> float:
    """최근에 이미 오른 만큼 거래대금 연속 점수를 깎는 배수(0~1)."""
    if recent_gain_pct is None:
        return 0.5
    for limit, factor in VOLUME_STREAK_GATES:
        if float(recent_gain_pct) <= limit:
            return factor
    return 0.0


def volume_streak_days(frame) -> int:
    """거래대금이 50일 평균 위에 며칠 연속인지. 오늘이 평균 아래면 0."""
    try:
        value = frame["Close"].astype(float) * frame["Volume"].astype(float)
        above = value > value.rolling(50).mean()
    except Exception:
        return 0
    days = 0
    for flag in reversed(above.tolist()):
        if flag is not True:
            break
        days += 1
    return days


def recent_gain_pct(frame, days: int = VOLUME_STREAK_LOOKBACK) -> float | None:
    """최근 며칠 동안 이미 얼마나 올랐는지(%)."""
    try:
        close = frame["Close"].dropna()
        if len(close) <= days:
            return None
        return (float(close.iloc[-1]) / float(close.iloc[-1 - days]) - 1) * 100
    except Exception:
        return None


def _crash_rank_key(row: dict):
    """순위 — ① 같은 테마 동반(검증됨) ② 낙폭 깊은 갈래 ③ 거래대금 연속(이미 오른
    종목은 깎는다) ④ 거래대금. 외국인+기관 동반은 재 보니 거꾸로라 안 쓴다."""
    streak = min(int(row.get("volume_streak") or 0), VOLUME_STREAK_LOOKBACK)
    return (
        -row.get("together_tier", 0),
        -row.get("together_count", 0),
        row.get("_order", 9),
        -streak * volume_streak_weight(row.get("recent_gain_pct")),
        -(row.get("liquidity_value") or 0),
    )


def _breakout_rank_key(row: dict):
    """상승장 순위 — 낙폭과 **다른 차례**다(실측이 다르다).

    ① 거래대금(500억 이상 100번 중 69~72번, 미만 55번 — 한국에서 가장 크게 갈렸다)
    ② 같은 테마 동반 ③ 최근 60일 상승폭 ④ 거래대금 평소 위 연속.
    낙폭에서 쓰던 '이미 오른 만큼 깎기'는 여기서 쓰지 않는다 — 상승장에서는 이미
    오른 종목이 더 좋았다(11일 이상 63번).
    """
    metrics = row.get("metrics") or {}
    return (
        -int(float(row.get("liquidity_value") or 0) // 5e10),   # 500억 묶음(그 아래는 안 가른다)
        -row.get("together_tier", 0),
        -float(metrics.get("ret60") or 0),
        -min(int(row.get("volume_streak") or 0), VOLUME_STREAK_LOOKBACK),
        str(row.get("code")),
    )


def _theme_rank_part(row: dict, weights: dict, label: str) -> tuple:
    """테마 등수 배점 한 줄. 두 그물이 같은 모양으로 쓴다."""
    rank = row.get("theme_rank")
    total = int(row.get("theme_rank_total") or 0)
    cutoff = int(row.get("theme_rank_cutoff") or 0)
    full = float(weights.get("theme_rank", 0.0))
    if not rank:
        note = "모름"
    else:
        note = f"{row.get('theme_rank_name') or '테마'} {int(rank)}등"
        if total:
            note += f" / {total}개"
        if cutoff:
            note += f" (상위 {cutoff}등까지 만점)"
    return (label, full if row.get("theme_rank_top") else 0.0, full, note)


def crash_rebound_score(row: dict) -> dict:
    """급락 후 반등장 후보의 점수(100점)와 근거."""
    metrics = row.get("metrics") or {}
    weights = CRASH_SCORE_WEIGHTS
    parts = []

    gain = row.get("recent_gain_pct")
    parts.append(("최근 11일에 안 올랐나",
                  _fade(gain, CRASH_RECENT_FULL, CRASH_RECENT_ZERO, weights["recent11"]),
                  weights["recent11"],
                  "모름" if gain is None else f"{float(gain):+.1f}% (5%↑ 오르면 0점)"))

    ret60 = metrics.get("ret60")
    parts.append(("60일에 안 올랐나",
                  _fade(ret60, CRASH_GAIN60_FULL, CRASH_GAIN60_ZERO, weights["gain60"]),
                  weights["gain60"],
                  "모름" if ret60 is None else f"{float(ret60):+.1f}% (40%↑ 오르면 0점)"))

    count = int(row.get("together_count") or 0)
    parts.append(("같은 테마 동반",
                  weights["together"] * min(count / 3.0, 1.0), weights["together"],
                  f"{count}개 함께 걸림 (3개↑ 만점)"))

    # 급락장에서는 '이미 오르던 테마'가 아니라 **덜 다친 테마**가 통했다.
    parts.append(_theme_rank_part(row, weights, "테마가 덜 빠졌나 (상위 20%)"))

    value = float(row.get("liquidity_value") or 0)
    parts.append(("사고팔기 쉬운가", _scale(value / 1e8, 50, 1000, weights["liquidity"]),
                  weights["liquidity"], _eok_text(value)))

    return {"score": round(sum(v for _n, v, _m, _t in parts), 1), "parts": parts, "max": 100.0}


def _eok_text(value: float) -> str:
    return f"{value / 1e8:,.0f}억" if value else "—"


# ── 상승장(신고가 눌림매수) 전용 배점 · 한국 (2026-08-01) ─────────────────────
# **미국 값을 옮겨 적지 않았다.** 한국 자료로 따로 쟀다 —
# 신고가 눌림 자리 1,779개 · 187종목 · 2015-06~2026-01 · 보유 120거래일.
# 기준선 가운데 +4.61% · 100번 중 57번.
#
# 아래는 전부 **'최근 60일 상승폭을 같게 맞춰 놓고도' 살아남은 것만** 적은 것이다.
# 그냥 나눠 보면 서로 겹쳐서(강한 종목이 대체로 거래대금도 크다) 이중으로 셀 수 있다.
#
#   30점 유동성(거래대금)  — 500억 이상이 100번 중 69번·72번(500억 미만 55번).
#                          한국에서 **가장 크게 갈린 값**이다. 미국(10점)보다 훨씬 높다.
#   30점 같은 테마 동반    — 0개 55번 → 1개 61번 → 2개 70번. 상승폭을 맞춰도 남는다
#                          (강한 구간에서 76번 vs 혼자 57번).
#   25점 최근 60일 상승폭  — 0~15% 52번 → 15~40% 58번 → 40% 넘음 61번.
#   15점 거래대금 평소 위 연속 — 0일 55번 → 4~10일 58번 → 11일 이상 63번.
#
# **미국 상승장과 정반대인 것 — 반드시 기억할 것**
#   거래대금 평소 위 연속: 미국 상승장에서는 거꾸로여서 0점이다(11일 이상 53번).
#   한국 상승장에서는 **바로 간다**(63번). 시장이 다르면 같은 값도 뜻이 다르다.
#
# 재 보고 **뺀 것**
#   * 눌린 폭 — -6~-4% 안에서 56/58/56/56번으로 평평하다. 미국은 갈렸지만(66번)
#     한국은 안 갈린다. 그래서 0점이다.
#   * 변동성 — 한 방향이 아니다. 강한 종목에서는 높은 변동성이 좋고(64번) 약한
#     종목에서는 나쁘다(44번). 조건에 따라 뒤집히는 값으로 점수를 주지 않는다.
#   * 기다린 날(3일 57번·5일 56번) — 차이 없음.
#   * 50·200일선 위 — 표본 1,779개가 **전부** 위였다. 신고가 종목은 정의상 그렇다.
#
# ── 2026-08-07 다시 잼 — 위 주석의 옛 배점은 **버린다** ──────────────────────
# 새 그물(거래대금 50억↑ · 신고가 뒤 3~10일 · -4~-6% · 250거래일) 위에서 다시 쟀다.
# 그물 안 8,415자리. 칸은 '승률로 이긴 창% / 수익률로 이긴 창%'.
#
#   30점 거래대금        — 500억↑가 100/90 · 100/100 · 100/100, 가장 나쁜 창 +4.9%p.
#                        1,000억↑는 더 좋다(가운데 +14.7%p). 한국에서 가장 크게 갈린다.
#   25점 같은 테마 동반   — 3개↑가 85/95 · 96/100 · 100/100.
#   25점 많이 흔들리지 않나 — **6%가 넘으면 최악이다.** 7/0 · 2/1 · 0/0으로
#                        295개 창 중 거의 전부에서 졌다(가운데 -9.9%p · 최악 -30.9%p).
#                        2026-08-01에는 '한 방향이 아니다'라며 0점을 줬는데,
#                        새 그물에서는 방향이 뚜렷하다.
#   20점 60일에 너무 오르지 않았나 — **40%가 넘으면 거꾸로다.** 17/13 · 28/21 · 31/15
#                        (가운데 -6.0%p). 2026-08-01에는 40%↑에 만점을 줬는데
#                        **정반대였다.** 앞뒤로 갈라 재지 않아 놓친 것이다.
#
# **뺀 것** — 거래대금 평소 위 연속(새 그물에서 74/73 · 63/68 · 52/59로 안 붙음)
# 2026-08-07: '테마 등수' 30점을 넣고 나머지를 비례해 줄였다(30/25/25/20 → 21/17.5/17.5/14).
# **테마 60일 수익률 상위 20%는 오늘 잰 것 중 가장 강했다** — 창 100 / 100 / 100%,
# 최악의 창에서도 +5.3p였다. 종목 항목 어느 것도 여기 못 미친다.
BREAKOUT_SCORE_WEIGHTS = {
    "liquidity": 21.0, "together": 17.5, "volatility": 17.5, "ret60": 14.0,
    "theme_rank": 30.0,
}
# 변동성(ATR/주가) — 4% 아래면 만점, 6%를 넘으면 0점.
BREAKOUT_ATR_FULL, BREAKOUT_ATR_ZERO = 4.0, 6.0
# 60일 상승폭 — 안 올랐으면 만점, 40% 넘게 올랐으면 0점.
BREAKOUT_GAIN60_FULL, BREAKOUT_GAIN60_ZERO = 0.0, 40.0

# 한국 상승장은 같은 날 같은 테마에서 함께 걸리는 일이 미국보다 드물다
# (0개 1,395 / 1개 311 / 2개 56 / 3개 이상 17). 그래서 낙폭용 2·3·4개 등급을
# 그대로 쓰면 거의 모두 0점이 된다. 실측이 갈린 자리에 맞춰 1·2개로 나눈다.
BREAKOUT_TOGETHER_TIERS = ((2, 3, "2개 이상"), (1, 2, "1개"))


def breakout_together_tier(count: int) -> tuple[int, str]:
    """상승장 전용 — 같은 테마에서 함께 걸린 종목 수 → (0~3점, 화면에 적을 말)."""
    for least, points, label in BREAKOUT_TOGETHER_TIERS:
        if count >= least:
            return points, label
    return 0, "혼자"


def breakout_score(row: dict) -> dict:
    """상승장(신고가 눌림매수) 후보의 점수(100점)와 근거. 한국 전용 배점."""
    metrics = row.get("metrics") or {}
    weights = BREAKOUT_SCORE_WEIGHTS
    parts = []

    value = float(row.get("liquidity_value") or 0)
    parts.append(("거래대금", _scale(value / 1e8, 50, 500, weights["liquidity"]),
                  weights["liquidity"], f"{_eok_text(value)} (500억↑ 만점)"))

    count = int(row.get("together_count") or 0)
    parts.append(("같은 테마 동반",
                  weights["together"] * min(count / 3.0, 1.0), weights["together"],
                  f"{count}개 함께 걸림 (3개↑ 만점)"))

    # 오늘 잰 것 중 가장 강했다 — 창 100 / 100 / 100%, 최악의 창에서도 +5.3p.
    parts.append(_theme_rank_part(row, weights, "테마 60일 등수 (상위 20%)"))

    atr = metrics.get("atr")
    ratio = None
    current = metrics.get("current")
    if atr is not None and current:
        ratio = float(atr) / float(current) * 100
    parts.append(("많이 흔들리지 않나",
                  _fade(ratio, BREAKOUT_ATR_FULL, BREAKOUT_ATR_ZERO, weights["volatility"]),
                  weights["volatility"],
                  "모름" if ratio is None else f"하루 {ratio:.1f}% (6%↑면 0점)"))

    ret60 = metrics.get("ret60")
    parts.append(("60일에 너무 오르지 않았나",
                  _fade(ret60, BREAKOUT_GAIN60_FULL, BREAKOUT_GAIN60_ZERO, weights["ret60"]),
                  weights["ret60"],
                  "모름" if ret60 is None else f"{float(ret60):+.1f}% (40%↑면 0점)"))

    return {"score": round(sum(v for _n, v, _m, _t in parts), 1), "parts": parts, "max": 100.0}


def breakout_plan(row: dict) -> dict:
    """상승장(신고가 눌림매수)의 매수 심사 결과. 기준가도 손절가도 규칙에 없다."""
    metrics = row.get("metrics") or {}
    hold = int(row.get("hold_days") or BREAKOUT_PULLBACK_RULE["hold_days"])
    score = float(breakout_score(row)["score"])
    if score >= 70:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= 50:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "breakout",
        "entry": "다음 거래일 시가",
        "hold_days": hold,
        "current": metrics.get("current"),
        "invalidation": None,
        "target": None,
        "buy_reason": (
            f"52주 신고가를 찍고 {int(row.get('wait_days') or 0)}거래일이 지나 "
            f"고점 대비 {metrics.get('from_high_pct', 0):.1f}%까지 눌린 자리입니다. "
            f"규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 사서 "
            f"{hold}거래일 뒤 종가에 팝니다. 이 규칙에는 손절가가 없습니다."
        ),
    }


def crash_rebound_plan(row: dict) -> dict:
    """급락 후 반등장의 매수 심사 결과.

    이 규칙에는 **넘어야 할 기준가도, 손절가도 없다.** 정해진 날 시가에 사서 정해진
    날 종가에 판다. 없는 것을 있는 것처럼 적지 않는다.
    """
    metrics = row.get("metrics") or {}
    hold = int(row.get("hold_days") or 0)
    score = float(crash_rebound_score(row)["score"])
    if score >= 70:
        state, recommendation = "규칙에 맞는 자리", "조건부 후보"
    elif score >= 50:
        state, recommendation = "자리는 맞으나 근거가 얇음", "관찰"
    else:
        state, recommendation = "규칙만 맞고 뒷받침이 없음", "관찰"
    return {
        "state": state,
        "recommendation": recommendation,
        "rule_mode": "crash",
        "entry": "다음 거래일 시가",
        "hold_days": hold,
        "current": metrics.get("current"),
        "invalidation": None,
        "target": None,
        "buy_reason": (
            f"고점 대비 {metrics.get('from_high_pct', 0):.1f}%까지 내려온 낙폭 종목입니다. "
            f"규칙대로라면 오늘 종가를 확인하고 다음 거래일 시가에 사서 "
            f"{hold}거래일 뒤 종가에 팝니다. 이 규칙에는 손절가가 없습니다."
        ),
    }


THEME_RANK_MIN_MEMBERS = 3
# 한국은 테마가 262개라 '상위 몇 등'보다 '상위 몇 %'가 안정적이다. 실측도 20%로 했다.
THEME_RANK_TOP_RATIO = 0.20


def attach_theme_rank(items: list, universe_metrics: dict, metric_key: str) -> None:
    """이 종목이 속한 테마가 **오늘 몇 등인지** 각 줄에 적는다 (2026-08-07 도입).

    한국은 그물마다 답이 달랐다(`research/kr_score_new.py`).

      · 상승장(250거래일) — **테마 60일 수익률 상위 20%**
        창 100 / 100 / 100%, 최악의 창에서도 +5.3p. 오늘 잰 것 중 가장 강했다.
      · 급락 후 반등장(20거래일) — **테마가 덜 빠졌나 상위 20%**
        창 86 / 88 / 86%, 최악 -2.0p. 여기서는 60일 수익률이 안 통했다(49/60/67).

    한 달 뒤에 볼 것과 1년 뒤에 볼 것이 다르다는 뜻이다. 급하게 반등을 노릴 때는
    '덜 다친 테마', 길게 들 때는 '이미 오르고 있는 테마'였다.

    `metric_key`는 종목 지표의 이름이고, 클수록 좋은 값이라야 한다
    (`ret60`은 그대로, `from_high_pct`는 0에 가까울수록 크므로 그대로 쓴다).
    """
    totals: dict[str, list] = {}
    for entry in (universe_metrics or {}).values():
        value = (entry.get("metrics") or {}).get(metric_key)
        if value is None:
            continue
        for name in entry.get("themes") or []:
            if _is_basket_theme(name):
                continue
            totals.setdefault(name, []).append(float(value))

    averages = {name: sum(values) / len(values)
                for name, values in totals.items()
                if len(values) >= THEME_RANK_MIN_MEMBERS}
    order = sorted(averages, key=lambda name: -averages[name])
    place = {name: index + 1 for index, name in enumerate(order)}
    cutoff = max(1, int(round(len(order) * THEME_RANK_TOP_RATIO)))

    for item in items:
        places = [place[name] for name in (item.get("themes") or []) if name in place]
        best = min(places) if places else None
        item["theme_rank"] = best
        item["theme_rank_total"] = len(order)
        item["theme_rank_cutoff"] = cutoff
        item["theme_rank_top"] = bool(best is not None and best <= cutoff)
        item["theme_rank_name"] = (
            next((name for name in (item.get("themes") or []) if place.get(name) == best), "")
            if best else "")


def _theme_together(matched: list) -> dict[str, int]:
    """테마마다 '같은 기준에 함께 걸린 종목이 몇 개인지' 센다.

    처음에는 테마 전체에서 오늘 오른 종목을 셌는데, 네이버 테마는 범위가 넓어
    64~135개가 나왔다(2026-08-01 실측). 그러면 2·3·4개 등급이 아무 뜻이 없다.
    그래서 **같은 낙폭 기준을 통과한 종목끼리** 센다 — '이 테마가 통째로 반등
    자리에 와 있나'를 재는 것이고, 사용자가 말한 2·3·4개 눈금과도 맞는다.
    """
    together: dict[str, int] = {}
    for item in matched:
        for theme in item.get("themes") or []:
            if _is_basket_theme(theme):
                continue
            together[theme] = together.get(theme, 0) + 1
    return together
# 한국은 대형주 목록이 따로 없다. 테마 구성종목 중 거래대금 상위 이만큼을 본다 —
# 미국의 '대형주 200개'와 같은 자리다.
RULEBOOK_SCAN_LIMIT = 200


def reference_drawdown(daily, reference_date: str | None) -> dict:
    """**기준일 그날** 그 종목이 고점에서 얼마나 빠져 있었나 (2026-08-07).

    갈래와 점수는 오늘 낙폭이 아니라 **그날 낙폭**으로 정해야 한다. 오늘 값으로
    정하면 이미 반등한 종목이 목록에서 사라져 정작 사야 할 자리를 놓친다
    (미국테마가 같은 이유로 그날 값을 쓴다).

    돌려주는 값 — judged: 그날 낙폭 · since: 그날 종가에서 지금까지의 변동.
    자료가 모자라면 빈 dict.
    """
    if daily is None or reference_date is None:
        return {}
    try:
        frame = daily[["High", "Close"]].dropna()
        stamp = pd.Timestamp(reference_date)
        upto = frame.loc[:stamp]
        if len(upto) < 60:
            return {}
        window = upto.tail(252)
        peak = float(window["High"].max())
        then = float(upto["Close"].iloc[-1])
        now = float(frame["Close"].iloc[-1])
        if peak <= 0 or then <= 0:
            return {}
        return {
            "judged_from_high_pct": (then / peak - 1.0) * 100.0,
            "since_reference_pct": (now / then - 1.0) * 100.0,
        }
    except Exception:
        return {}


def _rulebook_scan(match, *, min_trading_value: float, scan_limit: int,
                   result_limit: int, rule_key: str = "breakout") -> dict:
    """거래대금 상위 종목을 훑어 `match(metrics)`가 참인 것만 모은다.

    find_pullback_stocks와 같은 길을 쓴다 — 테마 구성종목 → 유동성 상위 → 일봉 →
    조건. 다른 점은 조건이 '설명서 규칙 하나'뿐이고 이동평균·테마 수를 보지 않는
    것이다(설명서에 없는 조건이라).
    """
    universe = get_theme_universe()
    if not universe.get("ok"):
        raise RuntimeError(universe.get("error") or "테마 구성종목 조회 실패")
    seen = universe["stocks"]
    candidates = []
    for item in seen.values():
        current_value = float(item.get("trading_value") or 0)
        previous_proxy = float(item.get("price") or 0) * float(item.get("previous_volume") or 0)
        liquidity = max(current_value, previous_proxy)
        if liquidity >= min_trading_value:
            candidates.append({**item, "liquidity_value": liquidity})
    liquid_total = len(candidates)
    # 동점은 종목코드로 갈라 순서를 고정한다(돌릴 때마다 목록이 바뀌지 않게).
    candidates.sort(key=lambda item: (-(item.get("liquidity_value") or 0), str(item.get("code"))))
    candidates = candidates[:scan_limit]

    def _screen(stock):
        daily = get_daily_frame(stock["code"])
        metrics = _series_metrics(daily, stock.get("price"))
        if not metrics.get("ok"):
            return None
        # 일부 규칙은 **그날 값**을 봐야 해서 일봉도 같이 넘긴다(2026-08-07).
        # 옛 방식대로 metrics 하나만 받는 규칙도 그대로 돈다.
        try:
            matched = match(metrics, daily)
        except TypeError:
            matched = match(metrics)
        # 테마 등수는 **명부 전체**로 매긴다 — 걸린 종목만으로 매기면 그날 몇 개가
        # 걸렸느냐에 따라 등수가 출렁인다. 그래서 걸리지 않은 종목의 지표도 남긴다.
        with _rank_lock:
            universe_metrics[str(stock.get("code"))] = {
                "metrics": metrics, "themes": stock.get("themes") or []}
        if not matched:
            return None
        return {**stock, "metrics": metrics, "daily": daily, "rule": matched,
                "volume_streak": volume_streak_days(daily),
                "recent_gain_pct": recent_gain_pct(daily)}

    universe_metrics: dict[str, dict] = {}
    _rank_lock = threading.Lock()
    screened = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for future in as_completed([executor.submit(_screen, s) for s in candidates]):
            try:
                item = future.result()
            except Exception:
                continue
            if item:
                screened.append(item)

    screened.sort(key=lambda item: (-(item.get("liquidity_value") or 0), str(item.get("code"))))
    picked = screened[:result_limit]

    kospi = _index_metrics("KS11")
    market_ret20 = kospi.get("ret20") if kospi.get("ok") else None

    def _finalize(item):
        flow = get_stock_flow(item["code"])
        score, parts = _stock_score(item["metrics"], flow, market_ret20)
        return {**item, "flow": flow, "score": score, "score_parts": parts,
                "pullback": _pullback_quality(item["metrics"], flow) or {}}

    final = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for future in as_completed([executor.submit(_finalize, s) for s in picked]):
            try:
                final.append(future.result())
            except Exception:
                continue
    # 같은 기준에 함께 걸린 종목이 테마마다 몇 개인지 — 낙폭 표의 2순위 기준이다.
    # 표에 보이는 20개가 아니라 **기준을 통과한 전부**로 센다. 보이는 것만 세면
    # 순위가 자기 자신을 보고 정해지는 꼴이 된다.
    together = _theme_together(screened)
    for item in final:
        # **자기 자신은 빼고 센다.** 검증할 때도 그렇게 셌고(docs/KR_RULE_BACKTEST.md),
        # 미국(jarvis3)도 같다. 안 빼면 2·3·4개 눈금이 한 칸씩 밀려 다른 뜻이 된다.
        pairs = [
            (max(together.get(name, 0) - 1, 0), name)
            for name in (item.get("themes") or [])
            if not _is_basket_theme(name)
        ]
        best = max(pairs) if pairs else (0, "")
        item["together_count"], item["together_theme"] = best[0], best[1]
        points, label = together_tier(best[0])
        item["together_tier"], item["together_label"] = points, label
    # 그물마다 줄 세우는 자가 다르다 — 급락은 '덜 빠졌나', 상승장은 '60일 수익률'.
    # 실측이 그렇게 갈렸다(`attach_theme_rank` 설명글).
    attach_theme_rank(
        final, universe_metrics,
        "from_high_pct" if rule_key == "crash" else "ret60")
    final.sort(key=lambda item: (-(item.get("liquidity_value") or 0), str(item.get("code"))))
    for index, item in enumerate(final, 1):
        item["pullback_rank"] = index
        item["plan"] = _entry_plan(item["metrics"], item["score"], 100, 100)
        item.pop("daily", None)
    return {
        "rows": final,
        "universe_count": len(seen),
        "liquid_count": liquid_total,
        "scanned_count": len(candidates),
        "screened_count": len(screened),
        "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
    }


def find_breakout_pullback_stocks(
    *, min_trading_value: float = KR_LIQUIDITY_FLOOR,
    scan_limit: int = RULEBOOK_SCAN_LIMIT,
    result_limit: int = 20, ttl_seconds: float = 600,
) -> dict:
    """설명서 1번의 한국판 — 정상 상승장의 '신고가 눌림매수' 자리.

    52주 신고가 뒤 3~10거래일이 지나고 그 고점에서 4~6% 내려온 종목만 본다.
    이동평균은 보지 않는다 — 설명서에 없는 조건이다.

    **거래대금 문턱이 200억에서 50억으로 내려왔다**(2026-08-07). 200억은 아무 근거
    없이 잡아 둔 값이었고, 격자로 재 보니 값이 갈리는 자리는 50억이었다. 화면 설명도
    50억이라고 적혀 있으므로 실제 문턱과 맞춘다.
    """
    wait_min, wait_max = BREAKOUT_PULLBACK_RULE["wait_days"]
    drop_low, drop_high = BREAKOUT_PULLBACK_RULE["drop_band"]

    def _match(metrics):
        days_ago = metrics.get("high52_days_ago")
        from_high = metrics.get("from_high_pct")
        if days_ago is None or not (wait_min <= days_ago <= wait_max):
            return None
        if from_high is None or not (drop_low <= from_high <= drop_high):
            return None
        return {"wait_days": int(days_ago), "hold_days": BREAKOUT_PULLBACK_RULE["hold_days"]}

    def _produce():
        found = _rulebook_scan(
            _match, min_trading_value=min_trading_value,
            scan_limit=scan_limit, result_limit=result_limit,
        )
        for row in found["rows"]:
            row.update(row.pop("rule"))
            row["partner5"] = int((row.get("flow") or {}).get("both_buy_days5") or 0)
            # 낙폭용 2·3·4개 등급을 쓰면 상승장에서는 거의 모두 0점이 된다
            # (한국 상승장은 같이 걸리는 일이 드물다). 실측이 갈린 1·2개로 다시 매긴다.
            points, label = breakout_together_tier(int(row.get("together_count") or 0))
            row["together_tier"], row["together_label"] = points, label
            # **갈래 점수가 곧 순위다** (2026-08-09 상하님 결정) — 아래 설명 참고.
            row["stock_score"] = row.get("score")     # 눌림목 조건점수는 이름을 옮긴다
            row["rule_score"] = float(breakout_score(row)["score"])
        # **차례는 갈래 점수 순이다** (2026-08-09 상하님 결정).
        #
        # 왜 바꿨나 — 2026-08-01에는 배점과 차례를 같은 측정에서 같이 만들어 둘이
        # 맞았다. 2026-08-07에 한국을 처음부터 다시 재면서 **배점만 갈아엎고**
        # 차례 함수(_breakout_rank_key)는 그대로 뒀다. 그래서 8/7에 "쓰지 마라"고
        # 결론 난 것들(낙폭 갈래·거래대금 연속)이 차례에는 계속 살아 있었고,
        # 제일 잘 들었던 테마 등수는 차례에 아예 안 쓰였다.
        # 점수와 차례가 코드에서 서로 다른 곳에 있어 한쪽만 고치기 쉬웠던 것이다.
        # 미국테마는 처음부터 점수를 차례로 쓰므로 고칠 곳이 한 군데뿐이다 —
        # 한국도 그렇게 맞춘다. 아래 _breakout_rank_key는 **동점 가르기**에만 쓴다.
        #
        # **성적이 좋아진다는 뜻은 아니다.** 8/7에 잰 것은 '항목 하나하나가 성적을
        # 가르는가'였고 '이 점수로 줄 세우면 위쪽이 나은가'는 아직 안 쟀다.
        found["rows"].sort(key=lambda row: (-float(row.get("rule_score") or 0.0),
                                            _breakout_rank_key(row)))
        for index, row in enumerate(found["rows"], 1):
            row["pullback_rank"] = index
        return {**found, "mode": "breakout", "rule": BREAKOUT_PULLBACK_RULE,
                "result_limit": int(result_limit)}

    try:
        key = ("kr_breakout_pullback", float(min_trading_value), int(scan_limit), int(result_limit))
        value, stale = _cached(key, ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}
    return {"ok": True, "stale": stale, **value}


def find_crash_rebound_stocks(
    *, min_trading_value: float = KR_LIQUIDITY_FLOOR,
    scan_limit: int = RULEBOOK_SCAN_LIMIT,
    result_limit: int = 20, ttl_seconds: float = 600,
) -> dict:
    """설명서 2번의 한국판 — 급락 후 반등장의 '낙폭 종목'.

    신고가가 언제였는지는 보지 않고 고점 대비 낙폭만 본다. 이동평균도 보지 않는다 —
    30~50% 빠진 종목이 50일선 위에 있을 리 없다.
    """

    # **갈래는 기준일 그날 낙폭으로 나눈다**(2026-08-07). 오늘 값으로 나누면 이미
    # 반등해서 -40% 밖으로 올라온 종목이 목록에서 사라진다 — 정작 사야 할 자리를
    # 놓친다. 미국테마가 같은 이유로 그날 값을 쓴다.
    # 기준일이 없으면(국면이 아니면) 예전처럼 오늘 값으로 나눈다.
    state = kr_crash_market_state()
    reference_date = state.get("reference_date") if state.get("ok") else None

    def _bucket_of(drop):
        if drop is None:
            return None
        for order, rule in enumerate(CRASH_REBOUND_RULES):
            low, high = rule["band"]
            if low <= drop < high:
                return {"bucket": rule["key"], "bucket_label": rule["label"],
                        "hold_days": rule["hold_days"], "_order": order}
        return None

    def _match(metrics, daily=None):
        # **기준일 낙폭은 여기서 재서 같이 실어 보내야 한다**(2026-08-09 고침).
        # `_rulebook_scan`은 줄을 돌려주기 전에 일봉(daily)을 떼어 낸다(무거워서).
        # 그래서 나중에 다시 재려고 하면 자료가 이미 없어 늘 빈칸이었다 —
        # 2026-08-07부터 화면의 '기준일 낙폭' 칸이 계속 비어 있던 까닭이다.
        # 갈래(bucket)는 제대로 나뉘고 있었다. 여기서 이미 이 값으로 나눴기 때문이다.
        ref = reference_drawdown(daily, reference_date) if reference_date else {}
        judged = ref.get("judged_from_high_pct")
        bucket = _bucket_of(judged if judged is not None
                            else metrics.get("from_high_pct"))
        if bucket is None:
            return None
        return {**bucket, **ref}

    def _produce():
        found = _rulebook_scan(
            _match, min_trading_value=min_trading_value,
            scan_limit=scan_limit, result_limit=result_limit,
            rule_key="crash",
        )
        counts = {rule["key"]: 0 for rule in CRASH_REBOUND_RULES}
        # 기준일 낙폭은 위 `_match`가 이미 재서 rule에 실어 보냈다 — 여기서 다시
        # 재려고 하면 일봉이 이미 떨어져 나가 늘 빈칸이 된다(2026-08-09 고침).
        for row in found["rows"]:
            row.update(row.pop("rule"))
            counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1
            row["partner5"] = int((row.get("flow") or {}).get("both_buy_days5") or 0)
            row["reference_date"] = reference_date
            row["now_from_high_pct"] = (row.get("metrics") or {}).get("from_high_pct")
            row["stock_score"] = row.get("score")     # 눌림목 조건점수는 이름을 옮긴다
            row["rule_score"] = float(crash_rebound_score(row)["score"])
        # **차례는 갈래 점수 순이다** (2026-08-09 상하님 결정, 위 상승장과 같은 이유).
        # 아래 _crash_rank_key는 동점 가르기에만 쓴다. 외국인+기관 동반은 재 보니
        # 거꾸로라(동반 일수가 많을수록 나빴다) 점수에도 차례에도 안 쓴다.
        found["rows"].sort(key=lambda row: (-float(row.get("rule_score") or 0.0),
                                            _crash_rank_key(row)))
        for index, row in enumerate(found["rows"], 1):
            row["pullback_rank"] = index
            row.pop("_order", None)
        return {**found, "mode": "crash", "rules": CRASH_REBOUND_RULES,
                "bucket_counts": counts, "result_limit": int(result_limit)}

    try:
        key = ("kr_crash_rebound", float(min_trading_value), int(scan_limit), int(result_limit))
        value, stale = _cached(key, ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}
    return {"ok": True, "stale": stale, **value}


def find_pullback_stocks(
    *,
    min_theme_count: int = 2,
    high_days_min: int = 1,
    # 20일이면 삼성전자(신고가 24일 전)처럼 조금 늦게 눌린 대형주가 통째로 빠진다.
    # 2026-07-24 사용자 지시로 30일까지 넓혔다.
    high_days_max: int = 30,
    min_stock_score: float = 75.0,
    min_trading_value: float = 2e10,
    theme_scan_limit: int = 300,
    scan_limit: int = 50,
    result_limit: int = 15,
    ttl_seconds: float = 600,
) -> dict:
    """상승추세 중 조정받은 눌림목 종목을 찾는다 (2026-07-22 사용자 스펙).

    조건 세 가지 — 사용자가 정한 것만 쓴다:
    1. **52주 최고가를 찍고 1~20일 지난 종목** — 방금 고점을 찍고 내려오는 중인 것.
    2. **2개 이상 테마에 속한 종목**
    3. **신고가 시점 종목 조건점수 75점 이상** — 나머지 품질은 이 점수 하나로 거른다.

    하락장 판단은 이 함수가 하지 않는다 — 시장 국면은 상단 '한국 전체시장 판단'에서
    사용자가 보고 정한다.
    """

    def _produce():
        universe = get_theme_universe()
        if not universe.get("ok"):
            raise RuntimeError(universe.get("error") or "테마 구성종목 조회 실패")
        seen = universe["stocks"]

        multi_theme = [
            item for item in seen.values() if len(item["themes"]) >= min_theme_count
        ]
        # 장전·장초반에는 오늘 누적 거래대금이 0에 가깝다. HTML에 이미 있는
        # 전일거래량×현재가를 유동성 대체값으로 함께 쓰되, 오늘 값과 둘 중 큰 값을
        # 선택해 시간대에 따라 후보 수가 수십 배 흔들리는 문제를 줄인다.
        for item in multi_theme:
            current_value = float(item.get("trading_value") or 0)
            previous_proxy = float(item.get("price") or 0) * float(item.get("previous_volume") or 0)
            item["liquidity_value"] = max(current_value, previous_proxy)
        candidates = [
            item for item in multi_theme
            if item["liquidity_value"] >= min_trading_value
        ]
        if not candidates:
            return {
                "rows": [],
                "universe_count": len(seen),
                "multi_theme_count": len(multi_theme),
                "liquid_count": 0,
                "scanned_count": 0,
                "screened_count": 0,
                "flow_checked_count": 0,
                "window": (high_days_min, high_days_max),
                "message": "유동성 기준을 통과한 종목이 없습니다.",
                "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
            }
        # 조회 시간이 후보 수에 비례하므로 거래대금 상위부터 상한을 둔다 —
        # 눌림목을 노릴 만한 종목은 거래대금이 받쳐주는 쪽이다.
        multi_theme_total = len(multi_theme)
        liquid_total = len(candidates)
        # 동점일 때 종목코드로 갈라 준다. 안 갈라 주면 스레드가 끝나는 순서에 따라
        # **어느 종목이 상위 50개에 드는지**가 돌릴 때마다 달라진다(2026-07-30 실측).
        candidates.sort(
            key=lambda item: (-(item.get("liquidity_value") or 0), str(item.get("code")))
        )
        candidates = candidates[:scan_limit]

        # 2) 일봉으로 '52주 최고가 찍고 1~15일 지난 종목'만 거른다.
        low, high = high_days_min, high_days_max

        def _screen(stock):
            daily = get_daily_frame(stock["code"])
            metrics = _series_metrics(daily, stock.get("price"))
            if not metrics.get("ok"):
                return None
            days_ago = metrics.get("high52_days_ago")
            if days_ago is None or not (low <= days_ago <= high):
                return None
            # 고점을 찍고 '내려가는' 종목이어야 한다(고점 그대로면 눌림이 아니다).
            if (metrics.get("from_high_pct") or 0) >= 0:
                return None
            return {**stock, "metrics": metrics, "daily": daily}

        screened = []
        # 일꾼을 16개에서 8개로 줄인다. 일봉은 대기보다 계산이 지배하는 일이고,
        # 일꾼을 늘리면 연결을 그만큼 새로 열어 SSL 준비를 반복한다.
        # 50종목 실측(2026-07-30, 공용연결로 바꾼 뒤):
        #   일꾼 4개 실제 1.21초/CPU 2.84 · 6개 0.67/1.58 · 8개 0.66/1.59 · 16개 1.17/8.09
        # 코어가 1~2개인 온라인에서는 실제시간이 CPU 시간을 따라가므로 CPU가 낮은 쪽이 낫다.
        #
        # 한 종목으로 연결을 먼저 데워 보는 것도 해 봤다. 따로 재면 CPU가 줄지만
        # 전체로 돌리면 CPU는 그대로고 실제시간만 0.5초 늘었다 — 그래서 안 넣었다
        # (2026-07-30 실측).
        with ThreadPoolExecutor(max_workers=8) as executor:
            for future in as_completed([executor.submit(_screen, s) for s in candidates]):
                try:
                    item = future.result()
                except Exception:
                    continue
                if item:
                    screened.append(item)

        # 3) 살아남은 종목만 수급을 조회해 최종 점수를 매긴다.
        # 상대강도 기준은 KOSPI 20일 수익률을 쓴다 — 테마를 가로지르는 검색이라
        # 테마 상대강도를 못 쓰는데, None으로 넘기면 20점이 통째로 0점이 돼
        # 하나금융지주가 95점에서 75.5점으로 떨어졌다(2026-07-22 실측 수정).
        kospi = _index_metrics("KS11")
        market_ret20 = kospi.get("ret20") if kospi.get("ok") else None
        try:
            kospi_daily, _kospi_stale = _cached(
                ("index", "KS11"), 300, lambda: _index_frame("KS11")
            )
        except Exception:
            kospi_daily = None

        def _finalize(item):
            flow = get_stock_flow(item["code"])
            quality = _pullback_quality(item["metrics"], flow)
            score, parts = _stock_score(item["metrics"], flow, market_ret20)
            # 신고가를 찍던 시점의 점수를 역산한다 — 눌림목은 '그때 좋았던 종목'이므로
            # 이 점수로 걸러야 한다(지금 점수는 눌린 만큼 낮게 나온다).
            past = score_at_past(
                item.get("daily"), flow, market_ret20,
                item["metrics"].get("high52_days_ago"),
                market_daily=kospi_daily,
            )
            return {**item, "flow": flow, "pullback": quality,
                    "score": score, "score_parts": parts,
                    "peak_score": past["score"] if past else None,
                    "peak_parts": past["parts"] if past else None,
                    "peak_score_date": past["as_of"] if past else None,
                    "peak_score_basis": past["basis"] if past else "현재 종합점수 대체"}

        final = []
        # 여기도 동점을 종목코드로 갈라 준다 — 수급을 조회할 25개가 흔들리면 결과가
        # 돌릴 때마다 달라진다.
        screened.sort(
            key=lambda item: (-(item.get("liquidity_value") or 0), str(item.get("code")))
        )
        flow_targets = screened[:25]
        with ThreadPoolExecutor(max_workers=10) as executor:
            for future in as_completed([executor.submit(_finalize, s) for s in flow_targets]):
                try:
                    item = future.result()
                except Exception:
                    continue
                # 80점 기준은 '신고가 시점 점수'로 본다 — 지금 점수는 눌린 만큼 낮다.
                # 역산이 안 되는 종목만 현재 점수로 대신 판단한다.
                gate_score = item.get("peak_score")
                if gate_score is None:
                    gate_score = item.get("score")
                if item.get("pullback") and float(gate_score or 0) >= min_stock_score:
                    final.append(item)

        # 신고가 기술점수가 같으면 종목코드로 갈라 순위를 고정한다. 안 갈라 주면
        # 새로 고칠 때마다 2위·3위가 뒤바뀐다 — 2026-07-30 실측: KB금융과 신한지주가
        # 둘 다 95.7점이라 네 번 돌려 한 번 자리가 바뀌었다. 점수는 하나도 안 바꾸고
        # 동점일 때만 순서를 정한다(종목코드는 값의 좋고 나쁨과 무관한 기준이다).
        final.sort(
            key=lambda item: (
                -float(item.get("peak_score") or item.get("score") or 0),
                str(item.get("code")),
            )
        )
        final = final[:result_limit]
        for index, item in enumerate(final, 1):
            item["pullback_rank"] = index
            item["plan"] = _entry_plan(item["metrics"], item["score"], 100, 100)
            item.pop("daily", None)
        return {
            "rows": final,
            "universe_count": len(seen),
            "multi_theme_count": multi_theme_total,
            "liquid_count": liquid_total,
            "scanned_count": len(candidates),
            "screened_count": len(screened),
            "flow_checked_count": len(flow_targets),
            "window": (low, high),
            "checked_at": datetime.now(_SEOUL).isoformat(timespec="seconds"),
        }

    try:
        cache_key = (
            "pullback_stocks", min_theme_count, high_days_min, high_days_max,
            float(min_stock_score), float(min_trading_value), int(theme_scan_limit),
            int(scan_limit), int(result_limit),
        )
        value, stale = _cached(cache_key, ttl_seconds, _produce)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "rows": []}
    return {"ok": True, "stale": stale, **value}


def get_live_quote(code: str) -> dict:
    """선택 종목 최근가 — 장중이면 네이버 테마 상세의 현재가와 같은 값을 쓴다."""
    daily = get_daily_frame(code, ttl_seconds=60)
    metrics = _series_metrics(daily)
    if not metrics.get("ok"):
        return {"ok": False, "error": "시세 조회 실패"}
    return {"ok": True, **metrics, "code": str(code)}


def _prepare_chart_payload(frame: pd.DataFrame, resample_rule: str | None, limit: int) -> dict:
    chart = frame.copy()
    if resample_rule:
        aggregations = {"Close": "last"}
        for column, how in (("Open", "first"), ("High", "max"), ("Low", "min"), ("Volume", "sum")):
            if column in chart.columns:
                aggregations[column] = how
        chart = chart.resample(resample_rule).agg(aggregations).dropna(subset=["Close"])
    chart["MA20"] = chart["Close"].rolling(20).mean()
    chart["MA50"] = chart["Close"].rolling(50).mean()
    chart = chart.tail(limit)
    return {
        "ok": True,
        "price": chart[["Close", "MA20", "MA50"]].copy(),
        "volume": chart[["Volume"]].copy() if "Volume" in chart.columns else None,
    }


# 차트용 일봉은 심사용(400일)보다 훨씬 길게 받는다.
# 400일이면 월봉이 14개월뿐이라 20개월선이 아예 안 그려지고, 주봉 50주선도
# 마지막 9개만 나와 선이 토막났다(2026-07-29 사용자 지적).
# 월봉 36개 + 50개월선을 채우려면 86개월(약 7년)이 필요하다. 실측 0.1초.
_CHART_HISTORY_DAYS = 2600


def get_chart_bundle(code: str) -> dict:
    """한 번의 일봉 조회로 일봉·주봉·월봉 차트를 함께 만든다."""
    code = str(code).strip()
    try:
        frame, _stale = _cached(
            ("chart_daily", code), 300,
            lambda: _read_daily(code, days=_CHART_HISTORY_DAYS),
        )
    except Exception:
        frame = None
    if frame is None or frame.empty:
        # 긴 자료를 못 받으면 심사용 짧은 자료로라도 그린다.
        frame = get_daily_frame(code, ttl_seconds=300)
    if frame is None or frame.empty:
        return {"ok": False, "error": "차트 자료가 없습니다", "charts": {}}
    return {
        "ok": True,
        "charts": {
            "일봉": _prepare_chart_payload(frame, None, 120),
            "주봉": _prepare_chart_payload(frame, "W-FRI", 60),
            "월봉": _prepare_chart_payload(frame, "ME", 36),
        },
    }
