"""네 갈래 목록을 하루 한 번 스스로 찍어 두는 수집기 (2026-08-09 상하님 지시).

상하님 요구는 두 줄이다.
  * "매수 시점 리스트를 그대로 옮겨 놓아라 — 시간이 지나 맞아떨어지는지 보게."
  * "내가 로그인하지 않아도 자동으로 저장되게 해라."

두 번째가 이 파일의 존재 이유다. 화면(Streamlit)은 사람이 들어와야 돌아가므로,
그것만으로는 상하님이 안 들어온 날 자료가 통째로 빈다. 자비스5가 이미 쓰는 방식
그대로 **GitHub 컴퓨터가 장 마감 뒤에 대신 돌려** 저장소에 올린다
(`.github/workflows/picklist_collect.yml`). 노트북은 꺼져 있어도 된다.

무엇을 찍나 — 화면의 네 갈래를 그대로다.
  눌림목 찾기 · 상승장(신고가 눌림매수) · 급락 후 반등장(낙폭종목) ·
  매수심사결과 높은 순위 7

쓰는 법
    python picklist_collector.py --market KR
    python picklist_collector.py --market US
    python picklist_collector.py --market both

**계산을 새로 만들지 않는다.** 화면이 부르는 것과 똑같은 함수를 똑같은 인자로
부른다 — 그래야 저장된 목록과 화면 목록이 같다. 이 파일에 점수 계산을 한 줄이라도
따로 쓰면 두 목록이 조용히 갈라진다.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import picklist_store as store

_SEOUL = ZoneInfo("Asia/Seoul")

# 윈도우 콘솔은 기본이 CP949라 '—'나 한글 일부에서 UnicodeEncodeError로 죽는다
# (2026-08-09 실제로 걸렸다 — 자료는 이미 저장됐는데 마지막 알림 한 줄에서 터졌다).
# 자료 저장이 화면 글자 때문에 실패로 보이면 안 되므로 출력만 UTF-8로 돌려 둔다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _log(message: str) -> None:
    print(f"[{datetime.now(_SEOUL):%H:%M:%S}] {message}", flush=True)


def collect_market(market: str, *, out_dir=None, limit: int = 20) -> dict:
    """한 시장의 네 갈래를 찍어 저장한다. 결과 요약(dict)을 돌려준다.

    한 갈래가 실패해도 **나머지는 저장한다.** 미국 yfinance가 막힌 날 한국 자료까지
    비면 그날이 통째로 사라진다.
    """
    market = str(market).upper()
    if market == "US":
        import jarvis3_data as data
    elif market == "KR":
        import jarvis4_data as data
    else:
        raise ValueError(f"시장은 US 또는 KR입니다: {market}")

    trade_date = store.trade_date_for(market)
    saved_at = datetime.now(_SEOUL).isoformat(timespec="seconds")
    collected: list[dict] = []
    errors: list[str] = []
    counts: dict[str, int] = {}

    def _run(kind: str, call):
        try:
            result = call()
        except Exception as exc:  # 한 갈래의 실패가 나머지를 막지 않는다
            errors.append(f"{kind}: {exc}")
            _log(f"  {kind} 실패 — {exc}")
            return None
        if not isinstance(result, dict) or not result.get("ok"):
            reason = (result or {}).get("error") if isinstance(result, dict) else "결과 없음"
            errors.append(f"{kind}: {reason}")
            _log(f"  {kind} 실패 — {reason}")
            return None
        rows = store.rows_from_result(
            result, market=market, list_kind=kind,
            trade_date=trade_date, saved_at=saved_at, limit=limit,
        )
        collected.extend(rows)
        counts[kind] = len(rows)
        _log(f"  {kind} {len(rows)}줄")
        return result

    _log(f"{market} {trade_date} 목록 찍는 중")

    # ① 테마 순위 — 순위 7이 이것을 재료로 쓴다. 화면과 같은 순서로 부른다.
    market_overview = {}
    theme_rows = []
    try:
        market_overview = data.get_market_overview() or {}
        ranking = data.get_theme_rankings() or {}
        theme_rows = list(ranking.get("rows") or [])
    except Exception as exc:
        errors.append(f"테마 순위: {exc}")
        _log(f"  테마 순위 실패 — {exc}")

    # ② 눌림목 찾기
    pullback = _run("pullback", data.find_pullback_stocks)

    # ③·④ 설명서 두 갈래
    _run("breakout", data.find_breakout_pullback_stocks)
    _run("crash", data.find_crash_rebound_stocks)

    # ⑤ 매수심사결과 높은 순위 7 — 테마 대장주와 눌림목 결과를 재료로 쓴다.
    #    화면과 같은 재료를 넣어야 같은 목록이 나온다.
    if theme_rows:
        extra_rows = list((pullback or {}).get("rows") or [])
        _run("top7", lambda: data.find_top_reviewed_stocks(
            theme_rows,
            market_score=float(market_overview.get("score") or 0),
            extra_rows=extra_rows,
        ))

    path = store.save_rows(collected, trade_date=trade_date, market=market, out_dir=out_dir)
    if path is None:
        _log(f"{market} {trade_date} — 저장할 줄이 없어 파일을 건드리지 않았습니다")
    else:
        _log(f"{market} {trade_date} — {len(collected)}줄 저장 → {path}")

    # ── 지난 날들의 **매수금액(다음 거래일 시가)**을 채운다 (2026-08-12) ──────
    # 신호가 난 날에는 다음 거래일 시가를 알 수 없어 빈칸으로 저장된다. 그것을
    # 다음 날 이후에 누군가 채워야 수익률이 나오는데, **아무도 하지 않아 232줄
    # 전부 빈칸이었다**(2026-08-12 상하님 지적: "하나도 저장이 안 되어 있고").
    # 화면 단추로만 채울 수 있었고, 온라인에서 채운 값은 저장소에 안 올라가
    # 앱이 한 번 쉬면 사라졌다. 이제 여기서 같이 돈다 — 상하님이 로그인하지
    # 않아도 채워진다. 한 번 채워진 값은 다시 안 건드린다.
    #
    # 목록 저장이 끝난 **뒤**에 한다. 여기서 막혀도 오늘 목록은 이미 파일에 있다.
    filled = {}
    try:
        filled = store.backfill_buy_opens(market, out_dir=out_dir)
    except Exception as exc:
        errors.append(f"매수금액 채우기: {exc}")
        _log(f"  매수금액 채우기 실패 — {exc}")
    if filled:
        for day, count in sorted(filled.items()):
            _log(f"  {day} 매수금액 {count}줄 채움")
    else:
        _log("  채울 매수금액이 없습니다 (이미 다 찼거나 다음 거래일이 아직 안 왔습니다)")

    return {
        "market": market, "trade_date": trade_date, "path": str(path) if path else "",
        "rows": len(collected), "counts": counts, "errors": errors,
        "buy_opens_filled": filled,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="네 갈래 목록을 날짜별로 저장한다")
    parser.add_argument("--market", default="both", choices=["US", "KR", "both"],
                        help="어느 시장을 찍을지 (기본: 둘 다)")
    parser.add_argument("--limit", type=int, default=20, help="갈래마다 몇 위까지 (기본 20)")
    parser.add_argument("--out-dir", default=None, help="저장 폴더 (기본 data/picklist)")
    args = parser.parse_args(argv)

    markets = ("US", "KR") if args.market == "both" else (args.market,)
    failed = 0
    for market in markets:
        try:
            summary = collect_market(market, out_dir=args.out_dir, limit=args.limit)
        except Exception:
            # 한 시장이 통째로 죽어도 다른 시장은 찍는다.
            traceback.print_exc()
            failed += 1
            continue
        if not summary["rows"]:
            failed += 1
    # 한 갈래도 못 찍었으면 실패로 알린다 — 클라우드 작업이 빨갛게 뜨는 편이
    # 조용히 빈 날이 쌓이는 것보다 낫다.
    return 1 if failed == len(markets) else 0


if __name__ == "__main__":
    sys.exit(main())
