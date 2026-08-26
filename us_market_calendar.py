"""미국 증시가 여는 날·닫는 날·일찍 닫는 날 (2026-08-26 상하님 지시).

상하님 말씀 — "미국장 개장시간 종료시간 썸머타임, 국경일, 개장일 등 다 반영해야한다."

지금까지 앱은 **주말만** 알았다. 국경일에도 장이 도는 줄 알았고, 일찍 닫는 날
(뉴욕 오후 1시)에도 세 시간을 더 장중으로 여겼다. 그 사이에는 '직전 미국장'이
하루 뒤처진 날을 가리켰다.

**날짜 계산만 한다.** 점수·판정·매매 규칙은 이 파일에 없다. 화면에 무엇을 적을지도
정하지 않는다 — 부르는 쪽이 정한다.

**왜 표를 안 받아 오고 직접 계산하나**
휴장일은 규칙이 정해져 있어 해마다 계산할 수 있다. 바깥에서 받아 오면 그 서버가
막히는 날 앱이 날짜를 잃는다. 이 파일은 통신을 하지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo


# 표시 방식이 아니라 **날짜 계산**을 바꾸면 이 숫자를 올린다.
MODULE_REVISION = 2026082601

NEW_YORK = ZoneInfo("America/New_York")

REGULAR_OPEN = dt_time(9, 30)
REGULAR_CLOSE = dt_time(16, 0)
EARLY_CLOSE = dt_time(13, 0)
PREMARKET_OPEN = dt_time(4, 0)
AFTERMARKET_CLOSE = dt_time(20, 0)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """그 달의 n번째 요일. weekday는 월요일이 0."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """그 달의 마지막 요일."""
    day = date(year, month, 28)
    while True:
        nxt = day + timedelta(days=1)
        if nxt.month != month:
            break
        day = nxt
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """부활절(그레고리력). 성금요일을 구하려고 쓴다."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lam = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lam) // 451
    month, day = divmod(h + lam - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _observed(day: date) -> date | None:
    """토요일에 걸리면 그 전 금요일, 일요일이면 다음 월요일에 쉰다.

    설날(1월 1일)만 예외다 — 토요일에 걸려도 전해 12월 31일에는 열려 있다.
    뉴욕증권거래소 규칙이다.
    """
    if day.weekday() == 5:
        if day.month == 1 and day.day == 1:
            return None
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def holidays(year: int) -> dict[date, str]:
    """그 해에 미국 증시가 쉬는 날. 날짜 → 한글 이름."""
    named: list[tuple[date | None, str]] = [
        (_observed(date(year, 1, 1)), "새해 첫날"),
        (_nth_weekday(year, 1, 0, 3), "마틴 루서 킹 데이"),
        (_nth_weekday(year, 2, 0, 3), "대통령의 날"),
        (_easter(year) - timedelta(days=2), "성금요일"),
        (_last_weekday(year, 5, 0), "현충일"),
        (_observed(date(year, 6, 19)) if year >= 2022 else None, "준틴스"),
        (_observed(date(year, 7, 4)), "독립기념일"),
        (_nth_weekday(year, 9, 0, 1), "노동절"),
        (_nth_weekday(year, 11, 3, 4), "추수감사절"),
        (_observed(date(year, 12, 25)), "성탄절"),
    ]
    return {day: name for day, name in named if day is not None}


def early_closes(year: int) -> dict[date, str]:
    """뉴욕 오후 1시에 일찍 닫는 날. 날짜 → 한글 이름."""
    closed = holidays(year)
    found: dict[date, str] = {}
    for day, name in (
        (date(year, 7, 3), "독립기념일 전날"),
        (_nth_weekday(year, 11, 3, 4) + timedelta(days=1), "추수감사절 다음날"),
        (date(year, 12, 24), "성탄절 전날"),
    ):
        if day.weekday() < 5 and day not in closed:
            found[day] = name
    return found


def holiday_name(day: date) -> str:
    """그날이 휴장일이면 이름, 아니면 빈 글자."""
    return holidays(day.year).get(day, "")


def early_close_name(day: date) -> str:
    """그날이 일찍 닫는 날이면 이름, 아니면 빈 글자."""
    return early_closes(day.year).get(day, "")


def is_trading_day(day: date) -> bool:
    """그날 미국 정규장이 열리나. 주말과 국경일이면 안 열린다."""
    return day.weekday() < 5 and not holiday_name(day)


def close_time(day: date) -> dt_time:
    """그날의 정규장 마감 시각. 일찍 닫는 날은 뉴욕 오후 1시다."""
    return EARLY_CLOSE if early_close_name(day) else REGULAR_CLOSE


def previous_trading_day(day: date) -> date:
    """그날보다 **앞선** 마지막 거래일."""
    found = day - timedelta(days=1)
    while not is_trading_day(found):
        found -= timedelta(days=1)
    return found


def next_trading_day(day: date) -> date:
    """그날보다 **뒤인** 첫 거래일."""
    found = day + timedelta(days=1)
    while not is_trading_day(found):
        found += timedelta(days=1)
    return found


def session_closed(now: datetime | None = None) -> bool:
    """지금 보는 미국장이 **끝난 장**인가.

    거래일이 아니면 언제나 참이다 — 열리지도 않은 장을 '돌고 있다'고 하면 안 된다.
    일찍 닫는 날에는 뉴욕 오후 1시에 이미 끝난 것이다.
    """
    now_ny = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    day = now_ny.date()
    if not is_trading_day(day):
        return True
    return now_ny.time() >= close_time(day)


def current_session_date(now: datetime | None = None) -> date:
    """지금 **다가오거나 돌고 있는** 장의 날짜 = 화면의 '당일'.

    상하님 지시(2026-08-26) — "당일은 장 시작 전이라도 떠야 하고, 장이 끝나면
    바로 다음 장으로 넘어가야 한다." 그래서 마감을 지나면 곧바로 다음 거래일이 된다.
    금요일 마감 뒤에는 월요일이 되고, 월요일이 국경일이면 화요일이 된다.
    """
    now_ny = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    day = now_ny.date()
    if is_trading_day(day) and now_ny.time() < close_time(day):
        return day
    return next_trading_day(day)


def previous_session_date(now: datetime | None = None) -> date:
    """마지막으로 **끝난** 장의 날짜 = 화면의 '전일'.

    마감 시각에 곧바로 그날로 넘어간다(상하님 — "전일은 장종료시점에 그걸 바로
    반영해야 되고").
    """
    return previous_trading_day(current_session_date(now))


def phase(now: datetime | None = None) -> dict:
    """지금이 미국장의 어느 대목인가. 날짜와 휴장 사유를 함께 준다.

    label 은 예전 이름을 그대로 쓴다 — 이미 화면 여러 곳이 이 글자를 보고 있다.
    """
    now_ny = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    day = now_ny.date()
    name = holiday_name(day)
    if day.weekday() >= 5:
        label = "주말 휴장"
    elif name:
        label = "휴장"
    elif now_ny.time() < PREMARKET_OPEN:
        label = "정규장 전"
    elif now_ny.time() < REGULAR_OPEN:
        label = "프리마켓"
    elif now_ny.time() < close_time(day):
        label = "정규장 시간"
    elif now_ny.time() < AFTERMARKET_CLOSE:
        label = "애프터마켓"
    else:
        label = "장 마감"
    return {
        "label": label,
        "new_york_time": now_ny.isoformat(timespec="seconds"),
        "holiday": name,
        "early_close": early_close_name(day),
        "trading_day": is_trading_day(day),
        "session_date": current_session_date(now_ny).isoformat(),
        "previous_session_date": previous_session_date(now_ny).isoformat(),
        "close_time": close_time(day).strftime("%H:%M"),
    }
