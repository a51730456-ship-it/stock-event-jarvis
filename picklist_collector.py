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
from datetime import date, datetime, timedelta
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


def _last_closed_session(market: str) -> str:
    """**마지막으로 끝난 장**의 날짜.

    예전에는 그냥 그 시장의 오늘 날짜(`store.trade_date_for`)를 썼다. 예약이
    제때 뜨면 그것이 맞다 — 미국 몫은 뉴욕 21:30(장 마감 5시간 반 뒤)에 도니까.

    **그런데 깃허브가 예약을 몇 시간씩 미룬다**(2026-08-28 실측 — 8/27 미국 몫이
    8시간 늦어 8/28 05:31 UTC 에 떴다. 그때 뉴욕은 8/28 새벽 1시 반이다).
    그러면 오늘 날짜는 8/28 인데 값은 8/27 장 종가다 — **아직 열리지도 않은 날짜로**
    남의 날 목록이 저장된다.

    그래서 시계가 아니라 **장이 끝났나**로 센다. 안 끝났으면 하루 되짚고,
    휴장일이면 더 되짚는다. 늦게 떠도 제 날짜에 붙는다.
    """
    day = date.fromisoformat(store.trade_date_for(market))
    if not store.session_is_over(market):
        day -= timedelta(days=1)
    for _ in range(10):          # 연휴가 아무리 길어도 열흘을 넘지 않는다
        if market == "US":
            if store.us_market_is_open(day):
                return day.isoformat()
        elif day.weekday() < 5:  # 한국 공휴일은 규칙으로 못 세어 주말만 거른다
            return day.isoformat()
        day -= timedelta(days=1)
    return day.isoformat()


def collect_market(market: str, *, out_dir=None, limit: int = 20,
                   trade_date: str | None = None) -> dict:
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

    # 날짜는 **마지막으로 끝난 장**의 날짜다. 손으로 되살릴 때만 지정할 수 있다
    # (2026-08-28 상하님 지시 — 8/27 목록이 2줄로 덮어써진 것을 되살렸다).
    # **아무 날이나 되살릴 수 있는 것이 아니다** — 여기서 만드는 값은 '마지막으로
    # 끝난 장'의 종가로 계산되므로, 그 장이 아직 그날인 동안에만 그날 것과 같다.
    trade_date = trade_date or _last_closed_session(market)
    # **미국 휴장일에는 아예 찍지 않는다** (2026-08-19 상하님 지시로 넣었다).
    # 예약 실행은 월~금에 도는데, 그중에는 성탄절·추수감사절처럼 장이 안 열린
    # 날이 섞여 있다. 그날 찍으면 **전날 마감값이 그 휴장일 날짜로** 저장된다.
    # 휴장일은 picklist_store.us_market_holidays가 규칙으로 센다.
    if market == "US" and not store.us_market_is_open(datetime.fromisoformat(trade_date).date()):
        _log(f"US {trade_date} — 미국 증시가 쉬는 날이라 찍지 않습니다")
        return {"ok": True, "skipped": "휴장일",
                "market": market, "trade_date": trade_date, "path": "",
                "counts": {}, "errors": []}
    # **한국도 휴장일에는 안 찍는다**(2026-08-19 저녁). 설·추석이 음력이라 달력을
    # 못 만드니 **코스피 일봉에 오늘 봉이 있나**로 가린다. 조회가 안 되면(None)
    # 막지 않는다 — 인터넷이 잠깐 끊겼다고 그날 목록이 통째로 비면 안 된다.
    if market == "KR":
        traded = getattr(data, "kr_market_traded_today", lambda: None)()
        if traded is False:
            _log(f"KR {trade_date} — 한국 증시가 쉬는 날이라 찍지 않습니다")
            return {"ok": True, "skipped": "휴장일",
                    "market": market, "trade_date": trade_date, "path": "",
                    "counts": {}, "errors": []}
    saved_at = datetime.now(_SEOUL).isoformat(timespec="seconds")
    collected: list[dict] = []
    errors: list[str] = []
    counts: dict[str, int] = {}

    def _run(kind: str, call):
        # 그 시장 화면에 없는 갈래는 새로 저장하지 않는다(2026-08-15 상하님 지시 —
        # "첫 번째 캡처 화면의 제목대로 저장해 둔 목록이 나와야지"). 미국은
        # '눌림목 찾기'를 2026-08-06에 화면에서 뺐는데 저장은 계속하고 있었다.
        if hasattr(store, "should_save") and not store.should_save(kind, market):
            _log(f"  {kind} 건너뜀 — {market} 화면에 없는 갈래입니다")
            return None
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

    # ①-2 상위 테마 5개 × 각 1~3위 = 15종목 (2026-08-15 상하님 지시).
    #     테마 순위를 재료로 쓰므로 바로 뒤에 둔다. 한국 화면에는 없어 건너뛴다.
    if theme_rows and hasattr(data, "find_theme_top_picks"):
        _run("theme15", lambda: data.find_theme_top_picks(
            theme_rows, market_score=float(market_overview.get("score") or 0)))

    # ② 눌림목 찾기 — 한국 화면에만 있다. 미국은 _run이 알아서 건너뛴다.
    #    미국 순위 9는 이것을 재료로 쓰지 않는다(collect_top_picks가 제 재료를 쓴다).
    pullback = _run("pullback", data.find_pullback_stocks)

    # ③·④ 설명서 두 갈래
    breakout = _run("breakout", data.find_breakout_pullback_stocks)
    crash = _run("crash", data.find_crash_rebound_stocks)

    # ⑤ 매수심사결과 높은 순위 9 — **화면이 부르는 함수를 그대로 부른다**(CLAUDE.md 10-1).
    #    2026-08-15까지는 여기서 find_top_reviewed_stocks를 불렀다. 그것은 화면이
    #    3·3·3으로 나누기 **전의 재료**여서, 저장된 목록에는 한 테마 종목이 1~9위를
    #    줄줄이 차지했다(상하님 지적 — "왜 순위가 123 123 123 이렇게 되어야지
    #    1~9위가 나오냐"). 이제 화면과 같은 collect_top_picks를 부른다.
    #    방금 찍은 두 갈래 결과를 넘겨 같은 조회를 두 번 하지 않는다.
    #    **한국은 아직 옛 방식이다** — jarvis4_data에는 collect_top_picks가 없다.
    #    그쪽까지 같이 고치지 않는다(CLAUDE.md 0-1 다). 한국은 예전 그대로 저장한다.
    if theme_rows:
        if hasattr(data, "collect_top_picks"):
            _run("top7", lambda: data.collect_top_picks(
                theme_rows,
                market_score=float(market_overview.get("score") or 0),
                breakout=breakout,
                crash=crash,
            ))
        else:
            extra_rows = list((pullback or {}).get("rows") or [])
            _run("top7", lambda: data.find_top_reviewed_stocks(
                theme_rows,
                market_score=float(market_overview.get("score") or 0),
                extra_rows=extra_rows,
            ))

    # ── **이미 있는 것보다 줄이 적으면 덮어쓰지 않는다** (2026-08-28) ──────────
    # 상하님 지적 — "8월 27일은 저장해 둔 목록에 상승장 신고가 눌림매수밖에 없냐?"
    # 맞았다. 8/27 미국 파일이 **2줄뿐**이었다. 다른 날은 41~54줄이다.
    #
    # 까닭 — 시세를 못 받는 때(야후가 거절하거나 장이 아직 안 끝난 때) 이것을
    # 돌리면 갈래 넷 중 셋이 빈손으로 돌아오는데, 그래도 **받아 온 몇 줄로 그날
    # 파일을 통째로 덮어썼다.** 45줄짜리가 2줄짜리로 바뀌고, 그날 목록은
    # 되살릴 수가 없다(그날 값으로 다시 계산하지 않는 것이 이 기능의 규칙이다).
    #
    # 그래서 **줄어드는 저장은 막는다.** 늘어나는 것은 그대로 둔다 — 갈래가
    # 나중에 더 붙는 일은 정상이다. 막았으면 그 사실을 크게 적어, 조용히 넘어가지
    # 않게 한다.
    existing = 0
    try:
        existing = len(store.load_rows(trade_date, market) or [])
    except Exception:
        existing = 0
    if existing and len(collected) < existing:
        _log(f"⚠ {market} {trade_date} — 받은 것이 {len(collected)}줄뿐인데 이미 "
             f"{existing}줄이 저장돼 있어 **덮어쓰지 않았습니다.** "
             f"시세를 제대로 못 받은 판입니다. 잠시 뒤 다시 돌리십시오.")
        path = None
    else:
        path = store.save_rows(collected, trade_date=trade_date, market=market,
                               out_dir=out_dir)
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
    parser.add_argument("--date", default=None,
                        help="되살릴 날짜 (예 2026-08-27). 안 주면 오늘. "
                             "마지막으로 끝난 장이 그날일 때만 값이 그날 것과 같다")
    args = parser.parse_args(argv)

    markets = ("US", "KR") if args.market == "both" else (args.market,)
    failed = 0
    for market in markets:
        try:
            summary = collect_market(market, out_dir=args.out_dir, limit=args.limit,
                                     trade_date=args.date)
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
