"""자비스 주식 기록장 (Streamlit 앱): 오늘 요약 / 새 기록 입력 / 오늘 주가 확인 / 지난 기록 보기 / 결과 확인 / 추가 기능."""

import re
from datetime import datetime

import pandas as pd
import streamlit as st

import database as db
import performance
import price_data

_SECTION_HEADER_RE = re.compile(r"^\[(.+?)\]\s*$")

# 간편 입력에서 자주 쓰는 표현을 판정 5종 내부값으로 정규화한다.
# 내부값/DB 저장값은 그대로 두고, 화면 표시는 아래쪽에 정의된 _display_verdict_name()으로 보여준다.
VERDICT_NORMALIZE = {
    "보류": "보류(선반영)",
    "보류(선반영)": "보류(선반영)",
    "관심 후보": "추천 후보",
    "관심종목": "추천 후보",
    "관심 종목": "추천 후보",
    "추천 후보": "추천 후보",
    "감시": "감시",
    "확인 필요": "확인 필요",
    "제외": "제외",
}


def _parse_optional_score(text):
    """빈 문자열이면 None, 숫자면 float로 변환, 숫자로 해석 안 되면 None을 반환한다."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_quick_text(text):
    """"간편 저장용 텍스트"([기본]/[오늘의 결론]/[종목] 구역)를 파싱한다.

    구분자는 '/'. 각 종목 줄은 세 형식을 지원한다.
    - 6개 필드(기존 형식): 종목명 / 티커 / market / 판정 / 신호 분류 / 이벤트명
      (trade_mode는 자동으로 '공통')
    - 7개 필드(신규 형식): 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명
    - 13개 필드(확장 형식, 판단 설명 포함): 위 7개 필드 +
      score / score_reason / top_candidate_reason / penalty_reason / buy_confirmed / buy_confirm_condition
    선택지에 없는 값은 안전한 기본값으로 대체하고 warnings에 기록한다.
    "시점 구분"은 timing_class가 저장 시각 기준 자동 분류라는 기존 규칙 때문에 파싱만 하고
    적용하지 않는다(경고만 남김).
    """
    warnings = []
    sections = {}
    current = None
    buffer = []
    for line in text.splitlines():
        m = _SECTION_HEADER_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = m.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()

    result = {
        "market_scope": None,
        "briefing_stage": None,
        "default_signal_type": None,
        "day_conclusion": sections.get("오늘의 결론", "").strip(),
        "items": [],
        "warnings": warnings,
    }

    for line in sections.get("기본", "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "시장 범위":
            if value in db.MARKET_SCOPE_CHOICES:
                result["market_scope"] = value
            else:
                warnings.append(f"시장 범위 '{value}'를 인식하지 못했습니다 (KR/US/MIXED 중 하나여야 함).")
        elif key == "브리핑 단계":
            if value in db.BRIEFING_STAGE_CHOICES:
                result["briefing_stage"] = value
            else:
                warnings.append(f"브리핑 단계 '{value}'가 선택지에 없어 '기타'로 대체됩니다.")
                result["briefing_stage"] = "기타"
        elif key == "신호 분류":
            if value in db.SIGNAL_TYPE_CHOICES:
                result["default_signal_type"] = value
            else:
                warnings.append(f"기본 신호 분류 '{value}'를 인식하지 못했습니다.")
        elif key == "시점 구분":
            warnings.append("시점 구분은 저장 시각 기준으로 자동 분류되어 이 값은 사용되지 않습니다.")

    for line in sections.get("종목", "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("/")]
        if len(parts) < 4:
            warnings.append(f"종목 줄을 해석하지 못했습니다(구분자 '/' 필드 부족): {line}")
            continue

        stock_name, ticker, market = parts[0], parts[1], parts[2]

        if len(parts) >= 13:
            # 확장 형식: 7개 기존 필드 + 6개 판단 설명 필드
            # 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명 /
            # score / score_reason / top_candidate_reason / penalty_reason / buy_confirmed / buy_confirm_condition
            trade_mode = parts[3]
            verdict = parts[4]
            signal_type = parts[5] if parts[5] else (result["default_signal_type"] or "")
            event_title = parts[6]
            score = _parse_optional_score(parts[7])
            score_reason = parts[8] or None
            top_candidate_reason = parts[9] or None
            penalty_reason = parts[10] or None
            buy_confirmed = parts[11] if parts[11] else "미확정"
            buy_confirm_condition = parts[12] if parts[12] else "확인 필요"
        elif len(parts) == 7:
            # 신규 형식(판단 설명 없음): 종목명 / 티커 / market / 매매유형 / 판정 / 신호 분류 / 이벤트명
            trade_mode = parts[3]
            verdict = parts[4]
            signal_type = parts[5] if parts[5] else (result["default_signal_type"] or "")
            event_title = parts[6]
            score = None
            score_reason = None
            top_candidate_reason = None
            penalty_reason = None
            buy_confirmed = "미확정"
            buy_confirm_condition = "확인 필요"
        else:
            # 기존 형식(6개 이하): 종목명 / 티커 / market / 판정 / 신호 분류 / 이벤트명
            trade_mode = "공통"
            verdict = parts[3]
            signal_type = parts[4] if len(parts) > 4 and parts[4] else (result["default_signal_type"] or "")
            event_title = parts[5] if len(parts) > 5 else ""
            score = None
            score_reason = None
            top_candidate_reason = None
            penalty_reason = None
            buy_confirmed = "미확정"
            buy_confirm_condition = "확인 필요"

        if market not in db.ITEM_MARKET_CHOICES:
            warnings.append(f"'{stock_name}' market 값 '{market}'을 인식 못해 'KR'로 대체합니다.")
            market = "KR"
        if trade_mode not in db.TRADE_MODE_CHOICES:
            warnings.append(f"'{stock_name}' 매매유형 값 '{trade_mode}'을 인식 못해 '공통'으로 대체합니다.")
            trade_mode = "공통"
        verdict = VERDICT_NORMALIZE.get(verdict, verdict)
        if verdict not in db.VERDICT_CHOICES:
            warnings.append(f"'{stock_name}' 판정 값 '{verdict}'을 인식 못해 '확인 필요'로 대체합니다.")
            verdict = "확인 필요"
        if signal_type not in db.SIGNAL_TYPE_CHOICES:
            warnings.append(f"'{stock_name}' 신호 분류 값 '{signal_type}'을 인식 못해 '미분류'로 대체합니다.")
            signal_type = "미분류"

        result["items"].append(
            {
                "stock_name": stock_name,
                "ticker": ticker,
                "market": market,
                "trade_mode": trade_mode,
                "verdict": verdict,
                "signal_type": signal_type,
                "event_title": event_title,
                "score": score,
                "score_reason": score_reason,
                "top_candidate_reason": top_candidate_reason,
                "penalty_reason": penalty_reason,
                "buy_confirmed": buy_confirmed,
                "buy_confirm_condition": buy_confirm_condition,
            }
        )

    return result

st.set_page_config(page_title="자비스 주식 기록장", layout="wide")

db.init_db()

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif;
    }
    .stApp {
        background-color: #0f1117;
    }
    h1 {
        font-size: 1.9rem !important;
    }
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: #9aa0a8 !important;
    }
    [data-testid="stExpander"] {
        background-color: #171a21;
        border: 1px solid #303642;
        border-radius: 10px;
        margin-bottom: 8px;
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] > div,
    [data-testid="stMultiSelect"] > div,
    [data-testid="stDateInput"] input {
        background-color: #20232b !important;
        border-radius: 6px !important;
        border: 1px solid #303642 !important;
    }
    [data-testid="stDataFrame"] [role="row"] {
        min-height: 38px;
    }
    button[kind="primary"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("자비스 주식 기록장")
st.caption("단타·스윙 판단을 기록하고 나중에 맞았는지 확인하는 도구")

VERDICT_ORDER = [
    "추천 후보",
    "감시",
    "확인 필요",
    "보류(선반영)",
    "제외",
]

# 화면 표시용 이름/색상 매핑. 내부 저장값(VERDICT_CHOICES/SIGNAL_TYPE_CHOICES/TRADE_MODE_CHOICES)은 그대로 둔다.
VERDICT_DISPLAY = {
    "추천 후보": "1순위 후보",
    "감시": "관찰 후보",
    "확인 필요": "재확인",
    "보류(선반영)": "보류",
    "제외": "제외",
}
REVERSE_VERDICT_DISPLAY = {v: k for k, v in VERDICT_DISPLAY.items()}

# 결과 확인 화면 / 장중 스냅샷 전용 "후보 점수". 실제 상승확률이 아니라 가격 위치·고점 대비
# 밀림·거래대금·판정을 기준으로 만든 화면 표시용 상대 우선순위 숫자다. DB 컬럼이 아니라
# 표를 그릴 때만 계산하며, 100점이 자동으로 나오지 않도록 항상 상한을 둔다.
CANDIDATE_BASE_SCORE = {
    "추천 후보": 85,
    "1순위 후보": 85,
    "감시": 65,
    "관찰 후보": 65,
    "확인 필요": 50,
    "재확인": 50,
    "보류(선반영)": 25,
    "보류": 25,
    "제외": 0,
}

_BASIS_PATTERNS = {
    "change_pct": r"전일대비\s*([+-]?\d+(?:\.\d+)?)%",
    "open_pos_pct": r"시가대비\s*([+-]?\d+(?:\.\d+)?)%",
    "high_drop_pct": r"고점대비\s*([+-]?\d+(?:\.\d+)?)%",
    "turnover_ratio_pct": r"시총대비\s*거래대금\s*([+-]?\d+(?:\.\d+)?)%",
}


def extract_score_basis_from_text(*texts):
    """report_item의 텍스트 필드들에서 전일대비/시가대비/고점대비/시총대비 거래대금 값을 뽑는다.

    장중 스냅샷의 "브리핑 입력용 문장 만들기"가 만드는 형식과 호환된다. 못 찾은 값은 None —
    이 경우 compute_candidate_score()는 판정 기본점수만 사용한다(자유 서술형 텍스트도 정상
    지원해야 하므로, 숫자 근거가 없다고 오류를 내지 않는다).
    """
    combined = " ".join(t for t in texts if t)
    basis = {}
    for key, pattern in _BASIS_PATTERNS.items():
        m = re.search(pattern, combined)
        basis[key] = float(m.group(1)) if m else None
    return basis


def compute_candidate_score(verdict, trade_mode, basis):
    """0~100 사이 "후보 점수"를 계산한다 (실제 상승확률 아님, 화면 표시 전용).

    판정 기본점수에서 시작해 시가대비/고점대비/시총대비 거래대금으로 가감하고,
    "단타+보류"는 강제로 낮게, 그 외 모든 경우도 100점이 자동으로 나오지 않도록 상한을 둔다.
    """
    score = float(CANDIDATE_BASE_SCORE.get(verdict, 50))

    open_pos = basis.get("open_pos_pct")
    high_drop = basis.get("high_drop_pct")
    turnover_ratio = basis.get("turnover_ratio_pct")

    if open_pos is not None:
        score += max(min(open_pos, 5.0), -5.0)

    if high_drop is not None:
        if high_drop <= -5:
            score -= 15
        elif high_drop <= -3:
            score -= 7
        elif high_drop <= -1:
            score -= 2
        else:
            score += 3

    if turnover_ratio is not None:
        if turnover_ratio >= 3:
            score += 5
        elif turnover_ratio >= 1:
            score += 2

    if trade_mode == "단타" and verdict in ("보류(선반영)", "보류"):
        score = min(score, 35)

    return round(max(0.0, min(score, 97.0)), 1)


def compute_snapshot_reference_score(
    mode, change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, external_good=False
):
    """장중 스냅샷에서 판정이 정해지기 전, 계산된 지표만으로 만드는 참고용 점수.

    자동매수 추천이 아니라 장중 후보 비교용 참고 점수다. 외부 환경(external_good)이
    입력되지 않았으면 최고점을 88점으로 제한하고, 외부 환경까지 좋을 때만 100점까지
    열어준다.
    """
    if mode == "단타":
        score = 45.0
        if open_pos_pct is not None:
            if open_pos_pct < 0:
                score -= 12
            elif open_pos_pct >= 3:
                score += 15
            elif open_pos_pct >= 1:
                score += 8
        if high_drop_pct is not None:
            if high_drop_pct >= -1.5:
                score += 15
            elif high_drop_pct >= -3:
                score += 8
            elif high_drop_pct <= -6:
                score -= 25
            elif high_drop_pct <= -5:
                score -= 20
        if turnover_ratio_pct is not None and turnover_ratio_pct >= 1:
            score += 10
        if change_pct is not None:
            if change_pct < 0:
                score -= 10
            elif change_pct >= 5:
                score += 5
        # 고점 대비 밀림이 -5% 이하면, 다른 지표가 아무리 좋아도 단타 생존력은
        # 이미 훼손된 것으로 보고 상한을 45점으로 눌러 다른 가산점이 이를
        # 덮어쓰지 못하게 한다.
        if high_drop_pct is not None and high_drop_pct <= -5:
            score = min(score, 45.0)
    else:  # 스윙
        score = 50.0
        if change_pct is not None:
            if change_pct < 0:
                score -= 10
            elif change_pct >= 5:
                score += 12
            elif change_pct >= 3:
                score += 8
            elif change_pct >= 1:
                score += 4
        if open_pos_pct is not None:
            if open_pos_pct < 0:
                score -= 8
            elif open_pos_pct >= 3:
                score += 12
            elif open_pos_pct >= 1:
                score += 7
            elif open_pos_pct >= 0:
                score += 3
        if high_drop_pct is not None:
            if high_drop_pct >= -1.5:
                score += 10
            elif high_drop_pct >= -3:
                score += 5
            elif high_drop_pct <= -6:
                score -= 20
            elif high_drop_pct <= -5:
                score -= 15
        if turnover_ratio_pct is not None:
            if turnover_ratio_pct >= 1:
                score += 8
            elif turnover_ratio_pct >= 0.4:
                score += 4

    cap = 100.0 if external_good else 88.0
    return round(max(0.0, min(score, cap)), 1)


def _snapshot_external_good():
    """외부 환경 입력이 되어 있고, 방향성이 우호적인지(부정적 신호 없이 우호 신호가
    하나라도 있는지) 판정한다. 하나도 입력하지 않았으면(전부 '미입력') False."""
    favorable = {"강함", "상승", "순매수"}
    unfavorable = {"약함", "하락", "순매도"}
    values = [
        st.session_state.get("snap_soxx_dir", "미입력"),
        st.session_state.get("snap_usdkrw_dir", "미입력"),
        st.session_state.get("snap_kospi200_dir", "미입력"),
        st.session_state.get("snap_foreign_dir", "미입력"),
        st.session_state.get("snap_program_dir", "미입력"),
    ]
    has_favorable = any(v in favorable for v in values)
    has_unfavorable = any(v in unfavorable for v in values)
    return has_favorable and not has_unfavorable


def _kr_danta_verdict(danta_score):
    """단기 관심 점수 기준 국내장 단타 판단(국내장 기록 바로 저장 전용).

    65점 이상 -> 감시, 45점 미만 -> 보류(선반영), 그 사이 -> 확인 필요(재확인 표시).
    """
    if danta_score >= 65:
        return "감시"
    if danta_score < 45:
        return VERDICT_NORMALIZE["보류"]
    return "확인 필요"


def _kr_swing_verdict(swing_score):
    """며칠 관심 점수 기준 국내장 스윙 판단(국내장 기록 바로 저장 전용).

    75점 이상 -> 관심 후보(추천 후보), 55점 이상 -> 감시, 그 미만 -> 보류(선반영).
    """
    if swing_score >= 75:
        return VERDICT_NORMALIZE["관심 후보"]
    if swing_score >= 55:
        return "감시"
    return VERDICT_NORMALIZE["보류"]


def _kr_score_reason_text(change_pct, open_pos_pct, turnover_ratio_pct):
    """국내장 기록 바로 저장 전용 점수 근거 한 줄 요약(계산된 지표 기반, 자동매수 근거 아님)."""
    parts = []
    if open_pos_pct is not None:
        parts.append("시가 위 유지" if open_pos_pct >= 0 else "시가 대비 약세")
    if change_pct is not None and change_pct >= 3:
        parts.append("전일 대비 상승폭 큼")
    if turnover_ratio_pct is not None and turnover_ratio_pct >= 1:
        parts.append("거래대금 증가")
    return " + ".join(parts) if parts else "특이 사항 없음"


def _kr_penalty_reason_text(high_drop_pct, change_pct):
    """국내장 기록 바로 저장 전용 감점 이유 한 줄 요약."""
    parts = []
    if high_drop_pct is not None and high_drop_pct <= -3:
        parts.append("장중 고점 대비 밀림")
    if change_pct is not None and change_pct < 0:
        parts.append("전일 대비 하락")
    return ", ".join(parts) if parts else "특별한 감점 요인 없음"


def _kr_top_candidate_reason_text(trade_mode, score, verdict_display):
    """국내장 기록 바로 저장 전용 1순위 후보 근거 한 줄 요약. 실제로 1순위 조건을
    충족했을 때만 긍정적으로 서술하고, 그렇지 않으면 부족한 상태를 그대로 알린다."""
    if trade_mode == "단타" and score >= 65:
        return "관찰 종목 중 단기 생존력(시가 위치·고점 대비 밀림)이 상대적으로 강함"
    if trade_mode == "스윙" and score >= 75:
        return "관찰 종목 중 거래대금과 추세가 상대적으로 강함"
    return f"현재 {verdict_display} 단계로 1순위 조건에는 못 미침"


def _us_swing_upside_score(change_pct):
    """상승률 점수(0~20). 전일 대비 등락률 기준."""
    if change_pct is None:
        return 0.0, "전일대비 데이터 없음"
    if change_pct >= 6:
        return 20.0, f"전일 대비 약 {change_pct:+.1f}% 이상 급등"
    if change_pct >= 4:
        return 16.0, f"전일 대비 {change_pct:+.1f}% 상승"
    if change_pct >= 2:
        return 12.0, f"전일 대비 {change_pct:+.1f}% 상승"
    if change_pct >= 0:
        return 8.0, f"전일 대비 {change_pct:+.1f}% 소폭 상승"
    return 4.0, f"전일 대비 {change_pct:+.1f}% 하락"


def _us_swing_close_pos_score(high_drop_pct):
    """종가 위치 점수(0~20). 장중 고점 대비 마감 위치 기준."""
    if high_drop_pct is None:
        return 0.0, "고점 대비 데이터 없음"
    if high_drop_pct >= -1:
        return 20.0, "장중 고가 근처에서 마감"
    if high_drop_pct >= -3:
        return 14.0, f"고점 대비 {high_drop_pct:.1f}%로 소폭 밀림"
    if high_drop_pct >= -5:
        return 8.0, f"고점 대비 {high_drop_pct:.1f}%로 밀림"
    return 4.0, f"고점 대비 {high_drop_pct:.1f}%로 크게 밀림"


def _us_swing_market_mood_score():
    """시장 분위기 점수(0~15). 나스닥100 선물 등락률 + 외부 환경 방향 입력을 종합.

    아무것도 입력하지 않았으면 중립값(7.5)을 준다(과대/과소 확정 방지).
    """
    nq_change = st.session_state.get("snap_nq_change", 0.0) or 0.0
    favorable = {"강함", "상승", "순매수"}
    unfavorable = {"약함", "하락", "순매도"}
    dirs = {
        "SOXX/SMH": st.session_state.get("snap_soxx_dir", "미입력"),
        "KOSPI200 선물": st.session_state.get("snap_kospi200_dir", "미입력"),
        "외국인 선물": st.session_state.get("snap_foreign_dir", "미입력"),
        "프로그램 수급": st.session_state.get("snap_program_dir", "미입력"),
    }
    fav = [k for k, v in dirs.items() if v in favorable]
    unfav = [k for k, v in dirs.items() if v in unfavorable]

    score = 7.5
    if nq_change >= 1:
        score += 4
    elif nq_change >= 0.3:
        score += 2
    elif nq_change < 0:
        score -= 2
    score += len(fav) * 1.5
    score -= len(unfav) * 1.5
    score = round(max(0.0, min(score, 15.0)), 1)

    if not fav and not unfav and not nq_change:
        note = "시장 분위기 입력 없음(중립 처리)"
    else:
        parts = []
        if nq_change:
            parts.append(f"나스닥100 선물 {nq_change:+.2f}%")
        if fav:
            parts.append(f"{'/'.join(fav)} 우호적")
        if unfav:
            parts.append(f"{'/'.join(unfav)} 비우호적")
        note = ", ".join(parts) if parts else "중립적 시장 분위기"
    return score, note


def _us_swing_material_score(material_memo):
    """재료 점수(0~20). 뉴스를 자동으로 읽지 못하므로 메모가 없으면 낮은 기본값을 준다."""
    if material_memo:
        return 15.0, material_memo
    return 8.0, "재료 메모 없음. 가격 흐름 중심 판단이며, 재료 확인 필요."


def _us_swing_momentum_score(turnover_ratio_pct):
    """거래/탄력 점수(0~15). 시총 대비 거래대금 기준."""
    if turnover_ratio_pct is None:
        return 0.0, "거래대금 데이터 없음"
    if turnover_ratio_pct >= 3:
        return 15.0, "거래량과 장중 탄력 양호"
    if turnover_ratio_pct >= 1.5:
        return 11.0, "거래량과 장중 탄력 보통"
    if turnover_ratio_pct >= 0.5:
        return 7.0, "거래량과 장중 탄력 약함"
    return 3.0, "거래량과 장중 탄력 매우 약함"


def _us_swing_risk_score(change_pct, high_drop_pct, has_material_memo):
    """위험 감점(최대 -10). 급등 눌림 위험 + 재료 미확인 위험 + 고점 대비 큰 밀림을 반영."""
    risk = 0.0
    notes = []
    if change_pct is not None and change_pct >= 6:
        risk -= 4
        notes.append("하루 급등 후 다음날 눌림 위험")
    elif change_pct is not None and change_pct >= 3:
        risk -= 2
        notes.append("단기 급등에 따른 되돌림 가능성")
    if not has_material_memo:
        risk -= 4
        notes.append("재료가 아직 실적 확정이 아닌 가격 흐름 중심 판단")
    if high_drop_pct is not None and high_drop_pct <= -5:
        risk -= 2
        notes.append("고점 대비 밀림 큰 편")
    risk = round(max(-10.0, risk), 1)
    note = "; ".join(notes) if notes else "특별한 위험 요인 없음"
    return risk, note


def _us_swing_tier_label(total_score):
    """총점(0~100) 기준 표시용 등급 이름. 저장용 판정(verdict)과는 별개다."""
    if total_score >= 90:
        return "매우 강한 1순위 후보"
    if total_score >= 85:
        return "강한 1순위 후보"
    if total_score >= 75:
        return "관심 후보"
    if total_score >= 60:
        return "감시"
    return "보류"


def _us_swing_verdict(total_score):
    """총점(0~100) 기준 저장용 판정(미국장 스윙 바로 저장 전용).

    75점 이상 -> 추천 후보(1순위/관심 후보 통합 저장), 60점 이상 -> 감시, 미만 -> 보류(선반영).
    등급 이름(매우 강한 1순위 후보 등)은 _us_swing_tier_label()이 표시용으로 따로 만든다.
    """
    if total_score >= 75:
        return VERDICT_NORMALIZE["관심 후보"]
    if total_score >= 60:
        return "감시"
    return VERDICT_NORMALIZE["보류"]


def compute_us_swing_breakdown(name, change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, material_memo):
    """미국장 스윙 기록 바로 저장 전용 100점 만점 점수 근거표를 계산한다.

    자동매수 신호가 아니라, 왜 그 점수/판단이 나왔는지 사람이 읽을 수 있는 근거를 만들기
    위한 것이다. 매수 확정 여부는 진입가/손절가/매수 비중/다음날 확인 조건 4가지가 이 화면에서
    입력되지 않는 한 항상 "미확정"이다.
    """
    upside_score, upside_note = _us_swing_upside_score(change_pct)
    close_score, close_note = _us_swing_close_pos_score(high_drop_pct)
    mood_score, mood_note = _us_swing_market_mood_score()
    material_score, material_note = _us_swing_material_score(material_memo)
    momentum_score, momentum_note = _us_swing_momentum_score(turnover_ratio_pct)
    risk_score, risk_note = _us_swing_risk_score(change_pct, high_drop_pct, bool(material_memo))

    total_score = round(
        upside_score + close_score + mood_score + material_score + momentum_score + risk_score, 1
    )
    total_score = max(0.0, min(total_score, 100.0))
    tier_label = _us_swing_tier_label(total_score)
    verdict = _us_swing_verdict(total_score)

    strong = []
    if upside_score >= 16:
        strong.append("상승률")
    if close_score >= 16:
        strong.append("종가 위치")
    if momentum_score >= 12:
        strong.append("거래 탄력")
    if mood_score >= 12:
        strong.append("시장 분위기")
    if material_score >= 16:
        strong.append("재료")

    if total_score >= 75:
        if strong:
            priority_reason = (
                f"가격 흐름은 총점 {total_score:.0f}점입니다. {', '.join(strong)}이(가) 모두 강한 편입니다."
            )
        else:
            priority_reason = (
                f"총점 {total_score:.0f}점으로 1순위 후보 기준을 충족하지만, 개별 항목은 고르게 보통 수준입니다."
            )
    else:
        priority_reason = f"총점 {total_score:.0f}점으로 1순위 후보 기준(75점)에 못 미칩니다. 개별 항목 점수를 참고하세요."

    deduction_reason = risk_note if risk_score < 0 else "특별한 감점 요인이 없습니다."

    return {
        "name": name,
        "total_score": total_score,
        "tier_label": tier_label,
        "verdict": verdict,
        "upside_score": upside_score,
        "upside_note": upside_note,
        "close_pos_score": close_score,
        "close_pos_note": close_note,
        "mood_score": mood_score,
        "mood_note": mood_note,
        "material_score": material_score,
        "material_note": material_note,
        "momentum_score": momentum_score,
        "momentum_note": momentum_note,
        "risk_score": risk_score,
        "risk_note": risk_note,
        "priority_reason": priority_reason,
        "deduction_reason": deduction_reason,
        "buy_confirmed": "미확정",
        "buy_confirm_condition": (
            "진입가, 손절가, 매수 비중, 다음날 확인 조건이 모두 정해져야 매수 확정으로 전환됩니다. "
            "이 화면은 아직 이 값을 입력받지 않으므로 항상 '미확정'으로 표시됩니다."
        ),
    }


def _us_swing_narrative_text(row):
    """compute_us_swing_breakdown() 결과 1건을 TSLA 예시와 같은 문장형 근거로 만든다."""
    lines = [
        f"{row['name']} 총점 {row['total_score']:.0f}점 ({row['tier_label']})",
        "",
        "점수 근거:",
        f"상승률 {row['upside_score']:.0f}/20: {row['upside_note']}",
        f"종가 위치 {row['close_pos_score']:.0f}/20: {row['close_pos_note']}",
        f"시장 분위기 {row['mood_score']:.0f}/15: {row['mood_note']}",
        f"재료 {row['material_score']:.0f}/20: {row['material_note']}",
        f"거래/탄력 {row['momentum_score']:.0f}/15: {row['momentum_note']}",
        f"위험 감점 {row['risk_score']:.0f}: {row['risk_note']}",
        "",
        "1순위 근거:",
        row["priority_reason"],
        "",
        "감점 이유:",
        row["deduction_reason"],
        "",
        "매수 확정 여부:",
        row["buy_confirmed"],
        "",
        "매수 확정 조건:",
        row["buy_confirm_condition"],
    ]
    return "\n".join(lines)


def _build_item_text_lookup():
    """(report_id, ticker, trade_mode) -> 관련 텍스트를 합친 문자열 목록. 후보 점수의 숫자
    근거를 저장된 문장에서 뽑아내기 위한 조회용이다(DB에 새 컬럼을 만들지 않는다)."""
    lookup = {}
    for report in db.list_reports():
        for item in db.get_report_items(report["id"]):
            key = (report["id"], item.get("ticker"), item.get("trade_mode"))
            text_parts = [
                item.get("event_title"),
                item.get("stock_market_basis_a"),
                item.get("stock_market_basis_b"),
                item.get("stock_market_basis_c"),
                item.get("betting_basis_ga"),
                item.get("betting_basis_na"),
                item.get("betting_basis_da"),
                item.get("stock_market_judgment"),
                item.get("betting_market_judgment"),
            ]
            lookup.setdefault(key, []).append(" ".join(p for p in text_parts if p))
    return lookup


def _build_item_judgment_lookup():
    """(report_id, ticker, trade_mode) -> report_item 전체 dict. 결과 확인의 '자세히 보기'에서
    저장 당시 점수/근거/매수 확정 정보를 다시 보여주기 위한 조회용이다."""
    lookup = {}
    for report in db.list_reports():
        for item in db.get_report_items(report["id"]):
            key = (report["id"], item.get("ticker"), item.get("trade_mode"))
            lookup[key] = item
    return lookup


def _rank_label(rank):
    """순위 숫자를 표시용 문구로 바꾼다. 1위="1순위 후보", 2위="2순위", 3위="3순위", 그 외="N위"."""
    if rank == 1:
        return "1순위 후보"
    if rank == 2:
        return "2순위"
    if rank == 3:
        return "3순위"
    return f"{rank}위"


def _rank_scores(pairs):
    """[(key, score), ...] 목록에서 score가 있고(>0) 큰 순으로 순위를 매긴다.

    score가 없거나(None) 0 이하이면 순위 계산에서 제외하고 "미평가"로 표시한다.
    자동매수 신호가 아니라 화면 표시용 상대 순위이며, DB에는 저장하지 않는다.
    반환: {key: 순위 라벨}
    """
    valid = [(k, s) for k, s in pairs if (s or 0) > 0]
    valid.sort(key=lambda pair: -pair[1])
    labels = {}
    for idx, (k, _) in enumerate(valid, start=1):
        labels[k] = _rank_label(idx)
    for k, _ in pairs:
        if k not in labels:
            labels[k] = "미평가"
    return labels


def _compute_score_rank_labels(items):
    """report_item dict 목록(같은 report일 수도, 여러 report가 섞여 있을 수도 있음)에서
    (report_id, market, trade_mode) 그룹별로 score 기준 순위를 매겨 item id -> 순위 라벨을 반환한다.

    한국장/미국장, 단타/스윙을 서로 섞지 않기 위해 report_id·market·trade_mode가 모두 같은
    항목끼리만 순위를 비교한다. 오래된 report처럼 score가 없는 항목은 "미평가"로 표시되며
    앱이 오류를 내지 않는다.
    """
    groups = {}
    for item in items:
        key = (item.get("report_id"), item.get("market") or "OTHER", item.get("trade_mode") or "공통")
        groups.setdefault(key, []).append(item)

    labels = {}
    for group_items in groups.values():
        pairs = [(it["id"], it.get("score")) for it in group_items]
        labels.update(_rank_scores(pairs))
    return labels


VERDICT_BADGE_COLOR = {
    "추천 후보": "green",
    "감시": "yellow",
    "확인 필요": "orange",
    "보류(선반영)": "gray",
    "제외": "red",
}
SIGNAL_TYPE_DISPLAY = {
    "선행 신호": "장전 신호",
    "재확인 신호": "재확인",
    "늦은 신호": "늦게 발견",
    "가짜 신호": "실패 가능",
    "미분류": "미정",
}
TRADE_MODE_BADGE_COLOR = {
    "단타": "blue",
    "스윙": "violet",
    "공통": "gray",
}


def _display_verdict_name(verdict):
    """판정 내부값을 화면 표시용 쉬운 이름으로 바꾼다 (저장값은 불변)."""
    return VERDICT_DISPLAY.get(verdict, verdict)


def _display_signal_type(signal_type):
    """신호 분류 내부값을 화면 표시용 쉬운 이름으로 바꾼다 (저장값은 불변)."""
    return SIGNAL_TYPE_DISPLAY.get(signal_type, signal_type)


def _verdict_badge(verdict):
    color = VERDICT_BADGE_COLOR.get(verdict, "gray")
    return f":{color}-badge[{_display_verdict_name(verdict)}]"


def _trade_mode_badge(trade_mode):
    color = TRADE_MODE_BADGE_COLOR.get(trade_mode, "gray")
    return f":{color}-badge[{trade_mode or '공통'}]"


TRADE_MODE_ORDER = ["단타", "스윙", "공통"]
TRADE_MODE_HEADING = {"단타": "단타 관점", "스윙": "스윙 관점", "공통": "공통"}
TRADE_MODE_EMOJI = {"단타": "🔵", "스윙": "🟣", "공통": "⚪"}


def _group_items_by_trade_mode_and_verdict(report_id):
    """report_items를 매매유형(단타→스윙→공통) → 판정(VERDICT_ORDER) 순서로 2단 그룹화한다.

    같은 매매유형 + 같은 판정 안에서는 db.get_report_items()가 반환하는 입력(저장) 순서를
    그대로 유지한다. 같은 종목이 단타/스윙 둘 다로 저장돼 있으면 각 그룹에 각각 나타난다
    (합치지 않음).
    """
    grouped = {tm: {v: [] for v in VERDICT_ORDER} for tm in TRADE_MODE_ORDER}
    for item in db.get_report_items(report_id):
        tm = item.get("trade_mode") or "공통"
        if tm not in TRADE_MODE_ORDER:
            tm = "공통"
        v = item.get("verdict")
        grouped[tm].setdefault(v, []).append(item)
    return grouped


def extract_priority_basis(raw_briefing):
    """상세 메모(raw_briefing) 안에서 "[우선순위 근거]" 구역만 표시용으로 추출한다.

    저장/파싱 로직(parse_quick_text, save_report)과는 무관한 읽기 전용 표시 보조 함수다.
    DB에 별도 컬럼을 만들지 않고, 이미 저장된 raw_briefing 텍스트에서 그때그때 뽑아 보여준다.
    """
    if not raw_briefing:
        return None
    sections = {}
    current = None
    buffer = []
    for line in raw_briefing.splitlines():
        m = _SECTION_HEADER_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = m.group(1).strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections.get("우선순위 근거") or None


def _render_trade_mode_section(tm, grouped, rank_labels=None):
    """단타/스윙/공통 중 하나(tm)의 판정별 그룹을 "현재 컨테이너 안에" 그려 넣는다.

    호출부에서 `with column:` 등으로 컨테이너를 이미 지정한 상태에서 호출한다.
    rank_labels가 있으면(같은 report·시장·매매유형 안에서 score 기준으로 계산한 순위) 각 항목
    제목/카드 상단에 순위를 표시하고, 같은 판정 그룹 안에서는 score 높은 순으로 정렬한다.
    score가 없는 항목("미평가")은 그룹 맨 뒤로 간다. rank_labels가 없으면(예: 계산 실패) 기존
    순서를 그대로 쓴다 — 오래된 report에도 이 화면이 오류 없이 동작해야 한다.
    """
    rank_labels = rank_labels or {}
    st.markdown(f"## {TRADE_MODE_EMOJI.get(tm, '')} {_trade_mode_badge(tm)} {TRADE_MODE_HEADING[tm]}")
    for verdict in VERDICT_ORDER:
        bucket = grouped[tm].get(verdict, [])
        bucket = sorted(bucket, key=lambda it: -(it.get("score") or 0))
        st.markdown(f"#### {_verdict_badge(verdict)} ({len(bucket)}건)")
        if not bucket:
            st.caption("해당 없음")
            continue
        for item in bucket:
            label = item.get("stock_name") or item.get("ticker") or item.get("event_title") or "(제목 없음)"
            trade_mode = item.get("trade_mode") or "공통"
            rank_label = rank_labels.get(item.get("id"), "미평가")
            card_title = f"{_trade_mode_badge(trade_mode)} [{rank_label}] {label}"
            if item.get("event_title"):
                card_title += f" - {item['event_title']}"
            if item.get("score") is not None:
                card_title += f" ({item['score']:.0f}점)"
            with st.expander(card_title):
                score_val = item.get("score")
                score_text = "-점" if score_val is None else f"{score_val:.0f}점"
                st.markdown(
                    f"**[{trade_mode} {rank_label}] {label} / {score_text} / "
                    f"{item.get('buy_confirmed') or '미확정'}**"
                )
                st.write(f"매매유형: {trade_mode}")
                st.write(f"판단: {_display_verdict_name(item.get('verdict'))}")
                st.write(f"종목코드: {item.get('ticker') or '-'}")
                st.write(f"시장: {item.get('market') or '-'}")
                st.write(f"신호 종류: {_display_signal_type(item.get('signal_type') or '-')}")
                st.write(f"주식시장 판단: {item.get('stock_market_judgment') or '-'}")
                st.write(f"베팅시장 판단: {item.get('betting_market_judgment') or '-'}")
                st.write(f"점수: {'-' if score_val is None else score_text}")
                st.write(f"점수 근거: {item.get('score_reason') or '-'}")
                top_reason = item.get("top_candidate_reason") or item.get("score_reason") or "-"
                st.write(f"1순위 후보 근거: {top_reason}")
                st.write(f"감점 이유: {item.get('penalty_reason') or '-'}")
                st.write(f"매수 확정 여부: {item.get('buy_confirmed') or '-'}")
                st.write(f"매수 확정 조건: {item.get('buy_confirm_condition') or '-'}")


def render_report_detail(report, show_raw_briefing=False):
    """report 1건의 한줄 요약 + report_items(판정 5종별 그룹, 최신 카드형)를 표시한다."""
    st.caption(
        f"저장 시각: {report['saved_at']}  |  시장: {report['market_scope']}  |  "
        f"장 구분: {report['timing_class']}  |  판단 시점: {report.get('briefing_stage') or '-'}"
    )
    st.markdown("**오늘 요약**")
    st.write(report["day_conclusion"])

    priority_basis = extract_priority_basis(report.get("raw_briefing"))
    if priority_basis:
        st.markdown("**우선순위 근거**")
        st.write(priority_basis)

    if show_raw_briefing:
        with st.expander("판단 근거 보기"):
            st.write(report["raw_briefing"])

    items = db.get_report_items(report["id"])

    if not items:
        st.info("종목별 기록은 없습니다. 오늘 요약만 저장되었습니다.")
        return

    st.markdown("---")
    st.markdown("**종목별 기록**")
    st.info("1순위 후보는 매수 확정이 아니라, 현재 기록 기준에서 가장 먼저 확인할 후보입니다.")
    st.caption(
        "정렬 기준: 단타와 스윙을 먼저 나누고, 각 관점 안에서 1순위 후보 → 관찰 후보 → "
        "재확인 → 보류 → 제외 순서로 표시합니다. 같은 그룹 안에서는 위에 있을수록 우선순위가 "
        "높으며, 입력 순서를 유지합니다."
    )

    grouped = _group_items_by_trade_mode_and_verdict(report["id"])
    rank_labels = _compute_score_rank_labels(items)

    # 좌우 2단: 왼쪽=스윙 관점, 오른쪽=단타 관점 (넓은 화면 기준. 좁은 화면에서는
    # Streamlit이 자동으로 세로 배치한다). 공통은 두 컬럼 아래에 별도 영역으로 표시.
    col_swing, col_danta = st.columns(2, gap="large")
    with col_swing:
        _render_trade_mode_section("스윙", grouped, rank_labels)
    with col_danta:
        _render_trade_mode_section("단타", grouped, rank_labels)

    common_count = sum(len(items) for items in grouped["공통"].values())
    if common_count > 0:
        st.markdown("---")
        _render_trade_mode_section("공통", grouped, rank_labels)


tab_today, tab_perf, tab_kr, tab_us, tab_archive, tab_paste, tab_next = st.tabs(
    ["오늘 요약", "결과 확인", "한국장", "미국장", "지난 기록 보기", "새 기록 입력", "추가 기능"]
)

SNAPSHOT_STOCKS = [
    {"name": "삼성전자", "ticker": "005930.KS", "sector": "반도체"},
    {"name": "SK하이닉스", "ticker": "000660.KS", "sector": "반도체"},
    {"name": "현대차", "ticker": "005380.KS", "sector": "자동차"},
    {"name": "기아", "ticker": "000270.KS", "sector": "자동차"},
    {"name": "현대모비스", "ticker": "012330.KS", "sector": "자동차부품"},
    {"name": "한화오션", "ticker": "042660.KS", "sector": "조선"},
    {"name": "한화에어로스페이스", "ticker": "012450.KS", "sector": "방산"},
]
SNAPSHOT_FIELDS = ["current", "prev_close", "open", "high", "low", "turnover", "market_cap"]
SNAPSHOT_NAME_TO_TICKER = {s["name"]: s["ticker"] for s in SNAPSHOT_STOCKS}

# 미국장 스윙 기록 바로 저장 전용 기본 종목(8개). 한국 종목(SNAPSHOT_STOCKS)과는
# ticker가 겹치지 않으므로 같은 session_state 키 규칙(snap_{ticker}_{field})을 그대로 쓴다.
US_SNAPSHOT_STOCKS = [
    {"name": "TSLA", "ticker": "TSLA", "sector": "미국-자동차"},
    {"name": "AMD", "ticker": "AMD", "sector": "미국-반도체"},
    {"name": "AVGO", "ticker": "AVGO", "sector": "미국-반도체"},
    {"name": "META", "ticker": "META", "sector": "미국-빅테크"},
    {"name": "GOOGL", "ticker": "GOOGL", "sector": "미국-빅테크"},
    {"name": "AAPL", "ticker": "AAPL", "sector": "미국-빅테크"},
    {"name": "NVDA", "ticker": "NVDA", "sector": "미국-반도체"},
    {"name": "MSFT", "ticker": "MSFT", "sector": "미국-빅테크"},
]


def _get_snapshot_value(ticker, field):
    """아직 위젯이 생성되기 전이라도, session_state에 있는 현재 입력값을 미리 읽는다.

    "계산 결과 요약표"를 "종목별 상세 입력 카드"보다 화면 위쪽에 배치하기 위한 방법이다.
    (Streamlit 위젯 값은 key로 session_state에 남으므로, 위젯 호출 순서와 무관하게
    같은 key로 먼저 읽을 수 있다.)
    """
    return st.session_state.get(f"snap_{ticker}_{field}", 0.0)


def _parse_snapshot_number(text):
    """쉼표 포함 숫자 문자열("309,000")을 float로 변환한다. 실패하면 None."""
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_quick_snapshot_text(text):
    """"종목명 / 현재가 / 전일종가 / 시가 / 장중고가 / 장중저가 / 거래대금 / 시가총액" 줄을 파싱한다.

    등록된 7개 종목명과 일치하는 줄만 반영한다. 모르는 종목명이나 숫자로 해석할 수 없는
    값은 경고 문자열로만 남기고(자동판정/저장과 무관), 해당 줄은 반영하지 않는다.
    """
    updates = {}
    warnings = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("/")]
        if len(parts) != 8:
            warnings.append(f"형식을 인식하지 못했습니다(종목명 포함 8개 필드 필요): {line}")
            continue
        name = parts[0]
        ticker = SNAPSHOT_NAME_TO_TICKER.get(name)
        if not ticker:
            warnings.append(f"'{name}'은(는) 등록된 7개 종목이 아니라 건너뜁니다.")
            continue
        values = {}
        line_ok = True
        for field, raw in zip(SNAPSHOT_FIELDS, parts[1:]):
            num = _parse_snapshot_number(raw)
            if num is None:
                warnings.append(f"'{name}'의 값 '{raw}'을(를) 숫자로 인식하지 못했습니다.")
                line_ok = False
                break
            values[field] = num
        if line_ok:
            updates[ticker] = values
    return updates, warnings


def _safe_pct_diff(a, b):
    """(a-b)/b*100. b가 0/None이면 None(계산 불가)."""
    if not b:
        return None
    return (a - b) / b * 100


def _safe_ratio_pct(a, b):
    """a/b*100. b가 0/None이면 None(계산 불가)."""
    if not b:
        return None
    return a / b * 100


def _fmt_pct(value):
    return "-" if value is None else f"{value:.2f}"


def _fmt_signed_pct(value):
    """부호를 명시해서 보여준다 (+3.36% / -4.92%). 브리핑 초안 문장용."""
    return "-" if value is None else f"{value:+.2f}%"


def classify_snapshot_temp(high_drop_pct, open_pos_pct, turnover_ratio_pct):
    """장중 스냅샷 계산값으로 임시 매매유형/판정을 만든다.

    자동판정이 아니라 브리핑 초안을 만들기 위한 참고용 임시 규칙이다. 실제 판정은
    사람이 브리핑 붙여넣기 탭에서 최종 확인/수정한 뒤 저장한다.
    - 고점대비 -3% 이하 -> 단타 / 보류
    - 시가대비 0% 이상 이고 시총대비 거래대금 1% 이상 -> 스윙 / 관심 후보
    - 그 외 -> 공통 / 감시
    """
    if high_drop_pct is not None and high_drop_pct <= -3:
        return "단타", "보류"
    if (
        open_pos_pct is not None
        and open_pos_pct >= 0
        and turnover_ratio_pct is not None
        and turnover_ratio_pct >= 1
    ):
        return "스윙", "관심 후보"
    return "공통", "감시"


def _reports_signature():
    return tuple(sorted(r["id"] for r in db.list_reports()))


@st.cache_data(ttl=600, show_spinner="결과 확인 데이터 조회 중 (시세 조회)...")
def _cached_verification_rows(signature):
    return performance.build_verification_rows()


@st.cache_data(ttl=600, show_spinner="오늘 관심 종목 없음 평가 조회 중 (시세 조회)...")
def _cached_no_recommendation_rows(signature):
    return performance.build_no_recommendation_rows()

with tab_today:
    st.subheader("오늘 요약")

    latest = db.get_latest_report()
    if latest is None:
        st.info("저장된 기록이 없습니다.")
    else:
        render_report_detail(latest)

with tab_paste:
    st.subheader("새 기록 입력")

    st.session_state.setdefault("form_version", 0)
    st.session_state.setdefault("draft_items", [])
    st.session_state.setdefault("item_seq", 0)

    fv = st.session_state.form_version

    with st.expander("쉽게 붙여넣는 입력칸 (입력 내용 정리)", expanded=False):
        st.caption(
            "[기본]/[오늘의 결론]/[종목] 형식으로 통째로 붙여넣고 '입력 내용 정리'를 누르면 "
            "시장·판단 시점·오늘 요약·종목별 기록이 한 번에 채워집니다. "
            "입력 형식의 '시장 범위:', '브리핑 단계:', '신호 분류:', '[오늘의 결론]' 표기는 "
            "그대로 입력해야 인식됩니다. "
            "종목 줄 구분자는 '/' 이며 세 형식을 지원합니다: "
            "6개 필드(기존) = 종목명 / 종목코드 / 시장 / 판정 / 신호 종류 / 판단 이유, "
            "7개 필드(신규, 매매유형 포함) = 종목명 / 종목코드 / 시장 / 매매유형 / 판정 / 신호 종류 / 판단 이유, "
            "13개 필드(확장, 판단 설명 포함) = 위 7개 필드 + 점수 / 점수 근거 / 1순위 후보 근거 / "
            "감점 이유 / 매수 확정 여부 / 매수 확정 조건."
        )
        quick_text = st.text_area(
            "쉽게 붙여넣는 입력칸",
            key=f"quick_text_{fv}",
            height=220,
            placeholder=(
                "[기본]\n시장 범위: KR\n브리핑 단계: 08:30 개장 전 예측\n신호 분류: 재확인 신호\n\n"
                "[오늘의 결론]\n...\n\n[종목]\n"
                "삼성전자 / 005930.KS / KR / 추천 후보 / 재확인 신호 / 실적 기대\n"
                "삼성전자 / 005930.KS / KR / 단타 / 보류(선반영) / 재확인 신호 / 장중 고점 대비 밀림"
            ),
        )
        if st.button("입력 내용 정리", key=f"quick_fill_{fv}"):
            parsed = parse_quick_text(quick_text)

            if parsed["market_scope"]:
                st.session_state[f"market_scope_{fv}"] = parsed["market_scope"]
            if parsed["briefing_stage"]:
                st.session_state[f"briefing_stage_{fv}"] = parsed["briefing_stage"]
            st.session_state[f"day_conclusion_{fv}"] = parsed["day_conclusion"]
            st.session_state[f"raw_briefing_{fv}"] = quick_text

            st.session_state.draft_items = []
            for item in parsed["items"]:
                st.session_state.item_seq += 1
                item_id = st.session_state.item_seq
                st.session_state.draft_items.append(item_id)
                prefix = f"item_{fv}_{item_id}_"
                st.session_state[prefix + "event_title"] = item["event_title"]
                st.session_state[prefix + "ticker"] = item["ticker"]
                st.session_state[prefix + "stock_name"] = item["stock_name"]
                st.session_state[prefix + "market"] = item["market"]
                st.session_state[prefix + "item_timing_class"] = "(미지정)"
                st.session_state[prefix + "trade_mode"] = item["trade_mode"]
                st.session_state[prefix + "verdict"] = item["verdict"]
                st.session_state[prefix + "signal_type"] = item["signal_type"]
                st.session_state[prefix + "score"] = item["score"] or 0.0
                st.session_state[prefix + "score_reason"] = item["score_reason"] or ""
                st.session_state[prefix + "top_candidate_reason"] = item["top_candidate_reason"] or ""
                st.session_state[prefix + "penalty_reason"] = item["penalty_reason"] or ""
                st.session_state[prefix + "buy_confirmed"] = item["buy_confirmed"]
                st.session_state[prefix + "buy_confirm_condition"] = item["buy_confirm_condition"]

            st.session_state[f"quick_fill_count_{fv}"] = len(parsed["items"])
            st.session_state[f"quick_fill_warnings_{fv}"] = parsed["warnings"]
            st.rerun()

        if st.session_state.get(f"quick_fill_count_{fv}") is not None:
            st.success(f"입력 내용 정리 완료: 종목별 기록 {st.session_state[f'quick_fill_count_{fv}']}개 생성됨")
        for w in st.session_state.get(f"quick_fill_warnings_{fv}", []):
            st.warning(w)

    st.markdown("---")

    market_scope = st.selectbox(
        "시장", db.MARKET_SCOPE_CHOICES, key=f"market_scope_{fv}"
    )
    briefing_stage = st.selectbox(
        "판단 시점", db.BRIEFING_STAGE_CHOICES, key=f"briefing_stage_{fv}"
    )
    day_conclusion = st.text_area(
        "오늘 요약",
        key=f"day_conclusion_{fv}",
        placeholder="예: 오늘은 추천 종목 없음. 관망 권장.",
    )
    raw_briefing = st.text_area(
        "판단 근거", key=f"raw_briefing_{fv}", height=200
    )
    st.caption("장 구분은 저장 시각을 기준으로 자동으로 정해집니다. 직접 입력하지 않습니다.")

    st.markdown("---")

    items_data = []
    remove_id = None
    with st.expander(
        f"고급 수동 입력 ({len(st.session_state.draft_items)}개 종목별 기록, 0개도 저장 가능)",
        expanded=False,
    ):
        st.caption("쉽게 붙여넣는 입력칸으로 자동 채운 종목도 여기서 직접 수정/추가/삭제할 수 있습니다.")

        if st.button("+ 종목별 기록 추가", key=f"add_item_{fv}"):
            st.session_state.item_seq += 1
            st.session_state.draft_items.append(st.session_state.item_seq)
            st.rerun()

        for item_id in st.session_state.draft_items:
            prefix = f"item_{fv}_{item_id}_"

            title_trade_mode = st.session_state.get(prefix + "trade_mode", "공통")
            title_stock_name = (
                st.session_state.get(prefix + "stock_name")
                or st.session_state.get(prefix + "ticker")
                or f"기록 #{item_id}"
            )
            title_verdict_raw = st.session_state.get(prefix + "verdict", db.VERDICT_CHOICES[0])
            title_event = st.session_state.get(prefix + "event_title", "")
            card_title = f"{_trade_mode_badge(title_trade_mode)} {_verdict_badge(title_verdict_raw)} {title_stock_name}"
            if title_event:
                card_title += f" - {title_event}"

            with st.expander(card_title, expanded=False):
                header_col, del_col = st.columns([6, 1])
                header_col.markdown(f"종목별 기록 #{item_id}")
                if del_col.button("삭제", key=prefix + "delete"):
                    remove_id = item_id

                c1, c2, c3 = st.columns(3)
                event_title = c1.text_input("판단 이유", key=prefix + "event_title")
                ticker = c2.text_input("종목코드", key=prefix + "ticker")
                stock_name = c3.text_input("종목명", key=prefix + "stock_name")

                c4, c5 = st.columns(2)
                market = c4.selectbox("시장", db.ITEM_MARKET_CHOICES, key=prefix + "market")
                item_timing_class_raw = c5.selectbox(
                    "항목 장 구분 (선택)",
                    ["(미지정)"] + db.TIMING_CLASS_CHOICES,
                    key=prefix + "item_timing_class",
                )

                st.caption("주식시장 근거")
                b1, b2, b3 = st.columns(3)
                basis_a = b1.text_input(
                    "가격·수급 근거",
                    key=prefix + "basis_a",
                    placeholder="예: 장중 고점 대비 밀림, 시가 위/아래, 프로그램 매수/매도",
                )
                basis_b = b2.text_input(
                    "거래대금·시총 근거",
                    key=prefix + "basis_b",
                    placeholder="예: 거래대금 강함, 시총 대비 거래대금 높음, 수급 탄력성",
                )
                basis_c = b3.text_input(
                    "섹터·지수 근거",
                    key=prefix + "basis_c",
                    placeholder="예: 자동차 섹터 동반 강세, KOSPI 대비 강함, 반도체 약세",
                )

                st.caption("베팅시장(예측시장) 근거")
                g1, g2, g3 = st.columns(3)
                basis_ga = g1.text_input(
                    "직접 예측시장 근거",
                    key=prefix + "basis_ga",
                    placeholder="예: Polymarket/Kalshi 확률 변화, 선거·금리·관세 이벤트 확률",
                )
                basis_na = g2.text_input(
                    "간접 시장가격 근거",
                    key=prefix + "basis_na",
                    placeholder="예: 나스닥100 선물, SOXX/SMH, 달러원, 금리, 유가, 비트코인",
                )
                basis_da = g3.text_input(
                    "이벤트·정책 근거",
                    key=prefix + "basis_da",
                    placeholder="예: 실적 발표, 수주, 정책 발표, 관세, 금리 이벤트",
                )

                j1, j2 = st.columns(2)
                stock_judgment = j1.text_area("주식시장 판단", key=prefix + "stock_judgment")
                betting_judgment = j2.text_area("베팅시장 판단", key=prefix + "betting_judgment")

                st.caption("판단 설명 (점수/근거/매수 확정 — 비워두면 기본값으로 저장됩니다)")
                p1, p2, p3 = st.columns(3)
                score = p1.number_input("점수", value=0.0, step=1.0, key=prefix + "score")
                score_reason = p2.text_input(
                    "점수 근거", key=prefix + "score_reason", placeholder="예: 시가 위 유지 + 거래대금 증가"
                )
                top_candidate_reason = p3.text_input(
                    "1순위 후보 근거", key=prefix + "top_candidate_reason", placeholder="예: 섹터 내 거래대금 우위"
                )
                p4, p5, p6 = st.columns(3)
                penalty_reason = p4.text_input(
                    "감점 이유", key=prefix + "penalty_reason", placeholder="예: 고점 대비 일부 밀림"
                )
                buy_confirmed = p5.selectbox(
                    "매수 확정 여부", ["미확정", "확정"], key=prefix + "buy_confirmed"
                )
                buy_confirm_condition = p6.text_input(
                    "매수 확정 조건", key=prefix + "buy_confirm_condition", placeholder="예: 종가 강세 유지 필요"
                )

                v1, v2, v3 = st.columns(3)
                trade_mode = v1.selectbox(
                    "매매유형", db.TRADE_MODE_CHOICES, key=prefix + "trade_mode"
                )
                verdict = v2.selectbox("판정", db.VERDICT_CHOICES, key=prefix + "verdict")
                signal_type = v3.selectbox(
                    "신호 종류", db.SIGNAL_TYPE_CHOICES, key=prefix + "signal_type"
                )

                items_data.append(
                    {
                        "event_title": event_title,
                        "ticker": ticker,
                        "stock_name": stock_name,
                        "market": market,
                        "item_timing_class": None if item_timing_class_raw == "(미지정)" else item_timing_class_raw,
                        "stock_market_basis_a": basis_a,
                        "stock_market_basis_b": basis_b,
                        "stock_market_basis_c": basis_c,
                        "betting_basis_ga": basis_ga,
                        "betting_basis_na": basis_na,
                        "betting_basis_da": basis_da,
                        "stock_market_judgment": stock_judgment,
                        "betting_market_judgment": betting_judgment,
                        "verdict": verdict,
                        "signal_type": signal_type,
                        "trade_mode": trade_mode,
                        "score": score or None,
                        "score_reason": score_reason,
                        "top_candidate_reason": top_candidate_reason,
                        "penalty_reason": penalty_reason,
                        "buy_confirmed": buy_confirmed,
                        "buy_confirm_condition": buy_confirm_condition,
                    }
                )

        if remove_id is not None:
            st.session_state.draft_items.remove(remove_id)
            st.rerun()

    st.markdown("---")
    if st.button("기록 저장", type="primary", key=f"save_{fv}"):
        if not day_conclusion.strip():
            st.error("오늘 요약을 입력해주세요.")
        else:
            final_raw_briefing = raw_briefing if raw_briefing.strip() else day_conclusion
            items_to_save = [
                item
                for item in items_data
                if (item.get("event_title") or "").strip()
                or (item.get("ticker") or "").strip()
                or (item.get("stock_name") or "").strip()
            ]
            report_id = db.save_report(
                market_scope=market_scope,
                day_conclusion=day_conclusion,
                raw_briefing=final_raw_briefing,
                items=items_to_save,
                briefing_stage=briefing_stage,
            )
            st.success(f"기록 저장 완료: 종목별 기록 {len(items_to_save)}개 저장됨 (report_id={report_id})")
            st.session_state["tab_paste_last_saved_id"] = report_id
            st.session_state.draft_items = []
            st.session_state.form_version += 1
            st.rerun()

    if st.session_state.get("tab_paste_last_saved_id"):
        last_saved_report = db.get_report(st.session_state["tab_paste_last_saved_id"])
        if last_saved_report:
            st.markdown("---")
            st.markdown("#### 방금 저장한 기록")
            render_report_detail(last_saved_report)

with tab_kr:
    st.subheader("한국장")
    st.caption(
        "한국장은 현재가, 시가, 고가, 저가, 거래대금을 보고 관심 종목을 비교하는 화면입니다 "
        "(단타/스윙 둘 다 확인). 자동매매나 매수 추천이 아닙니다."
    )
    st.info("이 탭의 입력값은 저장되지 않습니다. 화면에서 계산만 확인하는 1차 버전입니다.")

    # 1. 시장 분위기 (기본값은 전부 "미입력" — 위험해 보이는 강함/상승/순매수 기본값 금지)
    # 이 값은 미국장 탭의 시장 분위기 점수/상한 계산에서도 그대로 사용됩니다.
    st.markdown("### 시장 분위기")
    e1, e2, e3 = st.columns(3)
    nq_change = e1.number_input(
        "나스닥100 선물 등락률(%)", value=0.0, step=0.1, format="%.2f", key="snap_nq_change"
    )
    soxx_dir = e2.selectbox("SOXX/SMH 방향", ["미입력", "강함", "보통", "약함"], key="snap_soxx_dir")
    usdkrw_dir = e3.selectbox("달러/원 방향", ["미입력", "상승", "하락", "보합"], key="snap_usdkrw_dir")

    e4, e5, e6 = st.columns(3)
    kospi200_futures_dir = e4.selectbox(
        "KOSPI200 선물 방향", ["미입력", "상승", "하락", "보합"], key="snap_kospi200_dir"
    )
    foreign_futures_dir = e5.selectbox(
        "외국인 선물 방향", ["미입력", "순매수", "순매도", "중립"], key="snap_foreign_dir"
    )
    program_dir = e6.selectbox(
        "프로그램 수급 방향", ["미입력", "순매수", "순매도", "중립"], key="snap_program_dir"
    )

    # 2. 간편 스냅샷 입력 (붙여넣기 자동 채우기)
    st.markdown("---")
    with st.expander("주가 직접 붙여넣기", expanded=False):
        st.caption(
            "형식: 종목명 / 현재가 / 전일종가 / 시가 / 장중고가 / 장중저가 / 거래대금 / 시가총액 "
            "(등록된 7개 종목만 인식하며, 숫자에 쉼표가 있어도 처리됩니다.)"
        )
        quick_snapshot_text = st.text_area(
            "주가 직접 붙여넣기",
            key="snap_quick_text",
            height=140,
            placeholder=(
                "삼성전자 / 309,000 / 300,000 / 320,000 / 325,000 / 308,000 / 2,500,000,000,000 / 1,840,000,000,000,000\n"
                "기아 / 157,100 / 152,000 / 153,000 / 161,000 / 155,000 / 800,000,000,000 / 61,500,000,000,000"
            ),
        )
        if st.button("붙여넣은 주가 채우기", key="snap_quick_fill"):
            updates, warnings = parse_quick_snapshot_text(quick_snapshot_text)
            for ticker, values in updates.items():
                for field, value in values.items():
                    st.session_state[f"snap_{ticker}_{field}"] = value
            st.session_state["snap_quick_fill_count"] = len(updates)
            st.session_state["snap_quick_fill_warnings"] = warnings
            st.rerun()

        if st.session_state.get("snap_quick_fill_count") is not None:
            st.success(f"붙여넣은 주가 채우기 완료: 종목 {st.session_state['snap_quick_fill_count']}개 반영됨")
        for w in st.session_state.get("snap_quick_fill_warnings", []):
            st.warning(w)

    # 2-1. 기본값 자동 채우기 (yfinance 우선, FinanceDataReader 보조 — 저장 없음)
    st.markdown("---")
    st.caption(
        "아래 버튼은 네이버 등에서 직접 찾아 입력하지 않도록, yfinance(우선)/FinanceDataReader(보조)로 "
        "가장 최근 완료된 거래일 기준 시세를 조회해 채워줍니다. 실시간 시세가 아니며, 거래대금·"
        "시가총액은 근사값입니다. 조회 결과는 저장되지 않고 화면 계산에만 쓰입니다."
    )
    if st.button("오늘 주가 자동 채우기", key="snap_auto_fill"):
        fetch_results = {}
        for s in SNAPSHOT_STOCKS:
            result = price_data.get_snapshot_defaults(s["ticker"])
            fetch_results[s["ticker"]] = result
            if result.get("ok"):
                prefix = f"snap_{s['ticker']}_"
                st.session_state[prefix + "current"] = result["current"]
                st.session_state[prefix + "prev_close"] = result["prev_close"]
                st.session_state[prefix + "open"] = result["open"]
                st.session_state[prefix + "high"] = result["high"]
                st.session_state[prefix + "low"] = result["low"]
                st.session_state[prefix + "turnover"] = result["turnover"]
                st.session_state[prefix + "market_cap"] = result["market_cap"] or 0.0
        st.session_state["snap_auto_fill_results"] = fetch_results
        st.rerun()

    if st.session_state.get("snap_auto_fill_results"):
        auto_fill_results = st.session_state["snap_auto_fill_results"]
        success_names = [s["name"] for s in SNAPSHOT_STOCKS if auto_fill_results.get(s["ticker"], {}).get("ok")]
        if success_names:
            st.success(f"오늘 주가 자동 입력 완료: {', '.join(success_names)}")
        for s in SNAPSHOT_STOCKS:
            r = auto_fill_results.get(s["ticker"], {})
            if not r.get("ok"):
                st.warning(f"{s['name']}: 조회 실패 - {r.get('error', '알 수 없는 오류')}")
        st.caption("거래대금·시가총액은 근사값입니다 (거래량×현재가, 상장주식수×현재가). 정확한 실제 값이 아닙니다.")

    # 3. 계산 결과 요약표 (입력 카드보다 위에 표시 — session_state를 위젯 생성 전에 미리 읽음)
    st.markdown("---")
    st.markdown("### 오늘 주가 계산 결과")
    st.caption(
        "메모는 자동판정이 아니라 참고용 경고 문구입니다 (예: 고점 대비 밀림률이 -3% 이하이면 "
        "'고점 대비 밀림 큼'). 관심 후보/관찰 후보 같은 판정은 이 화면에서 만들지 않습니다."
    )

    result_rows = []
    snapshot_calc_data = []
    for s in SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            # 입력값이 하나도 없는 종목은 계산 결과표에서 제외한다(0으로 나오는 것 방지).
            # 종목별 상세 입력 카드에는 그대로 남아 있어 언제든 입력할 수 있다.
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        low_recover_pct = _safe_pct_diff(current, low)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)

        memos = []
        if high_drop_pct is not None and high_drop_pct <= -3:
            memos.append("고점 대비 밀림 큼")
        if open_pos_pct is not None:
            memos.append("시가 위 유지" if open_pos_pct >= 0 else "시가 아래")
        if turnover_ratio_pct is not None and turnover_ratio_pct >= 5:
            memos.append("시총 대비 거래대금 확인 필요")

        external_good = _snapshot_external_good()
        danta_score = compute_snapshot_reference_score(
            "단타", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, external_good
        )
        swing_score = compute_snapshot_reference_score(
            "스윙", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, external_good
        )

        result_rows.append(
            {
                "종목명": s["name"],
                "섹터": s["sector"],
                "현재가": current,
                "전일대비(%)": _fmt_pct(change_pct),
                "시가대비(%)": _fmt_pct(open_pos_pct),
                "고점대비(%)": _fmt_pct(high_drop_pct),
                "저점대비(%)": _fmt_pct(low_recover_pct),
                "시총대비 거래대금(%)": _fmt_pct(turnover_ratio_pct),
                "단기 관심 점수": danta_score,
                "며칠 관심 점수": swing_score,
                "메모": "; ".join(memos) if memos else "-",
            }
        )
        snapshot_calc_data.append(
            {
                "name": s["name"],
                "ticker": s["ticker"],
                "change_pct": change_pct,
                "open_pos_pct": open_pos_pct,
                "high_drop_pct": high_drop_pct,
                "turnover_ratio_pct": turnover_ratio_pct,
                "memos": memos,
                "danta_score": danta_score,
                "swing_score": swing_score,
            }
        )

    if not result_rows:
        st.info("아직 입력된 종목이 없습니다. 아래 '종목별 상세 입력' 카드나 '주가 직접 붙여넣기'로 값을 넣어주세요.")
    else:
        st.dataframe(pd.DataFrame(result_rows), width="stretch", hide_index=True)
        st.caption("시총 대비 거래대금 '확인 필요' 기준은 5% 이상(1차 버전 임시 기준)입니다.")
        st.caption(
            "점수는 자동매수 신호가 아니라 장중 후보 비교용 참고 점수입니다. 외부 환경과 "
            "종가 품질이 미입력인 경우 최고점은 제한됩니다."
        )

        st.info(
            "이 문장은 매수 추천이 아니라, 새 기록 입력칸에 붙여넣기 위한 초안입니다. "
            "필요하면 판단 문구를 수정한 뒤 저장하세요."
        )
        if st.button("기록 문장 만들기", key="snap_make_briefing_text"):
            lines = [
                "[기본]",
                "시장 범위: KR",
                "시점 구분: 장중",
                "브리핑 단계: 장중 스냅샷 기반 판단",
                "신호 분류: 재확인 신호",
                "",
                "[오늘의 결론]",
                "오늘 주가 확인 기준: 입력된 종목의 고점 대비 밀림, 시가 대비 위치, 시총 대비 거래대금을 "
                "기준으로 기록 입력용 초안을 생성함. 자동매수 추천이 아님.",
                "",
                "[종목]",
            ]
            for calc in snapshot_calc_data:
                trade_mode, verdict = classify_snapshot_temp(
                    calc["high_drop_pct"], calc["open_pos_pct"], calc["turnover_ratio_pct"]
                )
                if trade_mode == "단타":
                    basis = (
                        f"고점대비 {_fmt_signed_pct(calc['high_drop_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"{calc['memos'][0] if calc['memos'] else '고점 대비 밀림 큼'}"
                    )
                elif trade_mode == "스윙":
                    basis = (
                        f"전일대비 {_fmt_signed_pct(calc['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(calc['turnover_ratio_pct'])}"
                    )
                else:
                    basis = (
                        f"전일대비 {_fmt_signed_pct(calc['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(calc['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(calc['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(calc['turnover_ratio_pct'])}"
                    )
                lines.append(
                    f"{calc['name']} / {calc['ticker']} / KR / {trade_mode} / {verdict} / 재확인 신호 / {basis}"
                )
            st.session_state["snap_briefing_text"] = "\n".join(lines)

        if st.session_state.get("snap_briefing_text"):
            st.text_area(
                "기록 문장 (복사해서 '새 기록 입력' 탭의 쉽게 붙여넣는 입력칸에 붙여넣으세요)",
                value=st.session_state["snap_briefing_text"],
                height=160,
                key="snap_briefing_text_display",
            )

        # 3-2. 국내장 기록 바로 저장 (새 기록 입력 화면을 거치지 않고 이 화면에서 바로 저장)
        # 한국 종목(SNAPSHOT_STOCKS)만 대상으로 한다 — 미국 종목은 여기 나오지 않는다.
        st.markdown("---")
        st.markdown("### 국내장 기록 바로 저장")
        st.caption(
            "위 표의 한국 종목 7개만 대상으로 시장 KR / 단타·스윙을 함께 저장합니다. "
            "버튼을 누르면 바로 저장하지 않고 먼저 저장 전 확인 미리보기를 보여줍니다."
        )
        if st.button("국내장 기록 바로 저장", key="kr_quick_save", disabled=not snapshot_calc_data):
            kr_preview_rows = [
                {
                    "name": calc["name"],
                    "ticker": calc["ticker"],
                    "danta_score": calc["danta_score"],
                    "swing_score": calc["swing_score"],
                    "danta_verdict": _kr_danta_verdict(calc["danta_score"]),
                    "swing_verdict": _kr_swing_verdict(calc["swing_score"]),
                    "change_pct": calc["change_pct"],
                    "open_pos_pct": calc["open_pos_pct"],
                    "high_drop_pct": calc["high_drop_pct"],
                    "turnover_ratio_pct": calc["turnover_ratio_pct"],
                }
                for calc in snapshot_calc_data
            ]
            danta_counts = {"감시": 0, "확인 필요": 0, "보류(선반영)": 0}
            swing_counts = {"추천 후보": 0, "감시": 0, "보류(선반영)": 0}
            for row in kr_preview_rows:
                danta_counts[row["danta_verdict"]] = danta_counts.get(row["danta_verdict"], 0) + 1
                swing_counts[row["swing_verdict"]] = swing_counts.get(row["swing_verdict"], 0) + 1
            kr_day_conclusion = (
                f"오늘 주가 확인 기반 국내장 자동 기록: 총 {len(kr_preview_rows)}종목. "
                f"단타 {_display_verdict_name('감시')} {danta_counts['감시']}개/"
                f"{_display_verdict_name('확인 필요')} {danta_counts['확인 필요']}개/"
                f"{_display_verdict_name('보류(선반영)')} {danta_counts['보류(선반영)']}개, "
                f"스윙 {_display_verdict_name('추천 후보')} {swing_counts['추천 후보']}개/"
                f"{_display_verdict_name('감시')} {swing_counts['감시']}개/"
                f"{_display_verdict_name('보류(선반영)')} {swing_counts['보류(선반영)']}개. "
                "점수는 자동매수 신호가 아니라 오늘 주가 확인 표를 바탕으로 한 참고용 판단입니다."
            )
            kr_basis_text = "\n".join(
                f"{row['name']}: 단기 관심 점수 {row['danta_score']}점 -> 단타 {_display_verdict_name(row['danta_verdict'])}, "
                f"며칠 관심 점수 {row['swing_score']}점 -> 스윙 {_display_verdict_name(row['swing_verdict'])}"
                for row in kr_preview_rows
            )
            st.session_state["kr_quick_preview_rows"] = kr_preview_rows
            st.session_state["kr_quick_day_conclusion"] = kr_day_conclusion
            st.session_state["kr_quick_basis_text"] = kr_basis_text

        if st.session_state.get("kr_quick_preview_rows"):
            kr_preview_rows = st.session_state["kr_quick_preview_rows"]
            preview_timing_class = db.classify_timing_class(datetime.now())
            st.markdown("#### 저장 전 확인 미리보기")
            st.write("시장: KR")
            st.write(f"장 구분: {preview_timing_class}")
            st.write("판단 시점: 오늘 주가 확인 기반 국내장 판단")
            st.write(f"오늘 요약: {st.session_state['kr_quick_day_conclusion']}")
            st.write("판단 근거:")
            st.code(st.session_state["kr_quick_basis_text"])

            st.markdown("저장될 종목 목록")
            kr_danta_rank = _rank_scores([(row["ticker"], row["danta_score"]) for row in kr_preview_rows])
            kr_swing_rank = _rank_scores([(row["ticker"], row["swing_score"]) for row in kr_preview_rows])
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "종목명": row["name"],
                            "단기 관심 점수": row["danta_score"],
                            "단타 순위": kr_danta_rank.get(row["ticker"], "미평가"),
                            "며칠 관심 점수": row["swing_score"],
                            "스윙 순위": kr_swing_rank.get(row["ticker"], "미평가"),
                            "단타 판단": _display_verdict_name(row["danta_verdict"]),
                            "스윙 판단": _display_verdict_name(row["swing_verdict"]),
                        }
                        for row in kr_preview_rows
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

            kcol1, kcol2 = st.columns(2)
            if kcol1.button("이 내용으로 저장", type="primary", key="kr_quick_confirm_save"):
                items_to_save = []
                for row in kr_preview_rows:
                    basis_a = (
                        f"전일대비 {_fmt_signed_pct(row['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(row['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(row['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(row['turnover_ratio_pct'])}"
                    )
                    danta_verdict_display = _display_verdict_name(row["danta_verdict"])
                    swing_verdict_display = _display_verdict_name(row["swing_verdict"])
                    danta_score_reason = _kr_score_reason_text(
                        row["change_pct"], row["open_pos_pct"], row["turnover_ratio_pct"]
                    )
                    danta_penalty_reason = _kr_penalty_reason_text(row["high_drop_pct"], row["change_pct"])
                    buy_confirm_condition_text = (
                        "진입가, 손절가, 매수 비중, 다음날 확인 조건이 모두 정해져야 매수 확정으로 "
                        "전환됩니다. 이 화면은 아직 이 값을 입력받지 않으므로 항상 '미확정'으로 표시됩니다."
                    )
                    items_to_save.append(
                        {
                            "event_title": (
                                f"{row['name']} 단기 관심 점수 {row['danta_score']}점 - "
                                f"단타 {danta_verdict_display}"
                            ),
                            "ticker": row["ticker"],
                            "stock_name": row["name"],
                            "market": "KR",
                            "stock_market_basis_a": basis_a,
                            "stock_market_judgment": (
                                f"단기 관심 점수 {row['danta_score']}점 -> 단타 {danta_verdict_display}"
                            ),
                            "verdict": row["danta_verdict"],
                            "signal_type": "재확인 신호",
                            "trade_mode": "단타",
                            "score": row["danta_score"],
                            "score_reason": danta_score_reason,
                            "top_candidate_reason": _kr_top_candidate_reason_text(
                                "단타", row["danta_score"], danta_verdict_display
                            ),
                            "penalty_reason": danta_penalty_reason,
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": buy_confirm_condition_text,
                        }
                    )
                    swing_score_reason = _kr_score_reason_text(
                        row["change_pct"], row["open_pos_pct"], row["turnover_ratio_pct"]
                    )
                    swing_penalty_reason = _kr_penalty_reason_text(row["high_drop_pct"], row["change_pct"])
                    items_to_save.append(
                        {
                            "event_title": (
                                f"{row['name']} 며칠 관심 점수 {row['swing_score']}점 - "
                                f"스윙 {swing_verdict_display}"
                            ),
                            "ticker": row["ticker"],
                            "stock_name": row["name"],
                            "market": "KR",
                            "stock_market_basis_a": basis_a,
                            "stock_market_judgment": (
                                f"며칠 관심 점수 {row['swing_score']}점 -> 스윙 {swing_verdict_display}"
                            ),
                            "verdict": row["swing_verdict"],
                            "signal_type": "재확인 신호",
                            "trade_mode": "스윙",
                            "score": row["swing_score"],
                            "score_reason": swing_score_reason,
                            "top_candidate_reason": _kr_top_candidate_reason_text(
                                "스윙", row["swing_score"], swing_verdict_display
                            ),
                            "penalty_reason": swing_penalty_reason,
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": buy_confirm_condition_text,
                        }
                    )
                kr_report_id = db.save_report(
                    market_scope="KR",
                    day_conclusion=st.session_state["kr_quick_day_conclusion"],
                    raw_briefing=st.session_state["kr_quick_basis_text"],
                    items=items_to_save,
                    briefing_stage="오늘 주가 확인 기반 국내장 판단",
                )
                st.session_state.pop("kr_quick_preview_rows", None)
                st.session_state.pop("kr_quick_day_conclusion", None)
                st.session_state.pop("kr_quick_basis_text", None)
                st.success(
                    "국내장 기록 저장 완료. 오늘 요약, 지난 기록 보기, 결과 확인에서 확인할 수 있습니다. "
                    f"(report_id={kr_report_id})"
                )
            if kcol2.button("취소", key="kr_quick_cancel_preview"):
                st.session_state.pop("kr_quick_preview_rows", None)
                st.session_state.pop("kr_quick_day_conclusion", None)
                st.session_state.pop("kr_quick_basis_text", None)

    # 4. 종목별 상세 입력 카드 (기본 접힘)
    st.markdown("---")
    st.markdown("### 종목별 상세 입력")
    st.caption("카드를 펼치면 직접 숫자를 입력/수정할 수 있습니다. 0은 '입력 안 함'으로 취급합니다.")

    for s in SNAPSHOT_STOCKS:
        prefix = f"snap_{s['ticker']}_"
        with st.expander(f"{s['name']} / {s['sector']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.number_input("현재가", value=0.0, step=100.0, key=prefix + "current")
            c2.number_input("전일종가", value=0.0, step=100.0, key=prefix + "prev_close")
            c3.number_input("시가", value=0.0, step=100.0, key=prefix + "open")
            c4.number_input("장중고가", value=0.0, step=100.0, key=prefix + "high")

            c5, c6, c7 = st.columns(3)
            c5.number_input("장중저가", value=0.0, step=100.0, key=prefix + "low")
            c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
            c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")

with tab_us:
    st.subheader("미국장")
    st.caption(
        "미국장은 스윙 전용 흐름입니다. 미국 기본 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT)만 "
        "대상으로 하며, 한국 종목은 여기서 다루지 않습니다. 시장 분위기 입력은 '한국장' 탭에서 설정한 "
        "값을 그대로 사용합니다."
    )
    st.info("이 탭의 입력값은 저장되지 않습니다(저장은 아래 '미국장 스윙 기록 바로 저장'을 눌렀을 때만 됩니다).")

    # 1. 미국장 기본 종목 불러오기 (TSLA/AMD/AVGO/META/GOOGL/AAPL/NVDA/MSFT — 저장 없음)
    st.markdown("---")
    st.caption(
        "미국장 스윙 기록 바로 저장에 쓸 미국 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT) "
        "시세를 yfinance(우선)/FinanceDataReader(보조)로 불러옵니다. 조회 결과는 저장되지 않고 화면 계산에만 쓰입니다."
    )
    if st.button("미국장 기본 종목 불러오기", key="us_stock_auto_fill"):
        us_fetch_results = {}
        for s in US_SNAPSHOT_STOCKS:
            result = price_data.get_snapshot_defaults(s["ticker"])
            us_fetch_results[s["ticker"]] = result
            if result.get("ok"):
                prefix = f"snap_{s['ticker']}_"
                st.session_state[prefix + "current"] = result["current"]
                st.session_state[prefix + "prev_close"] = result["prev_close"]
                st.session_state[prefix + "open"] = result["open"]
                st.session_state[prefix + "high"] = result["high"]
                st.session_state[prefix + "low"] = result["low"]
                st.session_state[prefix + "turnover"] = result["turnover"]
                st.session_state[prefix + "market_cap"] = result["market_cap"] or 0.0
        st.session_state["us_stock_auto_fill_results"] = us_fetch_results
        st.rerun()

    if st.session_state.get("us_stock_auto_fill_results"):
        us_auto_fill_results = st.session_state["us_stock_auto_fill_results"]
        us_success_names = [
            s["name"] for s in US_SNAPSHOT_STOCKS if us_auto_fill_results.get(s["ticker"], {}).get("ok")
        ]
        if us_success_names:
            st.success(f"미국장 기본 종목 불러오기 완료: {', '.join(us_success_names)}")
        for s in US_SNAPSHOT_STOCKS:
            r = us_auto_fill_results.get(s["ticker"], {})
            if not r.get("ok"):
                st.warning(f"{s['name']}: 조회 실패 - {r.get('error', '알 수 없는 오류')}")

    # 2. 미국장 스윙 기록 바로 저장 (새 기록 입력 화면을 거치지 않고 이 화면에서 바로 저장)
    # 한국 종목(SNAPSHOT_STOCKS)과는 별도로, 미국장 기본 종목(US_SNAPSHOT_STOCKS)만 대상으로 한다.
    us_snapshot_calc_data = []
    for s in US_SNAPSHOT_STOCKS:
        ticker = s["ticker"]
        current = _get_snapshot_value(ticker, "current")
        prev_close = _get_snapshot_value(ticker, "prev_close")
        open_price = _get_snapshot_value(ticker, "open")
        high = _get_snapshot_value(ticker, "high")
        low = _get_snapshot_value(ticker, "low")
        turnover = _get_snapshot_value(ticker, "turnover")
        market_cap = _get_snapshot_value(ticker, "market_cap")

        if not any([current, prev_close, open_price, high, low]):
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)
        material_memo = (st.session_state.get(f"snap_{ticker}_material_memo", "") or "").strip()

        breakdown = compute_us_swing_breakdown(
            s["name"], change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, material_memo
        )
        breakdown["ticker"] = ticker
        breakdown["change_pct"] = change_pct
        breakdown["open_pos_pct"] = open_pos_pct
        breakdown["high_drop_pct"] = high_drop_pct
        breakdown["turnover_ratio_pct"] = turnover_ratio_pct
        us_snapshot_calc_data.append(breakdown)

    st.markdown("---")
    st.markdown("### 미국장 스윙 기록 바로 저장")
    st.caption(
        "미국장 기본 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT)만 대상으로 전부 "
        "시장 US / 스윙으로 저장합니다 (단타는 만들지 않습니다). 버튼을 누르면 바로 저장하지 않고 "
        "먼저 저장 전 확인 미리보기(점수 근거표 포함)를 보여줍니다."
    )
    if not us_snapshot_calc_data:
        st.info("미국장 스윙 기록을 저장하려면 먼저 미국장 종목 데이터를 불러와야 합니다.")
    if st.button("미국장 스윙 기록 바로 저장", key="us_swing_quick_save", disabled=not us_snapshot_calc_data):
        preview_rows = us_snapshot_calc_data
        counts = {"추천 후보": 0, "감시": 0, "보류(선반영)": 0}
        for row in preview_rows:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        day_conclusion_text = (
            f"미국장 마감 후 스윙 판단 자동 기록: 총 {len(preview_rows)}종목 "
            f"({_display_verdict_name('추천 후보')} {counts['추천 후보']}개, "
            f"{_display_verdict_name('감시')} {counts['감시']}개, "
            f"{_display_verdict_name('보류(선반영)')} {counts['보류(선반영)']}개). "
            "점수는 자동매수 신호가 아니라 종목별 점수 근거표를 바탕으로 한 참고용 판단입니다."
        )
        basis_text = "\n".join(
            f"{row['name']}: 총점 {row['total_score']:.0f}점 -> {row['tier_label']} "
            f"(저장 판정: {_display_verdict_name(row['verdict'])})"
            for row in preview_rows
        )
        st.session_state["us_swing_preview_rows"] = preview_rows
        st.session_state["us_swing_day_conclusion"] = day_conclusion_text
        st.session_state["us_swing_basis_text"] = basis_text

    if st.session_state.get("us_swing_preview_rows"):
        preview_rows = st.session_state["us_swing_preview_rows"]
        st.markdown("#### 저장 전 확인 미리보기")
        st.write("시장: US")
        st.write("장 구분: 장마감")
        st.write("판단 시점: 미국장 마감 후 스윙 판단")
        st.write(f"오늘 요약: {st.session_state['us_swing_day_conclusion']}")
        st.write("판단 근거:")
        st.code(st.session_state["us_swing_basis_text"])

        st.markdown("저장될 종목 목록 (점수 근거표)")
        us_swing_rank = _rank_scores([(row["ticker"], row["total_score"]) for row in preview_rows])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "종목명": row["name"],
                        "총점": row["total_score"],
                        "스윙 순위": us_swing_rank.get(row["ticker"], "미평가"),
                        "판단": row["tier_label"],
                        "상승률 점수": row["upside_score"],
                        "종가 위치 점수": row["close_pos_score"],
                        "시장 분위기 점수": row["mood_score"],
                        "재료 점수": row["material_score"],
                        "거래/탄력 점수": row["momentum_score"],
                        "위험 감점": row["risk_score"],
                        "1순위 근거": row["priority_reason"],
                        "감점 이유": row["deduction_reason"],
                        "매수 확정 여부": row["buy_confirmed"],
                        "매수 확정 조건": row["buy_confirm_condition"],
                    }
                    for row in preview_rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        st.markdown("종목별 점수 근거 문장")
        for row in preview_rows:
            with st.expander(f"{row['name']} 총점 {row['total_score']:.0f}점 ({row['tier_label']})"):
                st.text(_us_swing_narrative_text(row))

        pcol1, pcol2 = st.columns(2)
        if pcol1.button("이 내용으로 저장", type="primary", key="us_swing_confirm_save"):
            items_to_save = [
                {
                    "event_title": f"{row['name']} 총점 {row['total_score']:.0f}점 - {row['tier_label']}",
                    "ticker": row["ticker"],
                    "stock_name": row["name"],
                    "market": "US",
                    "stock_market_basis_a": (
                        f"전일대비 {_fmt_signed_pct(row['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(row['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(row['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(row['turnover_ratio_pct'])}"
                    ),
                    "stock_market_basis_b": (
                        f"상승률 {row['upside_score']:.0f}/20, 종가 위치 {row['close_pos_score']:.0f}/20, "
                        f"시장 분위기 {row['mood_score']:.0f}/15, 재료 {row['material_score']:.0f}/20, "
                        f"거래/탄력 {row['momentum_score']:.0f}/15, 위험 감점 {row['risk_score']:.0f}, "
                        f"총점 {row['total_score']:.0f}/100"
                    ),
                    "stock_market_judgment": _us_swing_narrative_text(row),
                    "verdict": row["verdict"],
                    "signal_type": "재확인 신호",
                    "trade_mode": "스윙",
                    "score": row["total_score"],
                    "score_reason": f"{row['upside_note']} + {row['close_pos_note']} + {row['momentum_note']}",
                    "top_candidate_reason": row["priority_reason"],
                    "penalty_reason": row["deduction_reason"],
                    "buy_confirmed": "미확정",
                    "buy_confirm_condition": row["buy_confirm_condition"],
                }
                for row in preview_rows
            ]
            us_raw_briefing = "\n\n".join(_us_swing_narrative_text(row) for row in preview_rows)
            us_report_id = db.save_report(
                market_scope="US",
                day_conclusion=st.session_state["us_swing_day_conclusion"],
                raw_briefing=us_raw_briefing,
                items=items_to_save,
                briefing_stage="미국장 마감 후 스윙 판단",
                timing_class="장마감",
            )
            st.session_state.pop("us_swing_preview_rows", None)
            st.session_state.pop("us_swing_day_conclusion", None)
            st.session_state.pop("us_swing_basis_text", None)
            st.success(f"미국장 스윙 기록 저장 완료 (report_id={us_report_id})")
        if pcol2.button("취소", key="us_swing_cancel_preview"):
            st.session_state.pop("us_swing_preview_rows", None)
            st.session_state.pop("us_swing_day_conclusion", None)
            st.session_state.pop("us_swing_basis_text", None)

    # 3. 종목별 상세 입력 카드 (기본 접힘)
    st.markdown("---")
    st.markdown("### 종목별 상세 입력")
    st.caption("카드를 펼치면 직접 숫자를 입력/수정할 수 있습니다. 0은 '입력 안 함'으로 취급합니다.")

    for s in US_SNAPSHOT_STOCKS:
        prefix = f"snap_{s['ticker']}_"
        with st.expander(f"{s['name']} / {s['sector']}", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.number_input("현재가", value=0.0, step=1.0, key=prefix + "current")
            c2.number_input("전일종가", value=0.0, step=1.0, key=prefix + "prev_close")
            c3.number_input("시가", value=0.0, step=1.0, key=prefix + "open")
            c4.number_input("장중고가", value=0.0, step=1.0, key=prefix + "high")

            c5, c6, c7 = st.columns(3)
            c5.number_input("장중저가", value=0.0, step=1.0, key=prefix + "low")
            c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
            c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")
            st.text_input(
                "재료 메모 (선택, 없으면 재료 점수는 낮은 기본값으로 처리됩니다)",
                key=prefix + "material_memo",
                placeholder="예: 로보택시 기대감, AI 실적 발표, 신제품 발표 등",
            )

with tab_archive:
    st.subheader("지난 기록 보기")

    with st.expander("찾아보기", expanded=False):
        fcol1, fcol2 = st.columns(2)
        filter_date_from = fcol1.date_input(
            "시작 날짜", value=None, key="filter_date_from"
        )
        filter_date_to = fcol2.date_input(
            "끝 날짜", value=None, key="filter_date_to"
        )

        filter_market_scope = st.multiselect(
            "시장", db.MARKET_SCOPE_CHOICES, key="filter_market_scope", placeholder="선택하세요"
        )
        filter_timing_class = st.multiselect(
            "장 구분", db.TIMING_CLASS_CHOICES, key="filter_timing_class", placeholder="선택하세요"
        )
        filter_verdict = st.multiselect(
            "판단", VERDICT_ORDER, format_func=_display_verdict_name, key="filter_verdict", placeholder="선택하세요"
        )
        filter_briefing_stage = st.multiselect(
            "판단 시점", db.BRIEFING_STAGE_CHOICES, key="filter_briefing_stage", placeholder="선택하세요"
        )
        filter_signal_type = st.multiselect(
            "신호 종류", db.SIGNAL_TYPE_CHOICES, format_func=_display_signal_type, key="filter_signal_type", placeholder="선택하세요"
        )
        filter_day_conclusion_kw = st.text_input(
            "오늘 요약 검색", key="filter_day_conclusion"
        )
        filter_raw_briefing_kw = st.text_input(
            "판단 근거 검색", key="filter_raw_briefing"
        )

        if st.button("검색 조건 지우기", key="filter_reset"):
            for k in (
                "filter_date_from",
                "filter_date_to",
                "filter_market_scope",
                "filter_timing_class",
                "filter_verdict",
                "filter_briefing_stage",
                "filter_signal_type",
                "filter_day_conclusion",
                "filter_raw_briefing",
            ):
                st.session_state.pop(k, None)
            st.rerun()

    reports = db.search_reports(
        date_from=filter_date_from.isoformat() if filter_date_from else None,
        date_to=filter_date_to.isoformat() if filter_date_to else None,
        market_scopes=filter_market_scope or None,
        timing_classes=filter_timing_class or None,
        verdicts=filter_verdict or None,
        day_conclusion_keyword=filter_day_conclusion_kw or None,
        raw_briefing_keyword=filter_raw_briefing_kw or None,
        briefing_stages=filter_briefing_stage or None,
        signal_types=filter_signal_type or None,
    )

    total_all = len(db.list_reports())
    st.caption(f"전체 {total_all}건 중 {len(reports)}건 표시")

    if not reports:
        st.info("조건에 맞는 기록이 없습니다.")
    else:
        options = {
            r["id"]: f"{r['saved_at']} | {r['market_scope']} | {r['timing_class']} | "
            f"{(r['day_conclusion'] or '')[:30]}"
            for r in reports
        }

        # reports는 saved_at 기준 최신순으로 정렬되어 있으므로 첫 항목이 (현재 필터 기준) 최신이다.
        newest_in_view_id = next(iter(options))

        # DB 전체 기준 최신 report id. 저장 직후 이 값이 바뀌면 자동으로 그 report를 선택한다.
        global_latest = db.get_latest_report()
        global_latest_id = global_latest["id"] if global_latest else None
        prev_global_latest_id = st.session_state.get("archive_prev_global_latest_id")

        if "archive_select" not in st.session_state or st.session_state.get("archive_select") not in options:
            # 최초 진입, 혹은 필터링으로 기존 선택이 더 이상 옵션에 없음 -> 현재 목록의 최신으로
            st.session_state["archive_select"] = newest_in_view_id
        elif global_latest_id is not None and global_latest_id != prev_global_latest_id and global_latest_id in options:
            # 새 report가 저장됨(전역 최신 id가 바뀜) -> 그 report로 자동 전환
            st.session_state["archive_select"] = global_latest_id

        st.session_state["archive_prev_global_latest_id"] = global_latest_id

        selected_id = st.selectbox(
            "지난 기록 선택",
            options=list(options.keys()),
            format_func=lambda rid: options[rid],
            key="archive_select",
        )
        selected_report = db.get_report(selected_id)
        st.markdown("---")
        render_report_detail(selected_report, show_raw_briefing=True)

with tab_perf:
    st.subheader("결과 확인")
    st.caption(
        "저장한 종목 판단이 며칠 뒤 실제 수익률로 어떻게 나왔는지 확인하는 화면입니다."
    )

    perf_rows_all = _cached_verification_rows(_reports_signature())

    if not perf_rows_all:
        st.info("종목코드가 있는 종목별 기록이 없습니다.")
    else:
        # 1. 보기 범위 (기본값 "최신 기록만" — 과거 기록이 기본 화면에 섞이지 않게 한다)
        view_scope = st.radio(
            "볼 기록 범위",
            ["방금 저장한 기록만", "오늘 저장한 기록 전체", "모든 지난 기록"],
            horizontal=True,
            key="perf_view_scope",
        )
        latest_report = db.get_latest_report()
        latest_report_id = latest_report["id"] if latest_report else None
        today_str = datetime.now().strftime("%Y-%m-%d")

        if view_scope == "방금 저장한 기록만":
            scoped_rows = [row for row in perf_rows_all if row["report_id"] == latest_report_id]
        elif view_scope == "오늘 저장한 기록 전체":
            scoped_rows = [row for row in perf_rows_all if row["saved_at"].startswith(today_str)]
        else:
            scoped_rows = perf_rows_all

        # 종목명이 "-"인 행(제목 없이 저장된 항목)은 기본 화면에서 숨긴다.
        scoped_rows = [row for row in scoped_rows if row["stock_name"] and row["stock_name"] != "-"]

        # 필터 영역 (매매유형/판정 기본값은 항상 "전체")
        fcol1, fcol2 = st.columns(2)
        trade_mode_filter = fcol1.radio(
            "단기/며칠 구분",
            ["전체", "단타", "스윙", "공통"],
            horizontal=True,
            key="perf_trade_mode_filter",
        )
        verdict_filter_display = fcol2.radio(
            "판단 구분",
            ["전체", "1순위 후보", "관찰 후보", "재확인", "보류", "제외"],
            horizontal=True,
            key="perf_verdict_filter",
        )

        perf_rows = scoped_rows
        if trade_mode_filter != "전체":
            perf_rows = [row for row in perf_rows if row["trade_mode"] == trade_mode_filter]
        if verdict_filter_display != "전체":
            internal_verdict = REVERSE_VERDICT_DISPLAY[verdict_filter_display]
            perf_rows = [row for row in perf_rows if row["verdict"] == internal_verdict]

        if not perf_rows:
            st.info("이 조건에 해당하는 종목별 기록이 없습니다.")
        else:
            # 후보 점수 계산: 저장된 문장에서 숫자 근거를 뽑아 판정 기본점수에 가감한다.
            item_text_lookup = _build_item_text_lookup()
            scored_rows = []
            for row in perf_rows:
                key = (row["report_id"], row["ticker"], row["trade_mode"])
                basis_text = " ".join(item_text_lookup.get(key, []))
                basis = extract_score_basis_from_text(basis_text)
                candidate_score = compute_candidate_score(row["verdict"], row["trade_mode"], basis)
                scored_rows.append((candidate_score, row))

            # 후보 점수 기준 내림차순 정렬 (동점은 입력 순서 유지 — sorted()는 안정 정렬)
            scored_rows = sorted(scored_rows, key=lambda pair: -pair[0])

            # score(저장된 판단 설명 점수) 기준 순위: 같은 report·시장·매매유형 안에서만 비교한다.
            item_judgment_lookup = _build_item_judgment_lookup()
            score_rank_labels = _compute_score_rank_labels(item_judgment_lookup.values())

            # 4. compact 요약 (큰 숫자 4개만)
            status_counts = {
                "계산 완료": sum(1 for row in perf_rows if row["status"] == "계산 완료"),
                "대기": sum(1 for row in perf_rows if row["status"] == "대기"),
                "데이터 부족": sum(1 for row in perf_rows if row["status"] == "데이터 부족"),
            }
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("지금 보이는 종목", len(perf_rows))
            m2.metric("결과 기다리는 중", status_counts["대기"])
            m3.metric("결과 확인 완료", status_counts["계산 완료"])
            m4.metric("가격 데이터 부족", status_counts["데이터 부족"])
            st.caption("현재 필터 기준으로 표시되는 종목 수입니다.")

            # 판정별 개수는 작은 배지 텍스트로만 표시 (큰 숫자 아님)
            verdict_counts = {
                v: sum(1 for row in perf_rows if row["verdict"] == v) for v in VERDICT_ORDER
            }
            badge_line = "  ".join(
                f"{_verdict_badge(v)} {verdict_counts[v]}건" for v in VERDICT_ORDER
            )
            st.markdown(badge_line)

            if st.button("수익률 다시 확인", key="perf_refresh"):
                _cached_verification_rows.clear()
                _cached_no_recommendation_rows.clear()
                st.rerun()
            st.caption("저장된 종목의 1일·3일·5일·10일·20일 수익률을 다시 확인합니다.")

            # 5. 관심 점수 설명
            st.info(
                "관심 점수는 실제 상승확률이 아닙니다. 오늘 주가 위치, 고점 대비 밀림, 거래대금, "
                "섹터 흐름을 기준으로 관심 순서를 비교한 점수입니다. 100점은 반드시 오른다는 "
                "뜻이 아닙니다. 조건표상 거의 완벽한 경우에만 나오는 높은 관심 점수입니다. "
                "일반적인 1순위 후보는 80~90점대가 정상입니다."
            )

            # 6. 결과 표 (기본 컬럼만, 관심 점수 높은 순 정렬)
            table_rows = []
            for score, row in scored_rows:
                saved_item = item_judgment_lookup.get(
                    (row["report_id"], row["ticker"], row["trade_mode"]), {}
                )
                table_rows.append(
                    {
                        "종목명": row["stock_name"],
                        "순위": score_rank_labels.get(saved_item.get("id"), "미평가"),
                        "관심 점수": score,
                        "구분": row["trade_mode"],
                        "판단": _display_verdict_name(row["verdict"]),
                        "결과 상태": row["status"],
                        "판단 시점": row["briefing_stage"],
                        "1일 뒤": _fmt_pct(row["returns"][1]),
                        "3일 뒤": _fmt_pct(row["returns"][3]),
                        "5일 뒤": _fmt_pct(row["returns"][5]),
                        "10일 뒤": _fmt_pct(row["returns"][10]),
                        "20일 뒤": _fmt_pct(row["returns"][20]),
                    }
                )
            perf_df = pd.DataFrame(table_rows)
            st.dataframe(perf_df, width="stretch", hide_index=True)

            # 7. 엑셀용 파일 내보내기 (기본 표와 동일한 컬럼)
            st.download_button(
                "결과 표 엑셀로 저장",
                data=perf_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="결과확인.csv",
                mime="text/csv",
                key="perf_csv_download",
            )

            # 8. 자세히 보기 (숨긴 컬럼 포함 전체)
            with st.expander("자세히 보기"):
                detail_table_rows = []
                for score, row in scored_rows:
                    saved_item = item_judgment_lookup.get(
                        (row["report_id"], row["ticker"], row["trade_mode"]), {}
                    )
                    saved_score = saved_item.get("score")
                    detail_table_rows.append(
                        {
                            "종목명": row["stock_name"],
                            "순위": score_rank_labels.get(saved_item.get("id"), "미평가"),
                            "관심 점수": score,
                            "구분": row["trade_mode"],
                            "판단": _display_verdict_name(row["verdict"]),
                            "결과 상태": row["status"],
                            "판단 시점": row["briefing_stage"],
                            "저장 시각": row["saved_at"],
                            "신호 종류": _display_signal_type(row["signal_type"]),
                            "종목코드": row["ticker"],
                            "시장": row["market"],
                            "비교 기준": row["benchmark"],
                            "검증 시작가": row["entry_rule"],
                            "1일 뒤": _fmt_pct(row["returns"][1]),
                            "3일 뒤": _fmt_pct(row["returns"][3]),
                            "5일 뒤": _fmt_pct(row["returns"][5]),
                            "10일 뒤": _fmt_pct(row["returns"][10]),
                            "20일 뒤": _fmt_pct(row["returns"][20]),
                            "초과수익률(%, 5일 기준)": _fmt_pct(row["excess_return"]),
                            "판단 근거": saved_item.get("stock_market_judgment") or "-",
                            "점수": "-" if saved_score is None else f"{saved_score:.0f}",
                            "점수 근거": saved_item.get("score_reason") or "-",
                            "1순위 후보 근거": saved_item.get("top_candidate_reason") or "-",
                            "감점 이유": saved_item.get("penalty_reason") or "-",
                            "매수 확정 여부": saved_item.get("buy_confirmed") or "-",
                            "매수 확정 조건": saved_item.get("buy_confirm_condition") or "-",
                        }
                    )
                st.dataframe(pd.DataFrame(detail_table_rows), width="stretch", hide_index=True)

    st.markdown("---")
    with st.expander("오늘 관심 종목 없음 평가", expanded=False):
        st.caption(
            "종목 항목이 0개인 기록(오늘 추천 없음)에 대해, 그날 이후 기준지수가 올랐으면 "
            "기회비용, 내렸으면 위험회피 성공으로 표시합니다. 지수 상승만으로 실패 처리하지 않습니다."
        )

        no_rec_rows = _cached_no_recommendation_rows(_reports_signature())

        if not no_rec_rows:
            st.info("종목 항목이 0개인 기록이 없습니다.")
        else:
            no_rec_status_counts = {
                "계산 완료": sum(1 for row in no_rec_rows if row["status"] == "계산 완료"),
                "대기": sum(1 for row in no_rec_rows if row["status"] == "대기"),
                "데이터 부족": sum(1 for row in no_rec_rows if row["status"] == "데이터 부족"),
            }
            n1, n2, n3, n4 = st.columns(4)
            n1.metric("전체 대상 수", len(no_rec_rows))
            n2.metric("결과 확인 완료", no_rec_status_counts["계산 완료"])
            n3.metric("결과 기다리는 중", no_rec_status_counts["대기"])
            n4.metric("가격 데이터 부족", no_rec_status_counts["데이터 부족"])

            no_rec_table_rows = [
                {
                    "결과 상태": row["status"],
                    "저장 시각": row["saved_at"],
                    "오늘 요약": row["day_conclusion"],
                    "시장 구분": row["market_label"],
                    "비교 기준": row["benchmark"],
                    "검증 시작가": row["entry_rule"],
                    "1일 뒤": _fmt_pct(row["returns"][1]),
                    "3일 뒤": _fmt_pct(row["returns"][3]),
                    "5일 뒤": _fmt_pct(row["returns"][5]),
                    "10일 뒤": _fmt_pct(row["returns"][10]),
                    "20일 뒤": _fmt_pct(row["returns"][20]),
                    "판단(5일 기준)": row["judgment_5d"],
                }
                for row in no_rec_rows
            ]
            no_rec_df = pd.DataFrame(no_rec_table_rows)
            st.dataframe(no_rec_df, width="stretch", hide_index=True)
            st.download_button(
                "결과 표 엑셀로 저장 (오늘 관심 종목 없음 평가)",
                data=no_rec_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="관심종목없음평가.csv",
                mime="text/csv",
                key="no_rec_csv_download",
            )

with tab_next:
    st.subheader("추가 기능")
    st.markdown(
        """
- 결과 확인 통계/요약 (추후 별도 논의)
- 지난 기록 보기 필터/검색 고도화 (추후 별도 논의)
"""
    )
