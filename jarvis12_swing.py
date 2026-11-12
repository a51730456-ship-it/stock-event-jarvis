"""자비스12 전용 — 상승장(신고가 눌림매수) 목록을 자비스12 규칙으로 다시 정한다 (2026-11-12 상하님 「다 해라」 ④ · ⑤).

**얼린 계산은 그대로 부른다** — jarvis3_data.breakout_scan()(= us_swing_selector.scan_eod · US_SWING_V1)이 낸 줄을 받아,
자비스12 에서 바뀐 두 가지만 그 줄 위에서 다시 정한다. 값을 새로 재지 않는다(강도 등수 · 신고가 · 눌림 폭 · 보조 점수는 그대로).

  ④ 시장 문 — 「나스닥 종합이 조정 전 최고 종가를 되찾았나」 대신 「나스닥 종합 종가가 200일선 위인가」.
     근거(10년 · 자격을 채운 2,950줄 · 1년 이긴 비율 / 가운데 값): 지금 문 60.3% / +19.0% · 200일선 위 66.2% / +27.8%(앞 69.6 · 뒤 63.0) ·
     200일선 아래 59.3% / +4.7%. 그래서 문만 바꾸고 나머지 자격 다섯은 그대로 본다.
  ⑤ 눌림 점수 — 6~10%(20점) 우대를 없애 3~6% 도 20점(둘 다 만점 · 총점 100점 그대로). 8~10% 는 「주의」 딱지만 단다.
     근거(6개월 이긴 비율): 3~4% 63.6 · 4~5% 68.3 · 5~6% 60.5 · 6~8% 62.9 · 8~10% 52.0(앞 54.4 · 뒤 50.3 · 손실 깊이 −20.5%).

스위치는 jarvis12_rules(SWING_GATE_200 · SWING_FLAT_PULLBACK) — 둘 다 False 면 얼린 결과를 **그대로** 돌려준다.
**날짜별 목록 저장은 그대로다** — 그 기록은 자비스3 과 같이 쓰는 기록이라 깃허브 수집기가 얼린 규칙으로 찍는다(CLAUDE.md 10-1).
"""
from __future__ import annotations

import copy

import jarvis3_data as j3
import jarvis12_rules as rules
import us_swing_selector as us_swing

# 계산이나 돌려주는 값을 바꾸면 올린다 — 화면이 옛 모듈을 다시 읽게(CLAUDE.md 11 과 같은 까닭).
MODULE_REVISION = 2026111201

PULLBACK_CAUTION_FROM = 8.0        # 눌림 8% 이상이면 「주의」(⑤)


def gate_200_on() -> bool:
    return bool(getattr(rules, "SWING_GATE_200", False))


def flat_pullback_on() -> bool:
    return bool(getattr(rules, "SWING_FLAT_PULLBACK", False))


MARKET_DETAIL_200 = ("좋은 종목도 시장 전체가 약하면 성공하기 어렵습니다. 나스닥 종합 종가가 200일 평균(200일선) 위에 "
                     "있을 때만 새로 살 후보를 냅니다(2026-11-12 — 예전에는 「큰 조정 뒤 이전 고점을 되찾았나」였습니다).")
PULLBACK_DETAIL_FLAT = ("신고가를 넘은 날 바로 쫓아사지 않고 1~3거래일 안에 나오는 조정을 기다립니다. "
                        "3~10% 내려온 자리를 정상으로 보고 모두 같은 20점입니다(2026-11-12 — 6~10% 우대를 없앴습니다). "
                        "8% 넘게 내려오면 「주의」입니다 — 과거 10년에 6개월 뒤 이긴 비율이 52%로 가장 낮았습니다. "
                        "10%보다 깊으면 정상 조정으로 보지 않습니다.")


def market_words(state: dict | None) -> str:
    """시장 문 상태를 사람 말로. 200일선 문이 켜져 있으면 200일선 위·아래로 말한다."""
    state = state or {}
    if not gate_200_on():
        return us_swing.plain_state(state.get("market_status")) or "자료부족"
    above = state.get("ixic_above_sma200")
    if above is True:
        return "200일선 위 · 살 만한 장"
    if above is False:
        return "200일선 아래 · 새로 사지 않는 장"
    return "자료부족"


def _reword(explanations: dict | None, gate: bool, flat: bool) -> dict | None:
    """화면 설명(사람 말)만 새 규칙에 맞춘다 — 점수·통과는 위에서 이미 정했다."""
    if not isinstance(explanations, dict):
        return explanations
    out = dict(explanations)
    if gate and isinstance(out.get("market"), dict):
        out["market"] = {**out["market"], "one_line_explanation": "나스닥 종합 종가가 200일선 위인지 봅니다.",
                         "one_line": "나스닥 종합 종가가 200일선 위인지 봅니다.",
                         "detail_explanation": MARKET_DETAIL_200, "detail": MARKET_DETAIL_200}
    if flat and isinstance(out.get("pullback"), dict):
        out["pullback"] = {**out["pullback"], "detail_explanation": PULLBACK_DETAIL_FLAT, "detail": PULLBACK_DETAIL_FLAT}
        if out["pullback"].get("status_code") == "PRIORITY_PULLBACK":
            out["pullback"]["status"] = "6~10% 내려옴"          # 「더 좋은 자리」는 6~10% 우대와 같이 뺐다
    return out


def _rescore(row: dict, cfg: dict) -> None:
    """⑤ — 3~6% 눌림도 6~10% 와 같은 만점. 다른 항목 점수는 줄에 적힌 그대로 더한다."""
    weights = cfg.get("weights") or us_swing.DEFAULT_CONFIG["weights"]
    if row.get("pullback_status") == "VALID_PULLBACK":
        row["pullback_score"] = float(weights["pullback"])
    row["core_score"] = round(float(row.get("rs60_score") or 0) + float(row.get("rs120_score") or 0)
                              + float(row.get("pullback_score") or 0), 6)
    row["total_score"] = round(row["core_score"] + float(row.get("support_score") or 0), 6)
    row["score"] = row["total_score"]
    parts = list(row.get("score_parts") or ())
    if len(parts) >= 3:
        title, _old, top, shown = parts[2]
        parts[2] = (title, row["pullback_score"], top, shown)
        row["score_parts"] = parts
    if isinstance(row.get("pullback"), dict):
        row["pullback"] = {**row["pullback"], "score": row["pullback_score"], "parts": [row["pullback_score"]]}


def adjust(scan: dict) -> dict:
    """얼린 상승장 결과(scan)를 자비스12 규칙으로 다시 정한 **복사본**. 스위치가 다 꺼져 있거나 못 하면 scan 그대로."""
    gate, flat = gate_200_on(), flat_pullback_on()
    if not (gate or flat) or not isinstance(scan, dict) or not scan.get("ok"):
        return scan
    rows_in = scan.get("all_rows")
    if not rows_in:
        return scan
    try:
        out = dict(scan)
        cfg = scan.get("config") or us_swing.merged_config({"universe": {"include_adr": True}})
        market = dict(scan.get("market") or {})
        above = market.get("ixic_above_sma200")
        gate_open = bool(market.get("valid")) and above is True
        shown_before = {str(r.get("ticker")) for r in (scan.get("primary_rows") or []) + (scan.get("watch_rows") or [])}
        rows = []
        for source in rows_in:
            row = copy.copy(source)
            if flat:
                _rescore(row, cfg)
                pull = row.get("pullback_pct_close")
                row["pullback_caution"] = bool(pull is not None and float(pull) >= PULLBACK_CAUTION_FROM
                                               and row.get("pullback_status") == "PRIORITY_PULLBACK")
            if gate:
                row["market_status_v1"] = row.get("market_status")
                row["market_status"] = "MARKET_ON" if gate_open else "MARKET_OFF"
            status, eligible = us_swing._candidate_status(row, cfg)
            row["primary_status"] = status
            row["eligible_primary"] = eligible
            row["failed_gates"] = us_swing._failed_gates(row, cfg)
            row["grade"] = us_swing.grade_for(row["total_score"], eligible, cfg)
            row["grade_text"] = us_swing.GRADE_TEXT.get(row["grade"] or "")
            row["status_text"] = us_swing.STATUS_TEXT.get(status, status)
            row["explanations"] = _reword(us_swing.explanation_payload(row, cfg), gate, flat)
            row["plan"] = j3.breakout_plan(row)
            rows.append(row)
        rows.sort(key=us_swing.candidate_sort_key)
        for rank, row in enumerate(rows, 1):
            row["overall_rank"] = rank
        limit = max(1, int(scan.get("result_limit") or 20))
        primary = [row for row in rows if row["eligible_primary"]][:limit]
        watch = [row for row in rows if not row["eligible_primary"]][:limit]
        for rank, row in enumerate(primary, 1):
            row["pullback_rank"] = rank
            row["primary_rank"] = rank
        # 새로 보이게 된 줄에는 화면 전용 값(ATR · 당일 거래량 등)을 얼린 함수와 같은 방법으로 붙인다(받아 둔 일봉만 읽음).
        missing = [row for row in primary + watch if str(row.get("ticker")) not in shown_before]
        if missing:
            try:
                daily, _meta, _members = j3._universe_daily(True)
            except Exception:
                daily = {}
            for row in missing:
                frame = (daily or {}).get(row.get("ticker"))
                if frame is None:
                    continue
                try:
                    import pandas as pd

                    index = pd.DatetimeIndex(frame.index)
                    target = pd.Timestamp(scan.get("date"))
                    if index.tz is not None:
                        target = target.tz_localize(index.tz)
                    legacy = j3._series_metrics(frame[index <= target])
                    row["metrics"] = {**legacy, **(row.get("metrics") or {})}
                except Exception:
                    continue
        if gate:
            market["market_status_v1"] = market.get("market_status")
            market["market_status"] = "MARKET_ON" if gate_open else "MARKET_OFF"
            market["j12_gate"] = "SMA200"
        out["explanation_catalog"] = _reword(scan.get("explanation_catalog"), gate, flat)
        out.update(all_rows=rows, primary_rows=primary, rows=primary, watch_rows=watch, market=market,
                   primary_count=len(primary), watch_count=len([r for r in rows if not r["eligible_primary"]]),
                   j12_rules={"gate_200": gate, "flat_pullback": flat}, j12_frozen_scan=scan)
        return out
    except Exception:
        return scan                        # 다시 정하다 실패하면 얼린 결과 그대로(CLAUDE.md 0-0 — 있던 것을 지우지 않는다)


def breakout_scan() -> dict:
    """화면이 부르는 자비스12 상승장 — 얼린 breakout_scan 결과(같은 기억 · 같은 저장)를 자비스12 규칙으로 다시 정한다."""
    return adjust(j3.breakout_scan())


def frozen(scan):
    """같이 쓰는 기록(날짜별 목록)에 남길 **얼린 규칙 결과**. 자비스12 규칙으로 다시 정한 것이면 그 앞 것을 돌려준다."""
    if isinstance(scan, dict) and isinstance(scan.get("j12_frozen_scan"), dict):
        return scan["j12_frozen_scan"]
    return scan


def top_pick_part():
    """순위 9 의 상승장 몫. 스위치가 다 꺼져 있으면 None — 얼린 collect_top_picks 가 예전처럼 스스로 찾는다."""
    if not (gate_200_on() or flat_pullback_on()):
        return None
    try:
        found = j3._memo_ok(j3._finder_memo_key("상승장"), j3.TOP_PICK_MEMO_SECONDS, j3.find_breakout_pullback_stocks)
    except Exception:
        return None
    return adjust(found)
