# stock_event_jarvis

GPT가 매일 제공하는 도박사/예측시장/주식시장 브리핑을 저장하고,
나중에 실제로 맞았는지 검증하기 위한 기록 도구.

**실시간 자동매매 프로그램이 아니다.** 증권사 API, 자동매매, 실계좌 주문,
Polymarket/Kalshi 자동연동은 사용하지 않는다.

자세한 스펙은 [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) 참고.
작업 규칙/금지사항은 [CLAUDE.md](CLAUDE.md) 참고.

## 폴더 구조

```
stock_event_jarvis/
├── app.py              # Streamlit 앱 (오늘의 결론 / 브리핑 붙여넣기 / 보관함 / 다음 단계)
├── database.py         # SQLite 연결, 스키마, CRUD, timing_class 자동 분류
├── data_test.py         # 무료 데이터 소스(yfinance/FinanceDataReader/pykrx) 조회 테스트
├── docs/
│   └── PROJECT_SPEC.md  # 상세 스펙
└── db/
    └── jarvis.sqlite3    # SQLite DB 파일 (최초 실행 시 자동 생성)
```

## 실행 방법 (Windows, 로컬 `.venv`)

```
<사용할 Python> -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 현재 단계

1단계 MVP 개발 중.
# 현재 운영 화면 요약

최종 상위 탭은 ① 한국장 판단, ② 미국장 판단, ③ 행동·청산, ④ 복기·통계, ⑤ 기록 조회, ⑥ 보조입니다. 한국장과 미국장 자료는 각 탭의 명시적 자료 불러오기 버튼을 눌렀을 때만 조회합니다.

KR 판단은 오늘 한국장 자료 불러오기 → 오늘 종목 판단 준비하기(시장 분위기 확인·오늘 주가 채우기·종목 판단 미리보기 일괄 실행) → 전체 결과표와 후보 카드 → 종목 선택 → 선택 종목 상세·리스크·상세 입력 → 저장 전 확인 → 최종 저장 순서입니다. US도 오늘 미국장 자료 불러오기부터 동일한 흐름으로 사용합니다.

후보는 전체를 비교할 수 있고 선택 상세만 1건 표시합니다. 테마는 전체 표와 선택 테마 1건의 세부 입력으로 구성됩니다. 뉴스·공시·시황·테마는 점수·판정·DB 저장에 반영되지 않으며 자동매매 기능은 없습니다. 태블릿은 카드 2열, 모바일은 1열입니다.
