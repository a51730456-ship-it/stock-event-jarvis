"""자비스13 시장분석 첫 화면이 어디서 오래 걸리나 재기 (2026-11-04 상하님 「한국테마 로딩 너무 오래 걸린다 · 첫 로딩이라 그런 건지 확인해 봐라」).

깃허브 컴퓨터(실제 네이버·야후 자료가 열리는 곳)에서 화면 파일을 스트림릿 시험 장치(AppTest)로 **세 번** 그린다.
  ① 처음(빈 보관함 — 첫 손님) ② 바로 다시(같은 서버 · 보관함 찬 뒤 — 두 번째 손님) ③ 새 손님(새 세션 · 같은 서버)
판마다 걸린 시간과, 우리 파일(jarvis*.py · pages · market_signal_ui 등) 안에서 오래 걸린 함수 위 30개를 적는다.
값·화면은 안 바꾼다 — 재기만 한다. 비밀번호는 이 실행 안에서만 만든 임시 값이다.
"""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
PAGE = ROOT / "pages" / "12_자비스13.py"
OURS = ("jarvis", "pages", "market_signal", "kr_intraday", "naver_", "kis_", "regime_gauge", "fear_greed",
        "us_index", "gauge_ui", "hero_banner", "picklist", "database")


def _run(label: str, app=None):
    from streamlit.testing.v1 import AppTest

    if app is None:
        app = AppTest.from_file(str(PAGE), default_timeout=600)
        app.secrets["APP_PASSWORD"] = "profile-only"
        app.session_state["authenticated"] = True
        app.session_state["jarvis_access_role"] = "guest"
    prof = cProfile.Profile()
    started = time.time()
    prof.enable()
    app.run(timeout=600)
    prof.disable()
    took = time.time() - started
    out = io.StringIO()
    stats = pstats.Stats(prof, stream=out)
    stats.sort_stats("cumulative")
    rows = []
    for (path, line, name), (_cc, _nc, _tt, ct, _callers) in stats.stats.items():
        if any(part in path for part in OURS) and "site-packages" not in path:
            rows.append((ct, f"{Path(path).name}:{line} {name}"))
    rows.sort(reverse=True)
    print(f"\n===== {label} · 걸린 시간 {took:.1f}초 · 오류 {len(app.exception)}개 =====", flush=True)
    for ct, where in rows[:30]:
        print(f"  {ct:7.2f}초  {where}", flush=True)
    return app, took


def main() -> int:
    first_app, first = _run("① 처음(첫 손님)")
    _app, second = _run("② 같은 손님 다시", first_app)
    _app, third = _run("③ 새 손님(같은 서버)")
    print(f"\n요약 — 첫 손님 {first:.1f}초 · 같은 손님 다시 {second:.1f}초 · 새 손님 {third:.1f}초", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
