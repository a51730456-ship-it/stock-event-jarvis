"""미국장 시장 상태·흐름 판독 엔진 (순수 판정 로직).

한국장 엔진과 상태값·시점·세기·신선도만 공유하고, 판정 기준은 전혀 공유하지 않는다.
미국은 장중 투자자별·프로그램 수급 공개 데이터가 없다. 그래서 한국장의 '기관 수급
반전'과 달리, 여기서는 선물·ETF·금리·변동성의 방향 일치 여부로 시장 상태를 읽는다.

한국장 항목(프로그램매매·금융투자·투신·연기금·베이시스)은 이 파일에 절대 넣지 않는다.

목적: 종목을 고르는 게 아니라 지금 미국 시장이 어떤 상태이고 무엇이 앞서 움직이는지
읽는 것이다. 그래서 결론 문구에 매수·매도 지시를 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from market_signal_common import (
    MarketCode,
    MarketSignal,
    SignalStatus,
    SignalStrength,
    SignalTiming,
    data_status_text,
    flow_reading,
    fmt_signed_pct,
    is_stale,
    pct_status,
)

# ---------------------------------------------------------------------------
# 임계치 — 여기만 고치면 판정이 바뀐다.
# ---------------------------------------------------------------------------
# 기존 0단계 시장 분위기 판정과 같은 ±0.3%를 기본으로 쓴다.
DIRECTION_THRESHOLD_PCT = 0.3
# VIX·금리는 평소에도 변동이 커서 "급등" 기준을 따로 둔다.
VIX_SPIKE_PCT = 5.0
RATE_SPIKE_PCT = 2.0


class UsMarketVerdict(str, Enum):
    RISK_ON = "risk_on"
    RISK_ON_EARLY = "risk_on_early"
    MIXED = "mixed"
    RISK_OFF = "risk_off"
    INSUFFICIENT_DATA = "insufficient_data"


VERDICT_LABEL = {
    UsMarketVerdict.RISK_ON: "🟢 위험선호 확산",
    UsMarketVerdict.RISK_ON_EARLY: "🔵 위험선호 초기 — 선행신호만",
    UsMarketVerdict.MIXED: "🟡 방향 혼조",
    UsMarketVerdict.RISK_OFF: "🔴 위험회피 우세",
    UsMarketVerdict.INSUFFICIENT_DATA: "⚪ 데이터 부족",
}


@dataclass
class UsSignalResult:
    verdict: UsMarketVerdict
    verdict_label: str
    headline: str
    flow_note: str = ""
    signals: list = field(default_factory=list)
    core_signals: list = field(default_factory=list)
    supporting_reasons: list = field(default_factory=list)
    missing_reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    data_status: str = ""

    def signal(self, key: str):
        return next((s for s in self.signals if s.key == key), None)


# ---------------------------------------------------------------------------
# 신호 정의
# ---------------------------------------------------------------------------
# (key, 라벨, 티커, 시점, 상승이 부정인가)
# 선물·반도체 ETF는 본장보다 먼저 움직여서 선행, 지수는 결과라서 확인 신호다.
US_SIGNAL_SPECS = (
    ("US_ES_FUTURES", "S&P500 선물", "ES=F", SignalTiming.LEADING, False),
    ("US_NQ_FUTURES", "나스닥100 선물", "NQ=F", SignalTiming.LEADING, False),
    ("US_SOXX", "SOXX", "SOXX", SignalTiming.LEADING, False),
    ("US_SMH", "SMH", "SMH", SignalTiming.LEADING, False),
    ("US_NVDA", "NVDA", "NVDA", SignalTiming.LEADING, False),
    ("US_TSLA", "TSLA", "TSLA", SignalTiming.CONFIRMING, False),
    ("US_VIX", "VIX", "^VIX", SignalTiming.LEADING, True),
    ("US_TNX", "미국 10년물", "^TNX", SignalTiming.LEADING, True),
    ("US_DXY", "달러지수", "DX-Y.NYB", SignalTiming.CONFIRMING, True),
    ("US_SP500", "S&P500", "^GSPC", SignalTiming.CONFIRMING, False),
    ("US_NASDAQ", "Nasdaq", "^IXIC", SignalTiming.CONFIRMING, False),
)

# 첫 화면 핵심 4개
US_CORE_KEYS = ("US_NQ_FUTURES", "US_SOXX", "US_VIX", "US_TNX")


def build_us_signal(key, label, change_pct, timing, inverted, *, as_of=None, freshness=None, source="시세 조회"):
    """등락률 하나로 신호를 만든다. 값이 없으면 UNKNOWN이고 0으로 만들지 않는다."""
    status = pct_status(change_pct, positive_at=DIRECTION_THRESHOLD_PCT, inverted=inverted)
    signal = MarketSignal(
        key=key,
        label=label,
        status=status,
        value=change_pct,
        display_value=fmt_signed_pct(change_pct),
        source=source,
        as_of=as_of,
        freshness_seconds=freshness,
        strength=SignalStrength.DIRECT,
        timing=timing,
        market=MarketCode.US,
    )
    if change_pct is None:
        signal.reason = f"{label} 확인 필요"
        return signal

    if inverted:
        # VIX·금리·달러는 오르면 위험자산에 부담이다.
        if status is SignalStatus.POSITIVE:
            signal.reason = f"{label} 하락 (위험자산에 우호)"
        elif status is SignalStatus.NEGATIVE:
            signal.reason = f"{label} 상승 (위험자산에 부담)"
        else:
            signal.reason = f"{label} 보합"
    else:
        if status is SignalStatus.POSITIVE:
            signal.reason = f"{label} 상승"
        elif status is SignalStatus.NEGATIVE:
            signal.reason = f"{label} 하락"
        else:
            signal.reason = f"{label} 보합"
    return signal


def _all_positive(signals):
    known = [s for s in signals if not s.is_unknown]
    return bool(known) and all(s.is_positive for s in known)


def _any_negative(signals):
    return any(s.is_negative for s in signals)


def detect_us_fake_signals(by_key, *, extras=None) -> list[str]:
    """가짜 상승·선반영 경고. 실제로 확인된 조건일 때만 경고한다."""
    extras = extras or {}
    warnings = []

    nq = by_key.get("US_NQ_FUTURES")
    es = by_key.get("US_ES_FUTURES")
    soxx = by_key.get("US_SOXX")
    smh = by_key.get("US_SMH")
    nvda = by_key.get("US_NVDA")
    vix = by_key.get("US_VIX")
    tnx = by_key.get("US_TNX")

    # 지수 선물만 오르고 반도체는 약세
    if (
        nq is not None and nq.is_positive
        and soxx is not None and soxx.is_negative
        and smh is not None and smh.is_negative
    ):
        warnings.append("나스닥 선물만 오르고 SOXX·SMH는 약세입니다 — 반도체가 따라오지 않는 상승입니다.")

    # NVDA 단독 상승
    if (
        nvda is not None and nvda.is_positive
        and soxx is not None and soxx.is_negative
        and smh is not None and smh.is_negative
    ):
        warnings.append("NVDA만 오르고 반도체 ETF는 하락입니다 — 종목 이슈이지 섹터 흐름이 아닙니다.")

    # 주가 상승 중 VIX·금리 동시 급등
    index_up = (nq is not None and nq.is_positive) or (es is not None and es.is_positive)
    vix_spike = _is_spike(vix, VIX_SPIKE_PCT)
    rate_spike = _is_spike(tnx, RATE_SPIKE_PCT)
    if index_up and vix_spike and rate_spike:
        warnings.append("지수 상승 중에 VIX와 금리가 동시에 급등했습니다 — 상승이 유지되기 어려운 조합입니다.")
    elif index_up and vix_spike:
        warnings.append("지수는 오르는데 VIX가 급등했습니다 — 시장이 상승을 믿지 않고 있습니다.")

    # 프리마켓 거래량 부족 (확인된 경우에만)
    if extras.get("premarket_volume_thin") is True and index_up:
        warnings.append("프리마켓 상승이지만 거래량이 얇습니다 — 본장에서 뒤집히기 쉽습니다.")

    # 예측시장 저유동성
    if extras.get("bookmaker_low_liquidity") is True:
        warnings.append("예측시장 확률이 움직였지만 거래량·유동성이 적습니다 — 저유동성 간접신호입니다.")

    return warnings


def _is_spike(signal, threshold):
    if signal is None or signal.value is None:
        return False
    try:
        return float(signal.value) >= threshold
    except (TypeError, ValueError):
        return False


def build_us_market_signal_result(quotes, *, now=None, extras=None) -> UsSignalResult:
    """quotes: {티커: {"change_pct":..., "as_of":..., "source":...}} → 판정.

    한국장 build_result_from_snapshots와 이름도 로직도 분리돼 있다. 두 시장 조건을
    한 함수 안에서 if로 처리하지 않는다.
    """
    quotes = quotes or {}
    now = now or datetime.now()
    extras = dict(extras or {})

    signals = []
    for key, label, ticker, timing, inverted in US_SIGNAL_SPECS:
        quote = quotes.get(ticker) or {}
        as_of = quote.get("as_of")
        freshness = None
        if isinstance(as_of, datetime):
            freshness = int((now - as_of).total_seconds())
        signals.append(
            build_us_signal(
                key, label, quote.get("change_pct"), timing, inverted,
                as_of=as_of, freshness=freshness,
                source=quote.get("source") or "시세 조회",
            )
        )

    by_key = {s.key: s for s in signals}
    core = [by_key[k] for k in US_CORE_KEYS if k in by_key]
    warnings = detect_us_fake_signals(by_key, extras=extras)

    # --- 데이터 부족 ---------------------------------------------------------
    core_unknown = sum(1 for s in core if s.is_unknown)
    stale_core = sum(1 for s in core if is_stale(s))
    if not core or core_unknown >= 2 or stale_core >= 2:
        return _build(
            UsMarketVerdict.INSUFFICIENT_DATA, signals, core, warnings,
            headline="미국장 핵심 신호가 부족해 지금은 상태를 읽지 않습니다.",
        )

    futures = [s for s in (by_key.get("US_ES_FUTURES"), by_key.get("US_NQ_FUTURES")) if s]
    semis = [s for s in (by_key.get("US_SOXX"), by_key.get("US_SMH")) if s]
    vix = by_key.get("US_VIX")
    tnx = by_key.get("US_TNX")

    futures_up = _all_positive(futures)
    semis_up = _all_positive(semis)
    vix_ok = vix is not None and not vix.is_negative
    rate_ok = tnx is not None and not tnx.is_negative

    # --- 위험회피 우세 -------------------------------------------------------
    vix_spike = _is_spike(vix, VIX_SPIKE_PCT)
    rate_spike = _is_spike(tnx, RATE_SPIKE_PCT)
    futures_down = _any_negative(futures)
    if (vix_spike or rate_spike) and futures_down:
        driver = "VIX 급등" if vix_spike else "금리 급등"
        return _build(
            UsMarketVerdict.RISK_OFF, signals, core, warnings,
            headline=f"{driver}과 지수 선물 하락이 함께 나타났습니다. 위험회피가 우세한 상태입니다.",
        )
    if futures_down and _any_negative(semis):
        return _build(
            UsMarketVerdict.RISK_OFF, signals, core, warnings,
            headline="지수 선물과 반도체가 함께 밀리고 있습니다. 위험회피가 우세한 상태입니다.",
        )

    # --- 위험선호 확산 -------------------------------------------------------
    if futures_up and semis_up and vix_ok and rate_ok:
        return _build(
            UsMarketVerdict.RISK_ON, signals, core, warnings,
            headline=(
                "지수 선물과 반도체가 함께 오르고 VIX·금리도 부담을 주지 않습니다. "
                "위험선호가 넓게 퍼진 상태입니다."
            ),
        )

    # --- 위험선호 초기 (선행만 켜짐) ------------------------------------------
    if futures_up and semis_up:
        blocker = "VIX" if not vix_ok else "금리"
        return _build(
            UsMarketVerdict.RISK_ON_EARLY, signals, core, warnings,
            headline=(
                f"선물과 반도체는 함께 오르지만 {blocker} 쪽이 아직 부담을 주고 있습니다. "
                "위험선호가 퍼지는 초기 단계입니다."
            ),
        )
    if futures_up or semis_up:
        leader = "지수 선물" if futures_up else "반도체"
        return _build(
            UsMarketVerdict.RISK_ON_EARLY, signals, core, warnings,
            headline=f"{leader}만 먼저 움직였고 나머지는 아직 따라오지 않았습니다.",
        )

    # --- 방향 혼조 -----------------------------------------------------------
    return _build(
        UsMarketVerdict.MIXED, signals, core, warnings,
        headline="선물·반도체·변동성이 서로 다른 방향을 가리키고 있습니다.",
    )


def _build(verdict, signals, core, warnings, *, headline) -> UsSignalResult:
    return UsSignalResult(
        verdict=verdict,
        verdict_label=VERDICT_LABEL[verdict],
        headline=headline,
        flow_note=flow_reading(signals),
        signals=signals,
        core_signals=core,
        supporting_reasons=[s.reason for s in signals if s.is_positive][:4],
        missing_reasons=[s.reason for s in signals if s.is_negative or s.is_unknown][:4],
        warnings=warnings,
        data_status=data_status_text(signals),
    )
