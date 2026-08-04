"""한국장 장중 기관 수급 반전 포착 엔진 (순수 판정 로직).

이 모듈은 네트워크 호출도 Streamlit 의존도 없다. KIS/가격 조회 결과를 받아
신호별 판정과 최종 판정만 계산한다. 그래야 테스트에서 외부 연결 없이 검증된다.

핵심 원칙 (사용자 지시 2026-07-20):
- 확인되지 않은 값을 만들어내지 않는다. 없으면 UNKNOWN이다.
- UNKNOWN을 FALSE나 0으로 바꾸지 않는다.
- 외국인 KOSPI200 선물 순매수는 KIS 공개 조회 API가 확인되지 않았다. 직접값이
  없을 때 시장베이시스를 쓰되, 그것이 "대체신호"임을 판정 단계에서 구분한다.
- 비차익 15분 유입은 누적값이 아니라 스냅숏 간 증분으로 판정한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 상태값·시점·세기·신선도는 미국장 엔진과 공유한다. 판정 기준은 공유하지 않는다.
from market_signal_common import (  # noqa: F401  (기존 호출부 호환용 재수출)
    FRESHNESS_DELAYED_SECONDS,
    FRESHNESS_OK_SECONDS,
    STATUS_COLOR,
    STATUS_MARK,
    STRENGTH_LABEL,
    TIMING_LABEL,
    MarketCode,
    MarketSignal,
    SignalStatus,
    SignalStrength,
    SignalTiming,
    counted_signals,
    data_status_text,
    flow_reading,
    freshness_label,
    is_stale,
)

# 한국장 엔진은 신호 타입 이름을 FlowSignal로 써왔다. 공통 타입의 별칭으로 둔다.
FlowSignal = MarketSignal

# ---------------------------------------------------------------------------
# 임계치 상수 — 화면 문구가 아니라 여기만 고치면 판정이 바뀐다.
# ---------------------------------------------------------------------------
LOW_RECOVERY_POSITIVE_PCT = 0.8
LOW_RECOVERY_NEUTRAL_PCT = 0.3

# 비차익 15분 연속 유입 판정에 필요한 최소 조건
NON_ARBITRAGE_MIN_DELTAS = 3
NON_ARBITRAGE_MIN_SPAN_SECONDS = 15 * 60


# 늦은 신호 기준 시각
LATE_SIGNAL_HOUR = 13

# 한국 정규장. '자료가 오래됐다'는 판정은 장중에만 뜻이 있다 — 장이 끝난 뒤의
# 15:30 종가는 늦은 값이 아니라 그날의 최종값이다(2026-07-29: 16시에 화면이
# '데이터 부족'으로 바뀌어 사용자가 지적했다. 신선도를 자료 시각으로 재게
# 고치면서 삼성전자·SK하이닉스 종가가 '30분 지남'으로 잡힌 탓이다).
SESSION_OPEN_HOUR_MINUTE = (9, 0)
SESSION_CLOSE_HOUR_MINUTE = (15, 30)


def is_session_open(moment: datetime | None) -> bool:
    """그 시각이 한국 정규장 안인가. 휴장일까지는 보지 않는다."""
    if moment is None:
        return False
    if moment.weekday() >= 5:
        return False
    minutes = moment.hour * 60 + moment.minute
    start = SESSION_OPEN_HOUR_MINUTE[0] * 60 + SESSION_OPEN_HOUR_MINUTE[1]
    end = SESSION_CLOSE_HOUR_MINUTE[0] * 60 + SESSION_CLOSE_HOUR_MINUTE[1]
    return start <= minutes <= end



class ReboundVerdict(str, Enum):
    VERY_BAD = "very_bad"
    CONFIRMED = "confirmed"
    PROXY_CONFIRMED = "proxy_confirmed"
    WATCHING = "watching"
    NOT_CONFIRMED = "not_confirmed"
    INSUFFICIENT_DATA = "insufficient_data"


# 계기판 단계명은 한국장·미국장이 같은 쉬운 말로 쓴다. 세부 근거는 headline에 남긴다.
VERDICT_LABEL = {
    ReboundVerdict.VERY_BAD: "● 매우 나쁨",
    ReboundVerdict.NOT_CONFIRMED: "● 나쁨",
    ReboundVerdict.WATCHING: "● 엇갈림",
    ReboundVerdict.PROXY_CONFIRMED: "● 좋음",
    ReboundVerdict.CONFIRMED: "● 매우 좋음",
    ReboundVerdict.INSUFFICIENT_DATA: "● 데이터 부족",
}




@dataclass
class ForeignFuturesFlowSnapshot:
    """외국인 KOSPI200 선물 순매수. 자동 조회처가 없어 수동 입력 또는 미연결이다."""

    net_contracts: int | None = None
    previous_net_contracts: int | None = None
    change: int | None = None
    as_of: datetime | None = None
    source: str = "미연결"
    confidence: str = "none"
    available: bool = False


@dataclass
class FlowEngineResult:
    verdict: ReboundVerdict
    verdict_label: str
    headline: str
    signals: list[FlowSignal] = field(default_factory=list)
    core_signals: list[FlowSignal] = field(default_factory=list)
    supporting_reasons: list[str] = field(default_factory=list)
    missing_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_status: str = ""
    flow_note: str = ""  # 무엇이 앞서고 무엇이 뒤따르는지 — 흐름 판독 한 줄
    # 이 판정을 만든 시각이 장중이었나. 장이 끝난 뒤에는 '오래된 자료'라는 말이
    # 성립하지 않으므로 화면과 판정이 둘 다 이 값을 본다.
    session_open: bool = True

    def signal(self, key: str) -> FlowSignal | None:
        return next((s for s in self.signals if s.key == key), None)


# ---------------------------------------------------------------------------
# 숫자 파싱
# ---------------------------------------------------------------------------
def parse_kis_number(value: object) -> float | None:
    """KIS 응답의 숫자 문자열을 float으로 바꾼다.

    빈 문자열/None/"-"는 0이 아니라 None이다. 0으로 만들면 "수급 없음"이
    "수급 0원"으로 둔갑해 판정이 오염된다.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number and number not in (float("inf"), float("-inf")) else None

    text = str(value).strip().replace(",", "").replace(" ", "")
    if text in ("", "-", "--", "None", "null", "N/A"):
        return None
    if text.startswith("+"):
        text = text[1:]
    try:
        number = float(text)
    except ValueError:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def normalize_sector_name(name: str) -> str:
    return (
        str(name or "")
        .replace("·", "")
        .replace("/", "")
        .replace(" ", "")
        .lower()
    )


ELECTRONICS_SECTOR_ALIASES = {
    normalize_sector_name(n) for n in ("전기전자", "전기·전자", "전기/전자")
}


def find_electronics_sector_code(rows) -> str | None:
    """업종 목록에서 전기전자 업종코드를 이름으로 찾는다. 못 찾으면 None."""
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if normalize_sector_name(row.get("hts_kor_isnm")) in ELECTRONICS_SECTOR_ALIASES:
            code = str(row.get("bstp_cls_code") or "").strip()
            if code:
                return code
    return None


# ---------------------------------------------------------------------------
# 신선도
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 증분 계산 (누적값 → 구간 순증)
# ---------------------------------------------------------------------------
def _deltas(series):
    """[(datetime, 누적값)] → [(구간종료시각, 증분)]. None 값은 구간을 끊는다."""
    points = [
        (ts, val)
        for ts, val in (series or [])
        if ts is not None and val is not None
    ]
    points.sort(key=lambda p: p[0])
    return [
        (points[i][0], points[i][1] - points[i - 1][1])
        for i in range(1, len(points))
    ]


# 판정을 '직전 1분 대비'로 내리면 자료가 조금만 출렁여도 매분 뒤집힌다.
# 2026-07-29 실측: 38구간 중 외국인 선물 17번·기관계 18번 뒤집혔다. 게다가
# 네이버가 아직 새 줄을 안 올린 분에는 증분이 정확히 0으로 잡혀 '유입 둔화'로
# 오판했다(기관계 20회). 시장이 멈춘 게 아니라 자료가 안 바뀐 것뿐이다.
# 그래서 한 구간이 아니라 최근 몇 분을 통째로 본다.
TREND_WINDOW_SECONDS = 5 * 60


def _recent_change(series, *, window_seconds=TREND_WINDOW_SECONDS):
    """최근 window 동안의 순변화. 1분 노이즈로 판정이 뒤집히지 않게 한다.

    창 안에 현재 점밖에 없으면(오래 쉬었다 다시 켠 경우) 바로 직전 점과 비교한다.
    비교할 점이 아예 없으면 None — 방향을 모른다는 뜻이며 0으로 바꾸지 않는다.
    """
    points = sorted(
        (ts, val) for ts, val in (series or []) if ts is not None and val is not None
    )
    if len(points) < 2:
        return None
    latest_ts, latest_val = points[-1]
    within = [
        p for p in points[:-1]
        if (latest_ts - p[0]).total_seconds() <= window_seconds
    ]
    base = within[0] if within else points[-2]
    return latest_val - base[1]


def _pick_freshness(measured, fallback):
    """자료 시각으로 잰 값이 있으면 그것을 쓰고, 없을 때만 조회 시각으로 내려간다.

    0초도 유효한 값이므로 `or`로 고르면 안 된다.
    """
    return fallback if measured is None else measured


def _span_seconds(series) -> float | None:
    points = [ts for ts, val in (series or []) if ts is not None and val is not None]
    if len(points) < 2:
        return None
    points.sort()
    return (points[-1] - points[0]).total_seconds()


# ---------------------------------------------------------------------------
# 개별 신호 판정
# ---------------------------------------------------------------------------
def evaluate_program_total(current_net, history, *, as_of=None, freshness=None) -> FlowSignal:
    """전체 프로그램 순매수 방향."""
    sig = FlowSignal(
        key="program_total",
        label="전체 프로그램",
        status=SignalStatus.UNKNOWN,
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=SignalTiming.CONFIRMING,
    )
    if current_net is None:
        sig.reason = "프로그램 순매수 확인 필요"
        return sig

    sig.value = current_net
    sig.display_value = _fmt_amount(current_net)
    deltas = [d for _, d in _deltas(history)]

    if not deltas:
        # 값 하나뿐이면 방향을 말할 수 없다. "15분 증가"라고 쓰지 않는다.
        sig.status = SignalStatus.POSITIVE if current_net > 0 else SignalStatus.NEUTRAL
        sig.reason = (
            "프로그램 순매수 상태 (방향 변화는 스냅숏 부족으로 미확인)"
            if current_net > 0
            else "프로그램 순매도 상태 (방향 변화는 스냅숏 부족으로 미확인)"
        )
        if current_net <= 0:
            sig.status = SignalStatus.NEUTRAL
        return sig

    # 방향은 최근 몇 분의 순변화로 본다. 한 구간만 보면 매분 뒤집힌다.
    last = _recent_change(history)
    if last is None:
        last = deltas[-1]
    recent = deltas[-3:]

    if current_net > 0 and last > 0:
        sig.status = SignalStatus.POSITIVE
        sig.reason = "프로그램 순매수이며 최근 구간에서 유입 증가"
    elif current_net > 0 and last <= 0:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "프로그램 순매수이나 최근 유입은 둔화"
    elif current_net <= 0 and len(recent) >= 2 and all(d > 0 for d in recent[-2:]):
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "아직 순매도이나 매도 규모가 계속 축소"
    elif last < 0:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = "프로그램 순매도 규모 확대"
    else:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "프로그램 방향 혼조"
    return sig


def evaluate_non_arbitrage(history, *, current_net=None, as_of=None, freshness=None) -> FlowSignal:
    """비차익 프로그램 15분 연속 유입. 누적값이 아니라 증분 3개로 본다."""
    sig = FlowSignal(
        key="non_arbitrage",
        label="비차익 프로그램",
        status=SignalStatus.UNKNOWN,
        value=current_net,
        display_value=_fmt_amount(current_net),
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=SignalTiming.LEADING,
    )
    deltas = _deltas(history)
    span = _span_seconds(history)

    if not deltas:
        sig.reason = "15분 연속 유입 확인에 필요한 스냅숏 부족"
        return sig

    recent = deltas[-NON_ARBITRAGE_MIN_DELTAS:]
    all_positive = all(d > 0 for _, d in recent)
    enough = (
        len(recent) >= NON_ARBITRAGE_MIN_DELTAS
        and span is not None
        and span >= NON_ARBITRAGE_MIN_SPAN_SECONDS
    )

    if all_positive and enough:
        sig.status = SignalStatus.POSITIVE
        sig.reason = "비차익 프로그램 최근 15분 순매수 연속 유입"
    elif all_positive:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "비차익 유입 중이나 15분 지속은 아직 미충족"
    elif deltas[-1][1] < 0:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = "비차익 프로그램 순매도 확대"
    else:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "비차익 프로그램 방향 혼조"
    return sig


def evaluate_arbitrage(history, basis_signal, *, current_net=None, as_of=None, freshness=None) -> FlowSignal:
    """차익 프로그램. 베이시스가 같이 개선돼야 의미를 준다."""
    sig = FlowSignal(
        key="arbitrage",
        label="차익 프로그램",
        status=SignalStatus.UNKNOWN,
        value=current_net,
        display_value=_fmt_amount(current_net),
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=SignalTiming.CONFIRMING,
    )
    deltas = _deltas(history)
    if not deltas:
        sig.reason = "차익 프로그램 증분 확인 필요"
        return sig

    last = deltas[-1][1]
    basis_ok = basis_signal is not None and basis_signal.status is SignalStatus.POSITIVE

    if last > 0 and basis_ok:
        sig.status = SignalStatus.POSITIVE
        sig.reason = "차익 순매수 유입 + 시장베이시스 개선"
    elif last > 0:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "차익 순매수이나 베이시스 개선은 미확인 (헤지성 가능)"
    elif last < 0:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = "차익 프로그램 순매도"
    else:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "차익 프로그램 변화 없음"
    return sig


def evaluate_basis(history, *, current_basis=None, as_of=None, freshness=None) -> FlowSignal:
    """KOSPI200 시장베이시스 개선 여부. 외국인 선물 직접값의 대체신호다."""
    sig = FlowSignal(
        key="market_basis",
        label="시장베이시스",
        status=SignalStatus.UNKNOWN,
        value=current_basis,
        display_value=_fmt_number(current_basis),
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        strength=SignalStrength.PROXY,
        timing=SignalTiming.LEADING,
    )
    points = [v for _, v in sorted(
        [(ts, v) for ts, v in (history or []) if ts is not None and v is not None]
    )]
    if len(points) < 2:
        sig.reason = "베이시스 변화 확인에 필요한 스냅숏 부족 — 외국인 선물 대신 보는 지표"
        return sig

    recent = points[-4:]
    improving = all(recent[i] > recent[i - 1] for i in range(1, len(recent)))
    worsening = all(recent[i] < recent[i - 1] for i in range(1, len(recent)))

    if improving and points[-2] < 0 <= points[-1]:
        sig.status = SignalStatus.POSITIVE
        sig.reason = "시장베이시스 음수 → 0 이상 전환 (백워데이션 해소)"
    elif improving:
        sig.status = SignalStatus.POSITIVE
        sig.reason = "시장베이시스 연속 개선"
    elif worsening:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = "시장베이시스 연속 악화"
    else:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = "시장베이시스 방향 혼조"
    # 출처 칸에는 '증권사'라고만 나오므로, 이것이 원래 보려던 값이 아니라는 사실은
    # 설명 칸에 적어야 전달된다(2026-07-29).
    sig.reason = f"{sig.reason} — 외국인 선물 대신 보는 지표"
    return sig


# 외국인 선물 자료가 '직접값'인 경우는 HTS 원본을 사람이 옮겨 적었을 때뿐이다.
# 네이버 파생 투자자동향은 공개된 지연치라 대체 신호다 (2026-07-29 사용자 지적:
# 신선도가 '확인 필요'인데 신호세기만 초록 '직접'으로 떠서 원본 자료처럼 보였다).
_FOREIGN_FUTURES_DIRECT_CONFIDENCE = ("manual",)


def evaluate_foreign_futures(snapshot: ForeignFuturesFlowSnapshot | None) -> FlowSignal:
    """외국인 KOSPI200 선물 순매수. 없으면 UNKNOWN이고 0으로 만들지 않는다.

    '전환'은 직전 값이 0 이하였다가 플러스로 넘어온 것을 실제로 확인했을 때만 쓴다.
    당일 누적이 플러스라는 것만으로 전환이라 적으면, 아침부터 계속 순매수였고 지금은
    오히려 줄어드는 중에도 "방금 돌아섰다"로 읽힌다 (2026-07-29 사용자 지적).
    """
    sig = FlowSignal(
        key="foreign_futures",
        label="외국인 선물 직접수급",
        status=SignalStatus.UNKNOWN,
        source="미연결",
        strength=SignalStrength.DIRECT,
        timing=SignalTiming.LEADING,
    )
    if snapshot is None or not snapshot.available or snapshot.net_contracts is None:
        sig.reason = "외국인 선물 수급 확인 필요 (네이버 자동 조회 실패 — HTS 수동 입력 가능)"
        sig.display_value = "못 읽음"
        return sig

    current = snapshot.net_contracts
    sig.value = current
    sig.display_value = f"{current:+,}계약"
    sig.source = snapshot.source
    sig.as_of = snapshot.as_of
    is_direct = snapshot.confidence in _FOREIGN_FUTURES_DIRECT_CONFIDENCE
    sig.strength = SignalStrength.DIRECT if is_direct else SignalStrength.PROXY

    previous = snapshot.previous_net_contracts
    change = snapshot.change
    if change is None and previous is not None:
        change = current - previous

    if change is None:
        # 직전 값이 없으면 방향이 바뀌었는지 말할 수 없다. 누적 부호만 밝힌다.
        sig.status = SignalStatus.POSITIVE if current > 0 else SignalStatus.NEUTRAL
        state = "순매수" if current > 0 else "순매도"
        sig.reason = f"외국인 선물 당일 누적 {state} (방향 변화는 스냅숏 부족으로 미확인)"
    elif change > 0:
        sig.status = SignalStatus.POSITIVE
        if previous is not None and previous <= 0 < current:
            sig.reason = "외국인 선물 순매도 → 순매수 전환"
        elif current > 0:
            sig.reason = "외국인 선물 순매수 확대"
        else:
            sig.reason = "외국인 선물 순매도 규모 감소"
    elif change < 0:
        if current > 0:
            sig.status = SignalStatus.NEUTRAL
            sig.reason = "외국인 선물 누적 순매수이나 최근 구간은 매수 감소"
        else:
            sig.status = SignalStatus.NEGATIVE
            sig.reason = "외국인 선물 순매도 확대"
    else:
        sig.status = SignalStatus.NEUTRAL
        state = "순매수" if current > 0 else "순매도"
        sig.reason = f"외국인 선물 당일 누적 {state} (최근 구간 변화 없음)"

    if not is_direct:
        # '대신'이라고만 적어두면 무엇을 무엇으로 바꾼 것인지 알 수 없다.
        sig.reason = f"{sig.reason} — 증권사 원본 대신 네이버 공개치"
    return sig


def evaluate_stock_rebound(
    key, label, quote, *, recent_lows=None, as_of=None, freshness=None
) -> FlowSignal:
    """삼성전자/SK하이닉스 시가·저점 회복 판정.

    quote: {"current":..., "open":..., "low":...}
    recent_lows: 최근 1분봉 저가 리스트(오래된 것 → 최신). 저점 재갱신 확인용.
    """
    sig = FlowSignal(
        key=key,
        label=label,
        status=SignalStatus.UNKNOWN,
        source="가격 스냅샷",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=SignalTiming.LEADING,
    )
    quote = quote or {}
    current = quote.get("current")
    open_price = quote.get("open")
    day_low = quote.get("low")

    if current is None or open_price is None or day_low is None or day_low <= 0:
        sig.reason = f"{label} 가격 확인 필요"
        return sig

    sig.value = current
    low_recovery_pct = (current - day_low) / day_low * 100
    # 전일 대비를 **앞에** 적는다. 저점 대비만 적으면 폭락일에도 늘 플러스라
    # 오른 것처럼 읽힌다 (2026-07-29: 코스피 -5.7%인 날 삼성전자가
    # '209,500 (저점대비 +1.21%)'로 떠서 네이버의 '-5.00%'와 어긋나 보였다).
    prev_close = quote.get("prev_close")
    if prev_close:
        change_pct = (current - prev_close) / prev_close * 100
        sig.display_value = (f"{current:,.0f} ({change_pct:+.2f}% · "
                             f"저점대비 +{low_recovery_pct:.2f}%)")
    else:
        sig.display_value = f"{current:,.0f} (저점대비 +{low_recovery_pct:.2f}%)"

    # 최근 구간에서 저점을 다시 깬 경우가 최우선 부정 조건이다.
    lows = [v for v in (recent_lows or []) if v is not None]
    made_new_low = False
    if len(lows) >= 2:
        # 저점이 그대로면 재갱신이 아니다. 반드시 이전 최저를 "깨야" 한다.
        made_new_low = lows[-1] < min(lows[:-1])

    if made_new_low:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = f"{label} 최근 저점 재갱신"
        return sig

    if current >= open_price:
        sig.status = SignalStatus.POSITIVE
        sig.reason = f"{label} 시가 회복"
    elif low_recovery_pct >= LOW_RECOVERY_POSITIVE_PCT:
        # 갭하락한 날 저점에서만 튄 것을 '돌아섰다'로 부르면 안 된다 —
        # 시가 아래에 있으면 아직 그날 흐름을 되돌린 것이 아니다(2026-07-24 사용자 지적:
        # 삼성전자·SK하이닉스가 갭하락 중인데 '반도체는 돌아섰다'로 나왔다).
        sig.status = SignalStatus.NEUTRAL
        sig.reason = f"{label} 저점에서만 반등 (아직 시가 아래 · 저점 대비 +{low_recovery_pct:.1f}%)"
    elif low_recovery_pct >= LOW_RECOVERY_NEUTRAL_PCT:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = f"{label} 저점 대비 소폭 회복 ({low_recovery_pct:.1f}%)"
    else:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = f"{label} 저점권에서 회복 미흡"
    return sig


def evaluate_investor(key, label, current_net, history, *, as_of=None, freshness=None, timing=SignalTiming.CONFIRMING) -> FlowSignal:
    """투자주체별 순매수(외국인/기관계/금융투자/투신/사모/기금 등) 공통 판정."""
    sig = FlowSignal(
        key=key,
        label=label,
        status=SignalStatus.UNKNOWN,
        value=current_net,
        display_value=_fmt_amount(current_net),
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=timing,
    )
    if current_net is None:
        sig.reason = f"{label} 수급 확인 필요"
        return sig

    # 직전 한 구간이 아니라 최근 몇 분의 순변화로 본다(위 _recent_change 설명 참고).
    last = _recent_change(history)

    if current_net > 0 and (last is None or last > 0):
        sig.status = SignalStatus.POSITIVE
        sig.reason = f"{label} 순매수" + (" 증가" if last else "")
    elif current_net > 0:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = f"{label} 순매수이나 유입 둔화"
    elif last is not None and last > 0:
        sig.status = SignalStatus.NEUTRAL
        sig.reason = f"{label} 순매도이나 매도 규모 축소"
    elif last is not None and last < 0:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = f"{label} 순매도 확대"
    else:
        sig.status = SignalStatus.NEGATIVE
        sig.reason = f"{label} 순매도"
    return sig


# ---------------------------------------------------------------------------
# 가짜 반등
# ---------------------------------------------------------------------------
def detect_fake_rebound(signals_by_key, *, extras=None) -> list[str]:
    """가짜 반등 경고 문구 목록. 조건이 실제로 확인될 때만 경고한다."""
    extras = extras or {}
    warnings = []

    samsung = signals_by_key.get("samsung")
    hynix = signals_by_key.get("hynix")
    program = signals_by_key.get("program_total")
    basis = signals_by_key.get("market_basis")
    personal = signals_by_key.get("personal")
    foreign_cash = signals_by_key.get("foreign_cash")
    institution = signals_by_key.get("institution")

    # 유형 1 — 삼성만 반등, 하이닉스 하락, 프로그램 매도
    if (
        samsung is not None and samsung.is_positive
        and hynix is not None and hynix.is_negative
        and program is not None and program.is_negative
    ):
        warnings.append("삼성전자만 반등하고 SK하이닉스·프로그램은 반대입니다 — 반도체 동시 반등이 아닙니다.")

    # 유형 2 — 가격은 올랐는데 거래대금이 줄었을 때만 "거래량 없는 반등"이라 쓴다
    turnover_down = extras.get("semis_turnover_declining")
    if (
        turnover_down is True
        and samsung is not None and samsung.is_positive
        and hynix is not None and hynix.is_positive
    ):
        warnings.append("두 종목 가격은 올랐으나 거래대금이 줄었습니다 — 거래량 없는 반등입니다.")

    # 유형 3 — 개인만 사고 기관·외국인 동시 매도
    if (
        personal is not None and personal.is_positive
        and institution is not None and institution.is_negative
        and foreign_cash is not None and foreign_cash.is_negative
    ):
        warnings.append("개인 순매수 확대에 기관·외국인 동시 순매도입니다 — 개인 주도 반등입니다.")

    # 유형 4 — 지수는 반등인데 프로그램·베이시스는 악화
    if (
        extras.get("index_rebounding") is True
        and program is not None and program.is_negative
        and basis is not None and basis.is_negative
    ):
        warnings.append("지수 반등에도 프로그램 순매도·베이시스 악화입니다 — 기술적 반등 가능성.")

    # 금융투자 단독 매수
    securities = signals_by_key.get("securities")
    others = [signals_by_key.get(k) for k in ("investment_trust", "private_fund", "fund")]
    negative_others = [s for s in others if s is not None and s.is_negative]
    if securities is not None and securities.is_positive and len(negative_others) >= 2:
        warnings.append("⚠ 금융투자 단독 매수 — 차익·헤지성 가능")

    return warnings


# ---------------------------------------------------------------------------
# 최종 판정
# ---------------------------------------------------------------------------
CORE_KEYS = ("foreign_futures", "non_arbitrage", "samsung", "hynix")


def decide_verdict(signals: list[FlowSignal], *, extras=None) -> FlowEngineResult:
    """판정 하나를 만든다. 장중이었는지는 결과에 실어 화면도 같이 보게 한다."""
    extras = extras or {}
    result = _decide_verdict(signals, extras=extras)
    result.session_open = bool(extras.get("session_open", True))
    return result


def _decide_verdict(signals: list[FlowSignal], *, extras) -> FlowEngineResult:
    by_key = {s.key: s for s in signals}

    foreign_futures = by_key.get("foreign_futures")
    non_arb = by_key.get("non_arbitrage")
    samsung = by_key.get("samsung")
    hynix = by_key.get("hynix")
    basis = by_key.get("market_basis")
    institution = by_key.get("institution")
    securities = by_key.get("securities")
    program = by_key.get("program_total")

    core = [by_key.get(k) for k in CORE_KEYS]
    core = [s for s in core if s is not None]

    warnings = detect_fake_rebound(by_key, extras=extras)

    # --- 데이터 부족 우선 판정 -------------------------------------------------
    core_unknown = sum(1 for s in core if s.is_unknown)
    # 장이 끝난 뒤에는 오래됨을 따지지 않는다. 종가는 늦은 값이 아니라 최종값이다.
    session_open = extras.get("session_open", True)
    stale = [s for s in core if is_stale(s)] if session_open else []
    if not core or core_unknown >= max(1, len(CORE_KEYS) // 2 + 1) or len(stale) >= 2:
        return _build_result(
            ReboundVerdict.INSUFFICIENT_DATA,
            signals,
            core,
            warnings,
            headline="핵심 수급 데이터가 부족해 지금은 판단하지 않습니다.",
        )

    both_semis_up = (
        samsung is not None and samsung.is_positive
        and hynix is not None and hynix.is_positive
    )

    # --- 1. 외국인·기관 반등 확인 (직접값 4개 전부) --------------------------------
    if (
        foreign_futures is not None and foreign_futures.is_positive and foreign_futures.is_direct
        and non_arb is not None and non_arb.is_positive
        and both_semis_up
    ):
        return _build_result(
            ReboundVerdict.CONFIRMED,
            signals,
            core,
            warnings,
            headline="외국인 선물·비차익·반도체 동시 반등이 모두 확인돼 외국인·기관 반등이 진행 중입니다.",
        )

    # --- 2. 외국인·기관 반등 유력 (베이시스 대체판정) ------------------------------
    institution_improving = any(
        s is not None and s.is_positive for s in (institution, securities)
    )
    if (
        (foreign_futures is None or foreign_futures.is_unknown)
        and non_arb is not None and non_arb.is_positive
        and both_semis_up
        and basis is not None and basis.is_positive
        and institution_improving
    ):
        return _build_result(
            ReboundVerdict.PROXY_CONFIRMED,
            signals,
            core,
            warnings,
            headline=(
                "비차익 프로그램, 시장베이시스, 반도체 동시 반등이 확인돼 외국인·기관 반등 "
                "가능성이 높습니다. 외국인 선물 직접 수급은 미확인이라 대체판정입니다."
            ),
        )

    # --- 1. 매우 나쁨 (명백한 부정 조건 우선) ---------------------------------
    hard_negative = any(
        s is not None and s.is_negative
        for s in (non_arb, basis, program)
    ) or (
        samsung is not None and samsung.is_negative
        and hynix is not None and hynix.is_negative
    )

    positives = sum(1 for s in core if s.is_positive)

    if hard_negative and positives <= 1:
        return _build_result(
            ReboundVerdict.VERY_BAD,
            signals,
            core,
            warnings,
            headline="프로그램·베이시스·반도체 어느 쪽도 아직 방향을 돌리지 않았습니다.",
        )

    # --- 3. 엇갈림 ------------------------------------------------------------
    if positives >= 2:
        return _build_result(
            ReboundVerdict.WATCHING,
            signals,
            core,
            warnings,
            headline=_watching_headline(non_arb, both_semis_up, samsung, hynix),
        )

    return _build_result(
        ReboundVerdict.NOT_CONFIRMED,
        signals,
        core,
        warnings,
        headline="기관 수급 반전 신호가 아직 나타나지 않았습니다.",
    )


def _watching_headline(non_arb, both_semis_up, samsung, hynix) -> str:
    if non_arb is not None and non_arb.is_positive and not both_semis_up:
        lagging = []
        if samsung is not None and not samsung.is_positive:
            lagging.append("삼성전자")
        if hynix is not None and not hynix.is_positive:
            lagging.append("SK하이닉스")
        if lagging:
            return f"비차익 매수는 들어오지만 {'·'.join(lagging)} 회복이 아직 없습니다."
    if both_semis_up:
        # '돌아섰다'는 시가를 되찾은 경우에만 쓴다(저점에서만 튄 날과 구분).
        return "반도체가 장중 시가를 되찾았지만 프로그램 수급 지속은 아직 확인되지 않았습니다."
    return "일부 신호만 돌아선 상태입니다. 추가 확인이 필요합니다."


def _build_result(verdict, signals, core, warnings, *, headline) -> FlowEngineResult:
    # 목록에서도 하위 내역은 뺀다. '기관계 순매수 / 금융투자 순매수 / 투신 순매수'가
    # 나란히 서면 서로 다른 세 근거처럼 읽히지만 같은 돈이다(2026-07-29).
    listed = counted_signals(signals)
    supporting = [s.reason for s in listed if s.is_positive][:4]
    missing = [s.reason for s in listed if s.is_negative or s.is_unknown][:4]

    return FlowEngineResult(
        verdict=verdict,
        verdict_label=VERDICT_LABEL[verdict],
        headline=headline,
        signals=signals,
        core_signals=core,
        supporting_reasons=supporting,
        missing_reasons=missing,
        warnings=warnings,
        data_status=data_status_text(signals),
        flow_note=flow_reading(signals),
    )


# ---------------------------------------------------------------------------
# 늦은 신호
# ---------------------------------------------------------------------------
def classify_late_signal(event_time: datetime | None, label: str) -> FlowSignal:
    """사이드카·대량매수 등 이벤트가 13시 이후면 늦은 신호로 분류한다."""
    sig = FlowSignal(
        key="late_event",
        label=label,
        status=SignalStatus.UNKNOWN,
        source="시장 이벤트",
        as_of=event_time,
        timing=SignalTiming.UNKNOWN,
    )
    if event_time is None:
        sig.reason = f"{label} 확인 필요"
        return sig
    if event_time.hour >= LATE_SIGNAL_HOUR:
        sig.status = SignalStatus.NEUTRAL
        sig.timing = SignalTiming.LATE
        sig.reason = f"{label} — 확정 신호지만 단타 진입에는 늦은 신호"
    else:
        sig.status = SignalStatus.POSITIVE
        sig.timing = SignalTiming.CONFIRMING
        sig.reason = f"{label} — 장중 확인 신호"
    sig.display_value = event_time.strftime("%H:%M")
    return sig


# ---------------------------------------------------------------------------
# 스냅숏 → 신호 조립
# ---------------------------------------------------------------------------
def _series(snapshots, column):
    """DB 스냅숏 행 목록에서 (시각, 값) 시계열을 뽑는다. 값 없는 행은 건너뛴다."""
    out = []
    for row in snapshots or []:
        ts = row.get("captured_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                continue
        if ts is None:
            continue
        value = row.get(column)
        if value is None:
            continue
        out.append((ts, float(value)))
    return out


def build_result_from_snapshots(
    snapshots,
    *,
    foreign_futures: ForeignFuturesFlowSnapshot | None = None,
    now: datetime | None = None,
    extras=None,
) -> FlowEngineResult:
    """DB에 쌓인 당일 스냅숏(오래된 순)으로 전체 판정을 만든다.

    snapshots가 비어 있으면 데이터 부족으로 끝난다. 마지막 행이 현재값이고,
    비차익·프로그램의 방향 판정은 행 간 증분으로만 한다.
    """
    snapshots = list(snapshots or [])
    if not snapshots:
        return _build_result(
            ReboundVerdict.INSUFFICIENT_DATA,
            [],
            [],
            [],
            headline="장중 수급 스냅숏이 아직 없습니다. 수급 다시 확인을 눌러주세요.",
        )

    latest = snapshots[-1]
    as_of = latest.get("captured_at")
    if isinstance(as_of, str):
        try:
            as_of = datetime.fromisoformat(as_of)
        except ValueError:
            as_of = None

    now = now or datetime.now()
    freshness = int((now - as_of).total_seconds()) if as_of else None

    def _row_stamp(column):
        """자료 자체의 기준시각을 읽는다. 스냅숏을 '저장한' 시각과 다르다.

        저장 시각으로 신선도를 재면 방금 저장했다는 이유만으로 항상 '정상'이 된다
        — 네이버가 5분 밀린 값을 줘도 초록으로 떴다(2026-07-29 사용자 지적).
        시각을 모르면 None을 돌려주고 화면은 '확인 필요'로 둔다.
        """
        stamp = latest.get(column)
        if isinstance(stamp, str):
            try:
                stamp = datetime.fromisoformat(stamp)
            except ValueError:
                return None
        if not isinstance(stamp, datetime):
            return None
        # 기존 신호 dataclass는 naive끼리 빼므로 tzinfo는 떼서 맞춘다.
        return stamp.replace(tzinfo=None) if stamp.tzinfo is not None else stamp

    def _row_freshness(column):
        stamp = _row_stamp(column)
        return None if stamp is None else int((now - stamp).total_seconds())

    basis_sig = evaluate_basis(
        _series(snapshots, "futures_market_basis"),
        current_basis=latest.get("futures_market_basis"),
        as_of=as_of,
        freshness=freshness,
    )

    signals = [
        evaluate_foreign_futures(foreign_futures),
        evaluate_non_arbitrage(
            _series(snapshots, "non_arbitrage_net_amount"),
            current_net=latest.get("non_arbitrage_net_amount"),
            as_of=as_of,
            freshness=freshness,
        ),
        evaluate_stock_rebound(
            "samsung",
            "삼성전자",
            {
                "current": latest.get("samsung_price"),
                "open": latest.get("samsung_open"),
                "low": latest.get("samsung_day_low"),
                "prev_close": latest.get("samsung_prev_close"),
            },
            recent_lows=[r.get("samsung_day_low") for r in snapshots[-4:]],
            as_of=_row_stamp("samsung_quote_as_of") or as_of,
            freshness=_pick_freshness(_row_freshness("samsung_quote_as_of"), freshness),
        ),
        evaluate_stock_rebound(
            "hynix",
            "SK하이닉스",
            {
                "current": latest.get("hynix_price"),
                "open": latest.get("hynix_open"),
                "low": latest.get("hynix_day_low"),
                "prev_close": latest.get("hynix_prev_close"),
            },
            recent_lows=[r.get("hynix_day_low") for r in snapshots[-4:]],
            as_of=_row_stamp("hynix_quote_as_of") or as_of,
            freshness=_pick_freshness(_row_freshness("hynix_quote_as_of"), freshness),
        ),
        evaluate_program_total(
            latest.get("program_net_amount"),
            _series(snapshots, "program_net_amount"),
            as_of=as_of,
            freshness=freshness,
        ),
        evaluate_arbitrage(
            _series(snapshots, "arbitrage_net_amount"),
            basis_sig,
            current_net=latest.get("arbitrage_net_amount"),
            as_of=as_of,
            freshness=freshness,
        ),
        basis_sig,
    ]

    # counts=False인 항목은 표에는 나오지만 '켜진 신호 N개'에는 안 들어간다.
    # 금융투자·투신·사모·기금은 전부 기관계를 쪼갠 것이라 같이 세면 한 건이 다섯 번
    # 켜진 것처럼 보이고, 개인은 기관·외국인의 거울상이라 같은 눈금에 못 올린다
    # (2026-07-29 사용자 선택 '가'안: 기관계만 세고 하위는 참고로 둔다).
    investor_specs = (
        ("foreign_cash", "외국인 현물", "foreign_cash_net_amount", SignalTiming.CONFIRMING, True),
        ("personal", "개인", "personal_cash_net_amount", SignalTiming.CONFIRMING, False),
        ("institution", "기관계", "institution_cash_net_amount", SignalTiming.CONFIRMING, True),
        ("securities", "금융투자", "securities_net_amount", SignalTiming.CONFIRMING, False),
        ("investment_trust", "투신", "investment_trust_net_amount", SignalTiming.CONFIRMING, False),
        ("private_fund", "사모", "private_fund_net_amount", SignalTiming.CONFIRMING, False),
        ("fund", "기금·연기금", "fund_net_amount", SignalTiming.CONFIRMING, False),
    )
    # 투자자별 수급이 KIS가 아니라 네이버 지연 공개치로 채워졌으면 '대체' 신호로 표시한다
    # (2026-07-22: KIS 실패 시 수급 항목이 통째로 비지 않도록 대체 경로를 붙였다).
    investor_source = latest.get("investor_flow_source")
    investor_as_of = _row_stamp("investor_flow_as_of")
    investor_freshness = _row_freshness("investor_flow_as_of")
    for key, label, column, timing, counts in investor_specs:
        from_naver = bool(investor_source) and latest.get(column) is not None
        signal = evaluate_investor(
            key,
            label,
            latest.get(column),
            _series(snapshots, column),
            # 네이버 대체 경로일 때는 그 표가 밝힌 기준시각으로 잰다. 시각이 없는
            # 일별 표로 내려갔다면 신선도를 지어내지 않고 '확인 필요'로 둔다.
            as_of=investor_as_of if from_naver else as_of,
            freshness=investor_freshness if from_naver else freshness,
            timing=timing,
        )
        signal.counts_toward_totals = counts
        if not counts:
            signal.strength = SignalStrength.INDIRECT
            signal.exclusion_note = (
                "참고만 (반대편)" if key == "personal" else "기관계에 포함"
            )
        if from_naver:
            signal.strength = SignalStrength.PROXY if counts else SignalStrength.INDIRECT
            signal.source = investor_source
            signal.reason = f"{signal.reason} — 증권사 대신 네이버 공개치"
        signals.append(signal)

    # 전기전자 — 거래대금과 투자자 수급은 따로 표시한다. 업종 수급이 검증되지
    # 않으면 KOSPI 전체 수급으로 대신 채우지 않는다.
    electronics_turnover = latest.get("electronics_turnover")
    turnover_sig = FlowSignal(
        key="electronics_turnover",
        label="전기전자 거래대금",
        status=SignalStatus.UNKNOWN,
        value=electronics_turnover,
        display_value=_fmt_amount(electronics_turnover),
        source="KIS",
        as_of=as_of,
        freshness_seconds=freshness,
        timing=SignalTiming.LEADING,
        reason="전기전자 거래대금 확인 필요",
    )
    if electronics_turnover is not None:
        turnover_series = [v for _, v in _series(snapshots, "electronics_turnover")]
        if len(turnover_series) >= 2 and turnover_series[-1] > turnover_series[-2]:
            turnover_sig.status = SignalStatus.POSITIVE
            turnover_sig.reason = "전기전자 거래대금 증가"
        elif len(turnover_series) >= 2:
            turnover_sig.status = SignalStatus.NEUTRAL
            turnover_sig.reason = "전기전자 거래대금 정체 또는 감소"
        else:
            turnover_sig.status = SignalStatus.NEUTRAL
            turnover_sig.reason = "전기전자 거래대금 (변화 확인에 스냅숏 부족)"
    signals.append(turnover_sig)

    signals.append(
        evaluate_investor(
            "electronics_institution",
            "전기전자 기관수급",
            latest.get("electronics_institution_net"),
            _series(snapshots, "electronics_institution_net"),
            as_of=as_of,
            freshness=freshness,
            timing=SignalTiming.CONFIRMING,
        )
    )

    merged_extras = dict(extras or {})
    merged_extras.setdefault(
        "semis_turnover_declining", _semis_turnover_declining(snapshots)
    )
    # 장이 끝난 뒤에는 '자료가 오래됐다'는 이유로 판정을 접지 않는다.
    merged_extras.setdefault("session_open", is_session_open(now))

    return decide_verdict(signals, extras=merged_extras)


def _semis_turnover_declining(snapshots):
    """전기전자 거래대금이 직전 대비 줄었는지. 확인 못 하면 None(경고 안 함)."""
    series = [v for _, v in _series(snapshots, "electronics_turnover")]
    if len(series) < 2:
        return None
    return series[-1] < series[-2]


# ---------------------------------------------------------------------------
# 표시 헬퍼
# ---------------------------------------------------------------------------
def _fmt_amount(value) -> str:
    """순매수 금액(백만원 단위 가정)을 억 단위로 축약."""
    if value is None:
        return "못 읽음"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "못 읽음"
    억 = number / 100.0  # KIS 금액 필드는 백만원 단위 → 100백만원 = 1억
    return f"{억:+,.0f}억"


def _fmt_number(value) -> str:
    if value is None:
        return "못 읽음"
    try:
        return f"{float(value):+,.2f}"
    except (TypeError, ValueError):
        return "못 읽음"
