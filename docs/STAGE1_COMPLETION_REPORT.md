# 1단계 MVP 최종 완료 보고서

작성일: 2026-07-05

## 1. 생성된 파일 목록

```
stock_event_jarvis/
├── app.py                          # Streamlit 앱 (4탭)
├── database.py                     # SQLite 스키마 + CRUD + timing_class 자동 분류
├── data_test.py                    # 무료 데이터 소스 조회 테스트 (보조)
├── README.md                       # 개요, 실행 방법
├── CLAUDE.md                       # 작업 규칙 / 금지사항 / 확정 설계
├── docs/
│   ├── PROJECT_SPEC.md             # 상세 스펙 (탭 정의, DB 스키마, 판정 기준)
│   ├── DATA_TEST_RESULTS.md        # data_test.py 실행 결과 기록
│   └── STAGE1_COMPLETION_REPORT.md # 본 보고서
└── db/
    └── jarvis.sqlite3              # 실행 데이터 (reports/report_items)
```

## 2. 구현된 기능

**탭 1. 오늘의 결론**
- 최신 저장 report 1건을 실제 조회하여 `saved_at`, `market_scope`, `timing_class`, `day_conclusion` 표시
- report_items를 판정 5종(추천 후보 / 감시 / 확인 필요 / 보류(선반영) / 제외)별로 그룹화해 표시
- 저장된 report가 없으면 안내 문구, 종목 항목이 0개면 "종목 항목은 없습니다. 오늘의 전체 결론만 저장되었습니다." 표시

**탭 2. 브리핑 붙여넣기**
- `market_scope`(KR/US/MIXED) 선택, `day_conclusion`/`raw_briefing` 텍스트 입력
- `timing_class`는 사용자 입력 없이 저장 시각 기준 자동 분류(00:00~05:59 혼합, 06:00~08:59 장전, 09:00~15:29 장중, 15:30~23:59 장후)
- 종목 항목을 0개 이상 동적으로 추가/삭제 가능. 각 항목: event_title, ticker, stock_name, market, item_timing_class(선택), 근거 A/B/C, 근거 가/나/다, 주식·베팅시장 판단, verdict(5종 고정)
- 저장 시 reports 1행 + report_items N행(N≥0)을 DB에 커밋

**탭 3. 보관함**
- 저장된 모든 report를 최신순 드롭다운으로 목록 표시
- 선택 시 원문(raw_briefing) 펼쳐보기 + 종목 판정 5종 그룹 상세 표시 (탭1과 동일한 렌더링 로직 재사용)

**탭 4. 다음 단계**
- 향후 로드맵 정적 안내 텍스트

## 3. 실행 방법

```
cd Documents/stock_event_jarvis
streamlit run app.py
```

브라우저에서 http://localhost:8501 접속.

## 4. data_test.py 결과 요약

18개 조합(라이브러리 3 × 대상 6) 중 15개 성공.

| 대상 | yfinance | FinanceDataReader | pykrx |
|---|---|---|---|
| 005930.KS | 성공 | 성공 | 성공 |
| 000660.KS | 성공 | 성공 | 성공 |
| KOSPI | 성공 | 성공 | 실패 (`KeyError: '지수명'`) |
| NVDA | 성공 | 성공 | 실패 (예상된 결과, KR 전용) |
| QQQ | 성공 | 성공 | 실패 (예상된 결과) |
| SOXX | 성공 | 성공 | 실패 (예상된 결과) |

`yfinance`, `FinanceDataReader`는 KR/US 전 대상 조회 가능. `pykrx`는 개별 KR 종목만 성공, KOSPI 지수 코드는 원인 미조사 상태로 실패. 상세는 [docs/DATA_TEST_RESULTS.md](DATA_TEST_RESULTS.md) 참고. 실패해도 스크립트가 중단되지 않고 끝까지 실행되는 것을 확인함.

## 5. 현재 제외된 기능

- 증권사 API, 자동매매, 실계좌 주문 (전면 금지, 미구현)
- Polymarket/Kalshi 자동연동, TradingAgents (금지, 미구현)
- 주가 성과표 / 점수화 / 가상매매 장부 (이번 단계 범위 밖)
- 보관함 필터/검색 (목록/상세 조회만 구현, 필터링 없음)
- 성과 검증(브리핑이 실제로 맞았는지 자동 채점) 기능 자체는 아직 없음 — 지금은 "기록"만 가능한 단계

## 6. 다음 단계에서 해야 할 일

- 보관함 탭 필터/검색 (기간, market_scope, timing_class, verdict별)
- 저장된 브리핑과 실제 시세(data_test.py에서 확인된 yfinance/FinanceDataReader)를 연결해 "그 판단이 맞았는지" 검증하는 기능 설계 (사용자와 별도 논의 필요 — 이번 세션 범위 밖으로 명시된 항목)
- pykrx KOSPI 지수 조회 실패 원인 조사(선택 사항, 필수 아님 — yfinance/FDR로 대체 가능)
- 통계/요약 기능 (판정별 적중률 등, 성과 검증 기능이 선행되어야 함)

## 7. 주의사항

- **Chrome 브라우저의 자동번역 기능을 반드시 꺼야 한다.** 이번 세션에서 판정 그룹명("추천 후보", "감시", "보류(선반영)" 등)과 탭 이름이 이상하게 보이는 문제가 있었는데, 원인은 코드나 인코딩 문제가 아니라 **브라우저 자동번역이 한글 UI 문구를 다른 한글 문구로 잘못 번역**해서 발생한 것이었다. 자동번역을 끄면 정상 표시됨을 확인함.
- 앱 실행 중 주소창에 번역 팝업이 뜨면 "번역 안 함"을 선택하거나, 브라우저 설정에서 해당 사이트(localhost)에 대한 자동번역을 비활성화할 것.
