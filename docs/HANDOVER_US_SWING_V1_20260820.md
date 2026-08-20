# 자비스3 미국 상승장(신고가 눌림매수) 인수인계서

작성일: 2026-08-20 (Codex 작성) · **2026-08-20 오후 Claude가 P0를 마무리하고 갱신**  
상태: **옛 상승장을 전부 걷어내고 새 배점으로 교체 완료.** 전체 시험 통과 ·
실제 자료 스캔 완료 · 화면 설명서와 용어까지 새 판. 남은 것은 라이브 명부와
자동 EOD 저장뿐이다.  
후속 담당: 다음 작업자

> **2026-08-20 저녁 — 옛 상승장을 전부 걷어냈다 (상하님 지시)**
> - *"배점관련은 상승장(신고가 눌림매수)관련만 새걸로 다 교체하는거야 과거는 다 필요없다"*
> - *"rs60 뭐 이런거 용어 쓰지말고 일반인이 알기 쉽게 해라"*
> - *"각 배점 설명서 한줄평 화면에 뿌려라"*
>
> 지운 것 — `theme_proximity_points` · `breakout_gain60` · `breakout_gain60_points` ·
> `_attach_theme_proximity` · `_us_shares` · `_theme_rank_part` · `BREAKOUT_HOLD_RESULTS` ·
> `BREAKOUT_BASE_WIN_RATE/MEDIAN` · `BREAKOUT_STATE_GOOD/FAIR` · `BREAKOUT_GAIN60_TIERS` ·
> `THEME_PROX_*` · 페이지의 옛 상승장 배점 설명표(`_SCORE_TABLE["breakout"]`) ·
> `method_help.US_MID_TEXT`와 옛 상승장 표 그림.
> 남긴 것 — `BREAKOUT_MARKET_MAX_DROP` · `BREAKOUT_DROP_BAND`는 research/의 옛 그물
> 스크립트가 아직 읽어서 남겼다. **화면도 계산도 안 쓴다.**
>
> 새로 한 것 — 항목 이름을 질문 꼴 쉬운 말로, 상태코드를 `plain_state()`로 사람 말로,
> 한 줄 설명을 배점표에 늘 보이게(「자세히」에 자세한 설명). 리비전 `2026082050`.
>
> **급락 갈래는 한 줄도 안 건드렸다.**

> **2026-08-20 오후 갱신 요약 (Claude)**
> - 7절 「아직 통과하지 않음」은 **모두 해결됐다.** 아래 11절 P0 앞에 결과를 적었다.
> - 8절 「실제 데이터 sample scan 미완료」도 **해결됐다.** 8절에 결과를 적었다.
> - 9절 「회귀테스트 미완료」도 **해결됐다** — `pytest` 전체 1,039 passed.

이 문서는 이번 작업에서 실제로 반영된 부분, 검증한 부분, 아직 끝내지 못한 부분을
구분하기 위한 인수인계서다. 아래의 `완료`는 해당 작은 항목의 코드가 들어갔다는
뜻일 뿐이며, 전체 사양의 완료를 뜻하지 않는다.

## 0. 원문 확인 및 범위

- 최종 지시문:  
  `C:\Users\jangs_tjkt17a\.codex\attachments\d245975d-a6b0-4431-bc7f-4ea896637418\pasted-text.txt`
- 확인한 크기: 52,151 bytes, 2,951줄.
- 마지막은 `72. 구현 후 보고 형식`이며 사용자가 알려 준 1~11번 보고 순서와
  `질문을 먼저 던지고 멈추지 말고 ... 실제 구현과 테스트까지 진행` 문구까지
  존재한다.
- 이것은 단순한 숫자 교체가 아니라 Universe, IXIC 시장 Gate, RS60/120,
  종가 신고가/anchor, 눌림, 7개 배점, DB, UI, EOD, 테스트를 함께 요구하는 전체
  selector 사양이다.
- 이번 변경은 자비스3의 미국 상승장 갈래만 대상으로 했다. 급락 후 반등장,
  자비스1/2/4/5, 한국테마, 기존 브리핑 보고서 계산은 의도적으로 건드리지 않았다.

## 1. 기존 프로젝트에서 확인한 관련 구조

- `pages/2_자비스3.py` 상승장 버튼이
  `jarvis3_data.find_breakout_pullback_stocks()`를 호출한다.
- 종전 상승장 규칙은 고정 약 200종목, 장중 High를 포함한 52주 고점,
  신고가 후 3~10일, 고점 대비 4~15% 하락이었다.
- 종전 점수는 테마 근접도 70 + 돌파 전 60일 상승 30이었다.
- 종전 시장상태는 QQQ 참고정보였고 후보를 차단하지 않았다.
- `jarvis3_store.py`에는 수동 매수기록만 있었고 selector 전체 원자료를 날짜별로
  보존하는 테이블이 없었다.
- 급락 갈래는 별도 함수와 별도 화면 분기로 나뉘어 있어 상승장 전용 경로를
  추가하는 방식으로 격리할 수 있었다.

## 2. 새로 만든/수정한 파일

### 새 파일

- `us_swing_selector.py`
  - 화면·네트워크·DB에서 분리한 순수 계산 엔진.
  - 현재 `MODULE_REVISION = 2026082020`, `SCORE_MODEL_VERSION = US_SWING_V1`.
- `test_us_swing_selector.py`
  - 핵심 공식, 정확 경계, 미래누수, 정렬, 5종목 합성 EOD 시나리오 시험.
- `test_us_swing_store.py`
  - 스캔 저장, 버전 보존, 원자료 변경, 무결성, 정렬, trade 버전 시험.
- 이 문서 `docs/HANDOVER_US_SWING_V1_20260820.md`.

### 수정 파일

- `jarvis3_data.py`
  - 새 selector를 호출하는 상승장 adapter로 교체.
  - 새 selector가 Streamlit 프로세스에 옛 버전으로 남지 않도록 리비전 검사 후
    reload하는 연결을 추가.
  - 상승장 관련 공개 함수명과 주요 호환 키는 유지.
- `jarvis3_store.py`
  - additive 방식의 swing scan/candidate 저장 테이블과 조회 함수를 추가.
  - 매수기록에 nullable `score_model_version`을 추가하는 migration과 저장 연결 추가.
- `pages/2_자비스3.py`
  - 상승장 전용 PRIMARY/WATCH 목록과 상세 카드 경로 추가.
  - 급락 화면은 기존 경로를 그대로 타도록 상승장만 조기 분기.
  - 페이지 요구 리비전을 `2026082020`으로 동기화.
- `CURRENT_STATUS.md`
  - 본 작업이 WIP임과 인수인계서 위치를 맨 위에 기록할 예정/기록.

### 수정하지 않은 중요 파일

- `app.py`, `price_data.py`, `performance.py`, `mobile_ui.py`, `method_help.py`
- `jarvis4_data.py`, 급락 계산 함수/배점, 기존 reports 데이터
- `app.py`를 수정하지 않았으므로 app.py 백업은 만들 필요가 없었다.
- `research/_out/`은 작업 전부터 있던 unrelated untracked 경로로 건드리지 않았다.

## 3. DB 변경

코드에 다음 additive 테이블 생성 로직을 넣었다.

- `jarvis3_swing_scan_runs`
  - 기준일, 실제/요청 Universe, config JSON/hash, 입력 fingerprint, 시장상태,
    종목수, PRIMARY/WATCH 수, 버전 등을 스캔 단위로 저장.
- `jarvis3_swing_candidates`
  - universe 전체 종목에 대해 RS, anchor, 눌림, 테마, breadth, RVOL, rebound,
    Core/Support/Total, Gate 실패사유, 상태, 설명 payload 등을 저장.
- `jarvis3_trades.score_model_version`
  - nullable 컬럼을 additive migration으로 추가하도록 구현.

안전장치:

- 동일 입력은 같은 `scan_key`로 idempotent 저장.
- config 또는 원자료가 달라지면 새 run으로 보존.
- V1 기록을 V2 가중치로 UPDATE하지 않음.
- 후보 필수점수가 빠지거나 후보 수가 맞지 않으면 성공으로 숨기지 않고 실패.

중요: 실제 `db/jarvis.sqlite3`에 이번 기능의 migration/scan을 실행하지 않았다.
저장 시험은 메모리 SQLite에서만 했다. 따라서 운영 DB 데이터는 그대로다.

운영 DB 읽기 전용 재검증(작업 종료 시점):

- DB SHA256:
  `71459EBBD2E69EDE300DA80A06BDB607A4AB73AE39EDE9922D872C93E06CDBF1`
- report 1~9: 전부 존재.
- report 1~9 item 수: `0, 0, 1, 1, 3, 1, 2, 1, 6` (합계 15).
- report 1~9 선택행 fingerprint:
  `77661BB5E76A2999ABD11859B5F10E4E583A0787C7794C359469887258F91443`
- 전체 DB 현황: reports 17건, report_items 90건.
- 위 값은 작업 전 기준과 동일하다.

## 4. 실제 구현한 종목선정 알고리즘

순서는 `공통 완료 세션 확정 → Universe/가격 검증 → IXIC Market Gate → RS →
종가 신고가/anchor → 눌림 → 보조지표 → HARD GATE → SCORE → PRIMARY/WATCH 정렬`이다.

### HARD GATE

다음 조건을 모두 통과해야만 `eligible_primary=True`가 된다.

1. IXIC 시장상태가 `MARKET_ON`.
2. RS60 percentile >= 80.
3. RS120 percentile >= 80.
4. 오늘을 제외한 직전 252거래일 최고 종가를 오늘 종가가 strict `>`로 돌파한
   유효 anchor가 존재.
5. anchor 뒤 IXIC 거래일 기준 day1~day3.
6. anchor 종가 대비 현재 종가 눌림이 3~10%.

보조점수가 높아도 Gate를 우회하지 못하며 Gate 탈락 종목은 WATCH로 분리한다.

### 주요 계산

- RS raw: `(종목 N일 수익률 - 같은 날짜 IXIC N일 수익률)`.
- 날짜별 유효 횡단면에서 내림차순 average rank.
- percentile: `100 * (N - rank) / (N - 1)`, N=1이면 100.
- 유효 횡단면 30종목 미만이면 `RS_RANK_UNRELIABLE`로 PRIMARY 차단.
- 52주 신고가는 장중 High가 아니라 조정 종가 Close만 사용.
- 종목 결측일이 있어도 anchor 경과일은 IXIC 세션으로 계산.
- exact 3%, 6%, 10% 및 시장 exact -10%에서 부동소수 오분류가 없도록 정규화.
- breakout RVOL은 돌파일을 제외한 직전 20개 거래량이 모두 유효해야 계산.
- avg dollar volume도 오늘 제외 직전 20일이 모두 유효해야 계산.
- 테마는 대상종목 제외(LOO) 구성원 RS120으로 mean/median/trimmed mean을 계산.
- 여러 테마 소속이면 유효 LOO percentile이 가장 높은 테마 하나를 선택하고,
  breadth도 같은 테마를 사용하도록 구현했다. 이는 원문에 없는 V1 해석이다.
- rebound는 prior-day-high reclaim, first green, pullback first touch 중 가장 높은
  한 항목만 적용하여 중복가산하지 않는다.
- `as_of` 이후 가격행은 절단하며 IXIC 실제 마지막 세션을 scan date로 사용한다.

## 5. 100점 배점 구현 내용

### Core 70

- RS60: 최대 25
  - >=95: 25, >=90: 23, >=80: 20, >=70: 12, >=60: 6, 그 아래 0.
- RS120: 최대 25
  - RS60과 같은 계단.
- 종가 눌림: 최대 20
  - 6~10%: 20, 3~<6%: 16, 1.5~<3%: 6,
    0~<1.5%: 2, 음수 또는 >10%: 0.

### Support 30

- Theme: 최대 10
  - percentile >=90: 10, >=75: 7, >=50: 3, 그 아래/invalid: 0.
- 돌파일 RVOL: 최대 8
  - >=2.0: 8, >=1.5: 6, >=1.2: 3, 그 아래/invalid: 0.
- Breadth: 최대 5
  - >=70%: 5, >=50%: 3, >=30%: 1, 그 아래/invalid: 0.
- Rebound: 최대 7
  - 전일고가 회복 7, 첫 양봉 5, 눌림 첫 진입 3, 없음 0.

모든 기간/cutoff/계단/점수/weight는 `DEFAULT_CONFIG`에 모았고 시작 시
Core=70, Support=30, Total=100 및 음수/비정상 weight를 검증한다.

## 6. 한 줄 설명/상세설명 구현 위치

- 중앙 설명 카탈로그와 explanation payload는 `us_swing_selector.py`에 있다.
- market, RS60, RS120, breakout, pullback, theme, volume, breadth, rebound마다
  실제값, 점수/만점, status, valid/reason, confidence, 한 줄 설명, 상세 설명을
  payload로 만든다.
- `pages/2_자비스3.py`의 상승장 전용 renderer는 이 payload를 표시한다.
- 화면에서 Total을 승률로 부르지 않으며 Gate 통과 종목에만 BUY grade를 표시한다.
- `method_help.py`의 종전 상승장 설명은 아직 갱신하지 않았다. 일부 다른 화면에서
  10~15%/70+30 옛 설명이 보일 수 있으므로 후속 수정 승인이 필요하다.

## 7. 테스트 개수와 결과

### 현재 통과

실행 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  test_us_swing_selector.py test_us_swing_store.py test_jarvis3_store.py
```

결과: **67 passed in 1.30s**.

- 새 selector 시험 54개.
- 새 swing store 시험 9개.
- 기존 jarvis3 store 시험 4개.
- 5종목 synthetic EOD 시나리오 포함:
  - A PRIMARY
  - B RS120 약함
  - C day0 신고가
  - D 얕은 눌림 WATCH
  - E 10% 초과 TOO_DEEP
- 수정한 production 4개 파일 `py_compile` 통과.

### 위 「아직 통과하지 않음」은 모두 해결됐다 (2026-08-20 오후 · Claude)

| 그때 | 지금 |
|---|---|
| `test_jarvis3_data.py` 10 실패 | **73 passed** — 옛 상승장 계약을 새 사양으로 교체 |
| `test_previous_session_freeze.py` 1 실패 | **16 passed** — jarvis4 요구 리비전 동기화 |
| `test_jarvis3_page.py` 6 실패 | **47 passed** — fixture를 실제 payload로 교체 |
| 전체 suite 미실행 | **1,039 passed · subtest 64 · 실패 0** (3분 25초) |
| 원문 30개 시험 미대조 | **17개 보강** — `test_us_swing_selector.py` 71 passed |

새로 만든 시험용 파일 하나가 늘었다 —

- `us_swing_testdata.py` : 여섯 겹 그물(시장 Gate · RS60 · RS120 · 종가 신고가 ·
  1~3거래일 · 3~10% 눌림)을 모두 만족하는 합성 일봉을 만든다. **계산·화면은 이
  파일을 부르지 않는다.** `test_jarvis3_data`와 `test_jarvis3_page`가 같은 자료를
  보게 해서, 표 시험과 계산 시험이 서로 다른 것을 굳히지 않게 한다.

### 화면 시험이 바뀐 방식 — 손으로 적은 숫자를 없앴다

옛 `test_jarvis3_page._breakout_result()`는 결과 payload를 손으로 적어 두었다.
그러면 계산이 바뀌어도 화면 시험은 옛 모양을 계속 통과시킨다(이번에 실제로 그랬다).
지금은 `us_swing_testdata.scan()`이 **`find_breakout_pullback_stocks`를 그대로
돌려** 만든 payload를 쓴다. 가격·점수도 그 payload에서 읽어 견준다.

## 8. 실제 데이터 sample scan 결과 — **완료 (2026-08-20 오후 · Claude)**

Codex 환경에서는 Yahoo 접근이 막혀 못 했는데, Claude 환경에서는 열려 있어 실제로 돌렸다.

`jarvis3_data.find_breakout_pullback_stocks()` · 15.3초 · 캐시 없이 처음 받음.

| 항목 | 값 |
|---|---|
| 기준일 | 2026-08-19 (완료된 미국 거래일) |
| Universe | `LEGACY_RESEARCH_200` (요청은 `LIVE_NASDAQ_COMMON`, 명부가 없어 경고와 함께 대체) |
| 시장 | `MARKET_ON` · IXIC 26,331.09 · 진행 ATH 대비 −2.8% · 회복 후 87거래일 |
| 명부/일봉 | 200 / 199 |
| RS 횡단면 | RS60 199 · RS120 199 (최소 30 조건 통과) |
| **정식 후보** | **1개** |
| WATCH | 198개 (화면에는 20개까지) |

정식 후보 —

| 티커 | 등급 | 총점 | 핵심 | 보조 | RS60 | RS120 | 눌림 | day |
|---|---|---|---|---|---|---|---|---|
| URI | C | 65 | 56 / 70 | 9 / 30 | 81.8 | 87.4 | 4.1% | 2 |

탈락 사유(명부 200 전체) — RS 둘 다 약함 143 · RS60만 약함 15 · RS120만 약함 15 ·
관찰창 지남 7 · 너무 깊음 7 · 신고가 당일(day0) 5 · 신고가 없음 3 ·
눌림 대기 2 · 자료부족 2 · 정식 후보 1.

**이 숫자를 미래 성적으로 읽으면 안 된다.** 하루치 스캔이 돌아간다는 것을 확인한
기록이다.

## 9. 기존 기능 회귀테스트 결과 — **완료 (2026-08-20 오후 · Claude)**

- 전체 suite **1,039 passed · 64 subtests passed · 실패 0** (3분 25초).
- 새 저장소 + 기존 jarvis3 store: 통과.
- 기존 report 1~9와 DB 파일: 읽기 전용 fingerprint 기준 완전 동일(3절 값 그대로).
- 급락 계산 코드는 한 줄도 바꾸지 않았고, 급락 시험도 그대로 통과한다.
- 자비스3 data/page suite는 옛 상승장 기대값을 새 사양으로 갈아 끼워 전부 통과한다.

## 10. 아직 연구상 미확정이라 구현하지 않은 항목

- 손절, 최종청산, 강제 보유기간은 점수에 넣지 않았고 구현하지 않았다.
- stop/exit를 승률 또는 보장수익처럼 표현하지 않았다.
- `MARKET_RISK`의 정교한 전이 규칙은 원문이 충분히 정의하지 않아 V1에서는
  correction/reclaim 사이클 전 자료부족/미확정 상태로 제한적으로 사용한다.
- 다중 테마 선택은 원문 미정이라 “가장 높은 유효 LOO percentile 한 테마”로
  임시 결정했다.
- Gate 통과 시 `primary_status=PRIMARY_CANDIDATE`, 눌림 종류는 별도
  `pullback_status=VALID_PULLBACK/PRIORITY_PULLBACK`으로 분리했다.
  따라서 문자열 `PRIMARY_PULLBACK`은 현재 생성하지 않는다. 후속 담당자가 원문의
  상태코드 요구와 맞는지 결정해야 한다.
- `PULLBACK_TOUCH` 3점은 literal first entry로 구현했다. 구간에 머무는 다음 날에도
  3점을 유지할지는 원문이 모호하다.

## 11. 남은 기술적 문제 및 후속 작업 순서

### P0 — **전부 완료됐다 (2026-08-20 오후 · Claude)**

1. ✅ `test_jarvis3_data.py`의 옛 상승장 시험 10개를 새 사양으로 교체했다.
   급락 시험은 한 줄도 바꾸지 않았다. 73 passed.
2. ✅ `test_jarvis3_page.py`의 `_breakout_result`를 **selector가 실제로 만든
   payload**로 바꿨다(`us_swing_testdata.py`). PRIMARY 있음/없음(MARKET_OFF),
   WATCH, 상세화면, 배점표, 접힌 설명까지 새로 확인한다. 47 passed.
3. ✅ `jarvis4_data._REQUIRED_J3_REVISION`을 `2026082020`으로 맞췄다(규칙 11).
   **자비스4 계산은 하나도 안 바꿨다** — 옛 모듈이 프로세스에 남았는지 보는
   표식뿐이다. `test_previous_session_freeze` 16 passed.
4. ✅ 원문 61번의 30개 시험명을 하나씩 대조해 **빠진 17개를 채웠다** —
   RS120 식(TEST 2) · day1/2/3 각각(TEST 7) · RS120 계단(TEST 15) ·
   테마 LOO(TEST 18) · 테마 구성원 부족(TEST 19) · RS 자료부족 차단(TEST 20) ·
   테마 없어도 통과(TEST 21) · 보조점수 우회 불가(TEST 22) ·
   항목합=핵심+보조=총점(TEST 23·24) · 점수버전(TEST 29).
   `test_us_swing_selector.py` 71 passed.
5. ✅ 전체 suite 실행 — **1,039 passed · 64 subtests passed · 실패 0**
   (`.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, 3분 25초).
6. ✅ 실제 자료 sample scan 완료 — 결과는 8절에 적었다.

### P1 — 라이브 정확성

1. 기본 요청은 `LIVE_NASDAQ_COMMON`이지만 실제 공급자가 없어 현재는
   `LEGACY_RESEARCH_200`으로 명시적 fallback한다. warning과 실제 mode는 저장한다.
   완전한 LIVE Nasdaq common roster와 asset type/effective date 공급자가 필요하다.
2. PIT universe는 공급자가 없어 adapter에서 명시적으로 차단한다.
3. theme membership이 effective-dated가 아니므로 과거 scan에서 미래 테마 편입을
   완전히 막지 못한다.
4. “entry signal 전까지만 새 신고가에서 anchor reset”을 알 prior episode state가
   live selector에 연결되지 않았다. 현재는 최신 신고가로 reset한다.
5. `suppress_overlapping_signals`는 helper만 있고 live EOD pipeline에 연결되지 않았다.
   `signal_index`가 없을 때 `pd.bdate_range`가 미국 휴장일을 센다.
6. explicit `as_of=오늘`을 장중에 넘기면 진행 중 daily bar를 허용할 수 있다.
   EOD 완료 세션 검증을 explicit as_of에도 강제해야 한다.
7. 종목 자료는 최근 2년만 받아 오래된 historical as_of/backtest에는 warm-up이 부족하다.
8. IXIC와 종목 batch의 마지막 날짜가 다를 때 data_count 0이 될 수 있다. stale/source
   경고를 화면에도 명확히 표시해야 한다.
9. 수동 `_KNOWN_US_ADRS` 목록은 실제 asset type 원자료가 아니며 오분류 가능성이 있다.

### P1 — 저장 자동화

- 페이지 버튼은 `persist=True`지만 `picklist_collector.py` 자동 EOD 작업은 기본
  `persist=False`라 새 raw DB를 자동 축적하지 않는다.
- GitHub runner가 영구 DB에 저장하려면 Turso URL/token을 GitHub Secrets로 연결해야
  한다. workflow와 비밀값은 이번 범위 밖이라 수정하지 않았다. 사용자 승인을 먼저
  받아야 한다.

### P2 — 정리

- `jarvis3_data.py`와 페이지에 옛 상승장 helper/상수/점수표가 dead path로 남아 있다.
  라이브 새 경로는 사용하지 않지만 static 문서/시험에 혼동을 준다.
- `research/us_breakout_speed.py`도 옛 -15~-10 band를 참조한다.
- `method_help.py`의 옛 상승장 설명을 중앙 설명으로 교체해야 한다. 급락 설명은 보존한다.
- 실제 배포 전 오래된 intermediate swing table이 존재하는 DB를 가정한 migration 시험,
  Turso adapter 시험, Streamlit AppTest가 필요하다.

## 후속 담당자가 먼저 실행할 명령

```powershell
git status --short
git diff -- jarvis3_data.py jarvis3_store.py "pages/2_자비스3.py"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  test_us_swing_selector.py test_us_swing_store.py test_jarvis3_store.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  test_jarvis3_data.py test_previous_session_freeze.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  test_jarvis3_page.py --maxfail=1
```

## 절대 건드리지 말아야 할 것

- `db/jarvis.sqlite3` 삭제/초기화 금지.
- 기존 report 및 report 1~9 삭제 금지.
- 사용자의 별도 승인 없이 `price_data.py`, `performance.py`, app.py, 급락 배점,
  자비스4 계산을 변경하지 말 것.
- 기존 사용자 변경과 `research/_out/`을 정리하거나 삭제하지 말 것.
- 아직 미통과 시험과 실데이터 scan이 있으므로 `완료` 또는 `배포 가능`으로 표시하지 말 것.

## 원문 72번 형식으로 본 현재 결론

1. 기존 구조: 1절에 기록.
2. 수정 파일: 2절에 기록.
3. DB 변경: 3절에 기록하되 실DB migration은 미실행.
4. 종목선정 알고리즘: 4절의 핵심 계산은 구현.
5. 100점 배점: 5절 구현.
6. 설명 위치: 6절 구현, `method_help.py`는 미갱신.
7. 테스트: 핵심 67 pass, 기존 회귀 미완료.
8. 실제 sample scan: 미완료.
9. 기존 기능 회귀: 부분 통과, 전체 미완료.
10. 손절/최종청산: 의도적으로 미구현.
11. 남은 문제: 11절 P0/P1/P2에 기록.

