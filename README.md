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
