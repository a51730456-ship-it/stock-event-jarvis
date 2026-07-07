# PROJECT_SPEC.md — stock_event_jarvis

## 프로젝트 목적

실시간 자동매매 프로그램이 아니다.
GPT가 매일 제공하는 도박사/예측시장/주식시장 브리핑을 **저장**하고, 그 브리핑이
**실제로 맞았는지 나중에 검증**하기 위한 기록/조회 도구다.

시장 브리핑 작성·해석 로직은 docs/BRIEFING_LOGIC.md를 따른다.

## 금지 사항 (전 단계 공통)

- 증권사 API 사용 금지 (한국투자증권 OpenAPI, 키움 OpenAPI 등)
- 자동매매, 실계좌 주문 금지
- Polymarket / Kalshi 자동연동 금지
- TradingAgents 금지
- 네이버/다음 등 시세 스크래핑 금지
- 주가 성과표, 점수화, 가상매매 장부 — 이번 단계 범위 밖 (추후 별도 논의)

## 앱 구조

Streamlit + SQLite.

### 탭 순서

1. **오늘의 결론**
2. **브리핑 붙여넣기**
3. **보관함**
4. **다음 단계**

---

### 탭 1: 오늘의 결론

단순 안내 화면이 아니라 **최신 저장 리포트를 실제로 조회해서 보여주는 탭**이다.

표시 내용:
- 가장 최근 `saved_at` 기준 report 1건을 조회
  - `saved_at`, `market_scope`, `timing_class`, `day_conclusion` 표시
  - 저장된 report가 하나도 없으면 "저장된 브리핑이 없습니다" 안내만 표시
- 해당 report에 속한 `report_items`를 **판정(verdict) 5종으로 그룹화**하여 표시
  - 추천 후보
  - 감시
  - 확인 필요
  - 보류(선반영)
  - 제외
  - 각 그룹 헤더 아래에 해당 종목들의 `event_title`, `ticker`/`stock_name`, `market`,
    `stock_market_judgment`, `betting_market_judgment` 등을 나열
  - report_items가 0개인 경우 "오늘은 추천 종목 없음 — day_conclusion 참고" 안내만 표시
    (0개 자체가 정상 상태이며 오류가 아님)

---

### 탭 2: 브리핑 붙여넣기

- 사용자가 GPT 브리핑 원문을 텍스트로 붙여넣는다 (`raw_briefing`).
- `market_scope`는 사용자가 **KR / US / MIXED 중 선택**한다 (라디오 버튼 또는 셀렉트박스).
- `timing_class`는 **입력받지 않는다.** 저장 시점(`saved_at`)을 기준으로 자동 분류한다
  (분류 규칙은 아래 "timing_class 자동 분류 규칙" 참고).
- `day_conclusion`(오늘의 결론 요약)을 텍스트로 입력.
- 종목 항목(report_items)은 0개 이상 자유롭게 추가 가능 (반복 입력 폼).
  - 종목 항목이 0개인 브리핑도 정상적으로 저장되어야 한다.
- 각 종목 항목의 `verdict`는 5종 중 하나를 선택 (자유 텍스트 아님, 고정 선택지).
- 저장 버튼 클릭 시 `reports` 1행 + `report_items` N행(N≥0)을 저장.

---

### 탭 3: 보관함

- 저장된 모든 report를 최신순으로 목록 표시 (`saved_at`, `market_scope`, `timing_class`, `day_conclusion` 요약).
- 목록에서 선택 시 상세 보기: 원문(`raw_briefing`) + report_items 전체(판정별 구분 없이 목록 또는 판정별 그룹, 탭1과 동일한 방식 재사용 가능).
- 최소 기능: 목록 조회 + 상세 조회. 필터/검색은 이번 단계 범위 밖(다음 단계에서 고려 가능).

---

### 탭 4: 다음 단계

- 향후 계획 메모 (성과 검증, 필터/검색, 통계 등) — 정적 텍스트 또는 향후 로드맵만 표시.
  구현 없음, 안내 문구 수준.

---

## timing_class 자동 분류 규칙

`saved_at`(저장 시각, 로컬 시각 기준)의 시:분만 보고 아래 규칙으로 자동 분류한다.
사용자는 이 값을 직접 입력하거나 수정할 수 없다.

| 시간대 (로컬 기준) | timing_class |
|---|---|
| 00:00 ~ 05:59 | 혼합 (미국 시장이 실제로 열려 있는 시간대라 KR/US 혼재로 간주) |
| 06:00 ~ 08:59 | 장전 |
| 09:00 ~ 15:29 | 장중 |
| 15:30 ~ 23:59 | 장후 |

- 이 규칙은 MVP 단계의 편의적 분류이며, 실제 사용해보면서 경계값(예: 09:00 정각)이나
  시간대 폭은 조정 가능하다. 조정 시 `database.py`의 분류 함수 한 곳만 수정하면 된다.
- `market_scope`(KR/US/MIXED)와 `timing_class`(장전/장중/장후/혼합)는 서로 다른 축이며
  독립적으로 저장된다. 즉 `market_scope=US`이면서 `timing_class=장중`(한국 시각 낮 시간에
  저장한 미국장 브리핑)도 가능하다.

---

## DB 스키마

### `reports` 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| saved_at | TEXT (ISO datetime) | 저장 시각, 자동 기록 |
| market_scope | TEXT | KR / US / MIXED (사용자 선택) |
| timing_class | TEXT | 장전 / 장중 / 장후 / 혼합 (saved_at 기준 자동 분류) |
| day_conclusion | TEXT | 오늘의 결론 요약 (추천 없음도 여기에 기록) |
| raw_briefing | TEXT | 브리핑 원문 전체 |

### `report_items` 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| report_id | INTEGER FK → reports.id | |
| event_title | TEXT | |
| ticker | TEXT | |
| stock_name | TEXT | |
| market | TEXT | KR / US / OTHER |
| item_timing_class | TEXT | 해당 종목 항목 자체의 시점 구분 (선택 입력, report의 timing_class와 별개일 수 있음) |
| stock_market_basis_a | TEXT | |
| stock_market_basis_b | TEXT | |
| stock_market_basis_c | TEXT | |
| betting_basis_ga | TEXT | |
| betting_basis_na | TEXT | |
| betting_basis_da | TEXT | |
| stock_market_judgment | TEXT | |
| betting_market_judgment | TEXT | |
| verdict | TEXT | 추천 후보 / 감시 / 확인 필요 / 보류(선반영) / 제외 (5종 고정) |

- report_items가 0개인 report도 정상 저장 가능해야 한다 (FK만 존재, 자식 행 없음).
- "오늘 추천 없음"은 종목 판정(verdict)이 아니라 `reports.day_conclusion`에 텍스트로 기록한다.

---

## data_test.py — 데이터 조회 테스트 계획

**목적**: 무료 데이터 소스로 최근 일봉/현재가 조회가 실제로 가능한지 사전 확인하는
**보조 테스트 파일**. 앱 본체(app.py/database.py)의 동작을 막지 않는다.

**대상 종목/지수**:
- 005930.KS (삼성전자)
- 000660.KS (SK하이닉스)
- KOSPI
- NVDA
- QQQ
- SOXX

**사용 라이브러리**: `yfinance`, `FinanceDataReader`, `pykrx`
(증권사 API, 네이버/다음 스크래핑 금지)

**오류 처리 원칙**:
- 각 라이브러리 × 각 종목 조회는 개별적으로 `try/except`로 감싼다.
- 특정 조합이 실패해도 **전체 스크립트를 중단하지 않고** 다음 조합으로 계속 진행한다.
- 성공/실패 여부와 오류 메시지를 콘솔에 출력(및 결과 리스트에 기록)하여
  어떤 라이브러리가 어떤 종목/지수에서 동작하는지 한눈에 파악할 수 있게 한다.
- data_test.py의 실패는 1단계 MVP(app.py, database.py) 개발을 막는 조건이 아니다.
  두 작업은 독립적으로 진행 가능하다.

**출력 형식(예정)**: 조합별 성공/실패, 조회된 데이터 건수 또는 마지막 종가, 오류 메시지 요약.
