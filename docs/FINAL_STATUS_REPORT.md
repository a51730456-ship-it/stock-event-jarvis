# FINAL_STATUS_REPORT.md — 오늘 최종 1차 완성본 (2026-07-05)

## 현재 완성된 기능

**1단계 MVP**
- Streamlit 4→5탭: 오늘의 결론 / 브리핑 붙여넣기 / 보관함 / 성과검증 / 다음 단계
- SQLite `reports`/`report_items` 저장, `timing_class`(장전/장중/장후/혼합) 자동 분류,
  `market_scope`(KR/US/MIXED) 선택, `verdict` 5종 고정, 종목 0개 브리핑도 저장 가능
- 브리핑 단계(`briefing_stage`)·신호 분류(`signal_type`) 입력 및 표시 (ALTER TABLE로
  기존 데이터 보존하며 추가)
- 빈 종목 항목(제목/티커/종목명 전부 공백) 저장 방지

**보관함 필터/검색**
- 날짜 범위, market_scope, timing_class, verdict, 브리핑 단계, 신호 분류, day_conclusion
  키워드, raw_briefing 키워드 — 전부 AND 결합, 필터 초기화 버튼

**2단계 성과검증 1차 (읽기 전용, 오늘 완료)**
- 종목 성과검증: ticker 있는 종목만 대상, 진입가 규칙(장전=당일 시가/장중=당일 종가/
  장후·혼합·기타=다음 거래일 시가)에 따라 1/3/5/10/20일 수익률과 5일 기준 초과수익률 계산
- 기준지수 자동 결정: KR→KOSPI, US 반도체(NVDA/MU/TSM/AMD 등 화이트리스트)→SOXX,
  그 외 US→SPY
- 요약 지표: 전체 대상 수 / 계산 완료 / 대기 / 데이터 부족 / 추천 후보 수 / 감시 수 /
  확인 필요 수
- **오늘 추천 없음 평가**: 종목 항목 0개인 report를 별도 섹션으로 표시. market_scope=KR
  →KOSPI, US→SPY, MIXED→KOSPI/SPY 분리 표시. 지수 상승=기회비용, 하락=위험회피 성공,
  상승만으로 실패 처리하지 않음
- 성과검증 표 / 오늘 추천 없음 표 각각 CSV 다운로드 버튼 제공
- 데이터 조회 실패·시간 미경과 시 앱이 죽지 않고 "데이터 부족"/"대기"로 표시

## 생성/수정된 주요 파일

```
stock_event_jarvis/
├── app.py                          # Streamlit 앱 (5탭, 성과검증 탭 포함)
├── database.py                     # SQLite 스키마/CRUD, briefing_stage/signal_type 포함
├── price_data.py                   # yfinance 우선 + FinanceDataReader 보조 과거 시세 조회
├── performance.py                  # 성과검증 계산 로직 (종목 + 오늘 추천 없음)
├── data_test.py                    # 무료 데이터 소스 조회 테스트 (보조)
├── README.md / CLAUDE.md
├── docs/
│   ├── PROJECT_SPEC.md             # 앱 구조/DB 스키마 스펙
│   ├── BRIEFING_LOGIC.md           # 시장 브리핑 작성·해석 로직(단계/신호분류 등)
│   ├── DATA_TEST_RESULTS.md        # data_test.py 결과 기록
│   ├── STAGE1_COMPLETION_REPORT.md # 1단계 MVP 완료 보고서
│   ├── STAGE2_PERFORMANCE_SPEC.md  # 성과검증 설계 + 1차 구현 메모
│   └── FINAL_STATUS_REPORT.md      # 본 보고서
└── db/
    └── jarvis.sqlite3              # 실행 데이터 (삭제/초기화 없이 계속 누적 중)
```

## 앱 실행 방법

```
cd Documents/stock_event_jarvis
streamlit run app.py
```

브라우저에서 http://localhost:8501 접속.

## 현재 가능한 것

- GPT 브리핑을 붙여넣어 저장 (종목 0개도 가능, 브리핑 단계/신호 분류 포함)
- 저장된 브리핑을 최신순으로 조회하고, 다양한 조건으로 필터/검색
- 저장된 종목 판정이 실제로 어떻게 움직였는지(1~20일 수익률, 기준지수 대비 초과수익률)
  사후 조회
- "오늘 추천 없음"으로 쉰 날이 기회비용이었는지 위험회피였는지 사후 조회
- 결과를 CSV로 내보내 엑셀 등에서 추가 분석

## 아직 안 되는 것

- 감시/기타 판정(확인 필요·보류·제외)의 표 3분리(추천 후보 표 / 감시 표 / 기타 판정
  추적표) — 현재는 하나의 표에 verdict 컬럼으로만 구분되어 있음. `STAGE2_PERFORMANCE_SPEC.md`
  5번에 방침은 정해져 있으나 UI 3분리는 미구현
- KOSDAQ 개별 지원 (현재 KR은 전부 KOSPI로 통일)
- 1/3/10/20일 각각에 대한 초과수익률(현재는 5일 기준 대표값 하나만)
- pykrx 활용 (1차에서는 계획대로 미사용)
- 통계/요약(적중률 집계, 시각화 등)
- 성과검증 결과를 자동으로 재계산/알림하는 기능 (현재는 수동 새로고침 버튼 기반)

## 다음에 할 작업 (후보)

1. 추천 후보/감시/기타 판정 3분리 표 (STAGE2_PERFORMANCE_SPEC.md 5번 반영)
2. 통계 탭: verdict별 적중률, 신호 분류별 성과 집계
3. KOSDAQ 지원 여부 결정 및 반영
4. 보관함 검색 결과와 성과검증 표 연동(선택한 브리핑만 필터링해서 보기)

## Chrome 자동번역 끄기 주의

**Chrome 브라우저의 자동번역 기능은 반드시 꺼야 한다.** 과거 세션에서 탭 이름/판정
문구가 이상하게 보이는 문제가 있었는데, 원인은 코드나 인코딩이 아니라 **브라우저 자동
번역이 한글 UI 문구를 다른 한글 문구로 잘못 번역**한 것이었다. 자동번역을 끄면 정상
표시된다. 주소창에 번역 팝업이 뜨면 "번역 안 함"을 선택할 것.

## 오늘 최종 판정

**1차 완성본으로 사용 가능한 상태.** 브리핑 저장 → 보관함 조회/필터 → 성과검증(종목 +
오늘 추천 없음) → CSV 내보내기까지 전체 흐름이 실제 데이터로 검증됨. 기존 저장 데이터는
전 과정에서 한 번도 삭제되지 않았고, DB 초기화도 발생하지 않았다. 자동매매, 매수/매도
신호, 증권사 API, 실시간 시세 연결, Polymarket/Kalshi 연동은 이번 1차에도 전혀 포함되지
않았다.
