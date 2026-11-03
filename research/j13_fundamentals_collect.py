"""자비스13 한국 재무 모으기 — 테마 명부(data/kr_roster.json) 종목을 네이버 증권에서 받아 data/fundamentals/KR.json 에 둔다.

깃허브(.github/workflows/j13_fundamentals.yml)가 주 1회(토요일 아침) 돌린다 — 실적은 분기마다 바뀌어 매일 받을 까닭이 없고,
파일을 올릴 때마다 온라인 앱이 한 번 껐다 켜지므로(CLAUDE.md 10-2) 장 없는 날에 올린다.
J13_DRY=1 이면 앞 J13_LIMIT(기본 30) 종목만 받아 보고 몇 종목을 찍어 본다 — 파일은 안 쓴다(올릴 때 시험용).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import jarvis13_fundamentals as fn  # noqa: E402

DRY = os.environ.get("J13_DRY") == "1"
LIMIT = int(os.environ.get("J13_LIMIT") or (30 if DRY else 0)) or None
SAMPLES = ("005930", "000660", "035420", "373220")      # 삼성전자 · SK하이닉스 · NAVER · LG에너지솔루션


def main() -> int:
    started = time.time()
    codes = fn.roster_codes()
    if DRY:
        codes = {**{code: code for code in SAMPLES}, **codes}
    path = Path(tempfile.mkdtemp()) / "KR.json" if DRY else fn.DATA_PATH
    if DRY and fn.DATA_PATH.exists():
        path.write_text(fn.DATA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    result = fn.collect(codes, path=path, limit=LIMIT)
    print(f"명부 {len(codes)}종목 · 받으려 한 것 {result['asked']} · 받음 {result['got']} · 못 받음 {result['failed']} · "
          f"파일 안 종목 {result['total']} · {time.time() - started:.0f}초" + (" · 시험(파일 안 씀)" if DRY else ""), flush=True)
    data = fn.load_file(path).get("stocks") or {}
    for code in SAMPLES:
        entry = data.get(code)
        if not entry:
            print(f"  {code} — 없음", flush=True)
            continue
        info = fn.summary(code, path=path)
        print(f"  {code} {entry.get('name')} · 시총 {fn._won_cap(info['mcap'])} · PER {fn._times(info['per'])} · "
              f"PBR {fn._times(info['pbr'])} · ROE {fn._pct(info['roe'])} · 영업이익률 {fn._pct(info['opm'])} · "
              f"부채비율 {fn._pct(info['debt'])} · 배당 {fn._pct(info['dy'])} · 지표 {entry.get('latest_at')}", flush=True)
        print(f"     연간 {json.dumps(entry.get('annual'), ensure_ascii=False)}", flush=True)
        print(f"     분기 {json.dumps(entry.get('quarter'), ensure_ascii=False)}", flush=True)
    ok = result["got"] >= max(1, int(result["asked"] * 0.8))
    print(f"\n끝 · {'됨' if ok else '안 됨 — 80% 넘게 받지 못함'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
