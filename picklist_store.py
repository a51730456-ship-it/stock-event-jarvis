"""그날의 종목 목록을 **찍은 그대로** 날짜별로 남기는 창고 (2026-08-09 상하님 지시).

왜 만들었나
-----------
상하님 말씀 그대로다 — "매수 시점 리스트를 그대로 옮겨 놓아라, 그래야 시간이
지나서 어느 정도 맞아떨어지는 데이터를 만들 수 있다."

지금까지 네 갈래(눌림목 찾기 · 상승장 · 급락 후 반등장 · 매수심사결과 높은 순위 7)는
누를 때마다 **그 순간의 시세로 새로 계산**했다. 그래서 어제 무엇이 1위였는지는
어디에도 남지 않았고, 나중에 "그때 그 목록이 맞았나"를 잴 방법이 없었다.
이 파일은 그날 화면에 뜬 줄을 손대지 않고 그대로 한 줄씩 적어 둔다.

두 가지 원칙
------------
1. **다시 계산하지 않는다.** 저장할 때도, 불러올 때도 값을 고치지 않는다.
   나중에 성적을 재는 것은 이 자료를 읽는 쪽이 할 일이다.
2. **하루에 한 판씩.** 같은 날 같은 갈래를 여러 번 저장하면 **마지막 것이 이긴다**
   (덮어쓴다). 장중에 눌러 보는 것과 마감 뒤 자동 저장이 섞이면 마감값이 남는다.

어디에 쌓나
-----------
``data/picklist/{날짜}.{시장}.csv`` — 날짜·시장마다 파일 하나다.
  * 하루치가 80줄 안팎(네 갈래 × 20위 × 두 시장)이라 자비스5처럼 gzip으로 묶지
    않는다. 그냥 CSV라야 저장소에서 눈으로 읽히고 무엇이 바뀌었는지 보인다.
  * 미국과 한국은 장 마감 시각이 달라 따로 저장한다. 한쪽을 쓰는 동안 다른 쪽
    파일을 건드리지 않으므로 클라우드에서 두 작업이 겹쳐도 서로를 지우지 않는다.
  * **저장소가 공개다**(CLAUDE.md 10번). 여기 들어가는 것은 시세·점수뿐이고
    비밀번호·열쇠는 한 글자도 들어가지 않는다.

칸을 늘리거나 줄이면 ``SCHEMA_VERSION``을 올린다. 옛 파일은 없는 칸을 빈칸으로
읽어 들이므로 지우지 않아도 된다.
"""

from __future__ import annotations

import csv
import io
import json
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from functools import lru_cache
from zoneinfo import ZoneInfo

# 계산 결과나 저장 칸을 바꾸면 이 숫자를 올리고, 페이지의 요구 리비전도 올린다
# (CLAUDE.md 11번 규칙).
MODULE_REVISION = 2026081940

SCHEMA_VERSION = 3

_SEOUL = ZoneInfo("Asia/Seoul")
_NEW_YORK = ZoneInfo("America/New_York")

ARCHIVE_DIR = Path(__file__).parent / "data" / "picklist"

MARKETS = ("US", "KR")

# 갈래 이름은 **화면에 쓰는 말 그대로** 둔다(CLAUDE.md 14번·쉬운 말 규칙).
# 파일에는 영문 열쇠를 적고, 화면에 보일 때만 이 표로 바꾼다.
LIST_KINDS = {
    "pullback": "눌림목 찾기",
    "breakout": "상승장 (신고가 눌림매수)",
    "crash": "급락 후 반등장 (낙폭종목)",
    "top7": "매수심사결과 높은 순위 9",
    # 2026-08-15 상하님 지시 — "20개 테마 중 상위 테마 5위, 각 테마 중 1~3위."
    "theme15": "상위 테마 5개 · 각 종목 1~3위",
}
KIND_ORDER = ("theme15", "pullback", "breakout", "crash", "top7")

# 순위 9는 **파트 안에서** 1·2·3으로 번호가 매겨진다(2026-08-15 상하님 지시 —
# "왜 순위가 123 123 123 이렇게 되어야지 1~9위가 나오냐"). 그래서 번호만으로 줄을
# 세우면 세 파트가 서로 섞인다. 파트 차례를 먼저 보고 그 다음에 번호를 본다.
# 이름은 jarvis3_data.TOP_PICK_QUOTA와 **같아야 한다.**
ORIGIN_ORDER = ("테마 대장주", "상승장", "급락 후 반등장")

# **저장 목록의 제목은 그 시장 화면의 제목과 같아야 한다**(2026-08-15 상하님 지시 —
# "첫 번째 캡처 화면의 제목대로 저장해 둔 목록이 나와야지. 제목들이 다른 것은 왜
# 그렇게 했나. 맞춰라"). 두 화면이 같은 갈래를 다른 이름으로 부르는 데가 둘이다.
#   · 순위 — 미국은 자리가 아홉(3·3·3), 한국은 아직 일곱이다.
#   · 눌림목 — 한국 화면은 「눌림목 종목 찾기 (상승추세 중 조정)」라 적는다.
#     미국 화면에는 2026-08-06에 뺐다(10년치로 재 보니 기준선을 못 이겼다).
#     그래서 미국은 **이제 저장하지 않는다.** 그전에 쌓인 날에는 남아 있으므로,
#     그 줄에는 화면에서 뺀 옛 갈래라고 적어 준다 — 지우지 않는다(CLAUDE.md 10-1).
KIND_LABELS_BY_MARKET = {
    "US": {
        "pullback": "눌림목 찾기 (2026-08-06에 화면에서 뺀 옛 갈래)",
        "top7": "매수심사결과 높은 순위 9",
    },
    "KR": {
        "pullback": "눌림목 종목 찾기 (상승추세 중 조정)",
        "top7": "매수심사결과 높은 순위 7",
    },
}

# 그 시장 화면에 **없는** 갈래는 새로 저장하지도, 화면에 보여 주지도 않는다.
# 2026-08-15 상하님 지적 — "저거는 없앴는데 왜 나오냐." 미국 화면에서 2026-08-06에
# 뺀 「눌림목 찾기」가 저장 목록에는 그대로 남아 있었다.
# **파일은 그대로 둔다**(CLAUDE.md 10-1 — 지우면 그때 목록이 맞았나를 잴 근거가
# 사라진다). 엑셀·CSV로 받으시면 그 줄도 다 들어 있다. 화면에서만 감춘다.
SKIP_KINDS_BY_MARKET = {"US": ("pullback",), "KR": ("theme15",)}


def kind_label(kind: str, market: str | None = None) -> str:
    """그 시장 화면이 쓰는 제목. 시장을 안 넘기면 갈래의 기본 이름."""
    per_market = KIND_LABELS_BY_MARKET.get(str(market or "").upper(), {})
    return per_market.get(kind) or LIST_KINDS.get(kind, kind)


def should_save(kind: str, market: str) -> bool:
    """그 시장에서 이 갈래를 새로 저장할지. 화면에 없는 갈래는 안 남긴다."""
    return kind not in SKIP_KINDS_BY_MARKET.get(str(market).upper(), ())


def should_show(kind: str, market: str) -> bool:
    """저장 목록 화면에 이 갈래를 보여 줄지. 파일에서 지우는 것이 아니다."""
    return should_save(kind, market)


def _origin_place(row) -> int:
    """같은 갈래 안에서 파트끼리의 차례. 상위 테마 15는 테마 등수를 쓴다."""
    if str(row.get("list_kind")) == "theme15":
        place = _num(row.get("theme_place"))
        return int(place) if place is not None else 99
    origin = str(row.get("origin") or "")
    return ORIGIN_ORDER.index(origin) if origin in ORIGIN_ORDER else len(ORIGIN_ORDER)

# 칸 순서가 곧 CSV·엑셀의 칸 순서다. 상하님이 부르신 이름을 그대로 쓴다.
FIELDS = (
    "trade_date",            # 매수 날짜 — 이 목록이 선 날
    "market",                # US · KR
    "list_kind",             # 위 LIST_KINDS의 열쇠
    "rank",                  # 1~20위
    "code",                  # 티커(미국) · 종목코드(한국)
    "name",                  # 종목명
    "themes",                # 소속 테마 (여럿이면 ' · '로 잇는다)
    "score",                 # 그 갈래가 순위를 매긴 점수
    "stock_score",           # 종목 조건점수 (순위 7이 쓰는 점수)
    "price",                 # 신호일 종가 — 신호가 난 그날의 값
    # **실제로 사는 값은 다음 거래일 시가다**(설명서 규칙, 2026-08-09 상하님 지시).
    # 신호가 난 날에는 아직 모르는 값이라 빈칸으로 저장되고, 다음 날 이후에
    # 화면에서 '계산' 단추를 누를 때 그날 시가를 찾아 채운다. 한 번 채워지면
    # 다시는 안 바뀐다 — 과거의 시가는 고정된 사실이다.
    "buy_open",              # 다음 거래일 시가 — 진짜 매수금액
    "change_pct",            # 그날 등락
    "from_high_pct",         # 고점 대비 (상승장에서는 '눌린 하락율')
    "judged_from_high_pct",  # 기준일 낙폭 — 급락 갈래가 갈래를 정하는 값
    "bucket_label",          # 낙폭 갈래 이름
    "wait_days",             # 고점 찍고 며칠 지났나 (상승장)
    "hold_days",             # 며칠 들고 가는 규칙인가
    "together_count",        # 같은 테마에서 함께 걸린 종목 수
    "recent_gain_pct",       # 최근 11일 등락
    "state",                 # 매수 상태
    "origin",                # 순위 7이 어느 갈래에서 데려온 줄인가 · 상위 테마 15는 테마 이름
    "theme_place",           # 그 테마가 20개 중 몇 등인가 (상위 테마 15)
    "saved_at",              # 적은 시각
    "schema",                # 칸 판 번호
)

_NUMBER_FIELDS = {
    "rank", "score", "stock_score", "price", "buy_open", "change_pct", "from_high_pct",
    "judged_from_high_pct", "wait_days", "hold_days", "together_count",
    "recent_gain_pct", "theme_place", "schema",
}


# ──────────────────────────────────────────────────────────────────────────
# 값 꺼내기 — 갈래마다 줄 모양이 조금씩 다르다
# ──────────────────────────────────────────────────────────────────────────

def _num(value):
    """숫자로 바꿔 준다. 못 바꾸면 None — **0으로 채우지 않는다.**

    0과 '못 잰 값'은 다른 것이다. 0으로 채우면 나중에 성적을 잴 때 안 잰 자리가
    잰 것처럼 섞인다.
    """
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN·무한대
        return None
    return number


def _first(row: dict, *paths):
    """``("metrics", "current")``처럼 여러 자리를 차례로 뒤져 첫 값을 준다."""
    for path in paths:
        keys = path if isinstance(path, tuple) else (path,)
        cursor = row
        for key in keys:
            if not isinstance(cursor, dict):
                cursor = None
                break
            cursor = cursor.get(key)
        if cursor not in (None, ""):
            return cursor
    return None


def _themes_text(row: dict) -> str:
    """테마 이름을 한 칸에 담는다. 여럿이면 ' · '로 잇는다."""
    for key in ("themes", "sources"):
        value = row.get(key)
        if isinstance(value, (list, tuple)):
            names = [str(item) for item in value if item]
            if names:
                return " · ".join(names)
        elif isinstance(value, str) and value:
            return value
    single = row.get("theme") or row.get("together_theme")
    return str(single) if single else ""


def normalize_row(row: dict, *, market: str, list_kind: str,
                  trade_date: str, rank: int, saved_at: str) -> dict:
    """화면의 한 줄을 창고의 한 줄로 옮긴다. **값은 하나도 고치지 않는다.**

    갈래마다 같은 뜻의 값이 다른 자리에 들어 있어(예: 눌림 점수는 눌림목 표에서는
    ``pullback.score``, 상승장·급락 표에서는 ``score``) 여기서 한 번만 맞춰 둔다.
    없는 값은 빈칸으로 남긴다 — 지어내지 않는다.
    """
    return {
        "trade_date": trade_date,
        "market": str(market).upper(),
        "list_kind": list_kind,
        "rank": int(rank),
        "code": str(_first(row, "ticker", "code") or ""),
        "name": str(_first(row, "name") or ""),
        "themes": _themes_text(row),
        "score": _num(_first(row, "score", ("pullback", "score"))),
        "stock_score": _num(_first(row, "stock_score", ("plan", "score"))),
        "price": _num(_first(row, ("metrics", "current"), "current", "price")),
        # 신호가 난 날에는 다음 거래일 시가를 알 수 없다. 나중에 채운다.
        "buy_open": _num(_first(row, "buy_open")),
        "change_pct": _num(_first(row, ("metrics", "change_pct"), "change_pct")),
        "from_high_pct": _num(_first(
            row, ("metrics", "from_high_pct"), ("pullback", "from_high_pct"),
            "from_high_pct", "now_from_high_pct")),
        "judged_from_high_pct": _num(_first(row, "judged_from_high_pct")),
        "bucket_label": str(_first(row, "bucket_label", "bucket") or ""),
        "wait_days": _num(_first(row, "wait_days", ("pullback", "high52_days_ago"),
                                 "high52_days_ago")),
        "hold_days": _num(_first(row, "hold_days")),
        "together_count": _num(_first(row, "together_count")),
        "recent_gain_pct": _num(_first(row, "recent_gain_pct")),
        "state": str(_first(row, ("plan", "state"), "state") or ""),
        # 상위 테마 15는 '어느 테마에서 왔나'가 곧 파트다 — 같은 칸에 담는다.
        "origin": str(_first(row, "top7_origin", "origin", "theme_name") or ""),
        "theme_place": _num(_first(row, "theme_place")),
        "saved_at": saved_at,
        "schema": SCHEMA_VERSION,
    }


def rows_from_result(result, *, market: str, list_kind: str,
                     trade_date: str, saved_at: str | None = None,
                     limit: int = 20) -> list[dict]:
    """찾기 결과(dict)를 창고 줄들로 바꾼다. 실패한 결과는 빈 목록이다.

    순위는 줄에 적힌 순위(``pullback_rank``·``pick_rank``)를 먼저 쓰고, 없으면
    목록에 담긴 차례를 쓴다 — 화면에 보이던 번호가 그대로 남아야 한다.
    """
    if list_kind not in LIST_KINDS:
        raise ValueError(f"모르는 갈래입니다: {list_kind}")
    if not isinstance(result, dict) or not result.get("ok"):
        return []
    saved_at = saved_at or datetime.now(_SEOUL).isoformat(timespec="seconds")
    # **순위 7은 자기 번호(pick_rank)를 먼저 본다.** 순위 7의 줄은 눌림목 결과에서
    # 데려온 것이라 눌림목 때의 번호(pullback_rank)를 그대로 달고 있다. 그것을 먼저
    # 보면 순위 7 표에 같은 번호가 두 번 찍힌다(2026-08-09 실제 자료에서 2위가 둘).
    # **상위 테마 15는 테마 안 등수를 그대로 쓴다** — 1·2·3이 테마마다 되풀이된다.
    rank_keys = (("pick_rank", "rank", "pullback_rank") if list_kind == "top7"
                 else ("rank", "pick_rank", "pullback_rank") if list_kind == "theme15"
                 else ("pullback_rank", "pick_rank", "rank"))
    out = []
    for index, row in enumerate(list(result.get("rows") or [])[: max(0, int(limit))], 1):
        if not isinstance(row, dict):
            continue
        rank = _num(_first(row, *rank_keys)) or index
        out.append(normalize_row(
            row, market=market, list_kind=list_kind,
            trade_date=trade_date, rank=int(rank), saved_at=saved_at,
        ))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 파일 읽고 쓰기
# ──────────────────────────────────────────────────────────────────────────

def trade_date_for(market: str, now: datetime | None = None) -> str:
    """그 시장의 '오늘'. 미국은 뉴욕 날짜, 한국은 서울 날짜다.

    한국시각으로 새벽 6시에 미국장이 끝나면 서울 날짜는 이미 다음 날이다. 서울
    날짜로 적으면 목록이 하루 뒤로 밀려 붙는다.
    """
    stamp = now or datetime.now(_SEOUL)
    zone = _NEW_YORK if str(market).upper() == "US" else _SEOUL
    return stamp.astimezone(zone).date().isoformat()


# 미국 정규장 마감 — 뉴욕 오후 4시. **서머타임은 저절로 맞는다** — 시각을
# UTC로 못박지 않고 ZoneInfo("America/New_York")로 재기 때문이다. 여름에는
# UTC-4, 겨울에는 UTC-5로 파이썬이 알아서 바꿔 준다.
US_MARKET_CLOSE_HOUR = 16
# 반휴장일(추수감사절 다음 날 등)은 뉴욕 **오후 1시**에 닫는다.
US_HALF_DAY_CLOSE_HOUR = 13


def _easter(year: int) -> date:
    """그해 부활절(그레고리력). 성금요일을 구하려고 쓴다.

    미국 증시 휴장일 열 개 중 아홉은 날짜가 정해져 있거나 '몇째 주 무슨 요일'이라
    바로 셀 수 있는데, **성금요일 하나만 부활절에 매달려 있다.** 부활절은 해마다
    3월 22일에서 4월 25일 사이를 오간다.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * i - h + m - k + 32) % 7
    month = (h - m + r + 90) // 25
    day = (h - m + r + month + 19) % 32
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """그달 n번째 무슨 요일. nth가 -1이면 **마지막** 그 요일(메모리얼데이)."""
    if nth < 0:
        last = date(year, month, calendar.monthrange(year, month)[1])
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = date(year, month, 1)
    first_hit = first + timedelta(days=(weekday - first.weekday()) % 7)
    return first_hit + timedelta(days=7 * (nth - 1))


def _observed(day: date) -> date:
    """토요일에 걸리면 앞 금요일, 일요일이면 다음 월요일에 쉰다(뉴욕증권거래소 규칙)."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


@lru_cache(maxsize=32)
def us_market_holidays(year: int) -> frozenset:
    """그해 미국 증시가 **하루 종일 쉬는 날** (2026-08-19 상하님 지시로 넣었다).

    상하님 — "미국 공휴일표 찾아서 넣으면 되지."

    **날짜를 손으로 박지 않고 규칙으로 센다.** 표로 박아 두면 해가 바뀔 때마다
    누군가 고쳐 넣어야 하고, 잊으면 그해부터 조용히 틀린다.

    뉴욕증권거래소·나스닥이 쉬는 날 열 개다 —
      새해 첫날 · 마틴루터킹의 날(1월 셋째 월) · 대통령의 날(2월 셋째 월) ·
      성금요일(부활절 앞 금요일) · 메모리얼데이(5월 마지막 월) ·
      준틴스(6월 19일 · 2022년부터) · 독립기념일(7월 4일) ·
      노동절(9월 첫 월) · 추수감사절(11월 넷째 목) · 성탄절(12월 25일)

    토·일에 걸리는 날은 앞 금요일이나 다음 월요일로 옮겨 쉰다. **다만 새해
    첫날이 토요일이면 앞 금요일(12월 31일)에 쉬지 않는다** — 거래소 규칙이
    그렇다. 그 하루만 예외다.
    """
    days = {
        _nth_weekday(year, 1, 0, 3),      # 마틴루터킹의 날 — 1월 셋째 월요일
        _nth_weekday(year, 2, 0, 3),      # 대통령의 날 — 2월 셋째 월요일
        _easter(year) - timedelta(days=2),          # 성금요일
        _nth_weekday(year, 5, 0, -1),     # 메모리얼데이 — 5월 마지막 월요일
        _nth_weekday(year, 9, 0, 1),      # 노동절 — 9월 첫째 월요일
        _nth_weekday(year, 11, 3, 4),     # 추수감사절 — 11월 넷째 목요일
    }
    for fixed in (date(year, 7, 4), date(year, 12, 25)):
        days.add(_observed(fixed))
    if year >= 2022:                      # 준틴스는 2022년부터 휴장일이다
        days.add(_observed(date(year, 6, 19)))
    # 새해 첫날 — 토요일이면 12월 31일에 안 쉰다(위 설명). 일요일이면 1월 2일.
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:
        days.add(_observed(new_year))
    return frozenset(d for d in days if d.year == year)


@lru_cache(maxsize=32)
def us_half_days(year: int) -> frozenset:
    """그해 미국 증시가 **뉴욕 오후 1시에 일찍 닫는 날**.

    추수감사절 다음 날 · 성탄절 앞날 · 독립기념일 앞날 셋이다. 앞뒤가 주말이거나
    그 자체가 휴장일이면 반휴장도 없다.
    """
    holidays = us_market_holidays(year)
    out = set()
    candidates = (
        _nth_weekday(year, 11, 3, 4) + timedelta(days=1),   # 추수감사절 다음 날
        date(year, 12, 24),
        date(year, 7, 3),
    )
    for day in candidates:
        if day.weekday() < 5 and day not in holidays:
            out.add(day)
    return frozenset(out)


def us_market_is_open(day: date) -> bool:
    """그날 미국 정규장이 열리나. 주말·휴장일이면 False."""
    return day.weekday() < 5 and day not in us_market_holidays(day.year)


# 한국 정규장 마감 — 서울 15시 30분(마감 동시호가 끝). jarvis4_data.market_phase가
# 쓰는 시각과 같다. 한쪽만 고치면 화면과 저장이 서로 다른 말을 한다.
KR_MARKET_CLOSE_HOUR = 15
KR_MARKET_CLOSE_MINUTE = 30


def kr_session_is_over(now: datetime | None = None) -> bool:
    """오늘 한국 정규장이 **이미 끝났나** (2026-08-19 상하님 지시로 넣었다).

    미국과 같은 구멍이 한국에도 있었다 — 화면의 자동 저장이 시간을 안 봐서,
    서울 오전에 화면을 열면 **전날 종가가 오늘 날짜로** 저장됐다.

    **공휴일은 여기서 못 가린다.** 설·추석이 음력이라 규칙으로 셀 수 없고
    이 집에 음력 달력이 없다(미국은 규칙으로 세어 us_market_holidays에 넣었다).
    대신 **코스피 일봉에 오늘 것이 있나**로 가린다 —
    `jarvis4_data.kr_market_traded_today()`가 그 일을 한다. 휴장이면 오늘 봉이
    없으므로 자료 자체가 답을 준다. 달력을 손으로 채우지 않아도 된다.
    """
    stamp = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    if stamp.weekday() >= 5:            # 토·일은 장이 없다
        return False
    return (stamp.hour, stamp.minute) >= (KR_MARKET_CLOSE_HOUR,
                                          KR_MARKET_CLOSE_MINUTE)


def session_is_over(market: str, now: datetime | None = None) -> bool:
    """그 시장의 오늘 정규장이 끝났나. 화면 자동 저장이 이걸 먼저 본다."""
    if str(market).upper() == "US":
        return us_session_is_over(now)
    return kr_session_is_over(now)


def us_session_is_over(now: datetime | None = None) -> bool:
    """오늘 뉴욕 정규장이 **이미 끝났나**. 안 끝났으면 저장하면 안 된다.

    **왜 필요한가 (2026-08-19 상하님 지적).** 화면의 자동 저장은 시간을 아예
    안 봤다. 그래서 한국 오후 5시 반(뉴욕 새벽 4시 반, 장 열리기 전)에 화면을
    열었더니 파일 이름은 그날 뉴욕 날짜인데 **안에 든 값은 전날 마감가**인
    목록이 저장됐다.

    GitHub 자동 저장(.github/workflows/picklist_collect.yml)은 마감 뒤에만
    돌아서 이 문제가 없다. 화면 쪽에만 막이 없었다.

    **주말·공휴일에는 저장하지 않는다.** 휴장일은 us_market_holidays가 규칙으로
    센다(2026-08-19 상하님 지시 — "미국 공휴일표 찾아서 넣으면 되지").

    **반휴장일은 오후 1시가 마감이다** — 추수감사절 다음 날처럼 일찍 닫는 날에
    오후 4시를 기다리면 그날 목록이 통째로 빈다.
    """
    stamp = (now or datetime.now(_SEOUL)).astimezone(_NEW_YORK)
    today = stamp.date()
    if not us_market_is_open(today):    # 토·일·휴장일
        return False
    closing = (US_HALF_DAY_CLOSE_HOUR if today in us_half_days(today.year)
               else US_MARKET_CLOSE_HOUR)
    return stamp.hour >= closing


def archive_path(trade_date: str, market: str, out_dir: Path | str | None = None) -> Path:
    base = Path(out_dir) if out_dir else ARCHIVE_DIR
    return base / f"{trade_date}.{str(market).upper()}.csv"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _restore_types(row: dict) -> dict:
    """CSV는 전부 글자로 읽힌다. 숫자 칸만 숫자로 되돌린다."""
    out = {field: row.get(field, "") for field in FIELDS}
    for field in _NUMBER_FIELDS:
        out[field] = _num(out.get(field))
    for field in FIELDS:
        if field not in _NUMBER_FIELDS:
            out[field] = str(out.get(field) or "")
    return out


def save_rows(rows, *, trade_date: str, market: str,
              out_dir: Path | str | None = None) -> Path | None:
    """한 갈래(또는 여러 갈래)의 줄을 그 날짜 파일에 넣는다.

    **같은 날·같은 갈래는 덮어쓴다.** 장중에 눌러 본 것과 마감 뒤 자동 저장이
    섞이면 마지막(=마감) 것이 남아야 한다. 다른 갈래는 건드리지 않는다.
    빈 목록을 주면 아무것도 하지 않고 None을 준다 — 조회에 실패한 날 멀쩡한
    어제 자료를 빈 파일로 덮는 사고를 막는다.
    """
    rows = [dict(row) for row in (rows or [])]
    if not rows:
        return None
    market = str(market).upper()
    path = archive_path(trade_date, market, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    replacing = {str(row.get("list_kind") or "") for row in rows}
    kept = [
        row for row in _read_csv(path)
        if str(row.get("list_kind") or "") not in replacing
    ]
    merged = kept + rows
    merged.sort(key=lambda row: (
        KIND_ORDER.index(str(row.get("list_kind")))
        if str(row.get("list_kind")) in KIND_ORDER else len(KIND_ORDER),
        _origin_place(row),
        _num(row.get("rank")) or 0,
    ))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in merged:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    return path


def available_dates(market: str | None = None,
                    out_dir: Path | str | None = None) -> list[str]:
    """저장된 날짜를 **새것부터** 준다. 폴더가 없으면 빈 목록."""
    base = Path(out_dir) if out_dir else ARCHIVE_DIR
    if not base.exists():
        return []
    wanted = str(market).upper() if market else None
    dates = set()
    for path in base.glob("*.csv"):
        parts = path.name.split(".")
        if len(parts) != 3:
            continue
        day, tag, _ = parts
        if wanted and tag.upper() != wanted:
            continue
        dates.add(day)
    return sorted(dates, reverse=True)


def load_rows(trade_date: str, market: str,
              out_dir: Path | str | None = None) -> list[dict]:
    """그 날짜·그 시장의 줄 전부. 없으면 빈 목록."""
    rows = [_restore_types(row) for row in _read_csv(archive_path(trade_date, market, out_dir))]
    rows.sort(key=lambda row: (
        KIND_ORDER.index(str(row.get("list_kind")))
        if str(row.get("list_kind")) in KIND_ORDER else len(KIND_ORDER),
        _origin_place(row),
        row.get("rank") or 0,
    ))
    return rows


def saved_kinds(trade_date: str, market: str,
                out_dir: Path | str | None = None) -> set[str]:
    """그날 이미 저장된 갈래 이름들. 하루 한 번만 적으려는 쪽이 물어본다."""
    return {
        str(row.get("list_kind") or "")
        for row in _read_csv(archive_path(trade_date, market, out_dir))
    }


# ──────────────────────────────────────────────────────────────────────────
# 내려받기
# ──────────────────────────────────────────────────────────────────────────

# 화면에서 그때그때 재는 칸. 파일에는 안 들어 있지만 **내려받을 때는 같이 나간다**
# (2026-08-09 상하님 지시) — 엑셀로 받아 놓고 손익을 못 보면 받을 값이 없다.
COMPUTED_FIELDS = ("now_price", "profit_pct", "days_since")


def download_fields(rows) -> tuple:
    """내려받을 칸 목록. 수익률이 계산된 줄이 있으면 그 칸도 붙인다."""
    extras = tuple(
        field for field in COMPUTED_FIELDS
        if any(row.get(field) not in (None, "") for row in rows)
    )
    return FIELDS + extras


def _display_rows(rows) -> list[dict]:
    """엑셀·CSV에 넣을 때는 갈래를 화면에 쓰는 말로 바꿔 적는다."""
    out = []
    for row in rows:
        item = dict(row)
        item["list_kind"] = LIST_KINDS.get(str(row.get("list_kind")), str(row.get("list_kind") or ""))
        out.append(item)
    return out


def to_csv_bytes(rows) -> bytes:
    """엑셀이 바로 여는 CSV. **BOM을 붙인다** — 없으면 한글이 깨져 열린다."""
    fields = download_fields(rows)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in _display_rows(rows):
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def to_excel_bytes(rows):
    """엑셀 파일(.xlsx) 알맹이. openpyxl이 없으면 None — 부르는 쪽이 CSV로 돌린다.

    온라인에 openpyxl이 안 깔린 판이 있어도 화면이 죽으면 안 된다(쿠키 로그인과
    같은 원칙). 그래서 없으면 조용히 None을 주고 CSV 단추만 남긴다.
    """
    try:
        import pandas as pd
    except Exception:
        return None
    try:
        frame = pd.DataFrame(_display_rows(rows), columns=list(download_fields(rows)))
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="목록")
        return buffer.getvalue()
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# 그 뒤로 얼마나 됐나 — 저장된 값은 건드리지 않고 견주기만 한다
# ──────────────────────────────────────────────────────────────────────────

def profit_pct(buy_price, now_price):
    """산 값 대비 지금 값이 몇 %인가. 못 재면 None.

    **저장된 값을 고치지 않는다.** 매수금액은 그날 찍힌 그대로 두고, 지금 값과
    견주기만 한다. 그래야 나중에 다시 봐도 그날 목록이 그대로다.
    0으로 나누는 자리(값이 0이거나 없는 종목)는 None으로 둔다 — 0%로 적으면
    '본전'이라는 뜻이 돼서 안 잰 것과 구별되지 않는다.
    """
    buy, now = _num(buy_price), _num(now_price)
    if buy is None or now is None or buy <= 0:
        return None
    return (now / buy - 1.0) * 100.0


def days_since(trade_date, today=None):
    """매수일에서 며칠이 지났나. 못 세면 None.

    **수익률은 다음 날부터 뜻이 생긴다.** 매수일 당일은 산 값과 지금 값이 같은
    자리라 0%가 나오는데, 그게 '본전'이 아니라 '아직 하루도 안 지났다'는 뜻이다.
    그 둘을 화면에서 가르려고 지난 날수를 같이 센다.
    달력 날수다 — 거래일이 아니다. 주말이 끼면 그만큼 더 세어진다.
    """
    try:
        start = date.fromisoformat(str(trade_date))
    except (TypeError, ValueError):
        return None
    end = today or datetime.now(_SEOUL).date()
    if isinstance(end, datetime):
        end = end.date()
    return (end - start).days


def fetch_buy_opens(market: str, rows) -> dict:
    """줄마다 **다음 거래일 시가**를 찾아 온다. 못 찾으면 목록에서 빠진다.

    설명서의 규칙이 "종가를 확인하고 다음 거래일 시가에 산다"이므로, 실제로 살 수
    있었던 값은 신호일 다음 거래일의 시가다(2026-08-09 상하님 지시).

    **화면(picklist_ui)과 클라우드 수집기(picklist_collector)가 같이 쓴다.**
    2026-08-12까지는 이 함수가 화면 쪽에만 있어서 상하님이 단추를 눌러야만 채워졌고,
    온라인에서 눌러 채운 값은 저장소에 안 올라가 앱이 한 번 쉬면 사라졌다. 그래서
    저장된 232줄 전부 매수금액이 빈칸이었다 — 수익률이 영원히 안 나왔다.
    여기(streamlit을 안 쓰는 창고)로 옮겨 수집기도 부를 수 있게 한다.

    `price_data.get_ohlc_history_for_chart`는 **차트 전용 읽기 함수**다 — 점수 계산과
    무관하고, 조회에 실패하면 예외 대신 None을 준다. (price_data는 고치지 않는다.
    읽기만 한다 — CLAUDE.md 2번.)

    주말·공휴일이 끼면 다음 거래일이 며칠 뒤일 수 있어 2주치를 받아 그중
    **신호일보다 뒤에 있는 첫 거래일**의 시가를 쓴다.
    """
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    import price_data

    wanted = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code or _num(row.get("buy_open")) is not None:
            continue     # 이미 채워진 줄은 다시 찾지 않는다
        wanted[code] = str(row.get("trade_date") or "")
    if not wanted:
        return {}

    def _one(item):
        code, day = item
        try:
            start = date.fromisoformat(day)
        except (TypeError, ValueError):
            return code, None
        try:
            frame = price_data.get_ohlc_history_for_chart(
                code, start.isoformat(), (start + timedelta(days=16)).isoformat())
        except Exception:
            return code, None
        if frame is None or getattr(frame, "empty", True) or "Open" not in frame:
            return code, None
        try:
            for stamp, bar in frame.iterrows():
                if getattr(stamp, "date", lambda: stamp)() > start:
                    value = float(bar["Open"])
                    return code, (value if value == value and value > 0 else None)
        except Exception:
            return code, None
        return code, None      # 아직 다음 거래일이 오지 않았다

    out = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for code, value in pool.map(_one, wanted.items()):
            if value is not None:
                out[code] = value
    return out


def backfill_buy_opens(market: str, *, out_dir=None, days: int = 10) -> dict:
    """지난 며칠치 저장 목록에서 **빈 매수금액을 채운다** (2026-08-12).

    신호가 난 날에는 다음 거래일 시가를 알 수 없어 빈칸으로 저장된다. 그것을
    **다음 날 이후에 누군가 채워 넣어야** 수익률이 나오는데, 그 일을 아무도 하지
    않아 232줄 전부 빈칸이었다. 이제 클라우드 수집기가 새 목록을 찍을 때 함께 돈다.

    **한 번 채워진 값은 다시 안 건드린다** — 과거의 시가는 고정된 사실이다.
    조회에 실패한 날은 그냥 넘어간다. 다음 날 다시 시도한다.

    돌려주는 값: {날짜: 채운 줄 수}
    """
    filled: dict[str, int] = {}
    for trade_date in available_dates(market, out_dir)[: max(0, int(days))]:
        rows = load_rows(trade_date, market, out_dir)
        missing = [row for row in rows if _num(row.get("buy_open")) is None]
        if not missing:
            continue
        try:
            opens = fetch_buy_opens(market, missing)
        except Exception:
            continue          # 하루가 막혀도 나머지 날은 계속한다
        if not opens:
            continue
        merged = set_buy_opens(rows, opens)
        if save_rows(merged, trade_date=trade_date, market=market, out_dir=out_dir):
            filled[trade_date] = sum(
                1 for row in merged if _num(row.get("buy_open")) is not None
            ) - (len(rows) - len(missing))
    return filled


def set_buy_opens(rows, opens) -> list[dict]:
    """다음 거래일 시가를 채워 준다. **이미 채워진 줄은 건드리지 않는다.**

    과거의 시가는 고정된 사실이다. 한 번 적힌 값을 다시 덮으면 자료원이 바뀔 때
    옛 손익률이 조용히 달라진다.
    """
    opens = opens or {}
    out = []
    for row in rows:
        item = dict(row)
        if _num(item.get("buy_open")) is None:
            item["buy_open"] = _num(opens.get(str(row.get("code") or "")))
        out.append(item)
    return out


def with_profit(rows, prices, *, today=None) -> list[dict]:
    """줄마다 '지금 값'·'수익률'·'지난 날수'를 붙여 돌려준다. 원본은 안 바꾼다.

    **무엇을 산 값으로 보나 — 다음 거래일 시가다.** 설명서의 규칙이 "종가를
    확인하고 다음 거래일 시가에 산다"이므로, 신호일 종가가 아니라 그 다음 날
    시가와 견뎌야 실제로 살 수 있었던 값이 된다(2026-08-09 상하님 지시).
    시가를 아직 못 채운 줄은 **수익률을 내지 않는다** — 종가로 대신 재면 반나절
    이른 값이라 실제보다 좋아 보이거나 나빠 보인다.

    prices : {종목코드: 지금 값}. 목록에 없는 종목은 빈칸으로 남는다
             (상장폐지·조회 실패 — 지어내지 않는다).
    """
    prices = prices or {}
    out = []
    for row in rows:
        item = dict(row)
        now = _num(prices.get(str(row.get("code") or "")))
        buy = _num(item.get("buy_open"))
        item["now_price"] = now
        item["profit_pct"] = profit_pct(buy, now)
        item["days_since"] = days_since(row.get("trade_date"), today)
        out.append(item)
    return out


def summarize(rows) -> str:
    """'눌림목 8 · 상승장 20' 처럼 그날 몇 줄이 남았는지 한 줄로."""
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("list_kind") or "")
        counts[key] = counts.get(key, 0) + 1
    parts = [
        f"{LIST_KINDS.get(kind, kind)} {counts[kind]}"
        for kind in KIND_ORDER if kind in counts
    ]
    return " · ".join(parts)


def to_json(rows) -> str:
    """사람이 읽어 보라고 두는 것이 아니라, 시험이 모양을 굳히는 데 쓴다."""
    return json.dumps(list(rows), ensure_ascii=False, sort_keys=True)
