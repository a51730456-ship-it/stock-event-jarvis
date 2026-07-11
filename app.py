"""자비스 주식 기록장 (Streamlit 앱): 오늘 요약 / 새 기록 입력 / 오늘 주가 확인 / 지난 기록 보기 / 결과 확인 / 추가 기능."""

import math
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

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


def create_daily_db_backup_once():
    """하루 1회, db/jarvis.sqlite3를 backups/jarvis_YYYYMMDD.sqlite3로 백업한다.

    sqlite3 내장 backup API를 사용한다(단순 파일 복사가 아님 — 연결이 열려 있는 상태에서도
    안전하게 백업할 수 있다). 같은 날짜 백업이 이미 있으면 건너뛰고 덮어쓰지 않는다.
    백업 실패는 앱을 죽이지 않고 경고만 표시한다. 원본 DB는 읽기만 하며 절대 수정하지 않는다.
    """
    try:
        db_path = db.DB_PATH
        if not db_path.exists():
            return
        backups_dir = db_path.parent.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backups_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.sqlite3"
        if backup_path.exists():
            return
        source_conn = sqlite3.connect(db_path)
        try:
            dest_conn = sqlite3.connect(backup_path)
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            source_conn.close()
    except Exception as e:
        st.warning(f"일일 DB 백업을 만들지 못했습니다(앱은 정상 동작합니다): {e}")


st.set_page_config(page_title="자비스 주식 기록장", layout="wide")

# 비밀번호 게이트: 인증 전에는 DB 초기화/자동 백업/앱 본문이 전혀 실행되지 않는다.
# 비밀번호는 .streamlit/secrets.toml의 APP_PASSWORD에서만 읽으며 코드에 직접 쓰지 않는다.
try:
    _app_password = st.secrets.get("APP_PASSWORD")
except Exception:
    _app_password = None

if not _app_password:
    st.warning("비밀번호 설정이 필요합니다. .streamlit/secrets.toml에 APP_PASSWORD를 설정하세요.")
    st.stop()

if not st.session_state.get("authenticated"):
    st.title("자비스 주식 기록장 - 로그인")
    _login_password_input = st.text_input("비밀번호", type="password", key="login_password_input")
    if st.button("로그인", key="login_submit"):
        if _login_password_input == _app_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

db.init_db()
create_daily_db_backup_once()

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif;
    }
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0f1117 !important;
    }
    h1 {
        font-size: 1.9rem !important;
    }
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: #9aa0a8 !important;
    }
    [data-testid="stExpander"] {
        background-color: rgba(23, 26, 33, 0.92);
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
    /* 표(데이터프레임) 가독성: 배경과 확실히 구분되는 어두운 카드톤 + 또렷한 글자 */
    [data-testid="stDataFrame"] {
        background-color: rgba(15, 18, 26, 0.96) !important;
        border: 1px solid #303642;
        border-radius: 10px;
        padding: 2px;
    }
    [data-testid="stDataFrame"] [role="row"] {
        min-height: 38px;
    }
    [data-testid="stDataFrame"] * {
        color: #e8ebf0 !important;
    }
    [data-testid="stMetric"] {
        background-color: rgba(23, 26, 33, 0.92);
        border: 1px solid #303642;
        border-radius: 10px;
        padding: 10px 14px;
    }
    button[kind="primary"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
    }
    /* v1.1 UX: 한국장/미국장 핵심 실행 버튼 강조 (조회/계산=주황, 저장=파랑).
       글자를 크고 굵게, 버튼 높이/클릭 영역도 키운다. */
    .st-key-snap_auto_fill button,
    .st-key-us_stock_auto_fill button,
    .st-key-kr_quick_save button,
    .st-key-kr_quick_confirm_save button,
    .st-key-us_swing_quick_save button,
    .st-key-us_final_save button,
    .st-key-snap_mood_auto_check button {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        padding: 14px 22px !important;
        min-height: 52px !important;
    }
    .st-key-snap_auto_fill button p,
    .st-key-us_stock_auto_fill button p,
    .st-key-kr_quick_save button p,
    .st-key-kr_quick_confirm_save button p,
    .st-key-us_swing_quick_save button p,
    .st-key-us_final_save button p,
    .st-key-snap_mood_auto_check button p {
        font-size: 1.15rem !important;
        font-weight: 800 !important;
    }
    .st-key-snap_auto_fill button,
    .st-key-us_stock_auto_fill button {
        background-color: #F97316 !important;
        border-color: #F97316 !important;
        color: #1a1a1a !important;
    }
    .st-key-kr_quick_save button,
    .st-key-kr_quick_confirm_save button,
    .st-key-us_swing_quick_save button,
    .st-key-us_final_save button {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        color: #ffffff !important;
    }
    .st-key-snap_mood_auto_check button {
        background-color: #0047AB !important;
        border-color: #0047AB !important;
        color: #ffffff !important;
    }
    .st-key-kr_auto_preview_run button {
        background-color: #FACC15 !important;
        border-color: #EAB308 !important;
        color: #1a1a1a !important;
        font-size: 1.22rem !important;
        font-weight: 900 !important;
        padding: 16px 24px !important;
        min-height: 58px !important;
    }
    .st-key-kr_auto_preview_run button p {
        font-size: 1.22rem !important;
        font-weight: 900 !important;
    }
    /* 상단 메뉴(탭) 확대 + 실제 고정(fixed) + 현재 선택 강조.
       주의: 이 구조에서 position:sticky는 조상 컨테이닝 블록 제약 때문에 실제로 고정되지
       않는다(브라우저에서 직접 확인, scrollTop 이동 시 sticky는 함께 스크롤되어 사라짐).
       position:fixed로 뷰포트 기준 고정하고, 바로 아래 탭 내용에 그만큼 padding-top을 더해
       가려지지 않게 한다. */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        position: fixed !important;
        top: 60px;
        left: 0;
        right: 0;
        width: 100%;
        z-index: 999999;
        background-color: rgba(2, 6, 23, 0.98);
        border-bottom: 1px solid #303642;
        padding: 10px 24px 6px 24px !important;
        gap: 6px;
    }
    [data-testid="stTabs"] [data-baseweb="tab-panel"] {
        padding-top: 64px !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        padding: 14px 20px !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"] p {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(37, 99, 235, 0.28);
        border-bottom: 4px solid #ff4b4b !important;
        border-radius: 6px 6px 0 0;
    }
    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div style="height:76px;"></div>', unsafe_allow_html=True)  # 고정 상단 메뉴에 가리지 않도록 여백 확보
# 한국장/미국장 사용 순서 안내는 각 화면(🇰🇷 한국장 먼저 확인 / 🇺🇸 미국장 스윙 확인) 상단의
# 짧은 안내문으로만 표시한다(예: "① ... → ② ... → ③ ..."). 여기(상단 공통 영역)에는
# 별도 카드를 두지 않아 본문보다 커 보이지 않게 한다.

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


def _kr_preview_reasons(change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, trade_mode):
    """국내장 바로 저장의 "저장 전 자동계산 미리보기" 전용: 시가 위치/고점 대비 밀림/거래대금
    신호를 수치 기반 문구로 만든다. 자동 점수 계산(_auto_fill_item_display)의 신호 카테고리
    판단 함수(_resolve_signal_category)를 그대로 재사용해 문구 스타일을 통일하고, 같은 의미의
    신호가 중복 표시되지 않게 한다. 반환: (score_reason, penalty_reason).
    """
    drop_from_high_pct = -high_drop_pct if high_drop_pct is not None else None
    high_drop_pos_threshold = 2 if trade_mode == "단타" else 3
    high_drop_neg_threshold = 5 if trade_mode == "단타" else 7
    liquidity_pos_threshold = 0.3 if trade_mode == "단타" else 0.2

    price_direction, price_phrase = _resolve_signal_category(
        "",
        [],
        [],
        open_pos_pct,
        lambda v: v > 0,
        lambda v: v < 0,
        lambda v: f"시가 대비 {v:+.2f}%로 시가 위 유지",
        lambda v: f"시가 대비 {v:+.2f}%로 시가 아래",
    )
    high_drop_direction, high_drop_phrase = _resolve_signal_category(
        "",
        [],
        [],
        drop_from_high_pct,
        lambda v, t=high_drop_pos_threshold: v <= t,
        lambda v, t=high_drop_neg_threshold: v >= t,
        lambda v: f"고점 대비 밀림 {v:.2f}%로 장중 생존력 양호",
        lambda v: f"고점 대비 {v:.2f}% 밀림",
    )
    liquidity_direction, liquidity_phrase = _resolve_signal_category(
        "",
        [],
        [],
        turnover_ratio_pct,
        lambda v, t=liquidity_pos_threshold: v >= t,
        lambda v: v < 0.1,
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 양호",
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 부족",
    )

    gains = []
    penalties = []
    if change_pct is not None:
        if change_pct > 0:
            gains.append(f"전일 대비 {change_pct:+.2f}%로 상승")
        elif change_pct < 0:
            penalties.append(f"전일 대비 {change_pct:+.2f}%로 하락")
    if price_direction == "positive":
        gains.append(price_phrase)
    elif price_direction == "negative":
        penalties.append(price_phrase)
    if high_drop_direction == "positive":
        gains.append(high_drop_phrase)
    elif high_drop_direction == "negative":
        penalties.append(high_drop_phrase)
    if liquidity_direction == "positive":
        gains.append(liquidity_phrase)
    elif liquidity_direction == "negative":
        penalties.append(liquidity_phrase)

    score_reason = ", ".join(gains) if gains else "특이 사항 없음"
    penalty_reason = ", ".join(penalties) if penalties else "없음"
    return score_reason, penalty_reason


def build_kr_stage2_preview():
    """한국장 2단계(관심점수/단타·스윙 판단/1순위 근거/감점 이유) 미리보기 전용 함수.

    session_state에 있는 현재 입력값(0단계 시장 분위기 자동 확인 결과, 1단계 오늘 주가 자동
    채우기 결과가 반영돼 있으면 그 값)을 그대로 읽어서 계산만 한다. DB에는 아무 것도 저장하지
    않으며, "③ 국내장 기록 바로 저장" 버튼의 저장 로직은 호출하지도, 그 결과에 영향을 주지도
    않는다 — 이 함수는 미리보기 전용이고 저장 버튼의 내부 로직과는 완전히 분리되어 있다.
    """
    stage0_reflected = bool(st.session_state.get("kr_mood_auto_results"))
    stage1_reflected = bool(st.session_state.get("snap_auto_fill_results"))

    external_good = _snapshot_external_good()
    rows = []
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
            continue

        change_pct = _safe_pct_diff(current, prev_close)
        open_pos_pct = _safe_pct_diff(current, open_price)
        high_drop_pct = _safe_pct_diff(current, high)
        turnover_ratio_pct = _safe_ratio_pct(turnover, market_cap)

        danta_score = compute_snapshot_reference_score(
            "단타", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, external_good
        )
        swing_score = compute_snapshot_reference_score(
            "스윙", change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, external_good
        )
        danta_verdict = _kr_danta_verdict(danta_score)
        swing_verdict = _kr_swing_verdict(swing_score)
        danta_score_reason, danta_penalty_reason = _kr_preview_reasons(
            change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, "단타"
        )
        swing_score_reason, swing_penalty_reason = _kr_preview_reasons(
            change_pct, open_pos_pct, high_drop_pct, turnover_ratio_pct, "스윙"
        )
        row_validation_errors = _validate_snapshot_price_inputs(
            s["name"], current, open_price, high, low,
            _get_snapshot_value(ticker, "volume"), turnover,
        )

        rows.append(
            {
                "name": s["name"],
                "ticker": ticker,
                "danta_score": danta_score,
                "swing_score": swing_score,
                "danta_verdict": danta_verdict,
                "swing_verdict": swing_verdict,
                "change_pct": change_pct,
                "open_pos_pct": open_pos_pct,
                "high_drop_pct": high_drop_pct,
                "turnover_ratio_pct": turnover_ratio_pct,
                "turnover": turnover,
                "danta_score_reason": danta_score_reason,
                "danta_penalty_reason": danta_penalty_reason,
                "swing_score_reason": swing_score_reason,
                "swing_penalty_reason": swing_penalty_reason,
                "danta_top_candidate_reason": _kr_top_candidate_reason_text(
                    "단타", danta_score, _display_verdict_name(danta_verdict)
                ),
                "swing_top_candidate_reason": _kr_top_candidate_reason_text(
                    "스윙", swing_score, _display_verdict_name(swing_verdict)
                ),
                "risk_fields": _collect_risk_fields(ticker),
                "danta_buy_confirm_condition": _auto_buy_confirm_condition("단타", "KR"),
                "swing_buy_confirm_condition": _auto_buy_confirm_condition("스윙", "KR"),
                "needs_confirmation": (danta_verdict == "확인 필요") or bool(row_validation_errors),
                "validation_errors": row_validation_errors,
            }
        )

    return {
        "rows": rows,
        "stage0_reflected": stage0_reflected,
        "stage1_reflected": stage1_reflected,
    }


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


def _item_combined_text(item):
    """report_item의 자유 서술 텍스트 필드를 전부 합친 문자열. 자동 점수 계산에서
    가점/감점 키워드를 찾는 용도로만 쓴다(저장/파싱 로직과는 무관)."""
    parts = [
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
    return " ".join(p for p in parts if p)


# 자동 점수 계산(1차 규칙 기반) 전용 상수. 실시간 시세 조회가 아니라, 이미 저장된
# 문장/판정/신호 분류/매매유형/시장 구분만으로 만드는 참고용 점수다.
_AUTO_SCORE_VERDICT_BASE = {
    "추천 후보": 70,  # 관심 후보
    "감시": 60,
    "확인 필요": 50,  # 기타/알 수 없음 취급
    "보류(선반영)": 45,
    "제외": 25,
}

_AUTO_SCORE_GAIN_KEYWORDS = {
    "종가 강함": 4,
    "종가 유지": 3,
    "섹터 강세": 4,
    "동반 강세": 3,
    "프로그램 매수": 5,
    "외국인 선물 매수": 5,
    "상대강도": 4,
    "주도주": 5,
    "대장주": 5,
}

_AUTO_SCORE_PENALTY_KEYWORDS = {
    "종가 약함": 4,
    "긴 윗꼬리": 4,
    "프로그램 매도": 5,
    "외국인 선물 매도": 5,
    "나스닥 선물 약세": 4,
    "보류": 3,
    "늦은 신호": 5,
    "추격 주의": 4,
    "확인 필요": 3,
}

# 단타/스윙 보정: 일반 목록과 겹치는 키워드는 가중치만 +-1 더하고, 스윙 전용 개념
# ("일봉 추세", "재료 지속성", "다음날 확인 필요", "거래대금은 큰데 주가 못 버팀")은
# 일반 목록에 없으므로 별도 점수를 준다. 시가 위치/고점 대비 밀림/거래대금은 아래
# "신호 카테고리"에서 텍스트·수치 신호를 하나로 합쳐 처리하므로 여기서는 빠진다
# (중복 가산/감점 방지).
_DANTA_EXTRA_GAIN_KEYWORDS = ["섹터 강세"]
_DANTA_EXTRA_PENALTY_KEYWORDS = ["추격 주의", "늦은 신호"]
_SWING_EXTRA_GAIN_KEYWORDS = ["종가 강함", "종가 유지"]
_SWING_EXTRA_PENALTY_KEYWORDS = ["긴 윗꼬리", "종가 약함"]
_SWING_ONLY_GAIN_KEYWORDS = {"일봉 추세": 4, "재료 지속성": 4}
_SWING_ONLY_PENALTY_KEYWORDS = {"다음날 확인 필요": 3, "거래대금은 큰데 주가 못 버팀": 5}

# 신호 카테고리(시가 위치/고점 대비 밀림/거래대금): 텍스트 키워드와 수치 계산값이 같은
# 의미를 가리키면 카테고리당 신호를 한 번만 반영한다. 수치 계산값이 있으면 그 값을
# 우선 쓰고(더 정확한 근거), 없으면 텍스트 키워드로 대체한다.
_PRICE_POSITION_POSITIVE_KEYWORDS = ["시가 위"]
_PRICE_POSITION_NEGATIVE_KEYWORDS = ["시가 아래"]
_HIGH_DROP_POSITIVE_KEYWORDS = ["고점 대비 밀림 적음"]
_HIGH_DROP_NEGATIVE_KEYWORDS = ["고점 대비 밀림"]
_LIQUIDITY_POSITIVE_KEYWORDS = ["거래대금 증가", "거래대금 유지", "거래대금 양호"]
_LIQUIDITY_NEGATIVE_KEYWORDS = ["거래대금 부족", "거래대금 감소"]

# 매매유형별 카테고리 점수(양수 가점, 음수 감점 크기). 카테고리당 이 점수를 한 번만
# 적용한다 — 0이면 그 매매유형에서는 해당 방향 신호를 점수에 반영하지 않는다(예: 스윙은
# 시가 부정/거래대금 부정에 대한 감점 규칙이 없음).
_CATEGORY_POINTS_BY_MODE = {
    "단타": {"price_position": (5, 6), "high_drop": (4, 6), "liquidity": (4, 4)},
    "스윙": {"price_position": (3, 0), "high_drop": (3, 5), "liquidity": (3, 0)},
    "__default__": {"price_position": (3, 4), "high_drop": (3, 5), "liquidity": (4, 4)},
}


def _find_keyword(text, keywords):
    for kw in keywords:
        if kw in text:
            return kw
    return None


def _resolve_signal_category(
    text, positive_keywords, negative_keywords, numeric_value, positive_fn, negative_fn, positive_phrase, negative_phrase
):
    """카테고리 하나(시가 위치/고점 대비 밀림/거래대금)의 텍스트+수치 신호를 하나로 합친다.
    수치 계산값이 있으면 그 값을 우선 쓰고(더 정확), 없으면 텍스트 키워드로 대체한다
    (같은 의미의 신호가 중복으로 가산/감점되지 않도록).
    반환: ("positive"|"negative"|None, 표시용 문구)
    """
    if numeric_value is not None:
        if positive_fn(numeric_value):
            return "positive", positive_phrase(numeric_value)
        if negative_fn(numeric_value):
            return "negative", negative_phrase(numeric_value)
        return None, None
    kw = _find_keyword(text, positive_keywords)
    if kw:
        return "positive", kw
    kw = _find_keyword(text, negative_keywords)
    if kw:
        return "negative", kw
    return None, None


def _auto_buy_confirm_condition(trade_mode, market):
    """매수 확정 조건 자동 문구. 매매유형(단타/스윙)을 먼저 보고, 공통/그 외면 시장(KR/US)
    기준 문구를 쓴다."""
    if trade_mode == "단타":
        return "시가 위 유지 + 고점 대비 밀림 제한 + 거래대금 유지 + 프로그램/외국인 수급 확인 필요"
    if trade_mode == "스윙":
        return "종가 강세 유지 + 거래대금 유지 + 다음날 흐름 재확인 필요"
    if market == "US":
        return "본장 거래량 + 섹터 동반 강도 + 프리/애프터 변동 확인 필요"
    return "장중 수급 + 섹터 강도 + 종가 위치 확인 필요"


def _auto_fill_item_display(item):
    """score/score_reason/penalty_reason/buy_confirmed/buy_confirm_condition 중 비어 있는
    값만 문장·판정·신호 분류·매매유형·시장 구분 기반 1차 규칙으로 자동 채워 화면 표시용으로
    반환한다. 실시간 가격 조회가 아니며, DB에는 다시 쓰지 않는다(표시 시점 계산).
    사용자가 이미 입력한 값은 그대로 쓰고 절대 덮어쓰지 않는다.

    반환: {"score", "score_is_auto", "score_reason", "penalty_reason",
           "buy_confirmed", "buy_confirm_condition"}
    """
    verdict = item.get("verdict")
    trade_mode = item.get("trade_mode") or "공통"
    market = item.get("market") or "KR"
    signal_type = item.get("signal_type")
    buy_confirmed = item.get("buy_confirmed") or "미확정"
    text = _item_combined_text(item)

    gains = []
    penalties = []
    for kw, pts in _AUTO_SCORE_GAIN_KEYWORDS.items():
        if kw in text:
            gains.append((kw, pts))
    for kw, pts in _AUTO_SCORE_PENALTY_KEYWORDS.items():
        if kw in text:
            penalties.append((kw, pts))
    if signal_type == "재확인 신호":
        gains.append(("재확인 신호", 3))
    if verdict == "추천 후보":
        gains.append(("관심 후보", 5))
    if trade_mode == "스윙":
        for kw, pts in _SWING_ONLY_GAIN_KEYWORDS.items():
            if kw in text:
                gains.append((kw, pts))
        for kw, pts in _SWING_ONLY_PENALTY_KEYWORDS.items():
            if kw in text:
                penalties.append((kw, pts))

    # 저장된 문장에 이미 담긴 전일대비/시가대비/고점대비/시총대비 거래대금 수치를 뽑아
    # price_vs_open_pct/drop_from_high_pct/trading_value_to_market_cap_pct 보조 신호로 쓴다.
    # drop_from_high_pct는 "밀린 정도(양수)"이므로 기존 high_drop_pct(음수 관례)의 부호를 뒤집는다.
    basis = extract_score_basis_from_text(text)
    price_vs_open_pct = basis.get("open_pos_pct")
    drop_from_high_pct = -basis["high_drop_pct"] if basis.get("high_drop_pct") is not None else None
    trading_value_to_market_cap_pct = basis.get("turnover_ratio_pct")

    # 시가 위치/고점 대비 밀림/거래대금: 텍스트 키워드와 수치 계산값이 같은 의미면
    # 카테고리당 신호를 한 번만 반영한다(중복 가산/감점 방지). 수치 계산값이 있으면
    # 그 값을 우선 쓴다(문구도 수치 기반이 우선).
    category_points = _CATEGORY_POINTS_BY_MODE.get(trade_mode, _CATEGORY_POINTS_BY_MODE["__default__"])
    high_drop_pos_threshold = 2 if trade_mode == "단타" else 3
    high_drop_neg_threshold = 5 if trade_mode == "단타" else 7
    liquidity_pos_threshold = 0.3 if trade_mode == "단타" else 0.2

    price_direction, price_phrase = _resolve_signal_category(
        text,
        _PRICE_POSITION_POSITIVE_KEYWORDS,
        _PRICE_POSITION_NEGATIVE_KEYWORDS,
        price_vs_open_pct,
        lambda v: v > 0,
        lambda v: v < 0,
        lambda v: f"시가 대비 {v:+.2f}%로 시가 위 유지",
        lambda v: f"시가 대비 {v:+.2f}%로 시가 아래",
    )
    high_drop_direction, high_drop_phrase = _resolve_signal_category(
        text,
        _HIGH_DROP_POSITIVE_KEYWORDS,
        _HIGH_DROP_NEGATIVE_KEYWORDS,
        drop_from_high_pct,
        lambda v, t=high_drop_pos_threshold: v <= t,
        lambda v, t=high_drop_neg_threshold: v >= t,
        lambda v: f"고점 대비 밀림 {v:.2f}%로 장중 생존력 양호",
        lambda v: f"고점 대비 {v:.2f}% 밀림",
    )
    liquidity_direction, liquidity_phrase = _resolve_signal_category(
        text,
        _LIQUIDITY_POSITIVE_KEYWORDS,
        _LIQUIDITY_NEGATIVE_KEYWORDS,
        trading_value_to_market_cap_pct,
        lambda v, t=liquidity_pos_threshold: v >= t,
        lambda v: v < 0.1,
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 양호",
        lambda v: f"시총 대비 거래대금 {v:.2f}%로 거래대금 부족",
    )

    pos_pts, neg_pts = category_points["price_position"]
    if price_direction == "positive" and pos_pts:
        gains.append((price_phrase, pos_pts))
    elif price_direction == "negative" and neg_pts:
        penalties.append((price_phrase, neg_pts))

    pos_pts, neg_pts = category_points["high_drop"]
    if high_drop_direction == "positive" and pos_pts:
        gains.append((high_drop_phrase, pos_pts))
    elif high_drop_direction == "negative" and neg_pts:
        penalties.append((high_drop_phrase, neg_pts))

    pos_pts, neg_pts = category_points["liquidity"]
    if liquidity_direction == "positive" and pos_pts:
        gains.append((liquidity_phrase, pos_pts))
    elif liquidity_direction == "negative" and neg_pts:
        penalties.append((liquidity_phrase, neg_pts))

    stored_score = item.get("score")
    score_is_auto = not stored_score  # None 또는 0이면 자동 계산 대상
    if score_is_auto:
        score = float(_AUTO_SCORE_VERDICT_BASE.get(verdict, 50))
        for _, pts in gains:
            score += pts
        for _, pts in penalties:
            score -= pts
        if trade_mode == "단타":
            for kw in _DANTA_EXTRA_GAIN_KEYWORDS:
                if kw in text:
                    score += 1
            for kw in _DANTA_EXTRA_PENALTY_KEYWORDS:
                if kw in text:
                    score -= 1
        elif trade_mode == "스윙":
            for kw in _SWING_EXTRA_GAIN_KEYWORDS:
                if kw in text:
                    score += 1
            for kw in _SWING_EXTRA_PENALTY_KEYWORDS:
                if kw in text:
                    score -= 1
        if buy_confirmed == "확정":
            score = max(score, 85)
        if verdict == "보류(선반영)":
            score = min(score, 60)
        if verdict == "제외":
            score = min(score, 35)
        score = int(round(max(0.0, min(score, 100.0))))
    else:
        score = stored_score

    score_reason = item.get("score_reason") or (
        " + ".join(kw for kw, _ in gains) if gains else "특이 사항 없음 (1차 규칙 기반 자동 계산)"
    )
    penalty_reason = item.get("penalty_reason") or (
        ", ".join(kw for kw, _ in penalties) if penalties else "특별한 감점 요인 없음 (1차 규칙 기반 자동 계산)"
    )
    buy_confirm_condition = item.get("buy_confirm_condition") or _auto_buy_confirm_condition(trade_mode, market)

    return {
        "score": score,
        "score_is_auto": score_is_auto,
        "score_reason": score_reason,
        "penalty_reason": penalty_reason,
        "buy_confirmed": buy_confirmed,
        "buy_confirm_condition": buy_confirm_condition,
    }


def _compute_score_rank_labels(items):
    """report_item dict 목록(같은 report일 수도, 여러 report가 섞여 있을 수도 있음)에서
    (report_id, market, trade_mode) 그룹별로 score 기준 순위를 매겨 item id -> 순위 라벨을 반환한다.

    한국장/미국장, 단타/스윙을 서로 섞지 않기 위해 report_id·market·trade_mode가 모두 같은
    항목끼리만 순위를 비교한다. score가 비어 있으면 _auto_fill_item_display()의 1차 규칙
    자동 계산값을 순위 계산에 쓰므로, 오래된 report도 순위가 매겨질 수 있다.
    """
    groups = {}
    for item in items:
        key = (item.get("report_id"), item.get("market") or "OTHER", item.get("trade_mode") or "공통")
        groups.setdefault(key, []).append(item)

    labels = {}
    for group_items in groups.values():
        pairs = [(it["id"], _auto_fill_item_display(it)["score"]) for it in group_items]
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
        bucket = sorted(bucket, key=lambda it: -_auto_fill_item_display(it)["score"])
        st.markdown(f"#### {_verdict_badge(verdict)} ({len(bucket)}건)")
        if not bucket:
            st.caption("해당 없음")
            continue
        for item in bucket:
            label = item.get("stock_name") or item.get("ticker") or item.get("event_title") or "(제목 없음)"
            trade_mode = item.get("trade_mode") or "공통"
            rank_label = rank_labels.get(item.get("id"), "미평가")
            auto_info = _auto_fill_item_display(item)
            auto_tag = " (자동계산)" if auto_info["score_is_auto"] else ""
            score_text = f"{auto_info['score']:.0f}점{auto_tag}"
            card_title = f"{_trade_mode_badge(trade_mode)} [{rank_label}] {label}"
            if item.get("event_title"):
                card_title += f" - {item['event_title']}"
            card_title += f" ({auto_info['score']:.0f}점){auto_tag}"
            top_reason = item.get("top_candidate_reason") or auto_info["score_reason"]
            with st.container(border=True):
                st.markdown(f"**{card_title}**")
                st.write(f"점수: {score_text}")
                st.write(f"점수 근거: {auto_info['score_reason']}")
                st.write(f"1순위 후보 근거: {top_reason}")
                st.write(f"감점 이유: {auto_info['penalty_reason']}")
                st.write(f"매수 확정 여부: {auto_info['buy_confirmed']}")
                with st.expander("전체 근거", expanded=False):
                    st.markdown(
                        f"**[{trade_mode} {rank_label}] {label} / {score_text} / "
                        f"{auto_info['buy_confirmed']}**"
                    )
                    st.write(f"매매유형: {trade_mode}")
                    st.write(f"판단: {_display_verdict_name(item.get('verdict'))}")
                    st.write(f"종목코드: {item.get('ticker') or '-'}")
                    st.write(f"시장: {item.get('market') or '-'}")
                    st.write(f"신호 종류: {_display_signal_type(item.get('signal_type') or '-')}")
                    st.write(f"주식시장 판단: {item.get('stock_market_judgment') or '-'}")
                    st.write(f"베팅시장 판단: {item.get('betting_market_judgment') or '-'}")
                    st.write(f"점수: {score_text}")
                    st.write(f"점수 근거: {auto_info['score_reason']}")
                    st.write(f"1순위 후보 근거: {top_reason}")
                    st.write(f"감점 이유: {auto_info['penalty_reason']}")
                    st.write(f"매수 확정 여부: {auto_info['buy_confirmed']}")
                    st.write(f"매수 확정 조건: {auto_info['buy_confirm_condition']}")


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


tab_kr, tab_us, tab_action, tab_review, tab_perf, tab_today, tab_archive, tab_paste, tab_next, tab_guide = st.tabs(
    [
        "🇰🇷 한국장 먼저 확인", "🇺🇸 미국장 스윙 확인", "③ 실제 행동·거래 종료", "④ 복기·통계", "저장 결과 확인", "오늘 저장 요약",
        "지난 기록 보기", "수동 기록 입력", "추가 기능", "사용법",
    ]
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
SNAPSHOT_FIELDS = ["current", "prev_close", "open", "high", "low", "turnover", "market_cap", "volume"]
SNAPSHOT_NAME_TO_TICKER = {s["name"]: s["ticker"] for s in SNAPSHOT_STOCKS}

# 사람이 보기 쉬운 "기준 이름" 정리(별칭/문서화용). 기존 session_state 키(snap_{ticker}_current 등)와
# 계산 변수 이름(open_pos_pct 등)은 그대로 두고 바꾸지 않는다 — 나중에 DB 저장이나 실제 시세 API를
# 연결할 때 이 기준 이름을 참고용으로 쓰기 위해 미리 정리만 해 둔다. 지금은 어떤 로직에도 쓰이지 않는다.
SNAPSHOT_FIELD_CANONICAL_NAMES = {
    "current": "current_price",
    "open": "open_price",
    "high": "high_price",
    "low": "low_price",
    "turnover": "trading_value",
    "market_cap": "market_cap",
    "volume": "volume",
}
SNAPSHOT_CALC_CANONICAL_NAMES = {
    "open_pos_pct": "price_vs_open_pct",
    "high_drop_pct": "drop_from_high_pct",
    "turnover_ratio_pct": "trading_value_to_market_cap_pct",
}

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

    기존 8개 필드(종목명 포함) 형식을 그대로 지원하고(거래량 없이도 동작), 맨 뒤에
    거래량을 추가한 9개 필드 형식도 함께 지원한다(선택 사항, 기존 형식은 깨지지 않는다).
    """
    updates = {}
    warnings = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("/")]
        if len(parts) not in (8, 9):
            warnings.append(f"형식을 인식하지 못했습니다(종목명 포함 8개 또는 9개 필드 필요): {line}")
            continue
        name = parts[0]
        ticker = SNAPSHOT_NAME_TO_TICKER.get(name)
        if not ticker:
            warnings.append(f"'{name}'은(는) 등록된 7개 종목이 아니라 건너뜁니다.")
            continue
        # 9개 필드면 거래량까지, 8개 필드면 기존 7개 필드까지만 사용한다(하위 호환).
        fields_to_use = SNAPSHOT_FIELDS if len(parts) == 9 else SNAPSHOT_FIELDS[:-1]
        values = {}
        line_ok = True
        for field, raw in zip(fields_to_use, parts[1:]):
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


def _parse_price_number(value):
    """숫자(float/int) 또는 쉼표 포함 숫자 문자열("71,500")을 float로 변환한다.
    비어 있거나(None/빈 문자열) 0이거나 변환 실패하면 None(계산 생략으로 취급).
    NaN/Infinity/-Infinity도 None으로 취급한다 — bool(float('nan'))이 True라서
    기존 "0이면 None" 처리만으로는 NaN이 정상 숫자처럼 통과했다."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        if not math.isfinite(num):
            return None
        return num if num else None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if not math.isfinite(num):
        return None
    return num if num else None


def compute_price_vs_open_pct(current_price, open_price):
    """시가 대비 등락률: (current_price - open_price) / open_price * 100.
    값이 없거나 open_price가 0이면 None(계산 생략, 0으로 나누기 방지)."""
    current_price = _parse_price_number(current_price)
    open_price = _parse_price_number(open_price)
    if current_price is None or not open_price:
        return None
    return (current_price - open_price) / open_price * 100


def compute_drop_from_high_pct(current_price, high_price):
    """고점 대비 밀림률(양수 = 밀린 정도): (high_price - current_price) / high_price * 100.
    값이 없거나 high_price가 0이면 None(계산 생략, 0으로 나누기 방지)."""
    current_price = _parse_price_number(current_price)
    high_price = _parse_price_number(high_price)
    if current_price is None or not high_price:
        return None
    return (high_price - current_price) / high_price * 100


def compute_trading_value(trading_value_input, current_price, volume):
    """거래대금: 직접 입력값이 있으면 그 값을 우선 쓰고, 없으면 current_price * volume으로
    추정한다. 둘 다 없으면 None(계산 생략)."""
    trading_value_input = _parse_price_number(trading_value_input)
    if trading_value_input is not None:
        return trading_value_input
    current_price = _parse_price_number(current_price)
    volume = _parse_price_number(volume)
    if current_price is None or volume is None:
        return None
    return current_price * volume


def compute_trading_value_to_market_cap_pct(trading_value, market_cap):
    """시총 대비 거래대금 비율: trading_value / market_cap * 100.
    값이 없거나 market_cap이 0이면 None(계산 생략, 0으로 나누기 방지)."""
    trading_value = _parse_price_number(trading_value)
    market_cap = _parse_price_number(market_cap)
    if trading_value is None or not market_cap:
        return None
    return trading_value / market_cap * 100


def _render_snapshot_calc_summary(ticker):
    """종목별 상세 입력 카드 안에서, 현재 입력값 기준 계산값(시가 대비/고점 대비 밀림/거래대금/
    시총 대비 거래대금)을 표시한다. 화면 표시 전용이며 DB에는 저장하지 않는다. 값이 비어 있으면
    (open_price/high_price/market_cap이 0이거나 없음) 해당 항목은 건너뛴다."""
    current = _get_snapshot_value(ticker, "current")
    open_price = _get_snapshot_value(ticker, "open")
    high = _get_snapshot_value(ticker, "high")
    turnover_input = _get_snapshot_value(ticker, "turnover")
    volume = _get_snapshot_value(ticker, "volume")
    market_cap = _get_snapshot_value(ticker, "market_cap")

    price_vs_open_pct = compute_price_vs_open_pct(current, open_price)
    drop_from_high_pct = compute_drop_from_high_pct(current, high)
    trading_value = compute_trading_value(turnover_input, current, volume)
    trading_value_to_market_cap_pct = compute_trading_value_to_market_cap_pct(trading_value, market_cap)

    lines = []
    if price_vs_open_pct is not None:
        lines.append(f"시가 대비: {price_vs_open_pct:+.2f}%")
    if drop_from_high_pct is not None:
        lines.append(f"고점 대비 밀림: {drop_from_high_pct:.2f}%")
    if trading_value is not None:
        lines.append(f"거래대금: {trading_value:,.0f}원")
    if trading_value_to_market_cap_pct is not None:
        lines.append(f"시총 대비 거래대금: {trading_value_to_market_cap_pct:.2f}%")

    if lines:
        st.caption(" · ".join(lines))


def _render_risk_and_warning_inputs(ticker, market, compact=False):
    """v1.1 리스크 엔진 + 청산 계획 + 경고형 확정 차단 입력/표시.

    화면 표시 계산(risk_amount/recommended_qty 등)은 저장하지 않는다. entry_price/stop_loss_price
    등 사용자가 입력한 값만 저장 대상이 된다(저장 시점에 items_to_save에 포함). compact=False는
    기존 한국장·미국장 종목별 상세 입력 카드 표시를 그대로 유지한다.
    """
    prefix = f"snap_{ticker}_"
    current = _get_snapshot_value(ticker, "current")
    high = _get_snapshot_value(ticker, "high")
    low = _get_snapshot_value(ticker, "low")
    prev_close = _get_snapshot_value(ticker, "prev_close")

    # entry_price 기본값은 current_price를 계속 따라가되, 사용자가 진입가를 직접 수정하면
    # 그 뒤로는 current_price가 바뀌어도 따라가지 않는다(아직 "직접 수정 전"인지는
    # 마지막 자동입력값과 현재 entry_price가 같은지로 판단한다).
    entry_key = prefix + "entry_price"
    auto_track_key = prefix + "entry_price_auto_track"
    if entry_key not in st.session_state or st.session_state.get(auto_track_key) == st.session_state[entry_key]:
        st.session_state[entry_key] = current
        st.session_state[auto_track_key] = current

    if compact:
        st.markdown("#### 리스크 관리")
        rc1, rc2, rc3 = st.columns(3)
        entry_price = rc1.number_input(
            "진입가", min_value=0.0, step=100.0, key=prefix + "entry_price"
        )
        stop_loss_price = rc2.number_input(
            "손절가", value=0.0, min_value=0.0, step=100.0, key=prefix + "stop_loss_price"
        )

        account_size = st.session_state.get("risk_account_size", 0.0)
        risk_percent = st.session_state.get("risk_percent_setting", 1.0)
        risk = _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price)
        if risk["recommended_qty"] is None:
            qty_display = "손절가 입력 후 계산" if not stop_loss_price else "-"
        else:
            qty_display = f"{risk['recommended_qty']:,}주"
        rc3.metric("권장 수량", qty_display)
        if risk["recommended_qty"] is not None:
            cap_note = " (계좌 25% 상한 적용)" if risk["capped"] else ""
            rc3.caption(f"권장 매수금액: {risk['recommended_buy_amount']:,.0f}{cap_note}")
        if risk["error"]:
            st.warning(risk["error"])
        if risk["warning"]:
            st.warning(risk["warning"])

        with st.expander("리스크 관리 공통 설정", expanded=False):
            st.caption(
                "계좌금액/1회 리스크%는 한국장·미국장 권장 수량 계산에 공통으로 쓰입니다. "
                "자동매매가 아니라 화면 표시용 참고 계산입니다."
            )
            r1, r2, r3 = st.columns(3)
            r1.number_input(
                "계좌금액", value=0.0, min_value=0.0, step=1000000.0, key="risk_account_size"
            )
            r2.number_input(
                "1회 리스크(%)", value=1.0, min_value=0.0, max_value=2.0, step=0.1,
                key="risk_percent_setting",
            )
            today_loss_r = r3.number_input(
                "금일 손실R (수동 입력)", value=0.0, step=0.1, key="risk_today_loss_r"
            )
            if today_loss_r <= -2:
                st.error("금일 신규 판단 중지 - 당일 손실 -2R 도달")

        with st.expander("청산 계획", expanded=False):
            ec1, ec2, ec3 = st.columns(3)
            ec1.number_input(
                "계획 손절가", value=0.0, min_value=0.0, step=100.0,
                key=prefix + "planned_stop_price",
            )
            ec2.number_input(
                "목표가", value=0.0, min_value=0.0, step=100.0, key=prefix + "target_price"
            )
            ec3.number_input(
                "예상 보유일수", value=0, min_value=0, step=1,
                key=prefix + "expected_holding_days",
            )

        with st.expander("경고·확정 차단", expanded=False):
            wc1, wc2, wc3 = st.columns(3)
            disclosure_type = wc1.selectbox(
                "공시 유형", ["없음", "수주", "기타"], key=prefix + "disclosure_type"
            )
            news_status = wc2.selectbox(
                "뉴스 확인 상태", ["있음", "없음확인", "확인실패", "루머테마"],
                key=prefix + "news_status",
            )
            five_day_change_pct = wc3.number_input(
                "5일 등락률(%)", value=0.0, min_value=0.0, step=1.0,
                key=prefix + "five_day_change_pct",
            )

            daily_change_pct = _safe_pct_diff(current, prev_close)
            retracement_ratio = _compute_retracement_ratio(high, low, current)
            if _check_disclosure_chase_warning(
                disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio
            ):
                suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
                st.error(f"수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지{suffix}")
            if _check_no_news_chase_warning(
                news_status, daily_change_pct, five_day_change_pct, retracement_ratio
            ):
                suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
                st.error(f"무뉴스 급등 - 반전 위험, 추격 금지{suffix}")
        return

    st.markdown("**리스크 관리 (v1.1)**")
    rc1, rc2 = st.columns(2)
    entry_price = rc1.number_input(
        "진입가(기본값=현재가)", min_value=0.0, step=100.0, key=prefix + "entry_price"
    )
    stop_loss_price = rc2.number_input(
        "손절가", value=0.0, min_value=0.0, step=100.0, key=prefix + "stop_loss_price"
    )

    account_size = st.session_state.get("risk_account_size", 0.0)
    risk_percent = st.session_state.get("risk_percent_setting", 1.0)
    risk = _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price)
    if risk["recommended_qty"] is not None:
        cap_note = " (계좌 25% 상한 적용)" if risk["capped"] else ""
        st.caption(
            f"권장 수량: {risk['recommended_qty']:,}주 / 권장 매수금액: "
            f"{risk['recommended_buy_amount']:,.0f}{cap_note}"
        )
    if risk["error"]:
        st.warning(risk["error"])
    if risk["warning"]:
        st.warning(risk["warning"])

    st.markdown("**청산 계획 (v1.1, 저장 전용)**")
    ec1, ec2, ec3 = st.columns(3)
    ec1.number_input("목표 손절가(planned)", value=0.0, min_value=0.0, step=100.0, key=prefix + "planned_stop_price")
    ec2.number_input("목표가", value=0.0, min_value=0.0, step=100.0, key=prefix + "target_price")
    ec3.number_input(
        "예상 보유일수", value=0, min_value=0, step=1, key=prefix + "expected_holding_days"
    )
    ec4, ec5 = st.columns(2)
    ec4.selectbox("계획 준수 여부", ["미입력", "예", "아니오", "부분"], key=prefix + "plan_followed")
    ec5.selectbox(
        "위반 사유", ["미입력", "손절지연", "조기매도", "복구매매", "감정매매", "뉴스변경", "기타"],
        key=prefix + "violation_reason",
    )

    st.markdown("**경고형 확정 차단 (v1.1)**")
    wc1, wc2, wc3 = st.columns(3)
    disclosure_type = wc1.selectbox("공시 유형", ["없음", "수주", "기타"], key=prefix + "disclosure_type")
    news_status = wc2.selectbox(
        "뉴스 확인 상태", ["있음", "없음확인", "확인실패", "루머테마"], key=prefix + "news_status"
    )
    five_day_change_pct = wc3.number_input(
        "5일 등락률(%)", value=0.0, min_value=0.0, step=1.0, key=prefix + "five_day_change_pct"
    )

    daily_change_pct = _safe_pct_diff(current, prev_close)
    retracement_ratio = _compute_retracement_ratio(high, low, current)
    if _check_disclosure_chase_warning(disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio):
        suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
        st.error(f"수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지{suffix}")
    if _check_no_news_chase_warning(news_status, daily_change_pct, five_day_change_pct, retracement_ratio):
        suffix = " (미국장은 추후 검증 대상)" if market == "US" else ""
        st.error(f"무뉴스 급등 - 반전 위험, 추격 금지{suffix}")


def _collect_risk_fields(ticker):
    """저장 시점에 v1.1 입력 필드 값을 세션 상태에서 모아온다(화면 표시 계산값은 포함하지 않음)."""
    prefix = f"snap_{ticker}_"
    plan_followed = st.session_state.get(prefix + "plan_followed", "미입력")
    violation_reason = st.session_state.get(prefix + "violation_reason", "미입력")
    return {
        "entry_price": st.session_state.get(prefix + "entry_price") or None,
        "stop_loss_price": st.session_state.get(prefix + "stop_loss_price") or None,
        "planned_stop_price": st.session_state.get(prefix + "planned_stop_price") or None,
        "target_price": st.session_state.get(prefix + "target_price") or None,
        "expected_holding_days": st.session_state.get(prefix + "expected_holding_days") or None,
        "plan_followed": None if plan_followed == "미입력" else plan_followed,
        "violation_reason": None if violation_reason == "미입력" else violation_reason,
        "disclosure_type": st.session_state.get(prefix + "disclosure_type", "없음"),
        "news_status": st.session_state.get(prefix + "news_status", "있음"),
        "five_day_change_pct": st.session_state.get(prefix + "five_day_change_pct") or None,
    }


def _fmt_pct(value):
    return "-" if value is None else f"{value:.2f}"


def _fmt_signed_pct(value):
    """부호를 명시해서 보여준다 (+3.36% / -4.92%). 브리핑 초안 문장용."""
    return "-" if value is None else f"{value:+.2f}%"


def _fmt_actual_entry_price_display(value):
    """실제 평균 체결가(REAL, NULL 허용)를 입력칸 기본값 문자열로 표시한다.

    NULL -> 빈칸. 정수 가격이면 불필요한 소수점(.0) 없이, 소수 가격이면 유효 소수만
    남기고 표시한다. 통화 기호는 붙이지 않는다.
    """
    if value is None:
        return ""
    value = float(value)
    if value == int(value):
        return f"{int(value):,}"
    text = f"{value:,.4f}".rstrip("0").rstrip(".")
    return text


def _parse_actual_entry_price_text(text):
    """실제 체결가 입력칸 문자열을 파싱한다. 반환: (price 또는 None, 에러 메시지 또는 None).

    앞뒤 공백 제거, 쉼표 제거 후 숫자로 변환한다. 빈 문자열은 (None, None)으로 반환해
    NULL 저장(미기록)을 허용한다. 숫자로 바꿀 수 없거나 0 이하/NaN/Infinity면
    (None, 에러 메시지)를 반환해 저장을 막는다(실제 DB 쓰기는 하지 않음, 파싱만).
    """
    text = (text or "").strip()
    if not text:
        return None, None
    cleaned = text.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None, f"'{text}' 값을 숫자로 변환할 수 없습니다."
    if not math.isfinite(value):
        return None, "유효한 숫자가 아닙니다(NaN/Infinity 불가)."
    if value <= 0:
        return None, "0보다 큰 값만 입력할 수 있습니다."
    return value, None


# ---- v1.2A: 청산 결과 기록 (기존 report_item 업데이트 전용, 새 report 생성 없음) ----

def _compute_result_r(entry_price, stop_loss_price, actual_exit_price):
    """R수익률 = (actual_exit_price - entry_price) / (entry_price - stop_loss_price).

    entry_price/stop_loss_price/actual_exit_price 중 하나라도 없거나(0/None),
    stop_loss_price가 entry_price보다 낮지 않으면 계산하지 않는다(None)."""
    if not entry_price or not stop_loss_price or not actual_exit_price:
        return None
    if not (stop_loss_price < entry_price):
        return None
    per_share_risk = entry_price - stop_loss_price
    if per_share_risk <= 0:
        return None
    return (actual_exit_price - entry_price) / per_share_risk


def _fmt_result_r(value):
    return "계산 불가" if value is None else f"{value:+.2f}R"


def _compute_realized_pnl(actual_entry_price, actual_exit_price, quantity, actual_fee):
    """실현손익 = (actual_exit_price - actual_entry_price) * quantity - actual_fee.

    actual_entry_price/actual_exit_price는 유한한 양수여야 하고, quantity는 bool이
    아닌 int이며 1 이상이어야 한다. actual_fee는 None이면 "미입력"을 뜻하므로 0으로
    치환하지 않고 그대로 계산 불가(None) 처리한다 — actual_fee=0은 "명시적으로 0원
    입력"이므로 정상 계산한다. 조건을 하나라도 만족하지 못하면 None을 반환한다."""
    if (
        not isinstance(actual_entry_price, (int, float))
        or isinstance(actual_entry_price, bool)
        or not math.isfinite(actual_entry_price)
        or actual_entry_price <= 0
    ):
        return None
    if (
        not isinstance(actual_exit_price, (int, float))
        or isinstance(actual_exit_price, bool)
        or not math.isfinite(actual_exit_price)
        or actual_exit_price <= 0
    ):
        return None
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None
    if actual_fee is None:
        return None
    if (
        not isinstance(actual_fee, (int, float))
        or isinstance(actual_fee, bool)
        or not math.isfinite(actual_fee)
        or actual_fee < 0
    ):
        return None
    return (actual_exit_price - actual_entry_price) * quantity - actual_fee


def _compute_realized_return_pct(realized_pnl, actual_entry_price, quantity):
    """실현수익률(%) = realized_pnl / (actual_entry_price * quantity) * 100.

    realized_pnl은 유한한 숫자여야 하고, actual_entry_price는 유한한 양수, quantity는
    bool이 아닌 int이며 1 이상이어야 한다. 분모(actual_entry_price * quantity)가 0
    이하이면 None을 반환한다."""
    if (
        not isinstance(realized_pnl, (int, float))
        or isinstance(realized_pnl, bool)
        or not math.isfinite(realized_pnl)
    ):
        return None
    if (
        not isinstance(actual_entry_price, (int, float))
        or isinstance(actual_entry_price, bool)
        or not math.isfinite(actual_entry_price)
        or actual_entry_price <= 0
    ):
        return None
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        return None
    denominator = actual_entry_price * quantity
    if denominator <= 0:
        return None
    return realized_pnl / denominator * 100


def _normalize_to_date(value):
    """문자열("YYYY-MM-DD")/date/datetime을 date로 정규화한다. 실패 시 None.

    datetime.datetime은 datetime.date의 하위 클래스이므로 datetime 인스턴스를 먼저
    검사해 .date()로 시각 정보를 제거한 뒤, 순수 date 인스턴스를 그대로 받아들인다."""
    from datetime import date as _date_cls

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, _date_cls):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _compute_holding_days(actual_entry_date, actual_exit_date):
    """보유일(달력일) = actual_exit_date - actual_entry_date.

    둘 다 "YYYY-MM-DD" 문자열/date/datetime 중 하나를 받아 date로 정규화한다. 정규화에
    실패하거나 None이면 계산 불가(None). 매도일이 매수일보다 빠르면 None(미청산/오류
    방지, 음수 보유일 차단). 같은 날이면 0을 반환한다(정상). 거래일이 아닌 달력일
    기준이며, 2차 과제인 거래일 계산은 이 함수의 범위가 아니다."""
    entry = _normalize_to_date(actual_entry_date)
    exit_ = _normalize_to_date(actual_exit_date)
    if entry is None or exit_ is None:
        return None
    if exit_ < entry:
        return None
    return (exit_ - entry).days


def _compute_verification_status(actual_exit_price, actual_exit_date):
    """실제 청산가/청산일 입력 여부만으로 검증 상태를 정한다(가격/일자 둘 다 있으면 입력완료,
    하나만 있으면 계산불가, 둘 다 없으면 미입력)."""
    has_price = bool(actual_exit_price)
    has_date = bool(actual_exit_date)
    if has_price and has_date:
        return "입력완료"
    if has_price or has_date:
        return "계산불가"
    return "미입력"


# ---- v1.2B: 필터 무시 매매 로그 (기존 report_item 업데이트 전용, 새 report 생성 없음) ----
# 화면에는 한국어로 표시하고, DB(filter_ignore_reason)에는 고정 코드를 콤마로 연결해 저장한다.
FILTER_IGNORE_TAG_OPTIONS = [
    ("NO_STOP", "손절없음"),
    ("STOP_DELAY", "손절지연"),
    ("UNCONFIRMED_ENTRY", "미확정진입"),
    ("PENALTY_IGNORED", "감점무시"),
    ("WARNING_IGNORED", "경고무시"),
    ("NEWS_IMPULSE", "뉴스충동"),
    ("RECOMMEND_BUY", "추천매수"),
    ("REVENGE_TRADE", "복구매매"),
    ("CHASE_BUY", "추격매수"),
    ("SIZE_OVER", "비중초과"),
    ("TAKE_PROFIT_DELAY", "익절지연"),
    ("EARLY_EXIT", "조기매도"),
]
FILTER_IGNORE_TAG_CODE_TO_LABEL = dict(FILTER_IGNORE_TAG_OPTIONS)
FILTER_IGNORE_TAG_LABEL_TO_CODE = {v: k for k, v in FILTER_IGNORE_TAG_OPTIONS}

EMOTION_TAG_OPTIONS = [
    ("EMOTION_CALM", "평온"),
    ("EMOTION_EXCITED", "흥분"),
    ("EMOTION_REVENGE", "복구욕"),
    ("EMOTION_ANXIOUS", "불안"),
]
EMOTION_TAG_CODE_TO_LABEL = dict(EMOTION_TAG_OPTIONS)
EMOTION_TAG_LABEL_TO_CODE = {v: k for k, v in EMOTION_TAG_OPTIONS}

# 플레이북 태그: 이 매매가 어떤 전략/셋업이었는지 기록하는 순수 분류 태그다. 수주공시추격금지/
# 뉴스충동매매/복구매매/손절지연처럼 경고·실수 성격의 개념은 여기 넣지 않고 filter_ignore_reason
# 쪽(FILTER_IGNORE_TAG_OPTIONS)에 남겨둔다.
PLAYBOOK_TAG_OPTIONS = [
    ("US_EARNINGS_SWING", "미국실적스윙"),
    ("KR_BUYBACK_SWING", "자사주스윙"),
    ("LEADER_LAGGARD_DAYTRADE", "1등주2등주단타"),
    ("RECOMMEND_BUY_SETUP", "추천매수셋업"),
    ("OTHER_SETUP", "기타셋업"),
]
PLAYBOOK_TAG_CODE_TO_LABEL = dict(PLAYBOOK_TAG_OPTIONS)
PLAYBOOK_TAG_LABEL_TO_CODE = {v: k for k, v in PLAYBOOK_TAG_OPTIONS}

# 종목별 테마 태그 선택지: 한국장 "오늘 강세 테마 1차 참고판"과 미국장 "테마 레이더 1차 참고판"에
# 이미 있는 테마 이름을 그대로 재사용한 목록이다(중복 문자열은 하나로 합침, 정렬해서 표시).
# 이 상수는 저장/점수/판단에 반영되지 않는 단순 기록용 선택지이며, 두 테마 참고판 코드 자체는
# 건드리지 않는다.
THEME_TAG_OPTIONS = sorted(
    {
        "반도체/HBM", "전력기기/전력망", "원전", "방산", "조선/해운", "자동차/부품",
        "2차전지", "바이오", "AI/로봇", "정유/화학",
        "AI/반도체", "금리/성장주", "전력망/원전", "방산/전쟁", "에너지/유가", "자동차/전기차",
    }
)


def _fetch_filter_compliance_stats():
    """전체 report_items에서 필터 준수/무시별 평균 R수익률을 계산한다(화면 표시 전용, 저장 없음).

    result_r이 NULL이거나 숫자로 변환할 수 없는 행은 평균 계산에서 제외한다."""
    conn = db.get_connection()
    rows = conn.execute("SELECT filter_ignored, result_r FROM report_items").fetchall()
    conn.close()

    ignored_count = 0
    followed_count = 0
    unset_count = 0
    ignored_r_values = []
    followed_r_values = []
    for row in rows:
        flag = row["filter_ignored"]
        if flag == "YES":
            ignored_count += 1
        elif flag == "NO":
            followed_count += 1
        else:
            unset_count += 1

        try:
            r_num = float(row["result_r"]) if row["result_r"] is not None else None
        except (TypeError, ValueError):
            r_num = None
        if r_num is None:
            continue
        if flag == "YES":
            ignored_r_values.append(r_num)
        elif flag == "NO":
            followed_r_values.append(r_num)

    return {
        "ignored_count": ignored_count,
        "followed_count": followed_count,
        "unset_count": unset_count,
        "ignored_avg_r": (sum(ignored_r_values) / len(ignored_r_values)) if ignored_r_values else None,
        "followed_avg_r": (sum(followed_r_values) / len(followed_r_values)) if followed_r_values else None,
        "comparable_n": len(ignored_r_values) + len(followed_r_values),
    }


def _fmt_avg_r(value):
    return "데이터 없음" if value is None else f"{value:+.2f}R"


def _n_confidence_label(n):
    if n < 30:
        return "미검증"
    if n < 50:
        return "참고"
    return "검토 가능"


def _fetch_worst_trades(limit=5):
    """전체 report_items에서 result_r이 숫자로 변환 가능한 행만 모아 낮은(손실이 큰) 순으로
    정렬해 상위 N개를 반환한다. 화면 표시 전용이며 계산/저장 로직에는 영향을 주지 않는다."""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT stock_name, ticker, trade_mode, result_r, actual_exit_date, exit_reason, filter_ignored "
        "FROM report_items WHERE result_r IS NOT NULL"
    ).fetchall()
    conn.close()

    parsed = []
    for row in rows:
        try:
            r_num = float(row["result_r"])
        except (TypeError, ValueError):
            continue
        parsed.append(
            {
                "종목명": row["stock_name"] or "-",
                "티커": row["ticker"] or "-",
                "매매유형": row["trade_mode"] or "-",
                "result_r": r_num,
                "청산일": row["actual_exit_date"] or "-",
                "청산사유": row["exit_reason"] or "-",
                "필터무시여부": {"YES": "예", "NO": "아니오"}.get(row["filter_ignored"], "미입력"),
            }
        )
    parsed.sort(key=lambda d: d["result_r"])
    total_n = len(parsed)
    worst_rows = parsed[:limit]
    avg_worst = (sum(d["result_r"] for d in worst_rows) / len(worst_rows)) if worst_rows else None
    lowest = worst_rows[0]["result_r"] if worst_rows else None
    return {"total_n": total_n, "worst_rows": worst_rows, "avg_worst": avg_worst, "lowest": lowest}


def _fetch_open_risk_positions():
    """전체 report_items에서 미청산(actual_exit_price IS NULL) + entry_price/stop_loss_price로
    1건당 위험(entry_price - stop_loss_price)을 계산할 수 있는 행만 모아 총 오픈 리스크를 낸다.

    화면 표시 전용이며 계산/저장 로직에는 영향을 주지 않는다. planned_stop_price와 buy_confirmed는
    이번 계산 기준에 쓰지 않는다(buy_confirmed는 현재 신뢰 가능한 값이 아님)."""
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT stock_name, ticker, trade_mode, entry_price, stop_loss_price, filter_ignored "
        "FROM report_items WHERE actual_exit_price IS NULL"
    ).fetchall()
    conn.close()

    positions = []
    excluded_count = 0
    for row in rows:
        try:
            entry = float(row["entry_price"]) if row["entry_price"] is not None else None
            stop = float(row["stop_loss_price"]) if row["stop_loss_price"] is not None else None
        except (TypeError, ValueError):
            entry = None
            stop = None
        if entry is None or stop is None or not (stop < entry):
            excluded_count += 1
            continue
        positions.append(
            {
                "종목명": row["stock_name"] or "-",
                "티커": row["ticker"] or "-",
                "매매유형": row["trade_mode"] or "-",
                "진입가": entry,
                "손절가": stop,
                "1건 위험": entry - stop,
                "필터무시여부": {"YES": "예", "NO": "아니오"}.get(row["filter_ignored"], "미입력"),
            }
        )
    total_risk = sum(p["1건 위험"] for p in positions)
    return {
        "positions": positions,
        "count": len(positions),
        "total_risk": total_risk,
        "excluded_count": excluded_count,
    }


def _open_risk_status_label(count, total_risk):
    if count == 0:
        return "데이터 없음"
    if total_risk < 1:
        return "낮음"
    if total_risk < 3:
        return "주의"
    return "위험"


# ---- v1.1: 리스크 엔진 / 경고형 확정 차단 / 입력 검증 (한국장·미국장 "바로 저장" 전용) ----
# 점수 가점/감점 로직과는 무관하며, 여기서 계산되는 값은 화면 표시/경고 문구 전용이다.
# 한국장/미국장 바로 저장은 이미 모든 항목을 "미확정"으로만 저장하므로(기존 동작), 별도의
# 확정 상태 차단 로직은 필요 없고 경고 문구를 눈에 띄게 보여주는 것으로 "확정 차단"을 만족한다.

def _compute_risk_engine(account_size, risk_percent, entry_price, stop_loss_price):
    """계좌금액/리스크% 기준 권장 수량을 계산한다. 화면 표시 전용이며 저장하지 않는다."""
    result = {
        "risk_amount": None,
        "per_share_loss": None,
        "recommended_qty": None,
        "recommended_buy_amount": None,
        "capped": False,
        "error": None,
        "warning": None,
    }
    if not account_size or not entry_price:
        return result

    risk_amount = account_size * risk_percent / 100
    result["risk_amount"] = risk_amount

    if not stop_loss_price:
        result["error"] = "손절가 없음 - 매수 확정 불가"
        return result

    per_share_loss = entry_price - stop_loss_price
    result["per_share_loss"] = per_share_loss

    if stop_loss_price >= entry_price or per_share_loss <= 0:
        result["error"] = "손절가는 진입가보다 낮아야 합니다"
        return result

    recommended_qty = math.floor(risk_amount / per_share_loss)
    recommended_buy_amount = recommended_qty * entry_price

    if recommended_buy_amount > account_size * 0.25:
        recommended_qty = math.floor((account_size * 0.25) / entry_price)
        recommended_buy_amount = recommended_qty * entry_price
        result["capped"] = True

    result["recommended_qty"] = recommended_qty
    result["recommended_buy_amount"] = recommended_buy_amount

    stop_pct = per_share_loss / entry_price
    if stop_pct > 0.08:
        result["warning"] = "손절폭 8% 초과 - 수량 축소 또는 보류 권고"

    return result


def _compute_retracement_ratio(high_price, low_price, current_price):
    """고점 대비 되돌림 비율: (high-current)/(high-low). 변동폭이 현재가의 1% 미만이면
    계산을 건너뛴다(None)."""
    if not high_price or not low_price or current_price is None:
        return None
    price_range = high_price - low_price
    if price_range <= 0 or price_range < current_price * 0.01:
        return None
    return (high_price - current_price) / price_range


def _is_surge_condition(daily_change_pct, five_day_change_pct):
    """급등 조건: 당일 등락률 10% 이상 또는 5일 등락률 15% 이상."""
    if daily_change_pct is not None and daily_change_pct >= 10:
        return True
    if five_day_change_pct is not None and five_day_change_pct >= 15:
        return True
    return False


def _check_disclosure_chase_warning(disclosure_type, daily_change_pct, five_day_change_pct, retracement_ratio):
    """경고1: 수주공시 과열 - 당일 정점 후 하락 위험, 추격 금지."""
    if disclosure_type != "수주":
        return False
    if not _is_surge_condition(daily_change_pct, five_day_change_pct):
        return False
    return retracement_ratio is not None and retracement_ratio >= 0.5


def _check_no_news_chase_warning(news_status, daily_change_pct, five_day_change_pct, retracement_ratio):
    """경고2: 무뉴스/루머 급등 - 반전 위험, 추격 금지."""
    if news_status not in ("없음확인", "루머테마"):
        return False
    if not _is_surge_condition(daily_change_pct, five_day_change_pct):
        return False
    return retracement_ratio is not None and retracement_ratio >= 0.5


def _validate_snapshot_price_inputs(name, current, open_price, high, low, volume, turnover):
    """가격/거래량/거래대금 입력값 검증(작업5). 위반 사유 문자열 목록을 반환(빈 목록=정상).

    NaN/Infinity/-Infinity는 먼저 명시적 오류로 걸러낸다. 이렇게 걸러진 값은 이후
    음수·가격 관계 비교에서 None과 동일하게(검증 대상에서 제외) 취급해 같은 값이
    "비정상 숫자"와 "음수"/"관계 오류"로 중복 표시되지 않게 한다. 기존 0/None/미입력
    처리 방식과 기존 가격 관계·음수 거래량 검증 로직 자체는 그대로 유지한다."""
    errors = []
    fields = (
        ("현재가", current), ("시가", open_price), ("고가", high), ("저가", low),
        ("거래량", volume), ("거래대금", turnover),
    )
    cleaned = {}
    for label, value in fields:
        if value is None:
            cleaned[label] = None
            continue
        try:
            is_finite = math.isfinite(value)
        except TypeError:
            is_finite = False
        if not is_finite:
            errors.append(f"{name}: {label}가 비정상 숫자입니다(NaN/Infinity)")
            cleaned[label] = None
        else:
            cleaned[label] = value
    current = cleaned["현재가"]
    open_price = cleaned["시가"]
    high = cleaned["고가"]
    low = cleaned["저가"]
    volume = cleaned["거래량"]
    turnover = cleaned["거래대금"]

    for label, value in (
        ("현재가", current), ("시가", open_price), ("고가", high), ("저가", low),
        ("거래량", volume), ("거래대금", turnover),
    ):
        if value is not None and value < 0:
            errors.append(f"{name}: {label}가 음수입니다")
    if high and current is not None and not (high >= current):
        errors.append(f"{name}: 고가가 현재가보다 낮습니다")
    if low and current is not None and not (current >= low):
        errors.append(f"{name}: 현재가가 저가보다 낮습니다")
    if high and open_price and not (high >= open_price):
        errors.append(f"{name}: 고가가 시가보다 낮습니다")
    if low and open_price and not (open_price >= low):
        errors.append(f"{name}: 시가가 저가보다 낮습니다")
    return errors


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
    st.subheader("오늘 저장 요약")
    st.info(
        "이 화면은 오늘 저장된 기록을 관점별로 다시 보여주는 화면입니다.\n"
        "증시 전체 요약 화면이 아닙니다.\n"
        "먼저 🇰🇷 한국장 먼저 확인 또는 🇺🇸 미국장 스윙 확인에서 계산 후 저장해야 오늘 저장 요약과 지난 기록에 반영됩니다."
    )

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

# ---- 0단계 시장 분위기 자동 확인 (한국장 전용, 읽기 전용, 저장 없음) ----
# 기존 "오늘 주가 자동 채우기"와 동일한 price_data.get_snapshot_defaults()를 재사용한다.
# price_data.py 자체는 수정하지 않는다.
KR_MARKET_MOOD_AUTO_TARGETS = [
    ("나스닥100 선물", "NQ=F"),
    ("SOXX", "SOXX"),
    ("SMH", "SMH"),
    ("달러/원", "KRW=X"),
    ("코스피", "^KS11"),
    ("코스닥", "^KQ11"),
]


def _kr_mood_auto_verdict(name, change_pct):
    """0단계 시장 분위기 자동 확인 전용 판정(참고용, 매수 신호 아님). 달러/원은 별도 문구."""
    if change_pct is None:
        return "확인 불가"
    if name == "달러/원":
        if change_pct >= 0.3:
            return "상승 (원화 약세, 한국장 부담)"
        if change_pct <= -0.3:
            return "하락 (원화 강세, 한국장 우호)"
        return "보합 (환율 중립)"
    if change_pct >= 0.3:
        return "강함 (상승 우세)"
    if change_pct <= -0.3:
        return "약함 (하락 우세)"
    return "보합 (중립)"


def run_kr_mood_auto_check():
    """0단계 시장 분위기 자동 확인 공용 조회 함수 (읽기 전용, DB 저장 없음).

    KR_MARKET_MOOD_AUTO_TARGETS를 조회해 기존과 동일한 형식으로
    st.session_state["kr_mood_auto_results"]/["kr_mood_auto_any_ok"]에 저장한다.
    0단계 버튼과 "0→1→2 한 번에 미리보기 생성" 버튼이 모두 이 함수를 호출한다.
    반환: {"status": "ok"/"partial"/"fail", "results": [...], "message": str 또는 None,
    "ok_count": int, "total": int}
    """
    _mood_results = []
    _ok_count = 0
    for _mood_name, _mood_ticker in KR_MARKET_MOOD_AUTO_TARGETS:
        _mood_result = price_data.get_snapshot_defaults(_mood_ticker)
        if _mood_result.get("ok"):
            _ok_count += 1
            _mood_change_pct = _safe_pct_diff(_mood_result["current"], _mood_result["prev_close"])
            _mood_results.append(
                {
                    "항목": _mood_name,
                    "등락률(%)": _fmt_signed_pct(_mood_change_pct),
                    "판정": _kr_mood_auto_verdict(_mood_name, _mood_change_pct),
                    "현재값": _mood_result["current"],
                    "출처": "자동 조회",
                }
            )
        else:
            _mood_results.append(
                {
                    "항목": _mood_name,
                    "등락률(%)": "-",
                    "판정": "확인 불가",
                    "현재값": "-",
                    "출처": "조회 실패",
                }
            )
    _total = len(KR_MARKET_MOOD_AUTO_TARGETS)
    if _ok_count == 0:
        status, message = "fail", "전체 조회 실패 (네트워크 또는 데이터 제공처 문제)"
    elif _ok_count == _total:
        status, message = "ok", None
    else:
        status, message = "partial", None

    st.session_state["kr_mood_auto_results"] = _mood_results
    st.session_state["kr_mood_auto_any_ok"] = _ok_count > 0

    return {"status": status, "results": _mood_results, "message": message, "ok_count": _ok_count, "total": _total}


def run_kr_snapshot_auto_fill():
    """1단계 오늘 주가 자동 채우기 공용 조회 함수 (읽기 전용, DB 저장 없음).

    SNAPSHOT_STOCKS를 조회해 성공한 종목만 session_state 입력값에 반영한다. 실패한 종목은
    session_state를 건드리지 않으므로 기존 입력값이 있으면 그대로 유지된다. 기존과 동일한
    형식으로 st.session_state["snap_auto_fill_results"]에 저장한다. ① 버튼과 "0→1→2 한
    번에 미리보기 생성" 버튼이 모두 이 함수를 호출한다.
    반환: {"status": "ok"/"partial"/"fail", "results": {...}, "message": str 또는 None,
    "ok_count": int, "total": int}
    """
    fetch_results = {}
    _ok_count = 0
    for s in SNAPSHOT_STOCKS:
        result = price_data.get_snapshot_defaults(s["ticker"])
        fetch_results[s["ticker"]] = result
        if result.get("ok"):
            _ok_count += 1
            prefix = f"snap_{s['ticker']}_"
            st.session_state[prefix + "current"] = result["current"]
            st.session_state[prefix + "prev_close"] = result["prev_close"]
            st.session_state[prefix + "open"] = result["open"]
            st.session_state[prefix + "high"] = result["high"]
            st.session_state[prefix + "low"] = result["low"]
            st.session_state[prefix + "turnover"] = result["turnover"]
            st.session_state[prefix + "market_cap"] = result["market_cap"] or 0.0
        # 실패 종목은 session_state를 건드리지 않는다 — 기존 입력값이 있으면 그대로 유지된다.
    _total = len(SNAPSHOT_STOCKS)
    if _ok_count == 0:
        status, message = "fail", "전체 조회 실패 (네트워크 또는 데이터 제공처 문제)"
    elif _ok_count == _total:
        status, message = "ok", None
    else:
        status, message = "partial", None

    st.session_state["snap_auto_fill_results"] = fetch_results

    return {"status": status, "results": fetch_results, "message": message, "ok_count": _ok_count, "total": _total}


_AUTO_FETCH_FIELD_LABELS = {
    "current": "현재가", "prev_close": "전일종가", "open": "시가",
    "high": "고가", "low": "저가", "volume": "거래량",
    "turnover": "거래대금", "market_cap": "시가총액",
}


def _render_auto_fetch_status_summary(results, stock_defs, prefix):
    total = len(stock_defs)
    complete = 0
    partial = 0
    failed = []
    details = []
    for stock in stock_defs:
        ticker = stock["ticker"]
        result = results.get(ticker) or {}
        if not result.get("ok"):
            failed.append((stock["name"], ticker, result.get("error") or "데이터 없음"))
            continue
        missing = [
            label for field, label in _AUTO_FETCH_FIELD_LABELS.items()
            if result.get(field) is None
        ]
        if missing:
            partial += 1
            details.append((stock["name"], ticker, "누락: " + ", ".join(missing)))
        else:
            complete += 1
    if partial == 0 and not failed:
        st.success(f"자동조회 완료: {total}개 종목 모두 정상 ({complete}/{total})")
        return
    st.warning(f"자동조회 결과: 전체 {total}개 / 완전 성공 {complete}개 / 일부 누락 {partial}개 / 전체 실패 {len(failed)}개")
    with st.expander("자동조회 누락·실패 상세", expanded=False):
        for name, ticker, reason in details:
            st.caption(f"{name} ({ticker}) — {reason}")
        for name, ticker, reason in failed:
            st.caption(f"{name} ({ticker}) — 전체 실패: {reason}")


KR_THEME_WATCH_INITIAL_ROWS = [
    {
        "테마": theme,
        "상태": "확인 필요",
        "대장주": "",
        "후발주": "",
        "추격주의": "",
        "메모": "",
    }
    for theme in [
        "반도체/HBM",
        "전력기기/전력망",
        "원전",
        "방산",
        "조선/해운",
        "자동차/부품",
        "2차전지",
        "바이오",
        "AI/로봇",
        "정유/화학",
    ]
]
KR_THEME_WATCH_DATA_KEY = "kr_theme_watch_rows"
KR_THEME_WATCH_EDITOR_KEY = "kr_theme_watch_editor"


def _render_kr_theme_chip_editor():
    """기존 한국장 테마 list[dict]를 단일 session_state 원본으로 편집한다 (DB 미사용)."""
    st.markdown(
        """
        <style>
        .jarvis-m1-theme-title {
            color: #f8fafc;
            font-size: 0.98rem;
            font-weight: 850;
            margin-bottom: 0.35rem;
        }
        .jarvis-m1-theme-status {
            display: inline-block;
            border-radius: 999px;
            padding: 0.22rem 0.58rem;
            margin: 0.15rem 0 0.55rem;
            font-size: 0.74rem;
            font-weight: 800;
        }
        .jarvis-m1-theme-strong { background: #14532d; color: #bbf7d0; }
        .jarvis-m1-theme-watch { background: #713f12; color: #fef08a; }
        .jarvis-m1-theme-normal { background: #1e3a5f; color: #bfdbfe; }
        .jarvis-m1-theme-weak { background: #334155; color: #cbd5e1; }
        .jarvis-m1-theme-check { background: #202938; color: #94a3b8; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    source_rows = st.session_state.get(KR_THEME_WATCH_DATA_KEY)
    if isinstance(source_rows, list):
        theme_rows = [dict(row) for row in source_rows]
    else:
        theme_rows = [dict(row) for row in KR_THEME_WATCH_INITIAL_ROWS]
        legacy_editor_state = st.session_state.get(KR_THEME_WATCH_EDITOR_KEY)
        if isinstance(legacy_editor_state, dict):
            legacy_edits = legacy_editor_state.get("edited_rows") or {}
            for raw_index, changes in legacy_edits.items():
                try:
                    row_index = int(raw_index)
                except (TypeError, ValueError):
                    continue
                if not (0 <= row_index < len(theme_rows)) or not isinstance(changes, dict):
                    continue
                for column, value in changes.items():
                    if column in theme_rows[row_index] and column != "테마":
                        theme_rows[row_index][column] = value

    status_options = ["강함", "감시", "보통", "약함", "확인 필요"]
    status_classes = {
        "강함": "strong",
        "감시": "watch",
        "보통": "normal",
        "약함": "weak",
        "확인 필요": "check",
    }
    field_specs = [
        ("대장주", "kr_theme_leader_"),
        ("후발주", "kr_theme_laggard_"),
        ("추격주의", "kr_theme_chase_warning_"),
        ("메모", "kr_theme_memo_"),
    ]
    theme_columns = st.columns(2, gap="large")
    split_index = (len(theme_rows) + 1) // 2
    updated_rows = []

    for index, row in enumerate(theme_rows):
        updated_row = dict(row)
        theme_name = str(row.get("테마") or "")
        if not theme_name:
            updated_rows.append(updated_row)
            continue

        slug = "_".join(f"u{ord(char):04x}" for char in theme_name if char.isalnum())
        status_key = f"kr_theme_status_{slug}"
        initial_status = row.get("상태")
        if initial_status not in status_options:
            initial_status = "확인 필요"
        if status_key not in st.session_state:
            st.session_state[status_key] = initial_status

        target_column = theme_columns[0 if index < split_index else 1]
        with target_column:
            with st.container(border=True):
                st.markdown(f'<div class="jarvis-m1-theme-title">{theme_name}</div>', unsafe_allow_html=True)
                if hasattr(st, "segmented_control"):
                    selected_status = st.segmented_control(
                        f"{theme_name} 상태",
                        status_options,
                        key=status_key,
                        label_visibility="collapsed",
                    )
                else:
                    selected_status = st.radio(
                        f"{theme_name} 상태",
                        status_options,
                        horizontal=True,
                        key=status_key,
                        label_visibility="collapsed",
                    )
                if selected_status not in status_options:
                    selected_status = "확인 필요"
                status_class = status_classes[selected_status]
                st.markdown(
                    f'<span class="jarvis-m1-theme-status jarvis-m1-theme-{status_class}">'
                    f"현재 상태 · {selected_status}</span>",
                    unsafe_allow_html=True,
                )

                detail_values = {}
                with st.expander("세부 입력", expanded=False):
                    for field_name, key_prefix in field_specs:
                        widget_key = f"{key_prefix}{slug}"
                        if widget_key not in st.session_state:
                            st.session_state[widget_key] = str(row.get(field_name) or "")
                        if field_name == "메모":
                            detail_values[field_name] = st.text_area(field_name, key=widget_key)
                        else:
                            detail_values[field_name] = st.text_input(field_name, key=widget_key)

        if "상태" in updated_row:
            updated_row["상태"] = selected_status
        for field_name, value in detail_values.items():
            if field_name in updated_row:
                updated_row[field_name] = value
        updated_rows.append(updated_row)

    st.session_state[KR_THEME_WATCH_DATA_KEY] = updated_rows
    st.caption("테마 참고판은 session_state에서만 유지되며 DB·점수·판정에는 반영되지 않습니다.")


def _render_kr_primary_actions():
    # ---- 0→1→2 한 번에 미리보기 생성 (자동 저장 아님, DB 미기록) ----
    # 0단계/1단계 버튼과 동일한 조회 로직을 그대로 재사용한다. 실행 결과는 기존 버튼과 같은
    # session_state 키(kr_mood_auto_results, snap_auto_fill_results)에 저장된다.
    if st.session_state.get("kr_auto_preview_running"):
        st.caption("0→1→2 한 번에 미리보기: 실행 중입니다. 잠시 기다리세요.")
    elif st.session_state.get("kr_auto_preview_last_error"):
        st.caption(f"0→1→2 한 번에 미리보기 최근 실행: 실패 - {st.session_state['kr_auto_preview_last_error']}")
    elif st.session_state.get("kr_auto_preview_done_at"):
        st.caption(f"0→1→2 한 번에 미리보기 최근 실행: 완료 ({st.session_state['kr_auto_preview_done_at']})")
        st.caption(
            f"0단계 반영: {st.session_state.get('kr_auto_preview_stage0_status', '-')} / "
            f"1단계 반영: {st.session_state.get('kr_auto_preview_stage1_status', '-')} / "
            f"2단계 미리보기 생성: {'예' if st.session_state.get('kr_auto_preview_stage2_generated') else '아니오'}"
        )

    if st.session_state.get("kr_mood_auto_running"):
        st.caption("0단계 최근 실행: 실행 중입니다. 잠시 기다리세요.")
    elif st.session_state.get("kr_mood_auto_last_error"):
        st.caption(f"0단계 최근 실행: 실패 - {st.session_state['kr_mood_auto_last_error']}")
    elif st.session_state.get("kr_mood_auto_done_at"):
        st.caption(f"0단계 최근 실행: 완료 ({st.session_state['kr_mood_auto_done_at']})")

    if st.session_state.get("kr_snapshot_auto_fill_running"):
        st.caption("1단계 최근 실행: 실행 중입니다. 잠시 기다리세요.")
    elif st.session_state.get("kr_snapshot_auto_fill_last_error"):
        st.caption(f"1단계 최근 실행: 실패 - {st.session_state['kr_snapshot_auto_fill_last_error']}")
    elif st.session_state.get("kr_snapshot_auto_fill_done_at"):
        st.caption(f"1단계 최근 실행: 완료 ({st.session_state['kr_snapshot_auto_fill_done_at']})")

    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button(
            "0→1→2 한 번에 미리보기 생성",
            key="kr_auto_preview_run",
            type="primary",
            disabled=bool(st.session_state.get("kr_auto_preview_running")),
        ):
            if st.session_state.get("kr_auto_preview_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_auto_preview_running"] = True

                _stage_status_display = {"ok": "예", "partial": "부분", "fail": "아니오"}

                # 1) 0단계: 시장 분위기 자동 확인 (공용 함수, 일부 실패해도 중단하지 않음)
                _mood_run_result = run_kr_mood_auto_check()
                _stage0_status = _stage_status_display[_mood_run_result["status"]]

                # 2) 1단계: 오늘 주가 자동 채우기 (공용 함수, 실패 종목은 건너뛰고 기존 입력값 유지)
                _fill_run_result = run_kr_snapshot_auto_fill()
                _stage1_status = _stage_status_display[_fill_run_result["status"]]

                # 3) 2단계: 미리보기 생성 (DB 저장 호출 없음 — build_kr_stage2_preview()는 조회 전용)
                _auto_stage2_preview = build_kr_stage2_preview()
                _stage2_generated = bool(_auto_stage2_preview["rows"])

                st.session_state["kr_auto_preview_stage0_status"] = _stage0_status
                st.session_state["kr_auto_preview_stage1_status"] = _stage1_status
                st.session_state["kr_auto_preview_stage2_generated"] = _stage2_generated
                if _mood_run_result["status"] == "fail" and _fill_run_result["status"] == "fail":
                    st.session_state["kr_auto_preview_last_error"] = (
                        "0단계·1단계 모두 조회 실패 (네트워크 또는 데이터 제공처 문제)"
                    )
                elif not _stage2_generated:
                    st.session_state["kr_auto_preview_last_error"] = "2단계 미리보기를 만들 종목 데이터가 없습니다."
                else:
                    st.session_state["kr_auto_preview_last_error"] = None
                st.session_state["kr_auto_preview_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_auto_preview_running"] = False
                st.rerun()
    with action_cols[1]:
        if st.button(
            "0단계 시장 분위기 자동 확인",
            key="snap_mood_auto_check",
            disabled=bool(st.session_state.get("kr_mood_auto_running")),
        ):
            if st.session_state.get("kr_mood_auto_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_mood_auto_running"] = True
                _mood_run_result = run_kr_mood_auto_check()
                st.session_state["kr_mood_auto_last_error"] = _mood_run_result["message"]
                st.session_state["kr_mood_auto_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_mood_auto_running"] = False
                st.rerun()
    with action_cols[2]:
        if st.button(
            "① 오늘 주가 자동 채우기",
            key="snap_auto_fill",
            disabled=bool(st.session_state.get("kr_snapshot_auto_fill_running")),
        ):
            if st.session_state.get("kr_snapshot_auto_fill_running"):
                st.info("이미 실행 중입니다.")
            else:
                st.session_state["kr_snapshot_auto_fill_running"] = True
                _fill_run_result = run_kr_snapshot_auto_fill()
                st.session_state["kr_snapshot_auto_fill_last_error"] = _fill_run_result["message"]
                st.session_state["kr_snapshot_auto_fill_done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["kr_snapshot_auto_fill_running"] = False
                st.rerun()

    st.caption(
        "0→1→2 버튼은 미리보기만 만듭니다. DB에 저장하지 않으며, 실제 기록을 남기려면 "
        "아래 '③ 국내장 기록 바로 저장' 버튼을 따로 눌러야 합니다."
    )


def _render_kr_fable_mockup1_preview():
    """기존 한국장 입력·저장 흐름 위에 실제 세션 데이터로 그리는 읽기 전용 안전 미리보기."""
    st.markdown(
        """
        <style>
        .jarvis-m1-shell {
            border: 1px solid #25334a;
            border-radius: 18px;
            padding: 1.1rem;
            margin: 0.35rem 0 1rem;
            background: linear-gradient(145deg, #111827 0%, #172033 100%);
        }
        .jarvis-m1-kicker {
            color: #7dd3fc;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .jarvis-m1-title {
            color: #f8fafc;
            font-size: 1.35rem;
            font-weight: 850;
            margin-top: 0.2rem;
        }
        .jarvis-m1-subtitle {
            color: #a9b8cf;
            font-size: 0.88rem;
            margin-top: 0.25rem;
        }
        .jarvis-m1-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 8.5rem), 1fr));
            gap: 0.55rem;
            margin: 0.9rem 0 1.15rem;
        }
        .jarvis-m1-strip-item {
            min-width: 0;
            border: 1px solid #31415d;
            border-radius: 12px;
            padding: 0.7rem 0.75rem;
            background: #0d1524;
        }
        .jarvis-m1-strip-label {
            display: block;
            color: #8ea1bc;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .jarvis-m1-strip-value {
            display: block;
            color: #f8fafc;
            font-size: 0.95rem;
            font-weight: 800;
            margin-top: 0.18rem;
            overflow-wrap: anywhere;
        }
        .jarvis-m1-stepper {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
            gap: 0.65rem;
            margin-bottom: 0.3rem;
        }
        .jarvis-m1-step {
            border: 1px solid #31415d;
            border-radius: 13px;
            padding: 0.8rem;
            background: #121b2c;
            color: #9fb0c8;
        }
        .jarvis-m1-step-active {
            border-color: #38bdf8;
            background: #102c46;
            box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.22);
            color: #f8fafc;
        }
        .jarvis-m1-step-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            margin-right: 0.35rem;
            background: #25334a;
            color: #bae6fd;
            font-size: 0.78rem;
            font-weight: 850;
        }
        .jarvis-m1-step-title {
            font-weight: 800;
        }
        .jarvis-m1-step-copy {
            display: block;
            margin: 0.45rem 0 0 2.05rem;
            color: #91a3bd;
            font-size: 0.78rem;
        }
        .jarvis-m1-stock-list {
            display: grid;
            gap: 0.5rem;
            margin-top: 0.7rem;
        }
        .jarvis-m1-stock {
            border: 1px solid #31415d;
            border-left-width: 5px;
            border-radius: 11px;
            padding: 0.72rem;
            background: #111827;
        }
        .jarvis-m1-stock-selected {
            box-shadow: 0 0 0 1px #7dd3fc;
            background: #16243a;
        }
        .jarvis-m1-stock-green { border-left-color: #22c55e; }
        .jarvis-m1-stock-yellow { border-left-color: #eab308; }
        .jarvis-m1-stock-orange { border-left-color: #f97316; }
        .jarvis-m1-stock-gray { border-left-color: #94a3b8; }
        .jarvis-m1-stock-red { border-left-color: #ef4444; }
        .jarvis-m1-stock-name {
            color: #f8fafc;
            font-weight: 850;
        }
        .jarvis-m1-stock-meta {
            color: #99abc4;
            font-size: 0.78rem;
            margin-top: 0.2rem;
        }
        .jarvis-m1-chip-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 9rem), 1fr));
            gap: 0.5rem;
        }
        .jarvis-m1-chip {
            border: 1px solid #334155;
            border-radius: 999px;
            padding: 0.55rem 0.7rem;
            background: #111827;
            color: #e2e8f0;
            font-size: 0.78rem;
            text-align: center;
        }
        .jarvis-m1-chip-note {
            display: block;
            color: #8192aa;
            font-size: 0.64rem;
            margin-top: 0.12rem;
        }
        .jarvis-m1-panel {
            border: 1px solid #334155;
            border-radius: 14px;
            padding: 1rem;
            background: #111827;
            color: #e2e8f0;
            min-height: 7rem;
        }
        .jarvis-m1-muted {
            color: #91a3bd;
            font-size: 0.86rem;
        }
        @media (max-width: 720px) {
            .jarvis-m1-strip,
            .jarvis-m1-stepper,
            .jarvis-m1-chip-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        <div class="jarvis-m1-shell">
            <div class="jarvis-m1-kicker">Fable Mockup 01 · Safe Preview</div>
            <div class="jarvis-m1-title">오늘 기록에서 복기까지, 한 화면 흐름 미리보기</div>
            <div class="jarvis-m1-subtitle">실제 세션 데이터를 읽어 표시하며 자동조회·판단·저장은 실행하지 않습니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mood_rows = st.session_state.get("kr_mood_auto_results") or []
    mood_by_name = {
        row.get("항목"): row
        for row in mood_rows
        if isinstance(row, dict) and row.get("항목")
    }
    kospi_row = mood_by_name.get("KOSPI") or mood_by_name.get("코스피") or {}
    kosdaq_row = mood_by_name.get("KOSDAQ") or mood_by_name.get("코스닥") or {}
    usdkrw_row = mood_by_name.get("달러/원") or {}
    nasdaq_row = mood_by_name.get("나스닥100 선물") or {}
    soxx_row = mood_by_name.get("SOXX") or {}
    smh_row = mood_by_name.get("SMH") or {}

    try:
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        today_saved = sum(
            1
            for report in db.list_reports()
            if str(report.get("saved_at") or "").startswith(today_prefix)
        )
    except Exception:
        today_saved = "-"

    if "risk_today_loss_r" in st.session_state and st.session_state["risk_today_loss_r"] is not None:
        today_loss_r = f"{st.session_state['risk_today_loss_r']}R"
    else:
        today_loss_r = "-"

    strip_items = [
        ("KOSPI", kospi_row.get("등락률(%)", "-")),
        ("KOSDAQ", kosdaq_row.get("등락률(%)", "-")),
        ("달러/원", usdkrw_row.get("등락률(%)", "-")),
        ("나스닥100 선물", nasdaq_row.get("등락률(%)", "-")),
        (
            "SOXX / SMH",
            f"SOXX {soxx_row.get('등락률(%)', '-')} · SMH {smh_row.get('등락률(%)', '-')}",
        ),
        ("오늘 저장", today_saved),
        ("금일 손실 R", today_loss_r),
    ]
    strip_html = "".join(
        '<div class="jarvis-m1-strip-item">'
        f'<span class="jarvis-m1-strip-label">{label}</span>'
        f'<span class="jarvis-m1-strip-value">{value}</span>'
        "</div>"
        for label, value in strip_items
    )
    st.markdown(f'<div class="jarvis-m1-strip">{strip_html}</div>', unsafe_allow_html=True)

    stage2_preview = build_kr_stage2_preview()
    rows = stage2_preview["rows"]
    active_step = 2 if rows else 1
    steps = [
        (1, "오늘 기록", "시장·주가 자동 채우기"),
        (2, "종목 판단", "점수 확인·리스크 입력"),
        (3, "저장 확인", "보고서·실매매 입력"),
        (4, "복기 / 통계", "태그별·셋업별 성과"),
    ]
    step_html = "".join(
        f'<div class="jarvis-m1-step {"jarvis-m1-step-active" if number == active_step else ""}">'
        f'<span class="jarvis-m1-step-number">{number}</span>'
        f'<span class="jarvis-m1-step-title">{title}</span>'
        f'<span class="jarvis-m1-step-copy">{copy}</span>'
        "</div>"
        for number, title, copy in steps
    )
    st.markdown(f'<div class="jarvis-m1-stepper">{step_html}</div>', unsafe_allow_html=True)

    st.markdown("### 오늘 기록 실행")
    st.caption("시장 분위기와 오늘 주가를 확인한 뒤 종목 판단 미리보기를 생성합니다.")
    _render_kr_primary_actions()

    st.markdown("### 종목 판단 미리보기")
    if not rows:
        st.info("0→1→2 미리보기를 실행하면 종목 판단 화면이 표시됩니다.")
    else:
        left_col, right_col = st.columns([0.34, 0.66], gap="large")
        with left_col:
            trade_mode = st.selectbox(
                "매매유형 선택",
                ["단타", "스윙"],
                key="mockup1_trade_mode",
            )
            score_key = "danta_score" if trade_mode == "단타" else "swing_score"
            verdict_key = "danta_verdict" if trade_mode == "단타" else "swing_verdict"
            sorted_rows = sorted(rows, key=lambda row: row[score_key], reverse=True)
            rows_by_ticker = {row["ticker"]: row for row in sorted_rows}
            selected_ticker = st.selectbox(
                "종목 선택",
                list(rows_by_ticker),
                format_func=lambda ticker: rows_by_ticker[ticker]["name"],
                key="mockup1_selected_ticker",
            )

            sector_by_ticker = {stock["ticker"]: stock["sector"] for stock in SNAPSHOT_STOCKS}
            verdict_colors = {
                "추천 후보": "green",
                "감시": "yellow",
                "확인 필요": "orange",
                "보류(선반영)": "gray",
                "제외": "red",
            }
            stock_html = []
            for row in sorted_rows:
                verdict = row[verdict_key]
                color = verdict_colors.get(verdict, "gray")
                selected_class = "jarvis-m1-stock-selected" if row["ticker"] == selected_ticker else ""
                confirmation = "예" if row["needs_confirmation"] else "-"
                stock_html.append(
                    f'<div class="jarvis-m1-stock jarvis-m1-stock-{color} {selected_class}">'
                    f'<div class="jarvis-m1-stock-name">{row["name"]}</div>'
                    f'<div class="jarvis-m1-stock-meta">{sector_by_ticker.get(row["ticker"], "-")} · '
                    f'{_display_verdict_name(verdict)} · {row[score_key]}점</div>'
                    f'<div class="jarvis-m1-stock-meta">확인 필요: {confirmation}</div>'
                    "</div>"
                )
            st.markdown(
                f'<div class="jarvis-m1-stock-list">{"".join(stock_html)}</div>',
                unsafe_allow_html=True,
            )

        selected_row = rows_by_ticker[selected_ticker]
        selected_verdict = selected_row[verdict_key]
        current_value = _get_snapshot_value(selected_ticker, "current")
        with right_col:
            st.markdown(f"## {selected_row['name']}")
            st.caption(
                f"{trade_mode} · {_display_verdict_name(selected_verdict)} · "
                f"{selected_row[score_key]}점"
            )
            metric_current, metric_open, metric_high, metric_turnover = st.columns(4)
            metric_current.metric(
                "현재가",
                "-" if current_value is None else f"{current_value:,.0f}",
                delta=(
                    None
                    if selected_row["change_pct"] is None
                    else _fmt_signed_pct(selected_row["change_pct"])
                ),
            )
            metric_open.metric(
                "시가 대비",
                "-"
                if selected_row["open_pos_pct"] is None
                else _fmt_signed_pct(selected_row["open_pos_pct"]),
            )
            metric_high.metric(
                "고점 대비",
                "-"
                if selected_row["high_drop_pct"] is None
                else _fmt_signed_pct(selected_row["high_drop_pct"]),
            )
            metric_turnover.metric(
                "시총 대비 거래대금",
                "-"
                if selected_row["turnover_ratio_pct"] is None
                else f"{selected_row['turnover_ratio_pct']:.2f}%",
            )

            if trade_mode == "단타":
                selected_score = selected_row["danta_score"]
                selected_score_reason = selected_row["danta_score_reason"]
                selected_top_reason = selected_row["danta_top_candidate_reason"]
                selected_penalty_reason = selected_row["danta_penalty_reason"]
            else:
                selected_score = selected_row["swing_score"]
                selected_score_reason = selected_row["swing_score_reason"]
                selected_top_reason = selected_row["swing_top_candidate_reason"]
                selected_penalty_reason = selected_row["swing_penalty_reason"]

            st.markdown("#### 핵심 근거")
            st.write(f"점수: {selected_score}")
            st.write(f"점수 근거: {selected_score_reason}")
            st.write(f"1순위 후보 근거: {selected_top_reason}")
            st.write(f"감점 이유: {selected_penalty_reason}")
            st.write("매수 확정 여부: 미확정")

            with st.expander("전체 근거", expanded=False):
                st.write(f"단타 점수: {selected_row['danta_score']}")
                st.write(f"단타 판정: {_display_verdict_name(selected_row['danta_verdict'])}")
                st.write(f"단타 점수 근거: {selected_row['danta_score_reason']}")
                st.write(f"단타 1순위 후보 근거: {selected_row['danta_top_candidate_reason']}")
                st.write(f"단타 감점 이유: {selected_row['danta_penalty_reason']}")
                st.write(f"스윙 점수: {selected_row['swing_score']}")
                st.write(f"스윙 판정: {_display_verdict_name(selected_row['swing_verdict'])}")
                st.write(f"스윙 점수 근거: {selected_row['swing_score_reason']}")
                st.write(f"스윙 1순위 후보 근거: {selected_row['swing_top_candidate_reason']}")
                st.write(f"스윙 감점 이유: {selected_row['swing_penalty_reason']}")
                st.write(f"시가 대비: {_fmt_signed_pct(selected_row['open_pos_pct'])}")
                st.write(f"고점 대비: {_fmt_signed_pct(selected_row['high_drop_pct'])}")
                st.write(
                    "시총 대비 거래대금: "
                    + (
                        "-"
                        if selected_row["turnover_ratio_pct"] is None
                        else f"{selected_row['turnover_ratio_pct']:.2f}%"
                    )
                )
                st.write("validation_errors:", selected_row["validation_errors"] or "-")
                st.write(f"단타 매수 확정 조건: {selected_row['danta_buy_confirm_condition']}")
                st.write(f"스윙 매수 확정 조건: {selected_row['swing_buy_confirm_condition']}")

            _render_risk_and_warning_inputs(selected_ticker, "KR", compact=True)

    theme_col, event_col = st.columns(2, gap="large")
    with theme_col:
        st.markdown("#### 테마 참고판")
        _render_kr_theme_chip_editor()

    with event_col:
        st.markdown("#### 이벤트 캘린더")
        st.markdown(
            '<div class="jarvis-m1-panel">'
            '<div class="jarvis-m1-muted">등록된 검증 일정이 없습니다.</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    st.caption("실제 자동조회·입력·저장은 아래 기존 화면을 사용합니다.")


def _render_review_tag_editors(saved_item, display_name, trade_mode, key_prefix="tab4_"):
    """Render the existing review tag/filter editors for one report item."""
    item_id = saved_item.get("id")
    if not item_id:
        return
    with st.expander("복기 태그·필터 기록", expanded=False):
        with st.expander(f"필터 무시 기록 - {display_name} ({trade_mode})"):
            fi_key = f"{key_prefix}filterignore_{item_id}"
            fi_options = ["미입력", "아니오", "예"]
            fi_default = {"YES": "예", "NO": "아니오"}.get(saved_item.get("filter_ignored"), "미입력")
            filter_ignored_in = st.selectbox("필터 무시 여부", fi_options, index=fi_options.index(fi_default), key=f"{fi_key}_ignored")
            stored_codes = [c.strip() for c in (saved_item.get("filter_ignore_reason") or "").split(",") if c.strip()]
            stored_tag_codes = [c for c in stored_codes if c in FILTER_IGNORE_TAG_CODE_TO_LABEL]
            stored_emotion_codes = [c for c in stored_codes if c in EMOTION_TAG_CODE_TO_LABEL]
            if filter_ignored_in == "예":
                ignore_tags_in = st.multiselect("필터 무시 태그", [label for _, label in FILTER_IGNORE_TAG_OPTIONS], default=[FILTER_IGNORE_TAG_CODE_TO_LABEL[c] for c in stored_tag_codes], key=f"{fi_key}_tags")
                emotion_options = ["미입력"] + [label for _, label in EMOTION_TAG_OPTIONS]
                emotion_default = EMOTION_TAG_CODE_TO_LABEL.get(stored_emotion_codes[0], "미입력") if stored_emotion_codes else "미입력"
                emotion_in = st.selectbox("감정 태그", emotion_options, index=emotion_options.index(emotion_default), key=f"{fi_key}_emotion")
            else:
                ignore_tags_in = []
                emotion_in = "미입력"
                st.caption("필터 무시 여부를 '예'로 선택하면 태그를 입력할 수 있습니다.")
            memo_in = st.text_input("자유 메모", value=saved_item.get("filter_ignore_memo") or "", key=f"{fi_key}_memo")
            st.caption(f"참고 R수익률(기존 값, 새로 계산하지 않음): {_fmt_result_r(saved_item.get('result_r'))}")
            if st.button("필터 무시 기록 저장", key=f"{fi_key}_save"):
                final_filter_ignored = {"예": "YES", "아니오": "NO"}.get(filter_ignored_in)
                final_tag_codes = [FILTER_IGNORE_TAG_LABEL_TO_CODE[label] for label in ignore_tags_in]
                if emotion_in != "미입력":
                    final_tag_codes.append(EMOTION_TAG_LABEL_TO_CODE[emotion_in])
                db.update_report_item_filter_ignore(
                    item_id,
                    final_filter_ignored,
                    ",".join(final_tag_codes) if final_tag_codes else None,
                    memo_in.strip() or None,
                )
                st.success("필터 무시 기록이 저장되었습니다.")
                st.rerun()
        with st.expander(f"플레이북 태그 - {display_name} ({trade_mode})"):
            pb_key = f"{key_prefix}playbook_{item_id}"
            stored_codes = [c.strip() for c in (saved_item.get("playbook_tags") or "").split(",") if c.strip()]
            pb_tags_in = st.multiselect("플레이북 태그", [label for _, label in PLAYBOOK_TAG_OPTIONS], default=[PLAYBOOK_TAG_CODE_TO_LABEL[c] for c in stored_codes if c in PLAYBOOK_TAG_CODE_TO_LABEL], key=f"{pb_key}_tags")
            if st.button("플레이북 태그 저장", key=f"{pb_key}_save"):
                db.update_report_item_playbook_tags(
                    item_id,
                    ",".join(PLAYBOOK_TAG_LABEL_TO_CODE[label] for label in pb_tags_in) or None,
                )
                st.success("플레이북 태그가 저장되었습니다.")
                st.rerun()
        with st.expander(f"테마 태그 - {display_name} ({trade_mode})"):
            theme_key = f"{key_prefix}themetag_{item_id}"
            theme_stored = db.parse_theme_tags(saved_item.get("theme_tags"))
            st.caption(f"현재 테마 태그: {', '.join(theme_stored) if theme_stored else '없음'}")
            theme_tags_in = st.multiselect("테마 태그", THEME_TAG_OPTIONS, default=[t for t in theme_stored if t in THEME_TAG_OPTIONS], key=f"{theme_key}_tags")
            if st.button("테마 태그 저장", key=f"{theme_key}_save"):
                db.update_report_item_theme_tags(item_id, theme_tags_in)
                st.success("테마 태그가 저장되었습니다.")
                st.rerun()


with tab_kr:
    st.subheader("한국장")
    _render_kr_fable_mockup1_preview()
    st.markdown("---")
    st.markdown("### 기존 입력·자동조회·저장 화면")
    st.caption("아래 기존 기능은 변경하지 않았습니다. 목업 승인 전까지 실제 입력과 저장은 기존 화면을 사용합니다.")
    # 1. 시장 분위기 (기본값은 전부 "미입력" — 위험해 보이는 강함/상승/순매수 기본값 금지)
    # 이 값은 미국장 탭의 시장 분위기 점수/상한 계산에서도 그대로 사용됩니다.
    st.caption("시장 분위기는 자비스가 먼저 자동 확인합니다. 안 나오거나 부족한 항목만 직접 입력하세요.")
    st.markdown("### 0단계 시장 분위기 입력(선택)")
    st.caption("입력하지 않아도 계산은 가능합니다. 입력값은 매수 신호가 아니라 오늘 판단의 참고값입니다.")
    st.caption("시장 분위기·주가 자동조회·미리보기 실행은 화면 상단에서 진행합니다.")

    if st.session_state.get("kr_mood_auto_results"):
        if not st.session_state.get("kr_mood_auto_any_ok"):
            st.warning(
                "시장 분위기 자동 확인 실패. 네트워크 또는 데이터 제공처 문제일 수 있습니다. "
                "수동 입력 없이도 ① 오늘 주가 자동 채우기는 사용할 수 있습니다."
            )
        else:
            st.markdown("#### 0단계 시장 분위기 자동 확인 결과")
            st.dataframe(
                pd.DataFrame(st.session_state["kr_mood_auto_results"]),
                width="stretch",
                hide_index=True,
            )
            st.caption("SOXX/SMH는 미국 반도체 ETF입니다. 둘 다 강하면 국내 반도체 투자심리에 우호적입니다.")
            _soxx_row = next(
                (r for r in st.session_state["kr_mood_auto_results"] if r["항목"] == "SOXX"), None
            )
            _smh_row = next(
                (r for r in st.session_state["kr_mood_auto_results"] if r["항목"] == "SMH"), None
            )
            if _soxx_row and _smh_row and "확인 불가" not in (_soxx_row["판정"], _smh_row["판정"]):
                _soxx_strong = _soxx_row["판정"].startswith("강함")
                _soxx_weak = _soxx_row["판정"].startswith("약함")
                _smh_strong = _smh_row["판정"].startswith("강함")
                _smh_weak = _smh_row["판정"].startswith("약함")
                if _soxx_strong and _smh_strong:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#1b4332", "#2d6a4f", "#7ee6a8"
                    _mood_verdict_msg = (
                        "반도체 우호 신호 — SOXX와 SMH가 모두 강세입니다. 미국 반도체 투자심리가 "
                        "우호적이므로 삼성전자·SK하이닉스 등 국내 반도체 대형주 분위기에 긍정적입니다."
                    )
                elif _soxx_weak and _smh_weak:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#4a2e05", "#d97706", "#fbbf6a"
                    _mood_verdict_msg = (
                        "반도체 부담 신호 — SOXX와 SMH가 모두 약세입니다. 미국 반도체 투자심리가 "
                        "약하므로 국내 반도체 대형주에는 부담 요인입니다."
                    )
                else:
                    _mood_verdict_bg, _mood_verdict_border, _mood_verdict_text = "#1e3a5f", "#3b82f6", "#93c5fd"
                    _mood_verdict_msg = (
                        "반도체 혼조 신호 — SOXX와 SMH 흐름이 엇갈립니다. "
                        "국내 반도체주는 추가 확인이 필요합니다."
                    )
                st.markdown(
                    f"""
                    <div style="background-color:{_mood_verdict_bg};border:2px solid {_mood_verdict_border};
                    border-radius:10px;padding:16px;margin-top:8px;">
                    <span style="font-size:1.15rem;font-weight:800;color:{_mood_verdict_text};">
                    {_mood_verdict_msg}
                    </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
            st.markdown(
                """
                <div style="background-color:#74d99f;border:1px solid #22c55e;color:#052e16;
                font-size:1.05rem;font-weight:800;border-radius:8px;padding:6px 12px;
                margin-top:14px;margin-bottom:10px;">
                🔥 오늘 강세 테마 1차 참고판 (저장 안 됨)
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            st.caption("테마 입력은 화면 상단의 테마 참고판에서 진행합니다.")
            st.caption("자동 조회 결과는 화면 확인용이며 저장되지 않습니다.")

    st.caption("외국인 선물 방향과 프로그램 수급 방향은 이번 1차 자동화에서는 수동 확인 항목입니다.")

    with st.expander("0단계 시장 분위기 수동 입력(선택) - 자동 확인이 부족할 때만 사용", expanded=False):
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

        st.markdown(
            f"""
            <div style="background-color:#171a21;border:1px solid #303642;border-radius:10px;padding:14px;margin-top:8px;">
            <b>시장 분위기 입력값 확인</b><br>
            - 나스닥100 선물: {nq_change:+.2f}%<br>
            - SOXX/SMH 방향: {soxx_dir}<br>
            - 달러/원 방향: {usdkrw_dir}<br>
            - KOSPI200 선물 방향: {kospi200_futures_dir}<br>
            - 외국인 선물 방향: {foreign_futures_dir}<br>
            - 프로그램 수급 방향: {program_dir}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "위에서 입력한 값입니다(자동 분석 아님). 매수 신호가 아니라 참고용이며, "
            "이 화면 입력값은 저장되지 않습니다."
        )
        _kr_mood_unset_count = sum(
            1 for v in (soxx_dir, usdkrw_dir, kospi200_futures_dir, foreign_futures_dir, program_dir)
            if v == "미입력"
        )
        if _kr_mood_unset_count >= 4:
            st.caption("시장 분위기 판단값이 거의 입력되지 않았습니다. 필요하면 위 항목을 선택하세요.")

    # 2. 간편 스냅샷 입력 (붙여넣기 자동 채우기)
    st.markdown("---")
    with st.expander("① 오늘 주가 채우기 - 직접 붙여넣기", expanded=False):
        st.caption(
            "형식: 종목명 / 현재가 / 전일종가 / 시가 / 장중고가 / 장중저가 / 거래대금 / 시가총액 "
            "(등록된 7개 종목만 인식하며, 숫자에 쉼표가 있어도 처리됩니다. 맨 뒤에 거래량을 "
            "추가한 종목명 / ... / 시가총액 / 거래량(9개 필드) 형식도 지원하며, 거래량 없이 "
            "기존 8개 필드로 붙여넣어도 그대로 동작합니다.)"
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
    st.caption("시장 분위기·주가 자동조회·미리보기 실행은 화면 상단에서 진행합니다.")

    if st.session_state.get("snap_auto_fill_results"):
        auto_fill_results = st.session_state["snap_auto_fill_results"]
        _render_auto_fetch_status_summary(auto_fill_results, SNAPSHOT_STOCKS, "kr_")
        st.caption("거래대금·시가총액은 근사값입니다 (거래량×현재가, 상장주식수×현재가). 정확한 실제 값이 아닙니다.")

    # 3. 계산 결과 요약표 (입력 카드보다 위에 표시 — session_state를 위젯 생성 전에 미리 읽음)
    st.markdown("---")
    st.markdown("### ② 오늘 주가 계산 결과")
    st.caption(
        "메모는 자동판정이 아니라 참고용 경고 문구입니다 (예: 고점 대비 밀림률이 -3% 이하이면 "
        "'고점 대비 밀림 큼'). 관심 후보/관찰 후보 같은 판정은 이 화면에서 만들지 않습니다."
    )
    st.caption(
        "정렬 기준: 단기 관심점수 높은 순 → 며칠 관심점수 높은 순 → 시총대비 거래대금 높은 순입니다. "
        "점수는 매수 신호가 아니라 관심 후보 정렬 기준입니다."
    )
    st.caption("※ 시가대비·고점대비·저점대비는 모두 오늘 장중 기준입니다. 전일 대비가 아닙니다.")

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
                "단기 관심 점수": int(round(danta_score)),
                "며칠 관심 점수": int(round(swing_score)),
                "메모": "; ".join(memos) if memos else "-",
                "현재가": "-" if current is None else f"{current:,.0f}",
                "전일대비(%)": _fmt_signed_pct(change_pct),
                "시가대비(오늘)": _fmt_signed_pct(open_pos_pct),
                "고점대비(오늘)": _fmt_signed_pct(high_drop_pct),
                "저점대비(오늘)": _fmt_signed_pct(low_recover_pct),
                "시총대비 거래대금(%)": _fmt_pct(turnover_ratio_pct),
                "섹터": s["sector"],
                "_sort_key": (
                    danta_score, swing_score,
                    turnover_ratio_pct if turnover_ratio_pct is not None else float("-inf"),
                ),
                "_change_pct_raw": change_pct,
                "_open_pos_raw": open_pos_pct,
                "_high_drop_raw": high_drop_pct,
                "_low_recover_raw": low_recover_pct,
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
                "risk_fields": _collect_risk_fields(ticker),
                "validation_errors": _validate_snapshot_price_inputs(
                    s["name"], current, open_price, high, low,
                    _get_snapshot_value(ticker, "volume"), turnover,
                ),
            }
        )

    result_rows.sort(key=lambda r: r["_sort_key"], reverse=True)
    change_pct_raw_list = [r.get("_change_pct_raw") for r in result_rows]
    open_pos_raw_list = [r.get("_open_pos_raw") for r in result_rows]
    high_drop_raw_list = [r.get("_high_drop_raw") for r in result_rows]
    low_recover_raw_list = [r.get("_low_recover_raw") for r in result_rows]
    for r in result_rows:
        r.pop("_sort_key", None)
        r.pop("_change_pct_raw", None)
        r.pop("_open_pos_raw", None)
        r.pop("_high_drop_raw", None)
        r.pop("_low_recover_raw", None)

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

            c5, c6, c7, c8 = st.columns(4)
            c5.number_input("장중저가", value=0.0, step=100.0, key=prefix + "low")
            c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
            c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")
            c8.number_input("거래량", value=0.0, step=1000.0, key=prefix + "volume")
            _render_snapshot_calc_summary(s["ticker"])
            st.markdown("---")
            st.caption("리스크 입력은 화면 상단의 선택 종목 상세에서 진행합니다.")
            st.caption(
                "상세 카드는 입력·수정 전용이며 카드 내부에는 저장 실행 버튼이 없습니다. "
                "최종 저장은 위쪽 ‘▼ 저장 전 확인으로 이동’ 구역에서 진행합니다."
            )

    if not result_rows:
        st.info("아직 입력된 종목이 없습니다. 아래 '종목별 상세 입력' 카드나 '주가 직접 붙여넣기'로 값을 넣어주세요.")
    else:
        def _signed_pct_color_styler(raw_list):
            def _apply(col):
                styles = []
                for raw in raw_list:
                    if raw is None or raw == 0:
                        styles.append("")
                    elif raw > 0:
                        styles.append("color: #ff4b4b")
                    else:
                        styles.append("color: #4b9fff")
                return styles
            return _apply

        result_df = pd.DataFrame(result_rows)
        styled_result_df = (
            result_df.style
            .apply(_signed_pct_color_styler(change_pct_raw_list), subset=["전일대비(%)"])
            .apply(_signed_pct_color_styler(open_pos_raw_list), subset=["시가대비(오늘)"])
            .apply(_signed_pct_color_styler(high_drop_raw_list), subset=["고점대비(오늘)"])
            .apply(_signed_pct_color_styler(low_recover_raw_list), subset=["저점대비(오늘)"])
            .set_properties(
                subset=[
                    "단기 관심 점수", "며칠 관심 점수", "현재가", "전일대비(%)",
                    "시가대비(오늘)", "고점대비(오늘)", "저점대비(오늘)", "시총대비 거래대금(%)",
                ],
                **{"text-align": "right"},
            )
        )
        st.dataframe(styled_result_df, width="stretch", hide_index=True)
        st.caption("시총 대비 거래대금 '확인 필요' 기준은 5% 이상(1차 버전 임시 기준)입니다.")
        st.caption(
            "점수는 자동매수 신호가 아니라 장중 후보 비교용 참고 점수입니다. 외부 환경과 "
            "종가 품질이 미입력인 경우 최고점은 제한됩니다."
        )

        st.caption("리스크 관리 공통 설정은 화면 상단의 선택 종목 상세에서 진행합니다.")

        st.caption("이 문장은 매수 추천이 아니라, 새 기록 입력칸에 붙여넣기 위한 초안입니다. 필요하면 수정 후 저장하세요.")
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

        st.markdown("---")
        st.markdown("#### 2단계 판단 미리보기 (저장 전, 자동 계산)")
        st.caption(
            "아직 저장하지 않은 상태의 참고용 미리보기입니다. 매수 신호가 아니며, 실제로 기록을 "
            "남기려면 아래 '▼ 저장 전 확인으로 이동' 버튼을 따로 눌러야 합니다. 이 미리보기 자체는 "
            "DB에 아무 것도 저장하지 않습니다."
        )
        _stage2_preview = build_kr_stage2_preview()
        st.caption(
            f"0단계 시장 분위기 반영: {'예' if _stage2_preview['stage0_reflected'] else '아니오 (수동 또는 미실행)'} / "
            f"1단계 오늘 주가 자동 채우기 반영: {'예' if _stage2_preview['stage1_reflected'] else '아니오 (수동 입력 값 기준)'}"
        )
        if not _stage2_preview["rows"]:
            st.info("아직 입력된 종목이 없어 2단계 판단 미리보기를 만들 수 없습니다.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "종목명": r["name"],
                            "단기 관심 점수": int(round(r["danta_score"])),
                            "며칠 관심 점수": int(round(r["swing_score"])),
                            "단타 판단": _display_verdict_name(r["danta_verdict"]),
                            "스윙 판단": _display_verdict_name(r["swing_verdict"]),
                            "확인 필요": "예" if r["needs_confirmation"] else "-",
                        }
                        for r in _stage2_preview["rows"]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.markdown("종목별 1순위 근거 / 감점 이유 (미리보기)")
            for r in _stage2_preview["rows"]:
                with st.expander(
                    f"{r['name']} — 단타 {_display_verdict_name(r['danta_verdict'])} / "
                    f"스윙 {_display_verdict_name(r['swing_verdict'])}"
                ):
                    st.write(f"단타 1순위 근거: {r['danta_top_candidate_reason']}")
                    st.write(f"단타 감점 이유: {r['danta_penalty_reason']}")
                    st.write(f"스윙 1순위 근거: {r['swing_top_candidate_reason']}")
                    st.write(f"스윙 감점 이유: {r['swing_penalty_reason']}")
                    if r["validation_errors"]:
                        st.warning("확인 필요: " + "; ".join(r["validation_errors"]))

        # 3-2. 국내장 기록 바로 저장 (새 기록 입력 화면을 거치지 않고 이 화면에서 바로 저장)
        # 한국 종목(SNAPSHOT_STOCKS)만 대상으로 한다 — 미국 종목은 여기 나오지 않는다.
        st.markdown("---")
        st.markdown("### 국내장 기록 바로 저장")
        st.caption(
            "현재 저장 기능을 유지한 확인 구역입니다. 첫 버튼은 즉시 저장하지 않고 저장 전 확인만 엽니다. "
            "실제 DB 저장은 확인 내용 아래의 최종 저장 버튼에서만 실행됩니다."
        )
        st.caption(
            "위 표의 한국 종목 7개만 대상으로 시장 KR / 단타·스윙을 함께 저장합니다. "
            "버튼을 누르면 바로 저장하지 않고 먼저 저장 전 확인 미리보기를 보여줍니다."
        )
        if st.button("▼ 저장 전 확인으로 이동", key="kr_quick_save", disabled=not snapshot_calc_data):
          st.session_state["kr_show_save_preview"] = True
          st.session_state.pop("kr_quick_preview_rows", None)
          st.session_state.pop("kr_quick_day_conclusion", None)
          st.session_state.pop("kr_quick_basis_text", None)
          all_kr_validation_errors = [e for calc in snapshot_calc_data for e in calc["validation_errors"]]
          if all_kr_validation_errors:
            st.error("입력값 오류로 저장할 수 없습니다:\n" + "\n".join(f"- {e}" for e in all_kr_validation_errors))
          else:
            # 미리보기(build_kr_stage2_preview())와 같은 판단 계산값을 재사용한다 — 미리보기와
            # 저장 결과가 서로 다른 값으로 보이는 사고를 막기 위함. 저장 흐름(items_to_save 구성,
            # db.save_report() 호출)은 그대로 두고, 판단 계산 부분만 대체한다.
            _stage2_preview_for_save = build_kr_stage2_preview()
            _stage2_rows_by_ticker = {r["ticker"]: r for r in _stage2_preview_for_save["rows"]}

            kr_preview_rows = []
            for calc in snapshot_calc_data:
                _s2row = _stage2_rows_by_ticker.get(calc["ticker"])
                if _s2row is not None:
                    danta_score = _s2row["danta_score"]
                    swing_score = _s2row["swing_score"]
                    danta_verdict = _s2row["danta_verdict"]
                    swing_verdict = _s2row["swing_verdict"]
                    danta_score_reason = _s2row["danta_score_reason"]
                    danta_penalty_reason = _s2row["danta_penalty_reason"]
                    swing_score_reason = _s2row["swing_score_reason"]
                    swing_penalty_reason = _s2row["swing_penalty_reason"]
                    danta_top_candidate_reason = _s2row["danta_top_candidate_reason"]
                    swing_top_candidate_reason = _s2row["swing_top_candidate_reason"]
                else:
                    # 방어적 대비책: 미리보기에 해당 종목이 없는 예외적인 경우 기존 방식대로 직접 계산한다.
                    danta_score = calc["danta_score"]
                    swing_score = calc["swing_score"]
                    danta_verdict = _kr_danta_verdict(danta_score)
                    swing_verdict = _kr_swing_verdict(swing_score)
                    danta_score_reason, danta_penalty_reason = _kr_preview_reasons(
                        calc["change_pct"], calc["open_pos_pct"], calc["high_drop_pct"], calc["turnover_ratio_pct"], "단타"
                    )
                    swing_score_reason, swing_penalty_reason = _kr_preview_reasons(
                        calc["change_pct"], calc["open_pos_pct"], calc["high_drop_pct"], calc["turnover_ratio_pct"], "스윙"
                    )
                    danta_top_candidate_reason = _kr_top_candidate_reason_text(
                        "단타", danta_score, _display_verdict_name(danta_verdict)
                    )
                    swing_top_candidate_reason = _kr_top_candidate_reason_text(
                        "스윙", swing_score, _display_verdict_name(swing_verdict)
                    )
                _preview_source_row = _s2row or {}
                change_pct = _preview_source_row.get("change_pct", calc["change_pct"])
                open_pos_pct = _preview_source_row.get("open_pos_pct", calc["open_pos_pct"])
                high_drop_pct = _preview_source_row.get("high_drop_pct", calc["high_drop_pct"])
                turnover_ratio_pct = _preview_source_row.get("turnover_ratio_pct", calc["turnover_ratio_pct"])
                turnover = _preview_source_row.get("turnover", _get_snapshot_value(calc["ticker"], "turnover"))
                risk_fields = _preview_source_row.get("risk_fields", calc["risk_fields"])
                danta_buy_confirm_condition = _preview_source_row.get(
                    "danta_buy_confirm_condition", _auto_buy_confirm_condition("단타", "KR")
                )
                swing_buy_confirm_condition = _preview_source_row.get(
                    "swing_buy_confirm_condition", _auto_buy_confirm_condition("스윙", "KR")
                )
                kr_preview_rows.append(
                    {
                        "name": calc["name"],
                        "ticker": calc["ticker"],
                        "danta_score": danta_score,
                        "swing_score": swing_score,
                        "danta_verdict": danta_verdict,
                        "swing_verdict": swing_verdict,
                        "change_pct": change_pct,
                        "open_pos_pct": open_pos_pct,
                        "high_drop_pct": high_drop_pct,
                        "turnover_ratio_pct": turnover_ratio_pct,
                        "turnover": turnover,
                        "danta_score_reason": danta_score_reason,
                        "danta_penalty_reason": danta_penalty_reason,
                        "swing_score_reason": swing_score_reason,
                        "swing_penalty_reason": swing_penalty_reason,
                        "danta_top_candidate_reason": danta_top_candidate_reason,
                        "swing_top_candidate_reason": swing_top_candidate_reason,
                        "danta_buy_confirm_condition": danta_buy_confirm_condition,
                        "swing_buy_confirm_condition": swing_buy_confirm_condition,
                        "risk_fields": risk_fields,
                    }
                )
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

        if st.session_state.get("kr_show_save_preview") and st.session_state.get("kr_quick_preview_rows"):
            kr_preview_rows = st.session_state["kr_quick_preview_rows"]
            preview_timing_class = db.classify_timing_class(datetime.now())
            st.markdown("#### 저장 전 확인 → 최종 저장")
            st.caption("이 구역의 최종 버튼 1개에서만 실제 DB 저장이 실행됩니다.")
            st.write("시장: KR")
            st.write(f"장 구분: {preview_timing_class}")
            st.write("판단 시점: 오늘 주가 확인 기반 국내장 판단")
            st.write(f"오늘 요약: {st.session_state['kr_quick_day_conclusion']}")
            st.write("판단 근거:")
            st.code(st.session_state["kr_quick_basis_text"])

            st.markdown("저장될 종목 목록 (자동계산 미리보기)")
            kr_danta_rank = _rank_scores([(row["ticker"], row["danta_score"]) for row in kr_preview_rows])
            kr_swing_rank = _rank_scores([(row["ticker"], row["swing_score"]) for row in kr_preview_rows])
            # 정렬: 1순위 후보(단타 또는 스윙)가 최우선, 그 다음 단기 관심점수 -> 며칠 관심점수 ->
            # 시총대비 거래대금 순으로 내림차순. 단타/스윙 둘 다 1순위 후보인 종목이 맨 위로 온다.
            kr_preview_rows_sorted = sorted(
                kr_preview_rows,
                key=lambda row: (
                    1 if (row["danta_verdict"] == "추천 후보" or row["swing_verdict"] == "추천 후보") else 0,
                    row["danta_score"],
                    row["swing_score"],
                    row["turnover_ratio_pct"] if row["turnover_ratio_pct"] is not None else float("-inf"),
                ),
                reverse=True,
            )
            kr_preview_open_pos_raw_list = [row["open_pos_pct"] for row in kr_preview_rows_sorted]
            kr_preview_high_drop_disp_raw_list = [
                (-row["high_drop_pct"] if row["high_drop_pct"] is not None else None)
                for row in kr_preview_rows_sorted
            ]

            def _preview_signed_pct_color_styler(raw_list):
                def _apply(col):
                    styles = []
                    for raw in raw_list:
                        if raw is None or raw == 0:
                            styles.append("")
                        elif raw > 0:
                            styles.append("color: #ff4b4b")
                        else:
                            styles.append("color: #4b9fff")
                    return styles
                return _apply

            kr_preview_df = pd.DataFrame(
                [
                    {
                        "종목명": row["name"],
                        "단타 판단": _display_verdict_name(row["danta_verdict"]),
                        "스윙 판단": _display_verdict_name(row["swing_verdict"]),
                        "단기 관심 점수": int(round(row["danta_score"])),
                        "며칠 관심 점수": int(round(row["swing_score"])),
                        "단타 순위": kr_danta_rank.get(row["ticker"], "미평가"),
                        "스윙 순위": kr_swing_rank.get(row["ticker"], "미평가"),
                        "현재가": f"{_get_snapshot_value(row['ticker'], 'current'):,.0f}",
                        "시가대비 등락률(%)": _fmt_signed_pct(row["open_pos_pct"]),
                        "고점 대비 밀림률(%)": _fmt_signed_pct(
                            -row["high_drop_pct"] if row["high_drop_pct"] is not None else None
                        ),
                        "거래대금": f"{row['turnover']:,.0f}원" if row["turnover"] else "-",
                        "시총 대비 거래대금(%)": _fmt_pct(row["turnover_ratio_pct"]),
                    }
                    for row in kr_preview_rows_sorted
                ]
            )
            kr_preview_styled_df = (
                kr_preview_df.style
                .apply(_preview_signed_pct_color_styler(kr_preview_open_pos_raw_list), subset=["시가대비 등락률(%)"])
                .apply(_preview_signed_pct_color_styler(kr_preview_high_drop_disp_raw_list), subset=["고점 대비 밀림률(%)"])
                .set_properties(
                    subset=[
                        "단기 관심 점수", "며칠 관심 점수", "현재가",
                        "시가대비 등락률(%)", "고점 대비 밀림률(%)", "거래대금", "시총 대비 거래대금(%)",
                    ],
                    **{"text-align": "right"},
                )
            )
            st.dataframe(kr_preview_styled_df, width="stretch", hide_index=True)

            st.caption(
                "점수는 자동매수 신호가 아닙니다. 직접 입력한 score가 없으므로 이 화면의 모든 점수는 "
                "'자동계산'입니다(직접 score를 입력할 수 있는 화면이 아닙니다)."
            )
            st.markdown("종목별 자동계산 근거 (단타/스윙 각각)")
            for row in kr_preview_rows:
                danta_label = kr_danta_rank.get(row["ticker"], "미평가")
                with st.expander(
                    f"[단타 {danta_label}] {row['name']} / {row['danta_score']:.0f}점 (자동계산)"
                ):
                    st.markdown(
                        f"**[단타 {danta_label}] {row['name']} / {row['danta_score']:.0f}점 (자동계산)**"
                    )
                    st.write(f"점수 근거: {row['danta_score_reason']}")
                    st.write(f"1순위 후보 근거: {row['danta_top_candidate_reason']}")
                    st.write(f"감점 이유: {row['danta_penalty_reason']}")
                    st.write("매수 확정 여부: 미확정")
                    st.write(f"매수 확정 조건: {row['danta_buy_confirm_condition']}")
                swing_label = kr_swing_rank.get(row["ticker"], "미평가")
                with st.expander(
                    f"[스윙 {swing_label}] {row['name']} / {row['swing_score']:.0f}점 (자동계산)"
                ):
                    st.markdown(
                        f"**[스윙 {swing_label}] {row['name']} / {row['swing_score']:.0f}점 (자동계산)**"
                    )
                    st.write(f"점수 근거: {row['swing_score_reason']}")
                    st.write(f"1순위 후보 근거: {row['swing_top_candidate_reason']}")
                    st.write(f"감점 이유: {row['swing_penalty_reason']}")
                    st.write("매수 확정 여부: 미확정")
                    st.write(f"매수 확정 조건: {row['swing_buy_confirm_condition']}")

            kcol1, kcol2 = st.columns(2)
            if kcol1.button("이 내용으로 최종 저장", type="primary", key="kr_quick_confirm_save"):
                items_to_save = []
                judged_at = datetime.now().isoformat(timespec="seconds")
                for row in kr_preview_rows:
                    basis_a = (
                        f"전일대비 {_fmt_signed_pct(row['change_pct'])}, "
                        f"시가대비 {_fmt_signed_pct(row['open_pos_pct'])}, "
                        f"고점대비 {_fmt_signed_pct(row['high_drop_pct'])}, "
                        f"시총대비 거래대금 {_fmt_signed_pct(row['turnover_ratio_pct'])}"
                    )
                    danta_verdict_display = _display_verdict_name(row["danta_verdict"])
                    swing_verdict_display = _display_verdict_name(row["swing_verdict"])
                    # 미리보기 단계에서 이미 계산한 근거를 그대로 재사용한다(미리보기와 저장 결과가
                    # 서로 다르게 보이지 않도록).
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
                            "score_reason": row["danta_score_reason"],
                            "top_candidate_reason": row["danta_top_candidate_reason"],
                            "penalty_reason": row["danta_penalty_reason"],
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": row["danta_buy_confirm_condition"],
                            "judged_at": judged_at,
                            **row["risk_fields"],
                        }
                    )
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
                            "score_reason": row["swing_score_reason"],
                            "top_candidate_reason": row["swing_top_candidate_reason"],
                            "penalty_reason": row["swing_penalty_reason"],
                            "buy_confirmed": "미확정",
                            "buy_confirm_condition": row["swing_buy_confirm_condition"],
                            "judged_at": judged_at,
                            **row["risk_fields"],
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
                st.session_state.pop("kr_show_save_preview", None)
                st.success(
                    "국내장 기록 저장 완료. 오늘 저장 요약, 지난 기록 보기, 저장 결과 확인에서 확인할 수 있습니다. "
                    f"(report_id={kr_report_id})"
                )
            if kcol2.button("취소", key="kr_quick_cancel_preview"):
                st.session_state.pop("kr_quick_preview_rows", None)
                st.session_state.pop("kr_quick_day_conclusion", None)
                st.session_state.pop("kr_quick_basis_text", None)
                st.session_state.pop("kr_show_save_preview", None)
                st.rerun()

with tab_us:
    st.subheader("미국장")
    st.caption(
        "스윙 전용 흐름(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT). 한국 종목은 다루지 않으며, "
        "시장 분위기는 한국장 탭 입력값을 그대로 사용합니다. 입력값은 저장되지 않으며, "
        "③ 스윙 기록 바로 저장을 눌렀을 때만 저장되어 오늘 저장 요약/지난 기록에 반영됩니다."
    )

    # 미국장 시장 분위기 요약 — 한국장 탭에서 입력한 값을 그대로 요약 표시만 한다(새 계산 없음).
    st.markdown("### 0단계 미국장 시장 분위기 확인")
    _us_nq_change = st.session_state.get("snap_nq_change", 0.0)
    _us_soxx_dir = st.session_state.get("snap_soxx_dir", "미입력")
    _us_usdkrw_dir = st.session_state.get("snap_usdkrw_dir", "미입력")
    st.markdown(
        f"""
        <div style="background-color:#171a21;border:1px solid #303642;border-radius:10px;padding:14px;margin-top:8px;">
        <b>미국장 시장 분위기 입력값 확인</b><br>
        - 나스닥100 선물: {_us_nq_change:+.2f}%<br>
        - SOXX/SMH 방향: {_us_soxx_dir}<br>
        - 달러/원 방향: {_us_usdkrw_dir}<br>
        - 미국장 판단 기준: 실시간 단타 아님, 스윙 후보 확인용
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("미국장은 한국시간 밤에 실시간 단타로 보지 않고, 전일 종가와 스윙 후보를 확인하는 용도입니다.")

    # ---- 미국장 테마 레이더 1차 참고판 (수기 참고용, 저장/점수/판단 미반영) ----
    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="background-color:#74d99f;border:1px solid #22c55e;color:#052e16;
        font-size:1.05rem;font-weight:800;border-radius:8px;padding:6px 12px;
        margin-top:14px;margin-bottom:10px;">
        🌐 미국장 테마 레이더 1차 참고판 (저장 안 됨)
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
    with st.expander("펼쳐서 테마 레이더 입력하기", expanded=False):
        st.caption(
            "이 영역은 저장/점수/판단에 반영되지 않는 수기 참고판입니다. "
            "미국장 테마와 한국장 연결 가능성을 빠르게 정리합니다."
        )
        _us_theme_watch_rows = [
            {
                "테마": theme,
                "참고 지표": indicators,
                "상태": "확인 필요",
                "대장주": "",
                "후발주": "",
                "추격주의": "",
                "메모": "",
            }
            for theme, indicators in [
                ("AI/반도체", "SOXX, SMH, NVDA, AVGO, AMD"),
                ("금리/성장주", "QQQ, VIX, 미국 10년물, DXY"),
                ("전력망/원전", "XLU, GRID, URA"),
                ("방산/전쟁", "ITA, XAR, LMT, NOC"),
                ("에너지/유가", "WTI, XLE, XOP"),
                ("자동차/전기차", "TSLA, LIT"),
                ("바이오", "XBI, IBB"),
            ]
        ]
        st.data_editor(
            pd.DataFrame(_us_theme_watch_rows),
            key="us_theme_watch_editor",
            width="stretch",
            height=308,
            row_height=38,
            hide_index=True,
            num_rows="fixed",
            disabled=["테마", "참고 지표"],
            column_config={
                "상태": st.column_config.SelectboxColumn(
                    "상태",
                    options=["강함", "감시", "보통", "약함", "확인 필요"],
                    required=True,
                ),
                "대장주": st.column_config.TextColumn("대장주"),
                "후발주": st.column_config.TextColumn("후발주"),
                "추격주의": st.column_config.TextColumn("추격주의"),
                "메모": st.column_config.TextColumn("메모"),
            },
        )

    _us_today_loss_r = st.session_state.get("risk_today_loss_r", 0.0)
    if _us_today_loss_r <= -2:
        st.error("금일 신규 판단 중지 - 당일 손실 -2R 도달")

    # 1. 미국장 기본 종목 불러오기 (TSLA/AMD/AVGO/META/GOOGL/AAPL/NVDA/MSFT — 저장 없음)
    st.markdown("---")
    st.caption(
        "미국장 스윙 기록 바로 저장에 쓸 미국 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT) "
        "시세를 yfinance(우선)/FinanceDataReader(보조)로 불러옵니다. 조회 결과는 저장되지 않고 화면 계산에만 쓰입니다."
    )
    if st.button("① 미국장 기본 종목 불러오기", key="us_stock_auto_fill"):
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
        _render_auto_fetch_status_summary(us_auto_fill_results, US_SNAPSHOT_STOCKS, "us_")
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
        breakdown["turnover"] = turnover
        breakdown["risk_fields"] = _collect_risk_fields(ticker)
        breakdown["validation_errors"] = _validate_snapshot_price_inputs(
            s["name"], current, open_price, high, low, _get_snapshot_value(ticker, "volume"), turnover,
        )
        us_snapshot_calc_data.append(breakdown)

    st.markdown("---")
    st.markdown("### ② 미국장 스윙 계산 결과")
    st.caption(
        "정렬 기준: 총점 높은 순 → 거래/탄력 점수 높은 순 → 위험 감점 작은 순입니다. "
        "점수는 매수 신호가 아니라 관심 후보 정렬 기준입니다."
    )
    if not us_snapshot_calc_data:
        st.info("아직 불러온 종목 데이터가 없습니다. 위 '① 미국장 기본 종목 불러오기'를 먼저 눌러주세요.")
    else:
        _us_calc_rank = _rank_scores([(r["ticker"], r["total_score"]) for r in us_snapshot_calc_data])
        # 정렬: 스윙 판단이 1순위 후보인 종목이 최우선, 그 다음 총점 -> 거래/탄력 점수 ->
        # 위험 감점(작은 순=0에 가까운 순) 내림차순.
        _us_calc_sorted = sorted(
            us_snapshot_calc_data,
            key=lambda r: (
                1 if r["verdict"] == "추천 후보" else 0,
                r["total_score"], r["momentum_score"], r["risk_score"],
            ),
            reverse=True,
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "종목명": r["name"],
                        "티커": r["ticker"],
                        "스윙 순위": _us_calc_rank.get(r["ticker"], "미평가"),
                        "총점": r["total_score"],
                        "스윙/며칠 관심점수": r["close_pos_score"],
                        "단기/상승률 점수": r["upside_score"],
                        "거래/탄력 점수": r["momentum_score"],
                        "위험 감점": r["risk_score"],
                        "판단": r["tier_label"],
                        "1순위 근거": r["priority_reason"],
                    }
                    for r in _us_calc_sorted
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    with st.expander("리스크 관리 설정(v1.1) — 필요할 때 펼치기", expanded=False):
        _us_risk_account_size = st.session_state.get("risk_account_size", 0.0)
        _us_risk_percent = st.session_state.get("risk_percent_setting", 1.0)
        st.caption(
            f"한국장 탭에서 입력한 값입니다: 계좌금액 {_us_risk_account_size:,.0f} / "
            f"1회 리스크 {_us_risk_percent:.1f}%"
        )

    st.markdown("---")
    st.markdown("### ③ 미국장 스윙 기록 바로 저장")
    st.caption(
        "미국장 기본 종목(TSLA, AMD, AVGO, META, GOOGL, AAPL, NVDA, MSFT)만 대상으로 전부 "
        "시장 US / 스윙으로 저장합니다 (단타는 만들지 않습니다). 버튼을 누르면 바로 저장하지 않고 "
        "먼저 저장 전 확인 미리보기(점수 근거표 포함)를 보여줍니다."
    )
    if not us_snapshot_calc_data:
        st.info("미국장 스윙 기록을 저장하려면 먼저 미국장 종목 데이터를 불러와야 합니다.")
    if st.button("③ 미국장 스윙 기록 바로 저장", key="us_swing_quick_save", disabled=not us_snapshot_calc_data):
      st.session_state["us_show_save_preview"] = True
      st.session_state.pop("us_swing_preview_rows", None)
      st.session_state.pop("us_swing_day_conclusion", None)
      st.session_state.pop("us_swing_basis_text", None)
      all_us_validation_errors = [e for calc in us_snapshot_calc_data for e in calc["validation_errors"]]
      if all_us_validation_errors:
        st.error("입력값 오류로 저장할 수 없습니다:\n" + "\n".join(f"- {e}" for e in all_us_validation_errors))
      else:
        preview_rows = sorted(
            us_snapshot_calc_data,
            key=lambda r: (r["total_score"], r["momentum_score"]),
            reverse=True,
        )
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

    if st.session_state.get("us_show_save_preview") and st.session_state.get("us_swing_preview_rows"):
        preview_rows = st.session_state["us_swing_preview_rows"]
        st.markdown("#### 저장 전 확인 미리보기")
        st.write("시장: US")
        st.write("장 구분: 장마감")
        st.write("판단 시점: 미국장 마감 후 스윙 판단")
        st.write(f"오늘 요약: {st.session_state['us_swing_day_conclusion']}")
        st.write("판단 근거:")
        st.code(st.session_state["us_swing_basis_text"])

        st.markdown("저장될 종목 목록 (자동계산 미리보기)")
        us_swing_rank = _rank_scores([(row["ticker"], row["total_score"]) for row in preview_rows])
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "종목명": row["name"],
                        "티커": row["ticker"],
                        "시장": "US",
                        "매매유형": "스윙",
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
                        "시가 대비 등락률(%)": _fmt_pct(row["open_pos_pct"]),
                        "고점 대비 밀림률(%)": _fmt_pct(
                            -row["high_drop_pct"] if row["high_drop_pct"] is not None else None
                        ),
                        "거래대금": f"{row['turnover']:,.0f}" if row["turnover"] else "-",
                        "시총 대비 거래대금(%)": _fmt_pct(row["turnover_ratio_pct"]),
                    }
                    for row in preview_rows
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "점수는 자동매수 신호가 아닙니다. 직접 입력한 score가 없으므로 이 화면의 모든 점수는 "
            "'자동계산'입니다(직접 score를 입력할 수 있는 화면이 아닙니다)."
        )

        st.markdown("종목별 점수 근거 문장")
        for row in preview_rows:
            rank_label = us_swing_rank.get(row["ticker"], "미평가")
            with st.expander(f"[스윙 {rank_label}] {row['name']} / {row['total_score']:.0f}점 (자동계산)"):
                st.markdown(f"**[스윙 {rank_label}] {row['name']} / {row['total_score']:.0f}점 (자동계산)**")
                st.text(_us_swing_narrative_text(row))

        pcol1, pcol2 = st.columns(2)
        if pcol1.button("이 내용으로 미국장 최종 저장", type="primary", key="us_final_save"):
            us_judged_at = datetime.now().isoformat(timespec="seconds")
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
                    "judged_at": us_judged_at,
                    **row["risk_fields"],
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
            st.session_state.pop("us_show_save_preview", None)
            st.success(f"미국장 스윙 기록 저장 완료 (report_id={us_report_id})")
        if pcol2.button("취소", key="us_cancel_save_preview"):
            st.session_state.pop("us_swing_preview_rows", None)
            st.session_state.pop("us_swing_day_conclusion", None)
            st.session_state.pop("us_swing_basis_text", None)
            st.session_state.pop("us_show_save_preview", None)
            st.rerun()

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

            c5, c6, c7, c8 = st.columns(4)
            c5.number_input("장중저가", value=0.0, step=1.0, key=prefix + "low")
            c6.number_input("거래대금", value=0.0, step=1000000.0, key=prefix + "turnover")
            c7.number_input("시가총액", value=0.0, step=1000000.0, key=prefix + "market_cap")
            c8.number_input("거래량", value=0.0, step=1000.0, key=prefix + "volume")
            _render_snapshot_calc_summary(s["ticker"])
            st.text_input(
                "재료 메모 (선택, 없으면 재료 점수는 낮은 기본값으로 처리됩니다)",
                key=prefix + "material_memo",
                placeholder="예: 로보택시 기대감, AI 실적 발표, 신제품 발표 등",
            )
            st.markdown("---")
            _render_risk_and_warning_inputs(s["ticker"], "US")

def _classify_actual_trade_status(saved_item):
    """저장된 actual_action/청산 필드만으로 ③ 화면 진행 상태를 분류한다."""
    action = db.normalize_actual_action(saved_item.get("actual_action"))
    if action == "미기록":
        return "행동 미입력"
    if action == "보류":
        return "보류"
    if action == "제외":
        return "제외"
    if (
        action == "매수"
        and saved_item.get("actual_exit_price") is not None
        and saved_item.get("actual_exit_date")
    ):
        return "청산 완료"
    if action == "매수":
        return "보유 중"
    return "행동 미입력"


def _render_judgment_outcome_save_button(selected_report_id, perf_rows_all, key_prefix=""):
    _item_lookup = _build_item_judgment_lookup()
    _eval_by_item_id = {}
    for _row in perf_rows_all:
        if _row["report_id"] != selected_report_id:
            continue
        _item = _item_lookup.get(
            (_row["report_id"], _row["ticker"], _row["trade_mode"]), {}
        )
        if _item.get("id"):
            _eval_by_item_id[_item["id"]] = _row

    _candidate_rows = []
    for _item_id, _eval_result in _eval_by_item_id.items():
        _candidate_rows.extend(
            performance.build_judgment_outcome_rows(_item_id, _eval_result)
        )

    st.caption(
        f"저장 가능: 종목 {len(_eval_by_item_id)}개 / "
        f"성과 {len(_candidate_rows)}건"
    )

    if st.button("판단 성과 저장", key=f"{key_prefix}judgment_outcome_save_button"):
        if not _candidate_rows:
            st.info("저장 가능한 완료 성과가 없습니다.")
        else:
            try:
                _saved_count = db.upsert_report_item_outcomes(_candidate_rows)
            except Exception as _save_err:
                st.error(f"판단 성과 저장 중 오류가 발생했습니다: {_save_err}")
            else:
                st.success(f"판단 성과 {_saved_count}건을 저장·갱신했습니다.")
                _after_save = db.get_report_outcomes(selected_report_id)
                _judgment_after_save = [
                    o for o in _after_save if o["entry_basis"] == "judgment"
                ]
                _horizons = sorted(
                    {o["horizon_sessions"] for o in _judgment_after_save}
                )
                _horizons_display = (
                    "·".join(f"{h}거래일" for h in _horizons)
                    if _horizons else "-"
                )
                st.caption(
                    f"저장 상태: judgment {len(_judgment_after_save)}건 / "
                    f"{_horizons_display}"
                )


def _render_actual_outcome_save_section(selected_report_id, key_prefix="") -> None:
    _actual_save_all_items = db.get_report_items(selected_report_id)
    _actual_save_target_items = [
        _ai
        for _ai in _actual_save_all_items
        if _ai.get("actual_action") == "매수"
        and _ai.get("actual_entry_price") is not None
        and _ai.get("actual_entry_date") is not None
    ]

    st.caption(f"실매매 기록 완료: {len(_actual_save_target_items)}종목")

    if st.button("실매매 성과 저장", key=f"{key_prefix}actual_outcome_save_button"):
        if not _actual_save_target_items:
            st.info("저장 가능한 완료 실매매 성과가 없습니다.")
        else:
            # 종목당 가격 조회 1회(ticker 기준 캐시), 벤치마크는 심볼별로 묶어
            # 필요한 날짜 범위를 합친 뒤 심볼당 1회만 조회한다(horizon별 재조회 없음).
            _actual_price_df_cache = {}
            for _ai in _actual_save_target_items:
                _ticker = (_ai.get("ticker") or "").strip()
                if not _ticker or _ticker in _actual_price_df_cache:
                    continue
                _entry_dt = datetime.strptime(_ai["actual_entry_date"], "%Y-%m-%d")
                _start = (_entry_dt - timedelta(days=10)).strftime("%Y-%m-%d")
                _end = (_entry_dt + timedelta(days=45)).strftime("%Y-%m-%d")
                _actual_price_df_cache[_ticker] = price_data.get_price_history(
                    _ticker, _start, _end
                )

            _actual_bench_ranges = {}
            for _ai in _actual_save_target_items:
                _bench_symbol = performance.determine_benchmark(
                    _ai.get("market"), _ai.get("ticker")
                )
                if _bench_symbol is None:
                    continue
                _entry_dt = datetime.strptime(_ai["actual_entry_date"], "%Y-%m-%d")
                _range = _actual_bench_ranges.setdefault(
                    _bench_symbol, {"min": _entry_dt, "max": _entry_dt}
                )
                _range["min"] = min(_range["min"], _entry_dt)
                _range["max"] = max(_range["max"], _entry_dt)

            _actual_bench_df_cache = {}
            for _bench_symbol, _range in _actual_bench_ranges.items():
                _start = (_range["min"] - timedelta(days=10)).strftime("%Y-%m-%d")
                _end = (_range["max"] + timedelta(days=45)).strftime("%Y-%m-%d")
                _actual_bench_df_cache[_bench_symbol] = price_data.get_benchmark_history(
                    _bench_symbol, _start, _end
                )

            _actual_save_candidate_rows = []
            _actual_save_failed = []
            for _ai in _actual_save_target_items:
                _ticker = (_ai.get("ticker") or "").strip()
                _price_df = _actual_price_df_cache.get(_ticker)
                _bench_symbol = performance.determine_benchmark(
                    _ai.get("market"), _ai.get("ticker")
                )
                _bench_df = (
                    _actual_bench_df_cache.get(_bench_symbol)
                    if _bench_symbol is not None
                    else None
                )
                try:
                    _actual_eval_result = performance.evaluate_actual_item(
                        _ai, _price_df, _bench_df
                    )
                    _rows_for_item = performance.build_actual_outcome_rows(
                        _ai["id"], _actual_eval_result
                    )
                except ValueError as _actual_calc_err:
                    _actual_save_failed.append(
                        (
                            _ai.get("stock_name") or _ai.get("ticker") or f"id={_ai['id']}",
                            str(_actual_calc_err),
                        )
                    )
                    continue
                _actual_save_candidate_rows.extend(_rows_for_item)

            for _fail_name, _fail_reason in _actual_save_failed:
                st.error(f"{_fail_name}: {_fail_reason}")

            if not _actual_save_candidate_rows:
                st.info("저장 가능한 완료 실매매 성과가 없습니다.")
            else:
                try:
                    _actual_saved_count = db.upsert_report_item_outcomes(
                        _actual_save_candidate_rows
                    )
                except Exception as _actual_save_err:
                    st.error(f"실매매 성과 저장 중 오류가 발생했습니다: {_actual_save_err}")
                else:
                    st.success(f"실매매 성과 {_actual_saved_count}건을 저장·갱신했습니다.")
                    _actual_after_save = db.get_report_outcomes(
                        selected_report_id
                    )
                    _actual_outcomes_after_save = [
                        o for o in _actual_after_save if o["entry_basis"] == "actual"
                    ]
                    _actual_horizons_after_save = sorted(
                        {o["horizon_sessions"] for o in _actual_outcomes_after_save}
                    )
                    _actual_horizons_display = (
                        "·".join(f"{h}거래일" for h in _actual_horizons_after_save)
                        if _actual_horizons_after_save
                        else "-"
                    )
                    st.caption(
                        f"저장 상태: actual {len(_actual_outcomes_after_save)}건 / "
                        f"{_actual_horizons_display}"
                    )

    # 저장된 실매매 성과 조회 전용 표시 (evaluate_actual_item()/evaluate_item() 재호출,
    # 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE 전혀 없음). get_report_outcomes()가
    # 반환하는 DB 스냅샷을 entry_basis='actual'만 걸러서 그대로 보여준다 — 임의로 행을
    # 만들지 않는다. judgment 표("저장된 판단 성과 보기")와는 완전히 별도 expander로
    # 유지하며 한 표에 섞지 않는다.


with tab_review:
    st.subheader("④ 복기·통계")
    st.caption("저장된 판단과 실제 행동·거래 종료 결과를 조회하고 복기 진행 상태를 확인하는 화면입니다.")

    _tab4_reports = db.list_reports()
    _tab4_report_saved_at = {report["id"]: report.get("saved_at") or "-" for report in _tab4_reports}
    _tab4_items = []
    _tab4_seen_ids = set()
    for _tab4_report in _tab4_reports:
        for _tab4_item in db.get_report_items(_tab4_report["id"]):
            _tab4_item_id = _tab4_item.get("id")
            if _tab4_item_id in _tab4_seen_ids:
                continue
            _tab4_seen_ids.add(_tab4_item_id)
            _tab4_items.append(_tab4_item)

    _tab4_pending_count = sum(1 for item in _tab4_items if item.get("review_done") not in (1, True))
    _tab4_done_count = sum(1 for item in _tab4_items if item.get("review_done") in (1, True))
    _tab4_closed_count = sum(
        1 for item in _tab4_items if _classify_actual_trade_status(item) == "청산 완료"
    )
    _tab4_summary_cols = st.columns(4)
    _tab4_summary_cols[0].metric("전체 종목 수", len(_tab4_items))
    _tab4_summary_cols[1].metric("복기 대기 수", _tab4_pending_count)
    _tab4_summary_cols[2].metric("복기 완료 수", _tab4_done_count)
    _tab4_summary_cols[3].metric("청산 완료 수", _tab4_closed_count)

    _tab4_market = st.selectbox(
        "시장", ["전체", "KR", "US"], key="tab4_market_filter"
    )
    _tab4_review_status = st.selectbox(
        "복기 상태", ["전체", "복기 대기", "복기 완료"], key="tab4_review_status_filter"
    )

    _tab4_filtered_items = []
    for _tab4_item in _tab4_items:
        if _tab4_market != "전체" and _tab4_item.get("market") != _tab4_market:
            continue
        _tab4_item_review_status = (
            "복기 완료" if _tab4_item.get("review_done") in (1, True) else "복기 대기"
        )
        if _tab4_review_status != "전체" and _tab4_item_review_status != _tab4_review_status:
            continue
        _tab4_filtered_items.append(_tab4_item)

    st.caption(f"필터 결과: {len(_tab4_filtered_items)}건 / 전체 {len(_tab4_items)}건")
    with st.expander("복기 진행 현황 보기", expanded=False):
        st.caption(
            "이 표는 어떤 보고서에 테마·실제 행동·성과 기록이 부족한지 확인하는 복기 "
            "진행 현황입니다."
        )

        _review_statuses = db.get_report_review_status()

        def _classify_review_status(s):
            if s["theme_tagged_count"] == 0 and s["action_recorded_count"] == 0:
                return "기록 전"
            if s["action_recorded_count"] < s["item_count"]:
                return "기록 중"
            if s["judgment_outcome_count"] == 0:
                return "성과 저장 대기"
            if s["judgment_item_count"] < s["item_count"]:
                return "복기 중"
            return "복기 데이터 있음"

        _review_total_judgment_outcomes = sum(
            s["judgment_outcome_count"] for s in _review_statuses
        )
        _review_total_actual_outcomes = sum(
            s["actual_outcome_count"] for s in _review_statuses
        )
        if _review_total_judgment_outcomes == 0 and _review_total_actual_outcomes == 0:
            st.caption(
                "아직 저장된 성과가 없습니다. 날짜가 충분히 지난 과거 보고서를 선택해 "
                "판단 성과부터 저장해야 합니다."
            )

        _review_status_filter_in = st.selectbox(
            "상태 필터",
            ["전체", "기록 전", "기록 중", "성과 저장 대기", "복기 중", "복기 데이터 있음"],
            key="tab4_progress_status_filter",
        )

        _review_rows_with_status = [
            {**s, "_status": _classify_review_status(s)} for s in _review_statuses
        ]
        if _review_status_filter_in != "전체":
            _review_rows_with_status = [
                s for s in _review_rows_with_status
                if s["_status"] == _review_status_filter_in
            ]

        if not _review_rows_with_status:
            st.info("이 조건에 해당하는 보고서가 없습니다.")
        else:
            _review_table_rows = [
                {
                    "보고서 ID": s.get("report_id"),
                    "저장일": s.get("saved_at") or "-",
                    "시장": s.get("market_scope") or "-",
                    "브리핑 단계": s.get("briefing_stage") or "-",
                    "시점 구분": s.get("timing_class") or "-",
                    "종목 수": s.get("item_count"),
                    "테마 기록": s.get("theme_tagged_count"),
                    "행동 기록": s.get("action_recorded_count"),
                    "실제 매수": s.get("actual_buy_count"),
                    "실매매 준비": s.get("actual_ready_count"),
                    "판단 성과 행": s.get("judgment_outcome_count"),
                    "실매매 성과 행": s.get("actual_outcome_count"),
                    "판단 성과 종목": s.get("judgment_item_count"),
                    "실매매 성과 종목": s.get("actual_item_count"),
                    "현재 상태": s.get("_status"),
                }
                for s in _review_rows_with_status
            ]
            st.dataframe(
                pd.DataFrame(_review_table_rows), width="stretch", hide_index=True,
            )

    with st.expander("성과 계산·저장(관리)", expanded=False):
        _tab4_outcome_reports = sorted(
            _tab4_reports,
            key=lambda report: report.get("saved_at") or "",
            reverse=True,
        )
        _tab4_outcome_options = {
            f"#{report['id']} ({report.get('saved_at') or '-'})": report["id"]
            for report in _tab4_outcome_reports
        }
        if _tab4_outcome_options:
            _tab4_outcome_label = st.selectbox(
                "성과 저장 대상 보고서",
                list(_tab4_outcome_options.keys()),
                key="tab4_outcome_report_select",
            )
            _tab4_outcome_report_id = _tab4_outcome_options[_tab4_outcome_label]
            _tab4_verification_rows = _cached_verification_rows(_reports_signature())
            _render_judgment_outcome_save_button(
                _tab4_outcome_report_id,
                _tab4_verification_rows,
                key_prefix="tab4_",
            )
            _render_actual_outcome_save_section(
                _tab4_outcome_report_id,
                key_prefix="tab4_",
            )
        else:
            st.info("성과 저장 대상 보고서가 없습니다.")

    st.markdown("---")
    with st.expander("탈락 종목 기록", expanded=False):
        st.caption("자비스가 걸러낸(또는 사용자가 스스로 제외한) 종목을 report와 별도로 기록합니다.")
        rc1, rc2, rc3 = st.columns(3)
        rej_market = rc1.selectbox("시장", ["KR", "US"], key="tab4_rej_market")
        rej_ticker = rc2.text_input("종목코드", key="tab4_rej_ticker")
        rej_stock_name = rc3.text_input("종목명", key="tab4_rej_stock_name")

        rc4, rc5 = st.columns(2)
        rej_trade_mode = rc4.selectbox("매매유형", ["단타", "스윙", "미정"], key="tab4_rej_trade_mode")
        rej_assumed_entry_price = rc5.number_input(
            "가정 진입가(선택)", value=0.0, min_value=0.0, step=100.0, key="tab4_rej_assumed_entry_price"
        )

        rej_reason = st.text_input("탈락 사유", key="tab4_rej_reason")
        rej_note = st.text_input("메모(선택)", key="tab4_rej_note")

        _rej_report_options = ["연결 안 함"] + [
            f"#{r['id']} {r['saved_at']} {r['market_scope']}" for r in db.list_reports()
        ]
        _rej_report_label_to_id = {
            f"#{r['id']} {r['saved_at']} {r['market_scope']}": r["id"] for r in db.list_reports()
        }
        rej_report_choice = st.selectbox("연결 report(선택)", _rej_report_options, key="tab4_rej_source_report")

        if st.button("탈락 종목 저장", key="tab4_rej_save"):
            if not rej_ticker.strip() and not rej_stock_name.strip():
                st.warning("종목코드 또는 종목명 중 하나는 반드시 입력해야 합니다.")
            else:
                _now_str = datetime.now().isoformat(timespec="seconds")
                _source_report_id = _rej_report_label_to_id.get(rej_report_choice)
                db.insert_rejected_item(
                    _now_str,
                    rej_market,
                    rej_ticker.strip() or None,
                    rej_stock_name.strip() or None,
                    rej_trade_mode,
                    rej_reason.strip() or None,
                    rej_assumed_entry_price or None,
                    rej_note.strip() or None,
                    _source_report_id,
                    _now_str,
                )
                st.success("탈락 종목 기록 저장 완료")
                st.rerun()

        st.markdown("#### 최근 탈락 기록 (최대 10건)")
        _recent_rejected = db.list_recent_rejected(limit=10)
        if not _recent_rejected:
            st.info("아직 기록된 탈락 종목이 없습니다.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "rejected_at": r["rejected_at"],
                            "market": r["market"],
                            "ticker": r["ticker"],
                            "stock_name": r["stock_name"],
                            "trade_mode": r["trade_mode"],
                            "reject_reason": r["reject_reason"],
                            "assumed_entry_price": r["assumed_entry_price"],
                            "source_report_id": r["source_report_id"],
                        }
                        for r in _recent_rejected
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


    _tab4_table_rows = []
    for _tab4_item in _tab4_filtered_items:
        _tab4_table_rows.append(
            {
                "보고서 날짜": _tab4_report_saved_at.get(_tab4_item.get("report_id"), "-"),
                "보고서 ID": _tab4_item.get("report_id") or "-",
                "시장": _tab4_item.get("market") or "-",
                "종목명": _tab4_item.get("stock_name") or "-",
                "티커": _tab4_item.get("ticker") or "-",
                "실제 행동": db.normalize_actual_action(_tab4_item.get("actual_action")),
                "거래 진행 상태": _classify_actual_trade_status(_tab4_item),
                "result_r": _fmt_result_r(_tab4_item.get("result_r")),
                "복기 상태": "복기 완료" if _tab4_item.get("review_done") in (1, True) else "복기 대기",
                "복기 메모": "있음" if (_tab4_item.get("review_memo") or "").strip() else "없음",
            }
        )
    if _tab4_table_rows:
        st.dataframe(pd.DataFrame(_tab4_table_rows), width="stretch", hide_index=True)
    else:
        st.info("조건에 맞는 복기 대상 종목이 없습니다.")

    for _tab4_item in _tab4_filtered_items:
        _tab4_item_status = _classify_actual_trade_status(_tab4_item)
        _tab4_item_id = _tab4_item["id"]
        _tab4_review_done_key = f"tab4_review_done_{_tab4_item_id}"
        _tab4_review_memo_key = f"tab4_review_memo_{_tab4_item_id}"
        if _tab4_item_status in ("청산 완료", "보류", "제외"):
            with st.expander(
                f"복기 입력 — {_tab4_item.get('stock_name') or '-'} ({_tab4_item.get('market') or '-'})",
                expanded=False,
            ):
                _tab4_review_done_in = st.checkbox(
                    "복기 완료",
                    value=_tab4_item.get("review_done") in (1, True),
                    key=_tab4_review_done_key,
                )
                _tab4_review_memo_in = st.text_area(
                    "복기 메모",
                    value=_tab4_item.get("review_memo") or "",
                    key=_tab4_review_memo_key,
                )
                if st.button("복기 저장", key=f"tab4_review_save_{_tab4_item_id}"):
                    try:
                        _tab4_review_saved = db.update_report_item_review(
                            _tab4_item_id,
                            1 if _tab4_review_done_in else 0,
                            _tab4_review_memo_in,
                        )
                    except ValueError as _tab4_review_err:
                        st.error(f"복기 저장 실패: {_tab4_review_err}")
                    else:
                        if _tab4_review_saved:
                            st.success("복기가 저장되었습니다.")
                            st.rerun()
                        else:
                            st.error("복기 저장 실패: 대상 기록을 찾지 못했습니다.")
        else:
            st.caption(
                f"{_tab4_item.get('stock_name') or '-'}: 거래 상태 확정 후 복기 가능 "
                f"({_tab4_item_status})"
            )
        _render_review_tag_editors(
            _tab4_item,
            _tab4_item.get("stock_name") or "-",
            _tab4_item.get("trade_mode") or "-",
            key_prefix="tab4_",
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

def _render_actual_trade_entry_inputs(saved_item, key_prefix=""):
    """실제 행동·매수 입력 및 저장 UI를 렌더링한다."""
    if not saved_item.get("id"):
        return

    _item_name = saved_item.get("stock_name") or "-"
    with st.expander("실제 행동·매수 입력", expanded=False):
        st.markdown("---")
        _action_key = f"{key_prefix}actualaction_{saved_item['id']}"
        _action_options = ["미기록", "매수", "보류", "제외"]
        _action_stored = db.normalize_actual_action(saved_item.get("actual_action"))
        _action_in = st.selectbox(
            "실제 행동",
            _action_options,
            index=_action_options.index(_action_stored),
            key=f"{_action_key}_select",
        )
        if st.button("실제 행동 저장", key=f"{_action_key}_save"):
            _final_action = None if _action_in == "미기록" else _action_in
            try:
                _action_ok = db.update_report_item_actual_action(saved_item["id"], _final_action)
            except ValueError as _action_err:
                st.error(f"{_item_name}: {_action_err}")
            else:
                if _action_ok:
                    st.success("실제 행동이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"실제 행동 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        st.markdown("---")
        _price_key = f"{key_prefix}actualentryprice_{saved_item['id']}"
        _price_default_text = _fmt_actual_entry_price_display(saved_item.get("actual_entry_price"))
        _price_text_in = st.text_input(
            "실제 평균 체결가",
            value=_price_default_text,
            key=f"{_price_key}_input",
            help=(
                "실제로 매수한 평균 체결가입니다. 실제 행동이 '매수'일 때만 "
                "저장할 수 있습니다."
            ),
        )
        if st.button("실제 체결가 저장", key=f"{_price_key}_save"):
            _parsed_price, _parse_error = _parse_actual_entry_price_text(_price_text_in)
            if _parse_error:
                st.error(f"{_item_name}: {_parse_error}")
            else:
                try:
                    _price_ok = db.update_report_item_actual_entry_price(
                        saved_item["id"], _parsed_price
                    )
                except ValueError as _price_err:
                    st.error(f"{_item_name}: {_price_err}")
                else:
                    if _price_ok:
                        st.success("실제 체결가가 저장되었습니다.")
                        st.rerun()
                    else:
                        st.error(
                            f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                            f"(id={saved_item['id']})."
                        )

        st.markdown("---")
        _entry_date_key = f"{key_prefix}actualentrydate_{saved_item['id']}"
        _entry_date_default_text = saved_item.get("actual_entry_date") or ""
        _entry_date_text_in = st.text_input(
            "실제 매수 거래일",
            value=_entry_date_default_text,
            key=f"{_entry_date_key}_input",
            placeholder="2026-07-10",
            help=(
                "실제 매수한 거래소 기준 거래일입니다. 미국장은 한국시간 "
                "날짜가 아니라 미국 현지 거래일을 입력합니다."
            ),
        )
        if st.button("실제 매수일 저장", key=f"{_entry_date_key}_save"):
            try:
                _entry_date_ok = db.update_report_item_actual_entry_date(
                    saved_item["id"], _entry_date_text_in
                )
            except ValueError as _entry_date_err:
                st.error(f"{_item_name}: {_entry_date_err}")
            else:
                if _entry_date_ok:
                    st.success("실제 매수 거래일이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        _quantity_key = f"{key_prefix}quantity_{saved_item['id']}"
        _quantity_in = st.number_input(
            "매수 수량",
            value=saved_item.get("quantity"),
            min_value=1,
            step=1,
            format="%d",
            key=f"{_quantity_key}_input",
        )
        if st.button("매수 수량 저장", key=f"{_quantity_key}_save"):
            try:
                _quantity_ok = db.update_report_item_quantity(
                    saved_item["id"], _quantity_in
                )
            except ValueError as _quantity_err:
                st.error(f"{_item_name}: {_quantity_err}")
            else:
                if _quantity_ok:
                    st.success("매수 수량이 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        _fee_key = f"{key_prefix}actualfee_{saved_item['id']}"
        st.caption("실제 수수료와 세금을 합산한 금액을 직접 입력합니다. 0원과 미입력은 구분됩니다.")
        _fee_in = st.number_input(
            "실제 수수료·세금 합계",
            value=saved_item.get("actual_fee"),
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key=f"{_fee_key}_input",
        )
        if st.button("실제 수수료·세금 합계 저장", key=f"{_fee_key}_save"):
            try:
                _fee_ok = db.update_report_item_actual_fee(saved_item["id"], _fee_in)
            except ValueError as _fee_err:
                st.error(f"{_item_name}: {_fee_err}")
            else:
                if _fee_ok:
                    st.success("실제 수수료·세금 합계가 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )

        if saved_item.get("actual_action") == "매수":
            if (
                saved_item.get("actual_entry_price") is not None
                and saved_item.get("actual_entry_date") is not None
            ):
                st.caption("실매매 성과 계산 준비 완료")
            else:
                st.caption(
                    "실매매 성과 계산에는 실제 평균 체결가와 실제 매수 "
                    "거래일이 모두 필요합니다."
                )


def _render_trade_exit_inputs(saved_item, key_prefix=""):
    """청산 결과 입력·수정 및 저장 UI를 렌더링한다."""
    if not saved_item.get("id"):
        return

    _item_name = saved_item.get("stock_name") or "-"
    _trade_mode = saved_item.get("trade_mode") or "-"
    with st.expander(f"청산 결과 입력 / 수정 — {_item_name} ({_trade_mode})"):
        _exit_key = f"{key_prefix}exit_{saved_item['id']}"
        _exit_price_in = st.number_input(
            "실제 청산가", value=float(saved_item.get("actual_exit_price") or 0.0),
            min_value=0.0, step=100.0, key=f"{_exit_key}_price",
        )
        _exit_date_default = None
        if saved_item.get("actual_exit_date"):
            try:
                _exit_date_default = datetime.strptime(
                    saved_item["actual_exit_date"], "%Y-%m-%d"
                ).date()
            except ValueError:
                _exit_date_default = None
        _exit_date_in = st.date_input(
            "실제 청산일", value=_exit_date_default, key=f"{_exit_key}_date",
        )
        _plan_followed_options = ["미입력", "예", "아니오", "부분"]
        _plan_followed_default = saved_item.get("plan_followed") or "미입력"
        if _plan_followed_default not in _plan_followed_options:
            _plan_followed_default = "미입력"
        _plan_followed_in = st.selectbox(
            "계획 준수 여부", _plan_followed_options,
            index=_plan_followed_options.index(_plan_followed_default),
            key=f"{_exit_key}_plan_followed",
        )
        _exit_reason_options = [
            "미입력", "손절", "목표가", "시간청산", "조기매도",
            "손절지연", "복구매매", "감정매매", "뉴스변경", "기타",
        ]
        _exit_reason_default = saved_item.get("exit_reason") or "미입력"
        if _exit_reason_default not in _exit_reason_options:
            _exit_reason_default = "미입력"
        _exit_reason_in = st.selectbox(
            "청산 사유", _exit_reason_options,
            index=_exit_reason_options.index(_exit_reason_default),
            key=f"{_exit_key}_reason",
        )

        _r_basis_price = saved_item.get("actual_entry_price") or saved_item.get("entry_price")
        _r_basis_is_plan = (
            not saved_item.get("actual_entry_price") and bool(saved_item.get("entry_price"))
        )
        _preview_result_r = _compute_result_r(
            _r_basis_price, saved_item.get("stop_loss_price"), _exit_price_in or None,
        )
        _r_preview_suffix = "(계획가 기준)" if _r_basis_is_plan else ""
        st.caption(f"R수익률 미리보기: {_fmt_result_r(_preview_result_r)} {_r_preview_suffix}".rstrip())

        if st.button("청산 결과 저장", key=f"{_exit_key}_save"):
            _final_exit_price = _exit_price_in or None
            _final_exit_date = _exit_date_in.isoformat() if _exit_date_in else None
            _final_plan_followed = None if _plan_followed_in == "미입력" else _plan_followed_in
            _final_exit_reason = None if _exit_reason_in == "미입력" else _exit_reason_in
            _final_result_r = _compute_result_r(
                _r_basis_price, saved_item.get("stop_loss_price"), _final_exit_price,
            )
            _final_verification_status = _compute_verification_status(
                _final_exit_price, _final_exit_date
            )
            try:
                _exit_ok = db.update_report_item_trade_exit(
                    saved_item["id"],
                    _final_exit_price,
                    _final_exit_date,
                    _final_plan_followed,
                    _final_exit_reason,
                    _final_result_r,
                    _final_verification_status,
                )
            except ValueError as _exit_err:
                st.error(f"{_item_name}: {_exit_err}")
            else:
                if _exit_ok:
                    _cached_verification_rows.clear()
                    st.success("청산 결과가 저장되었습니다.")
                    st.rerun()
                else:
                    st.error(
                        f"{_item_name}: 저장 실패 — 대상 기록을 찾지 못했습니다 "
                        f"(id={saved_item['id']})."
                    )


with tab_action:
    st.subheader("③ 실제 행동·거래 종료")
    st.caption("저장된 판단 이후 실제 행동과 거래 종료를 기록하는 화면입니다.")

    _tab3_market = st.selectbox(
        "시장", ["전체", "KR", "US"], key="tab3_market_filter"
    )
    _tab3_status = st.selectbox(
        "진행 상태",
        ["전체", "행동 미입력", "보유 중", "청산 완료", "보류", "제외"],
        key="tab3_status_filter",
    )

    _tab3_items = []
    _tab3_seen_ids = set()
    for _tab3_report in db.list_reports():
        for _tab3_item in db.get_report_items(_tab3_report["id"]):
            _tab3_item_id = _tab3_item.get("id")
            if _tab3_item_id in _tab3_seen_ids:
                continue
            _tab3_seen_ids.add(_tab3_item_id)
            _tab3_items.append(_tab3_item)

    _tab3_filtered_items = []
    for _tab3_item in _tab3_items:
        if _tab3_market != "전체" and _tab3_item.get("market") != _tab3_market:
            continue
        if _tab3_status != "전체" and _classify_actual_trade_status(_tab3_item) != _tab3_status:
            continue
        _tab3_filtered_items.append(_tab3_item)

    st.caption(f"필터 결과: {len(_tab3_filtered_items)}건 / 전체 {len(_tab3_items)}건")
    for _tab3_item in _tab3_filtered_items:
        _tab3_item_status = _classify_actual_trade_status(_tab3_item)
        st.caption(
            f"{_tab3_item.get('market') or '-'} · {_tab3_item_status} · "
            f"{_tab3_item.get('stock_name') or '-'} ({_tab3_item.get('trade_mode') or '-'})"
        )
        _render_actual_trade_entry_inputs(_tab3_item, key_prefix="tab3_")
        if db.normalize_actual_action(_tab3_item.get("actual_action")) == "매수":
            _render_trade_exit_inputs(_tab3_item, key_prefix="tab3_")
        if _tab3_item_status == "청산 완료":
            _actual_fee = _tab3_item.get("actual_fee")
            _actual_entry_price = _tab3_item.get("actual_entry_price")
            _actual_pnl = None
            if _actual_entry_price is None:
                _pnl_text = "실제 매수가 미입력 · 계산 불가"
                _return_text = "실제 매수가 미입력 · 계산 불가"
            else:
                if _actual_fee is None:
                    _pnl_text = "비용 미입력 · 계산 불가"
                else:
                    _actual_pnl = _compute_realized_pnl(
                        _actual_entry_price,
                        _tab3_item.get("actual_exit_price"),
                        _tab3_item.get("quantity"),
                        _actual_fee,
                    )
                    if _actual_pnl is None:
                        _pnl_text = "입력값 부족 · 계산 불가"
                    else:
                        _pnl_text = f"{_actual_pnl:,.2f}"

                _return_pct = None
                if _actual_pnl is not None:
                    _return_pct = _compute_realized_return_pct(
                        _actual_pnl,
                        _actual_entry_price,
                        _tab3_item.get("quantity"),
                    )
                _return_text = (
                    "입력값 부족 · 계산 불가"
                    if _return_pct is None
                    else f"{_return_pct:+.2f}%"
                )

            _holding_days = _compute_holding_days(
                _tab3_item.get("actual_entry_date"),
                _tab3_item.get("actual_exit_date"),
            )
            if _holding_days is not None:
                _holding_text = f"{_holding_days}일"
            elif _tab3_item.get("actual_entry_date") and _tab3_item.get("actual_exit_date"):
                _holding_text = "날짜 확인 필요"
            else:
                _holding_text = "입력값 부족 · 계산 불가"

            _summary_cols = st.columns(3)
            _summary_cols[0].metric("실현손익", _pnl_text)
            _summary_cols[1].metric("실현수익률", _return_text)
            _summary_cols[2].metric("보유일", _holding_text)




with tab_perf:
    st.subheader("결과 확인")
    st.caption("? ??? ?? ?????. ?? ??? ?? ??? ? ??????? ???.")
    st.caption(
        "저장한 종목 판단이 며칠 뒤 실제 수익률로 어떻게 나왔는지 확인하는 화면입니다."
    )
    st.caption(
        "승률보다 R수익률과 기대값이 중요합니다. 손절을 지키면 승률은 낮아져도 계좌는 좋아질 수 있습니다."
    )

    st.markdown("---")

    perf_rows_all = _cached_verification_rows(_reports_signature())

    if not perf_rows_all:
        st.info("종목코드가 있는 종목별 기록이 없습니다.")
    else:
        # 1. 보기 범위 (기본값 "오늘 저장한 기록 전체" — "방금 저장한 기록만"은 최신 report 1건만
        # 보여줘서 한국장/미국장을 같은 날 둘 다 저장해도 한쪽만 보이는 것처럼 보일 수 있다.
        # 기본값을 오늘 저장한 기록 전체로 넓혀 두 시장이 함께 보이게 한다.)
        view_scope = st.radio(
            "볼 기록 범위",
            ["방금 저장한 기록만", "오늘 저장한 기록 전체", "모든 지난 기록"],
            horizontal=True,
            index=1,
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

        # 판단 성과 저장 (report_id 1건만 대상, 명시적 버튼 클릭 시에만 저장 —
        # evaluate_item()/build_judgment_outcome_rows()로 이미 계산된 결과를 재사용하고
        # 저장을 위해 별도로 다시 평가하지 않는다. 매매유형/판정 표시 필터와는 무관하게,
        # 선택한 report_id에 속한 종목 전체(티커가 있는 항목)를 대상으로 한다 — 아래 표시용
        # 필터(단기/며칠 구분, 판단 구분)에 저장 대상이 좌우되지 않게 하기 위함이다.
        # actual 성과·pending/unavailable/error 행은 이 화면에서 만들지 않는다.
        if scoped_rows:
            st.markdown("#### 판단 성과 저장")
            st.caption(
                "선택한 보고서 1건의 정상 계산된 판단(judgment) 성과만 report_item_outcomes에 "
                "저장합니다. 자동 저장되지 않으며, 아래 버튼을 눌러야 저장됩니다."
            )

            _outcome_save_reports = []
            _outcome_save_seen_report_ids = set()
            for _osr_row in scoped_rows:
                if _osr_row["report_id"] not in _outcome_save_seen_report_ids:
                    _outcome_save_seen_report_ids.add(_osr_row["report_id"])
                    _outcome_save_reports.append((_osr_row["report_id"], _osr_row["saved_at"]))
            _outcome_save_reports.sort(key=lambda pair: pair[1], reverse=True)

            _outcome_save_report_options = {
                f"#{_rid} ({_saved_at})": _rid for _rid, _saved_at in _outcome_save_reports
            }
            _outcome_save_report_label = st.selectbox(
                "저장 대상 보고서 선택",
                list(_outcome_save_report_options.keys()),
                key="judgment_outcome_save_report_select",
            )
            _outcome_save_target_report_id = _outcome_save_report_options[_outcome_save_report_label]

            # 저장된 판단 성과 조회 전용 표시 (evaluate_item() 재호출/가격·벤치마크 네트워크
            # 조회/DB INSERT·UPDATE 전혀 없음). get_report_outcomes()가 반환하는 DB 스냅샷을
            # entry_basis='judgment'만 걸러서 그대로 보여준다 — 임의로 행을 만들지 않는다.
            with st.expander("저장된 판단 성과 보기", expanded=False):
                st.caption(
                    "이 표는 계산 화면의 실시간 값이 아니라, 저장 버튼을 눌렀을 때 DB에 "
                    "기록된 판단 성과입니다."
                )
                _saved_outcomes = db.get_report_outcomes(_outcome_save_target_report_id)
                _saved_judgment_outcomes = [
                    o for o in _saved_outcomes if o["entry_basis"] == "judgment"
                ]
                if not _saved_judgment_outcomes:
                    st.info("아직 저장된 판단 성과가 없습니다.")
                else:
                    _saved_judgment_outcomes = sorted(
                        _saved_judgment_outcomes,
                        key=lambda o: (o["report_item_id"], o["horizon_sessions"]),
                    )
                    _outcome_status_display = {
                        "evaluated": "완료",
                        "pending": "대기",
                        "unavailable": "데이터 없음",
                        "error": "오류",
                    }
                    _saved_outcome_table_rows = [
                        {
                            "종목명": o.get("item_name") or "-",
                            "티커": o.get("ticker") or "-",
                            "시장": o.get("market") or "-",
                            "거래일수": o.get("horizon_sessions"),
                            "기준가격": _fmt_actual_entry_price_display(o.get("entry_price_used")) or "-",
                            "목표일": o.get("target_date") or "-",
                            "종가": _fmt_actual_entry_price_display(o.get("close_price")) or "-",
                            "수익률(%)": _fmt_pct(o.get("return_pct")),
                            "벤치마크": o.get("benchmark_symbol") or "-",
                            "벤치마크 수익률(%)": _fmt_pct(o.get("benchmark_return_pct")),
                            "초과수익률(%)": _fmt_pct(o.get("excess_return_pct")),
                            "상태": _outcome_status_display.get(o.get("status"), o.get("status") or "-"),
                            "평가시각": o.get("evaluated_at") or "-",
                        }
                        for o in _saved_judgment_outcomes
                    ]
                    st.dataframe(
                        pd.DataFrame(_saved_outcome_table_rows), width="stretch", hide_index=True
                    )
            st.markdown("---")

            # 실매매 성과 저장 (판단 성과 저장 바로 아래, 같은 선택 report_id 1건만 대상,
            # 명시적 버튼 클릭 시에만 계산·저장). actual_action='매수'이고
            # actual_entry_price/actual_entry_date가 모두 채워진 종목만 대상으로 한다.
            # evaluate_item()/build_verification_rows()는 원시 price_df/benchmark_df를
            # 보존·노출하지 않으므로(가공된 결과만 반환) 재사용이 불가능하다 — 버튼을 누른
            # 뒤에만 기존 price_data.py 조회 함수로 새로 가져온다. judgment 성과(위 섹션,
            # entry_basis='judgment')는 이 섹션에서 전혀 건드리지 않는다.
            st.markdown("#### 실매매 성과 저장")
            st.caption(
                "선택한 보고서에서 실제 행동이 '매수'이고 실제 체결가·실제 매수 거래일이 "
                "모두 입력된 종목만 대상으로 실매매(actual) 성과를 계산해 저장합니다. "
                "자동 저장되지 않으며, 아래 버튼을 눌러야 계산·저장됩니다."
            )

            with st.expander("저장된 실매매 성과 보기", expanded=False):
                st.caption(
                    "이 표는 실제 평균 체결가와 실제 매수 거래일을 기준으로 계산해 DB에 "
                    "저장한 실매매 성과입니다."
                )
                st.caption("수수료·세금·매수 수량은 아직 반영되지 않았습니다.")
                _saved_actual_outcomes_raw = db.get_report_outcomes(_outcome_save_target_report_id)
                _saved_actual_outcomes = [
                    o for o in _saved_actual_outcomes_raw if o["entry_basis"] == "actual"
                ]
                if not _saved_actual_outcomes:
                    st.info("아직 저장된 실매매 성과가 없습니다.")
                else:
                    _saved_actual_outcomes = sorted(
                        _saved_actual_outcomes,
                        key=lambda o: (o["report_item_id"], o["horizon_sessions"]),
                    )
                    _actual_outcome_status_display = {
                        "evaluated": "완료",
                        "pending": "대기",
                        "unavailable": "데이터 없음",
                        "error": "오류",
                    }
                    _saved_actual_outcome_table_rows = [
                        {
                            "종목명": o.get("item_name") or "-",
                            "티커": o.get("ticker") or "-",
                            "시장": o.get("market") or "-",
                            "실제 매수일": o.get("actual_entry_date") or "-",
                            "실제 기준가격": (
                                _fmt_actual_entry_price_display(o.get("entry_price_used")) or "-"
                            ),
                            "거래일수": o.get("horizon_sessions"),
                            "목표일": o.get("target_date") or "-",
                            "종가": _fmt_actual_entry_price_display(o.get("close_price")) or "-",
                            "실매매 수익률(%)": _fmt_pct(o.get("return_pct")),
                            "벤치마크": o.get("benchmark_symbol") or "-",
                            "벤치마크 수익률(%)": _fmt_pct(o.get("benchmark_return_pct")),
                            "초과수익률(%)": _fmt_pct(o.get("excess_return_pct")),
                            "상태": _actual_outcome_status_display.get(
                                o.get("status"), o.get("status") or "-"
                            ),
                            "평가시각": o.get("evaluated_at") or "-",
                        }
                        for o in _saved_actual_outcomes
                    ]
                    st.dataframe(
                        pd.DataFrame(_saved_actual_outcome_table_rows),
                        width="stretch",
                        hide_index=True,
                    )

            # 판단(judgment) 대 실매매(actual) 비교 조회 전용 표시. evaluate_item()/
            # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE
            # 전혀 없음 — db.get_report_outcomes()의 DB 스냅샷을
            # performance.build_judgment_actual_comparison_rows()에 그대로 넘겨 이미
            # 완성된 judgment+actual 쌍만 보여준다. 위 두 expander와 완전히 별도로 둔다.
            with st.expander("판단과 실매매 차이 보기", expanded=False):
                st.caption(
                    "양수는 실제 진입 성과가 판단 기준보다 좋았다는 뜻이고, 음수는 실제 "
                    "진입이 더 불리했다는 뜻입니다."
                )
                _comparison_outcome_rows = db.get_report_outcomes(_outcome_save_target_report_id)
                _comparison_rows = performance.build_judgment_actual_comparison_rows(
                    _comparison_outcome_rows
                )
                if not _comparison_rows:
                    st.info("비교 가능한 판단 성과와 실매매 성과가 아직 없습니다.")
                else:
                    _comparison_rows = sorted(
                        _comparison_rows,
                        key=lambda c: (c["report_item_id"], c["horizon_sessions"]),
                    )
                    _comparison_table_rows = [
                        {
                            "종목명": c.get("종목명") or "-",
                            "티커": c.get("ticker") or "-",
                            "시장": c.get("market") or "-",
                            "거래일수": c.get("horizon_sessions"),
                            "판단 기준가격": (
                                _fmt_actual_entry_price_display(c.get("judgment_entry_price"))
                                or "-"
                            ),
                            "실제 기준가격": (
                                _fmt_actual_entry_price_display(c.get("actual_entry_price"))
                                or "-"
                            ),
                            "판단 수익률(%)": _fmt_pct(c.get("judgment_return_pct")),
                            "실매매 수익률(%)": _fmt_pct(c.get("actual_return_pct")),
                            "수익률 차이(%p)": _fmt_pct(c.get("return_gap_pct")),
                            "판단 초과수익률(%)": _fmt_pct(c.get("judgment_excess_return_pct")),
                            "실매매 초과수익률(%)": _fmt_pct(c.get("actual_excess_return_pct")),
                            "초과수익률 차이(%p)": _fmt_pct(c.get("excess_return_gap_pct")),
                        }
                        for c in _comparison_rows
                    ]
                    st.dataframe(
                        pd.DataFrame(_comparison_table_rows),
                        width="stretch",
                        hide_index=True,
                    )

            # 판단 잔차 원자료 조회 전용 표시. evaluate_item()/evaluate_actual_item() 재호출,
            # 가격·벤치마크 네트워크 조회, DB INSERT·UPDATE 전혀 없음 — 위 "판단과 실매매
            # 차이 보기" expander에서 이미 조회한 _comparison_outcome_rows(동일 report_id의
            # db.get_report_outcomes() 결과)를 그대로 재사용해 같은 report_id를 중복 조회하지
            # 않는다. 자동 성공/실패 판정이나 점수는 표시하지 않는다.
            with st.expander("판단 잔차 원자료 보기", expanded=False):
                st.caption(
                    "진입 효과가 양수면 실제 진입 성과가 판단 기준보다 유리했고, 음수면 "
                    "불리했다는 뜻입니다."
                )
                st.caption(
                    "보류·제외 종목의 미매수 수익률은 당시 판단 이후 종목이 얼마나 "
                    "움직였는지 보여주는 원자료입니다. 아직 성공·실패나 실수로 자동 "
                    "판정하지 않습니다."
                )
                _residual_rows = performance.build_decision_residual_rows(
                    _comparison_outcome_rows
                )
                if not _residual_rows:
                    st.info("아직 분석 가능한 판단 잔차 원자료가 없습니다.")
                else:
                    _residual_rows = sorted(
                        _residual_rows,
                        key=lambda d: (d["report_item_id"], d["horizon_sessions"]),
                    )
                    _residual_table_rows = [
                        {
                            "종목명": d.get("종목명") or "-",
                            "티커": d.get("ticker") or "-",
                            "시장": d.get("market") or "-",
                            "테마 태그": (
                                ", ".join(db.parse_theme_tags(d.get("theme_tags"))) or "-"
                            ),
                            "실제 행동": d.get("actual_action") or "미기록",
                            "거래일수": d.get("horizon_sessions"),
                            "판단 기준가격": (
                                _fmt_actual_entry_price_display(d.get("judgment_entry_price"))
                                or "-"
                            ),
                            "판단 수익률(%)": _fmt_pct(d.get("judgment_return_pct")),
                            "판단 초과수익률(%)": _fmt_pct(d.get("judgment_excess_return_pct")),
                            "실제 기준가격": (
                                _fmt_actual_entry_price_display(d.get("actual_entry_price"))
                                or "-"
                            ),
                            "실매매 수익률(%)": _fmt_pct(d.get("actual_return_pct")),
                            "실매매 초과수익률(%)": _fmt_pct(d.get("actual_excess_return_pct")),
                            "진입 효과(%p)": _fmt_pct(d.get("entry_effect_pct")),
                            "진입 초과효과(%p)": _fmt_pct(d.get("entry_excess_effect_pct")),
                            "미매수 종목 수익률(%)": _fmt_pct(d.get("non_buy_return_pct")),
                            "미매수 종목 초과수익률(%)": _fmt_pct(
                                d.get("non_buy_excess_return_pct")
                            ),
                        }
                        for d in _residual_rows
                    ]
                    st.dataframe(
                        pd.DataFrame(_residual_table_rows),
                        width="stretch",
                        hide_index=True,
                    )

            # 전체 행동별 누적 통계. 위의 다른 세 expander와 달리 현재 선택한 report_id
            # 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된 성과를
            # db.get_all_report_outcomes()로 한 번에 모아 집계한다. evaluate_item()/
            # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
            # 없음 — 필터를 바꿔도 조회만 다시 할 뿐 DB에 아무것도 쓰지 않는다.
            with st.expander("전체 행동별 누적 통계 보기", expanded=False):
                st.caption(
                    "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                    "여러 보고서의 저장된 성과를 함께 집계합니다."
                )
                st.caption(
                    "표본수가 적으면 결과가 크게 흔들릴 수 있으며, 현재 표는 자동 판정이 "
                    "아닌 누적 원자료 통계입니다."
                )

                _summary_filter_cols = st.columns(3)
                _summary_market_in = _summary_filter_cols[0].selectbox(
                    "시장",
                    ["전체", "KR", "US", "OTHER"],
                    key="action_summary_market_filter",
                )
                _summary_date_from_in = _summary_filter_cols[1].text_input(
                    "시작일",
                    value="",
                    key="action_summary_date_from_filter",
                    placeholder="2026-07-01",
                )
                _summary_date_to_in = _summary_filter_cols[2].text_input(
                    "종료일",
                    value="",
                    key="action_summary_date_to_filter",
                    placeholder="2026-07-31",
                )

                _summary_market_filter = (
                    None if _summary_market_in == "전체" else _summary_market_in
                )
                _summary_date_from_filter = _summary_date_from_in.strip() or None
                _summary_date_to_filter = _summary_date_to_in.strip() or None

                try:
                    _summary_outcome_rows = db.get_all_report_outcomes(
                        market=_summary_market_filter,
                        date_from=_summary_date_from_filter,
                        date_to=_summary_date_to_filter,
                    )
                except ValueError as _summary_query_err:
                    st.error(f"조회 조건 오류: {_summary_query_err}")
                else:
                    _summary_residual_rows = performance.build_decision_residual_rows(
                        _summary_outcome_rows
                    )
                    _summary_action_rows = performance.build_action_residual_summary(
                        _summary_residual_rows
                    )
                    if not _summary_action_rows:
                        st.info("아직 누적 통계를 계산할 저장 성과가 없습니다.")
                    else:
                        _summary_table_rows = [
                            {
                                "거래일수": s.get("horizon_sessions"),
                                "실제 행동": s.get("actual_action"),
                                "전체 표본수": s.get("sample_count"),
                                "판단 수익률 표본수": s.get("judgment_return_count"),
                                "판단 평균 수익률(%)": _fmt_pct(s.get("judgment_return_avg")),
                                "판단 중앙 수익률(%)": _fmt_pct(
                                    s.get("judgment_return_median")
                                ),
                                "판단 양수 개수": s.get("judgment_positive_count"),
                                "판단 양수 비율(%)": _fmt_pct(s.get("judgment_positive_rate")),
                                "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                "판단 평균 초과수익률(%)": _fmt_pct(
                                    s.get("judgment_excess_avg")
                                ),
                                "진입 효과 표본수": s.get("entry_effect_count"),
                                "평균 진입 효과(%p)": _fmt_pct(s.get("entry_effect_avg")),
                                "중앙 진입 효과(%p)": _fmt_pct(s.get("entry_effect_median")),
                                "미매수 표본수": s.get("non_buy_return_count"),
                                "미매수 평균 수익률(%)": _fmt_pct(s.get("non_buy_return_avg")),
                                "미매수 중앙 수익률(%)": _fmt_pct(
                                    s.get("non_buy_return_median")
                                ),
                                "미매수 양수 개수": s.get("non_buy_positive_count"),
                                "미매수 양수 비율(%)": _fmt_pct(s.get("non_buy_positive_rate")),
                                "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                "미매수 평균 초과수익률(%)": _fmt_pct(
                                    s.get("non_buy_excess_avg")
                                ),
                            }
                            for s in _summary_action_rows
                        ]
                        st.dataframe(
                            pd.DataFrame(_summary_table_rows),
                            width="stretch",
                            hide_index=True,
                        )

            # 테마별 누적 통계. 위 "전체 행동별 누적 통계 보기"와 마찬가지로 현재 선택한
            # report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된
            # 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
            # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
            # 없음. 테마/실제 행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는
            # 화면 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다.
            with st.expander("테마별 누적 통계 보기", expanded=False):
                st.caption(
                    "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                    "여러 보고서의 저장된 성과를 함께 집계합니다."
                )
                st.caption(
                    "한 종목에 여러 테마 태그가 있으면 각 테마에 각각 포함됩니다. 표본수가 "
                    "적으면 결과가 크게 흔들릴 수 있으며, 현재 표는 자동 판정이 아닌 누적 "
                    "원자료 통계입니다."
                )

                _theme_filter_cols = st.columns(3)
                _theme_market_in = _theme_filter_cols[0].selectbox(
                    "시장",
                    ["전체", "KR", "US", "OTHER"],
                    key="theme_summary_market_filter",
                )
                _theme_date_from_in = _theme_filter_cols[1].text_input(
                    "시작일",
                    value="",
                    key="theme_summary_date_from_filter",
                    placeholder="2026-07-01",
                )
                _theme_date_to_in = _theme_filter_cols[2].text_input(
                    "종료일",
                    value="",
                    key="theme_summary_date_to_filter",
                    placeholder="2026-07-31",
                )

                _theme_market_filter = (
                    None if _theme_market_in == "전체" else _theme_market_in
                )
                _theme_date_from_filter = _theme_date_from_in.strip() or None
                _theme_date_to_filter = _theme_date_to_in.strip() or None

                try:
                    _theme_outcome_rows = db.get_all_report_outcomes(
                        market=_theme_market_filter,
                        date_from=_theme_date_from_filter,
                        date_to=_theme_date_to_filter,
                    )
                except ValueError as _theme_query_err:
                    st.error(f"조회 조건 오류: {_theme_query_err}")
                else:
                    _theme_residual_rows = performance.build_decision_residual_rows(
                        _theme_outcome_rows
                    )
                    _theme_summary_rows = performance.build_theme_residual_summary(
                        _theme_residual_rows
                    )
                    if not _theme_summary_rows:
                        st.info("아직 테마별 누적 통계를 계산할 저장 성과가 없습니다.")
                    else:
                        _theme_tag_options_seen = []
                        for _t in _theme_summary_rows:
                            if _t["theme_tag"] not in _theme_tag_options_seen:
                                _theme_tag_options_seen.append(_t["theme_tag"])

                        _theme_display_cols = st.columns(3)
                        _theme_tag_in = _theme_display_cols[0].selectbox(
                            "테마",
                            ["전체"] + _theme_tag_options_seen,
                            key="theme_summary_theme_filter",
                        )
                        _theme_action_in = _theme_display_cols[1].selectbox(
                            "실제 행동",
                            ["전체", "매수", "보류", "제외", "미기록"],
                            key="theme_summary_action_filter",
                        )
                        _theme_horizon_in = _theme_display_cols[2].selectbox(
                            "거래일수",
                            ["전체", 1, 3, 5, 10, 20],
                            key="theme_summary_horizon_filter",
                        )

                        _theme_filtered_rows = _theme_summary_rows
                        if _theme_tag_in != "전체":
                            _theme_filtered_rows = [
                                s for s in _theme_filtered_rows
                                if s["theme_tag"] == _theme_tag_in
                            ]
                        if _theme_action_in != "전체":
                            _theme_filtered_rows = [
                                s for s in _theme_filtered_rows
                                if s["actual_action"] == _theme_action_in
                            ]
                        if _theme_horizon_in != "전체":
                            _theme_filtered_rows = [
                                s for s in _theme_filtered_rows
                                if s["horizon_sessions"] == _theme_horizon_in
                            ]

                        if not _theme_filtered_rows:
                            st.info("아직 테마별 누적 통계를 계산할 저장 성과가 없습니다.")
                        else:
                            _theme_table_rows = [
                                {
                                    "테마": s.get("theme_tag"),
                                    "거래일수": s.get("horizon_sessions"),
                                    "실제 행동": s.get("actual_action"),
                                    "전체 표본수": s.get("sample_count"),
                                    "판단 수익률 표본수": s.get("judgment_return_count"),
                                    "판단 평균 수익률(%)": _fmt_pct(
                                        s.get("judgment_return_avg")
                                    ),
                                    "판단 중앙 수익률(%)": _fmt_pct(
                                        s.get("judgment_return_median")
                                    ),
                                    "판단 양수 개수": s.get("judgment_positive_count"),
                                    "판단 양수 비율(%)": _fmt_pct(
                                        s.get("judgment_positive_rate")
                                    ),
                                    "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                    "판단 평균 초과수익률(%)": _fmt_pct(
                                        s.get("judgment_excess_avg")
                                    ),
                                    "진입 효과 표본수": s.get("entry_effect_count"),
                                    "평균 진입 효과(%p)": _fmt_pct(
                                        s.get("entry_effect_avg")
                                    ),
                                    "중앙 진입 효과(%p)": _fmt_pct(
                                        s.get("entry_effect_median")
                                    ),
                                    "미매수 표본수": s.get("non_buy_return_count"),
                                    "미매수 평균 수익률(%)": _fmt_pct(
                                        s.get("non_buy_return_avg")
                                    ),
                                    "미매수 중앙 수익률(%)": _fmt_pct(
                                        s.get("non_buy_return_median")
                                    ),
                                    "미매수 양수 개수": s.get("non_buy_positive_count"),
                                    "미매수 양수 비율(%)": _fmt_pct(
                                        s.get("non_buy_positive_rate")
                                    ),
                                    "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                    "미매수 평균 초과수익률(%)": _fmt_pct(
                                        s.get("non_buy_excess_avg")
                                    ),
                                }
                                for s in _theme_filtered_rows
                            ]
                            st.dataframe(
                                pd.DataFrame(_theme_table_rows),
                                width="stretch",
                                hide_index=True,
                            )

            # 판단 맥락별 누적 통계. 위 두 통계(행동별/테마별)와 마찬가지로 현재 선택한
            # report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의 저장된
            # 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
            # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
            # 없음. 맥락값/실제 행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는
            # 화면 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다. 분석 기준은 한 번에
            # 하나만 선택한다(복합 조건 분석 아님). 내부 group_by 코드(trade_mode 등)는
            # 화면에 노출하지 않고 선택된 한글 분석 기준 이름만 표시한다.
            with st.expander("판단 맥락별 누적 통계 보기", expanded=False):
                st.caption(
                    "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                    "여러 보고서의 저장된 성과를 함께 집계합니다."
                )
                st.caption(
                    "각 분석 기준을 한 번에 하나씩 분리해 집계한 원자료 통계입니다. "
                    "표본수가 적으면 결과가 크게 흔들릴 수 있습니다."
                )

                _context_filter_cols = st.columns(3)
                _context_market_in = _context_filter_cols[0].selectbox(
                    "시장",
                    ["전체", "KR", "US", "OTHER"],
                    key="context_summary_market_filter",
                )
                _context_date_from_in = _context_filter_cols[1].text_input(
                    "시작일",
                    value="",
                    key="context_summary_date_from_filter",
                    placeholder="2026-07-01",
                )
                _context_date_to_in = _context_filter_cols[2].text_input(
                    "종료일",
                    value="",
                    key="context_summary_date_to_filter",
                    placeholder="2026-07-31",
                )

                _context_basis_options = {
                    "매매유형": "trade_mode",
                    "당시 판정": "verdict",
                    "신호 분류": "signal_type",
                    "이벤트": "event_name",
                    "브리핑 단계": "briefing_stage",
                    "시점 구분": "timing_class",
                }
                _context_basis_label_in = st.selectbox(
                    "분석 기준",
                    list(_context_basis_options.keys()),
                    key="context_summary_basis_filter",
                )
                _context_group_by = _context_basis_options[_context_basis_label_in]

                _context_market_filter = (
                    None if _context_market_in == "전체" else _context_market_in
                )
                _context_date_from_filter = _context_date_from_in.strip() or None
                _context_date_to_filter = _context_date_to_in.strip() or None

                try:
                    _context_outcome_rows = db.get_all_report_outcomes(
                        market=_context_market_filter,
                        date_from=_context_date_from_filter,
                        date_to=_context_date_to_filter,
                    )
                except ValueError as _context_query_err:
                    st.error(f"조회 조건 오류: {_context_query_err}")
                else:
                    _context_residual_rows = performance.build_decision_residual_rows(
                        _context_outcome_rows
                    )
                    _context_summary_rows = performance.build_context_residual_summary(
                        _context_residual_rows, _context_group_by
                    )
                    if not _context_summary_rows:
                        st.info(
                            "아직 판단 맥락별 누적 통계를 계산할 저장 성과가 없습니다."
                        )
                    else:
                        _context_value_options_seen = []
                        for _c in _context_summary_rows:
                            if _c["context_value"] not in _context_value_options_seen:
                                _context_value_options_seen.append(_c["context_value"])

                        _context_display_cols = st.columns(3)
                        _context_value_in = _context_display_cols[0].selectbox(
                            "맥락값",
                            ["전체"] + _context_value_options_seen,
                            key="context_summary_value_filter",
                        )
                        _context_action_in = _context_display_cols[1].selectbox(
                            "실제 행동",
                            ["전체", "매수", "보류", "제외", "미기록"],
                            key="context_summary_action_filter",
                        )
                        _context_horizon_in = _context_display_cols[2].selectbox(
                            "거래일수",
                            ["전체", 1, 3, 5, 10, 20],
                            key="context_summary_horizon_filter",
                        )

                        _context_filtered_rows = _context_summary_rows
                        if _context_value_in != "전체":
                            _context_filtered_rows = [
                                s for s in _context_filtered_rows
                                if s["context_value"] == _context_value_in
                            ]
                        if _context_action_in != "전체":
                            _context_filtered_rows = [
                                s for s in _context_filtered_rows
                                if s["actual_action"] == _context_action_in
                            ]
                        if _context_horizon_in != "전체":
                            _context_filtered_rows = [
                                s for s in _context_filtered_rows
                                if s["horizon_sessions"] == _context_horizon_in
                            ]

                        if not _context_filtered_rows:
                            st.info(
                                "아직 판단 맥락별 누적 통계를 계산할 저장 성과가 없습니다."
                            )
                        else:
                            _context_table_rows = [
                                {
                                    "분석 기준": _context_basis_label_in,
                                    "맥락값": s.get("context_value"),
                                    "거래일수": s.get("horizon_sessions"),
                                    "실제 행동": s.get("actual_action"),
                                    "전체 표본수": s.get("sample_count"),
                                    "판단 수익률 표본수": s.get("judgment_return_count"),
                                    "판단 평균 수익률(%)": _fmt_pct(
                                        s.get("judgment_return_avg")
                                    ),
                                    "판단 중앙 수익률(%)": _fmt_pct(
                                        s.get("judgment_return_median")
                                    ),
                                    "판단 양수 개수": s.get("judgment_positive_count"),
                                    "판단 양수 비율(%)": _fmt_pct(
                                        s.get("judgment_positive_rate")
                                    ),
                                    "판단 초과수익률 표본수": s.get("judgment_excess_count"),
                                    "판단 평균 초과수익률(%)": _fmt_pct(
                                        s.get("judgment_excess_avg")
                                    ),
                                    "진입 효과 표본수": s.get("entry_effect_count"),
                                    "평균 진입 효과(%p)": _fmt_pct(
                                        s.get("entry_effect_avg")
                                    ),
                                    "중앙 진입 효과(%p)": _fmt_pct(
                                        s.get("entry_effect_median")
                                    ),
                                    "미매수 표본수": s.get("non_buy_return_count"),
                                    "미매수 평균 수익률(%)": _fmt_pct(
                                        s.get("non_buy_return_avg")
                                    ),
                                    "미매수 중앙 수익률(%)": _fmt_pct(
                                        s.get("non_buy_return_median")
                                    ),
                                    "미매수 양수 개수": s.get("non_buy_positive_count"),
                                    "미매수 양수 비율(%)": _fmt_pct(
                                        s.get("non_buy_positive_rate")
                                    ),
                                    "미매수 초과수익률 표본수": s.get("non_buy_excess_count"),
                                    "미매수 평균 초과수익률(%)": _fmt_pct(
                                        s.get("non_buy_excess_avg")
                                    ),
                                }
                                for s in _context_filtered_rows
                            ]
                            st.dataframe(
                                pd.DataFrame(_context_table_rows),
                                width="stretch",
                                hide_index=True,
                            )

            # 두 조건 조합별 누적 통계. 위 세 통계(행동별/테마별/맥락별)와 마찬가지로 현재
            # 선택한 report_id 1건이 아니라, 아래 필터 조건(시장/기간)에 맞는 여러 보고서의
            # 저장된 성과를 db.get_all_report_outcomes()로 모아 집계한다. evaluate_item()/
            # evaluate_actual_item() 재호출, 가격·벤치마크 네트워크 조회, DB UPSERT 전혀
            # 없음. 조건값/행동/거래일수 필터는 이미 계산된 통계 결과에만 적용하는 화면
            # 표시용 필터이며 DB나 통계 원본값을 바꾸지 않는다. 조건은 정확히 2개만 선택
            # 하며(세 조건 이상 조합 아님), 내부 코드명은 화면에 노출하지 않고 선택된 한글
            # 분석 기준 이름만 표시한다.
            with st.expander("두 조건 조합별 누적 통계 보기", expanded=False):
                st.caption(
                    "이 통계는 현재 선택한 보고서 한 건이 아니라, 아래 필터 조건에 맞는 "
                    "여러 보고서의 저장된 성과를 함께 집계합니다."
                )
                st.caption(
                    "두 조건이 동시에 해당한 기록을 집계한 원자료 통계입니다. 한 종목에 "
                    "여러 테마가 있으면 각 테마 조합에 각각 포함되며, 표본수가 적으면 "
                    "결과가 크게 흔들릴 수 있습니다."
                )

                _combo_basis_options = {
                    "테마": "theme_tag",
                    "매매유형": "trade_mode",
                    "당시 판정": "verdict",
                    "신호 분류": "signal_type",
                    "이벤트": "event_name",
                    "브리핑 단계": "briefing_stage",
                    "시점 구분": "timing_class",
                }
                _combo_basis_label_list = list(_combo_basis_options.keys())

                _combo_basis_cols = st.columns(2)
                _combo_basis_1_label = _combo_basis_cols[0].selectbox(
                    "첫 번째 조건",
                    _combo_basis_label_list,
                    index=_combo_basis_label_list.index("테마"),
                    key="combination_summary_basis1_filter",
                )
                _combo_basis_2_label = _combo_basis_cols[1].selectbox(
                    "두 번째 조건",
                    _combo_basis_label_list,
                    index=_combo_basis_label_list.index("매매유형"),
                    key="combination_summary_basis2_filter",
                )
                _combo_group_by_1 = _combo_basis_options[_combo_basis_1_label]
                _combo_group_by_2 = _combo_basis_options[_combo_basis_2_label]

                _combo_filter_cols = st.columns(3)
                _combo_market_in = _combo_filter_cols[0].selectbox(
                    "시장",
                    ["전체", "KR", "US", "OTHER"],
                    key="combination_summary_market_filter",
                )
                _combo_date_from_in = _combo_filter_cols[1].text_input(
                    "시작일",
                    value="",
                    key="combination_summary_date_from_filter",
                    placeholder="2026-07-01",
                )
                _combo_date_to_in = _combo_filter_cols[2].text_input(
                    "종료일",
                    value="",
                    key="combination_summary_date_to_filter",
                    placeholder="2026-07-31",
                )

                _combo_market_filter = (
                    None if _combo_market_in == "전체" else _combo_market_in
                )
                _combo_date_from_filter = _combo_date_from_in.strip() or None
                _combo_date_to_filter = _combo_date_to_in.strip() or None

                if _combo_group_by_1 == _combo_group_by_2:
                    st.error("첫 번째 조건과 두 번째 조건은 서로 달라야 합니다.")
                else:
                    try:
                        _combo_outcome_rows = db.get_all_report_outcomes(
                            market=_combo_market_filter,
                            date_from=_combo_date_from_filter,
                            date_to=_combo_date_to_filter,
                        )
                    except ValueError as _combo_query_err:
                        st.error(f"조회 조건 오류: {_combo_query_err}")
                    else:
                        _combo_residual_rows = performance.build_decision_residual_rows(
                            _combo_outcome_rows
                        )
                        _combo_summary_rows = (
                            performance.build_combination_residual_summary(
                                _combo_residual_rows,
                                [_combo_group_by_1, _combo_group_by_2],
                            )
                        )
                        if not _combo_summary_rows:
                            st.info(
                                "아직 두 조건 조합별 누적 통계를 계산할 저장 성과가 "
                                "없습니다."
                            )
                        else:
                            _combo_value1_options_seen = []
                            _combo_value2_options_seen = []
                            for _c in _combo_summary_rows:
                                if _c["context_value_1"] not in _combo_value1_options_seen:
                                    _combo_value1_options_seen.append(
                                        _c["context_value_1"]
                                    )
                                if _c["context_value_2"] not in _combo_value2_options_seen:
                                    _combo_value2_options_seen.append(
                                        _c["context_value_2"]
                                    )

                            _combo_display_cols = st.columns(4)
                            _combo_value1_in = _combo_display_cols[0].selectbox(
                                f"{_combo_basis_1_label} 조건값",
                                ["전체"] + _combo_value1_options_seen,
                                key="combination_summary_value1_filter",
                            )
                            _combo_value2_in = _combo_display_cols[1].selectbox(
                                f"{_combo_basis_2_label} 조건값",
                                ["전체"] + _combo_value2_options_seen,
                                key="combination_summary_value2_filter",
                            )
                            _combo_action_in = _combo_display_cols[2].selectbox(
                                "실제 행동",
                                ["전체", "매수", "보류", "제외", "미기록"],
                                key="combination_summary_action_filter",
                            )
                            _combo_horizon_in = _combo_display_cols[3].selectbox(
                                "거래일수",
                                ["전체", 1, 3, 5, 10, 20],
                                key="combination_summary_horizon_filter",
                            )

                            _combo_filtered_rows = _combo_summary_rows
                            if _combo_value1_in != "전체":
                                _combo_filtered_rows = [
                                    s for s in _combo_filtered_rows
                                    if s["context_value_1"] == _combo_value1_in
                                ]
                            if _combo_value2_in != "전체":
                                _combo_filtered_rows = [
                                    s for s in _combo_filtered_rows
                                    if s["context_value_2"] == _combo_value2_in
                                ]
                            if _combo_action_in != "전체":
                                _combo_filtered_rows = [
                                    s for s in _combo_filtered_rows
                                    if s["actual_action"] == _combo_action_in
                                ]
                            if _combo_horizon_in != "전체":
                                _combo_filtered_rows = [
                                    s for s in _combo_filtered_rows
                                    if s["horizon_sessions"] == _combo_horizon_in
                                ]

                            if not _combo_filtered_rows:
                                st.info(
                                    "아직 두 조건 조합별 누적 통계를 계산할 저장 성과가 "
                                    "없습니다."
                                )
                            else:
                                _combo_table_rows = [
                                    {
                                        "첫 번째 분석 기준": _combo_basis_1_label,
                                        "첫 번째 조건값": s.get("context_value_1"),
                                        "두 번째 분석 기준": _combo_basis_2_label,
                                        "두 번째 조건값": s.get("context_value_2"),
                                        "거래일수": s.get("horizon_sessions"),
                                        "실제 행동": s.get("actual_action"),
                                        "전체 표본수": s.get("sample_count"),
                                        "판단 수익률 표본수": s.get(
                                            "judgment_return_count"
                                        ),
                                        "판단 평균 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_avg")
                                        ),
                                        "판단 중앙 수익률(%)": _fmt_pct(
                                            s.get("judgment_return_median")
                                        ),
                                        "판단 양수 개수": s.get(
                                            "judgment_positive_count"
                                        ),
                                        "판단 양수 비율(%)": _fmt_pct(
                                            s.get("judgment_positive_rate")
                                        ),
                                        "판단 초과수익률 표본수": s.get(
                                            "judgment_excess_count"
                                        ),
                                        "판단 평균 초과수익률(%)": _fmt_pct(
                                            s.get("judgment_excess_avg")
                                        ),
                                        "진입 효과 표본수": s.get("entry_effect_count"),
                                        "평균 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_avg")
                                        ),
                                        "중앙 진입 효과(%p)": _fmt_pct(
                                            s.get("entry_effect_median")
                                        ),
                                        "미매수 표본수": s.get("non_buy_return_count"),
                                        "미매수 평균 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_avg")
                                        ),
                                        "미매수 중앙 수익률(%)": _fmt_pct(
                                            s.get("non_buy_return_median")
                                        ),
                                        "미매수 양수 개수": s.get(
                                            "non_buy_positive_count"
                                        ),
                                        "미매수 양수 비율(%)": _fmt_pct(
                                            s.get("non_buy_positive_rate")
                                        ),
                                        "미매수 초과수익률 표본수": s.get(
                                            "non_buy_excess_count"
                                        ),
                                        "미매수 평균 초과수익률(%)": _fmt_pct(
                                            s.get("non_buy_excess_avg")
                                        ),
                                    }
                                    for s in _combo_filtered_rows
                                ]
                                st.dataframe(
                                    pd.DataFrame(_combo_table_rows),
                                    width="stretch",
                                    hide_index=True,
                                )
            st.markdown("---")

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

            # 4-1. 필터 준수 vs 필터 무시 R 비교 카드 (report_items 전체 기준, 화면 표시 전용)
            st.markdown("#### 필터 준수 vs 필터 무시 R 비교")
            st.caption("이 통계는 매수 추천이 아니라 행동 검증용입니다.")
            _fi_stats = _fetch_filter_compliance_stats()
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("필터 무시 기록 수", _fi_stats["ignored_count"])
            fc2.metric("필터 준수 기록 수", _fi_stats["followed_count"])
            fc3.metric("필터 미입력 수", _fi_stats["unset_count"])
            fc4, fc5, fc6 = st.columns(3)
            fc4.metric("필터 무시 평균 R", _fmt_avg_r(_fi_stats["ignored_avg_r"]))
            fc5.metric("필터 준수 평균 R", _fmt_avg_r(_fi_stats["followed_avg_r"]))
            fc6.metric(
                "비교 가능 R 데이터 수",
                f"{_fi_stats['comparable_n']}건" if _fi_stats["comparable_n"] else "0건",
            )
            if _fi_stats["comparable_n"] == 0:
                st.info(
                    "아직 필터 준수/무시와 청산 R 데이터가 부족합니다. "
                    "필터 무시 기록과 청산 결과가 쌓이면 비교됩니다."
                )
            elif _fi_stats["comparable_n"] < 30:
                st.caption(f"표본 N<30: 미검증 구간입니다. ({_n_confidence_label(_fi_stats['comparable_n'])})")
            else:
                st.caption(
                    f"표본 N={_fi_stats['comparable_n']}: {_n_confidence_label(_fi_stats['comparable_n'])} 구간입니다."
                )

            # 4-2. 최악 5매매 R 점검 카드 (report_items 전체 기준, 화면 표시 전용)
            st.markdown("#### 최악 5매매 R 점검")
            st.caption("이 카드는 매수 추천이 아니라 손실 원인 점검용입니다.")
            _worst_stats = _fetch_worst_trades(limit=5)
            if _worst_stats["total_n"] == 0:
                st.info("아직 청산 R 데이터가 없습니다. 청산 결과가 쌓이면 최악 5개 매매가 표시됩니다.")
            else:
                wc1, wc2, wc3, wc4 = st.columns(4)
                wc1.metric("R 데이터 개수", _worst_stats["total_n"])
                wc2.metric("최악 5개 평균 R", _fmt_avg_r(_worst_stats["avg_worst"]))
                wc3.metric("최저 R", _fmt_avg_r(_worst_stats["lowest"]))
                wc4.metric("검증 상태", _n_confidence_label(_worst_stats["total_n"]))
                if _worst_stats["total_n"] < 30:
                    st.caption(f"표본 N<30: {_n_confidence_label(_worst_stats['total_n'])} 구간입니다.")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "종목명": d["종목명"],
                                "티커": d["티커"],
                                "매매유형": d["매매유형"],
                                "result_r": _fmt_avg_r(d["result_r"]),
                                "청산일": d["청산일"],
                                "청산사유": d["청산사유"],
                                "필터무시여부": d["필터무시여부"],
                            }
                            for d in _worst_stats["worst_rows"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

            # 4-3. 총 오픈 리스크 3R 점검 카드 (report_items 전체 기준, 화면 표시 전용)
            st.markdown("#### 총 오픈 리스크 3R 점검")
            st.caption("이 카드는 매수 추천이 아니라 여러 포지션의 손실 노출을 점검하는 장치입니다.")
            _open_risk = _fetch_open_risk_positions()
            oc1, oc2, oc3, oc4 = st.columns(4)
            oc1.metric("계산 가능한 오픈 포지션 수", _open_risk["count"])
            oc2.metric("총 오픈 리스크", f"{_open_risk['total_risk']:.2f}R")
            oc3.metric("3R 기준 상태", _open_risk_status_label(_open_risk["count"], _open_risk["total_risk"]))
            oc4.metric("계산 제외 항목 수", _open_risk["excluded_count"])
            if _open_risk["count"] == 0:
                st.info(
                    "아직 진입가와 손절가가 입력된 미청산 항목이 없습니다. "
                    "새 기록에서 진입가와 손절가가 쌓이면 총 오픈 리스크가 계산됩니다."
                )
            else:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "종목명": p["종목명"],
                                "티커": p["티커"],
                                "매매유형": p["매매유형"],
                                "진입가": f"{p['진입가']:,.0f}",
                                "손절가": f"{p['손절가']:,.0f}",
                                "1건 위험": f"{p['1건 위험']:.2f}R",
                                "필터무시여부": p["필터무시여부"],
                            }
                            for p in _open_risk["positions"]
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )

            # 5. 관심 점수 설명
            st.info(
                "관심 점수는 실제 상승확률이 아닙니다. 오늘 주가 위치, 고점 대비 밀림, 거래대금, "
                "섹터 흐름을 기준으로 관심 순서를 비교한 점수입니다. 100점은 반드시 오른다는 "
                "뜻이 아닙니다. 조건표상 거의 완벽한 경우에만 나오는 높은 관심 점수입니다. "
                "일반적인 1순위 후보는 80~90점대가 정상입니다."
            )

            # 6. 결과 표 (기본 컬럼만, 관심 점수 높은 순 정렬) — 화면 표시는 한국장/미국장으로 나눠서 보여준다.
            table_rows = []
            for score, row in scored_rows:
                saved_item = item_judgment_lookup.get(
                    (row["report_id"], row["ticker"], row["trade_mode"]), {}
                )
                table_rows.append(
                    {
                        "종목명": row["stock_name"],
                        "티커": row["ticker"],
                        "시장": row["market"],
                        "매매유형": row["trade_mode"],
                        "순위": score_rank_labels.get(saved_item.get("id"), "미평가"),
                        "관심 점수": score,
                        "판단": _display_verdict_name(row["verdict"]),
                        "결과 상태": row["status"],
                        "판단 시점": row["briefing_stage"],
                        "1일 뒤": _fmt_pct(row["returns"][1]),
                        "3일 뒤": _fmt_pct(row["returns"][3]),
                        "5일 뒤": _fmt_pct(row["returns"][5]),
                        "10일 뒤": _fmt_pct(row["returns"][10]),
                        "20일 뒤": _fmt_pct(row["returns"][20]),
                        "실제 청산가": (
                            f"{saved_item['actual_exit_price']:,.0f}"
                            if saved_item.get("actual_exit_price") else "-"
                        ),
                        "청산일": saved_item.get("actual_exit_date") or "-",
                        "계획 준수": saved_item.get("plan_followed") or "-",
                        "청산 사유": saved_item.get("exit_reason") or "-",
                        "R수익률": _fmt_result_r(saved_item.get("result_r")),
                        "검증 상태": saved_item.get("verification_status") or "미입력",
                    }
                )
            perf_df = pd.DataFrame(table_rows)

            kr_table_rows = [r for r in table_rows if r["시장"] == "KR"]
            us_table_rows = [r for r in table_rows if r["시장"] == "US"]

            st.markdown("#### 한국장 저장 결과")
            if kr_table_rows:
                st.dataframe(pd.DataFrame(kr_table_rows), width="stretch", hide_index=True)
            else:
                st.info("한국장 저장 기록 없음")

            st.markdown("#### 미국장 저장 결과")
            if us_table_rows:
                st.dataframe(pd.DataFrame(us_table_rows), width="stretch", hide_index=True)
            else:
                st.info("미국장 저장 기록 없음")

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
                    if saved_item:
                        auto_info = _auto_fill_item_display(saved_item)
                        score_text = f"{auto_info['score']:.0f}" + (" (자동계산)" if auto_info["score_is_auto"] else "")
                        top_reason = saved_item.get("top_candidate_reason") or auto_info["score_reason"]
                    else:
                        auto_info = {"score_reason": "-", "penalty_reason": "-", "buy_confirmed": "-", "buy_confirm_condition": "-"}
                        score_text = "-"
                        top_reason = "-"
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
                            "점수": score_text,
                            "점수 근거": auto_info["score_reason"],
                            "1순위 후보 근거": top_reason,
                            "감점 이유": auto_info["penalty_reason"],
                            "매수 확정 여부": auto_info["buy_confirmed"],
                            "매수 확정 조건": auto_info["buy_confirm_condition"],
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

with tab_guide:
    st.subheader("자비스 사용법")
    st.caption("이 화면은 자비스_사용법.md 파일을 앱 안에서 보여주는 화면입니다.")
    try:
        _guide_path = Path(__file__).parent / "자비스_사용법.md"
        _guide_text = _guide_path.read_text(encoding="utf-8")
        st.markdown(_guide_text)
    except FileNotFoundError:
        st.warning("자비스_사용법.md 파일을 찾을 수 없습니다.")
    except Exception as e:
        st.warning(f"사용법 파일을 불러오지 못했습니다: {e}")
