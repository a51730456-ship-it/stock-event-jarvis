"""한국 급락 「그림자 목록」 저장 (2026-10-31 상하님 「라 로 해라」) — 미리 적어 둔 규칙으로 고른 목록을 **저장만** 한다.

화면의 급락 목록(그물)은 그대로 두고, 재기에서 가장 나았던 자비스12 식 규칙을 날짜와 함께 따로 쌓아 앞으로의 성적으로 가린다.
규칙은 docs/KR_THEME_SPEC.md 3-4 「그림자 목록」에 적어 둔 그대로이며 **바꾸지 않는다**(바꾸면 시험이 무너진다).

  · 국면 — 코스피 종가가 1년(252거래일) 최고 종가보다 15% 넘게 낮은 날들(20거래일 안에 다시 들어오면 같은 국면)
  · 신호 — 국면 안에서 코스피 종가가 그 국면의 새 바닥을 찍은 날. 그날 저장하고, 다음 거래일 시가에 산 것으로 잰다
  · 종목 낙폭 — 그날 종가 ÷ 코스피 고점일(1년 최고 종가 날) 그 종목 고가 − 1 이 −50~−80%
  · 울타리 — 50일 평균 거래대금 50억↑ · 250거래일 넘게 거래 · 보통주(스팩·리츠·우선주 등 뺌)
  · 빼기 — 흔들림 · 복권 · 급등 · 몰림(20일 평균 거래대금 10억↑ 안에서 순위) · 최근 11거래일 +5% 넘게 오른 종목
  · 성적 — 20 · 40 · 60거래일을 나란히(파는 때를 정하지 않는다 · CLAUDE.md 0-1 바)

셈은 research/j13_kr_crash_remeasure.py 의 prepare · episodes · stock_dd 를 **그대로** 부른다 — 따로 짜면 재기와 갈라진다.
신호가 난 날에만 data/picklist_shadow/{날짜}.KR.json 을 새로 쓴다(있으면 덮지 않는다 · 지우지 않는다 · CLAUDE.md 10-1 과 같다).
화면 추천에는 쓰지 않는다. 다시 잴 날 — 이번 국면이 끝난(코스피 종가가 −15% 위로 올라온) 날부터 60거래일 뒤.
깃허브 「자비스13 그림자 목록 저장」(.github/workflows/j13_shadow_collect.yml)이 한국장 마감 뒤 돌린다.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import j13_kr_crash_remeasure as rm  # noqa: E402  — 재기와 같은 셈

RULE = "j13-shadow-v1"
RULE_TEXT = ("코스피 1년 최고 종가 −15% 아래 국면 · 국면 안 새 바닥(종가)마다 · 종목 낙폭 = 그날 종가 ÷ 코스피 고점일 그 종목 고가 "
             "−50~−80% · 50일 평균 거래대금 50억↑ · 250거래일↑ · 빼기(흔들림·복권·급등·몰림 + 최근 11일 +5%↑) · "
             "다음 거래일 시가 · 20/40/60거래일")
THRESHOLD = -0.15
BAND = (-0.80, -0.50)
COUNT = 420                     # 받을 일봉 줄 수 — 1년 최고(252) · 거래 250일 · 국면 시작까지 넉넉히
OUT = pathlib.Path(os.environ.get("J13_SHADOW_OUT") or ROOT / "data" / "picklist_shadow")
FAKE = os.environ.get("J13_FAKE") == "1"
ANY_DAY = os.environ.get("J13_SHADOW_ANY_DAY") == "1"     # 시험용 — 마지막 봉이 오늘이 아니어도 셈만 해 본다(파일은 안 쓴다)
SEOUL = ZoneInfo("Asia/Seoul")


def load_recent(count: int = COUNT):
    """지금 상장된 보통주 일봉(짧게) + 코스피 — 재기의 universe · _naver 를 그대로 쓴다."""
    uni, note = rm.universe()
    uni = uni[uni["status"] == "listed"]
    frames, fail = {}, 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(rm._naver, code, count): code for code in uni["code"]}
        for fut in as_completed(futs):
            try:
                df = fut.result()
            except Exception:
                fail += 1
                continue
            if df is not None and len(df) >= 260:
                frames[futs[fut]] = df
    kospi = rm._naver("KOSPI", count)
    dates = kospi.index
    wide = {key: pd.DataFrame({code: frame[key] for code, frame in frames.items()}).reindex(dates)
            for key in ("open", "high", "close", "volume")}
    meta = uni.set_index("code").reindex(list(frames))
    return wide, {"KOSPI": kospi}, meta, f"{note} · 상장 {len(uni)} · 일봉 {len(frames)} · 실패 {fail}"


def decide(env, meta) -> dict:
    """마지막 날이 국면 안 새 바닥이면 그날의 목록. 아니면 왜 아닌지만."""
    dates = env["dates"]
    last = len(dates) - 1
    out = {"rule": RULE, "rule_text": RULE_TEXT, "date": str(pd.Timestamp(dates[last]).date()),
           "kospi_close": float(env["k_close"].iloc[last]), "kospi_dd_pct": float(env["k_dd"].iloc[last] * 100)}
    eps = rm.episodes(env, THRESHOLD)
    if not eps or eps[-1]["end"] != last:
        return {**out, "phase": False, "signal": False}
    episode = eps[-1]
    out.update({"phase": True, "phase_start": str(pd.Timestamp(dates[episode["start"]]).date()),
                "phase_low": str(pd.Timestamp(dates[episode["deepest"]]).date())})
    if last not in episode["lows"]:
        return {**out, "signal": False}
    dd = rm.stock_dd(env, "kpeak", last)
    with np.errstate(invalid="ignore"):
        cand = env["pool_np"][last] & (dd <= BAND[1]) & (dd >= BAND[0])
        cand &= ~env["bad_np"][last]                      # 빼기 — 흔들림·복권·급등·몰림
        cand &= ~(env["ret11_np"][last] > 0.05)           # 빼기 — 최근 11일 +5% 넘게 오름
    codes = list(env["codes"])
    rows = []
    for i in np.where(cand)[0]:
        code = codes[i]
        info = meta.loc[code] if code in meta.index else pd.Series(dtype=object)
        rows.append({"code": code, "name": str(info.get("name") or ""), "market": str(info.get("market") or ""),
                     "close": float(env["close"][last][i]), "dd_from_kospi_peak_pct": round(float(dd[i] * 100), 2),
                     "value50_eok": round(float(env["value50"].iloc[last, i]), 1)})
    rows.sort(key=lambda row: row["dd_from_kospi_peak_pct"])
    peak = env["k_peak_np"][last]
    return {**out, "signal": True, "count": len(rows),
            "kospi_peak_date": None if np.isnan(peak) else str(pd.Timestamp(dates[int(peak)]).date()),
            "rows": rows}


def save(result: dict, out_dir: pathlib.Path = OUT) -> pathlib.Path | None:
    """신호 난 날만 새 파일로 쓴다. 이미 있으면 덮지 않는다(그날 처음 적은 것이 기록이다)."""
    if not result.get("signal"):
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['date']}.KR.json"
    if path.exists():
        return None
    result = {**result, "saved_at": datetime.now(SEOUL).isoformat(timespec="seconds")}
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main() -> int:
    started = time.time()
    if FAKE:
        wide, idx, meta, note = rm.load_fake()
    else:
        wide, idx, meta, note = load_recent()
    env = rm.prepare(wide, idx)
    result = decide(env, meta)
    today = datetime.now(SEOUL).date().isoformat()
    print(f"자료: {note} · 마지막 봉 {result['date']} · 코스피 {result['kospi_close']:,.2f} "
          f"(1년 최고 종가 대비 {result['kospi_dd_pct']:+.1f}%) · {time.time() - started:.0f}초")
    if not result["phase"]:
        print("국면 아님(코스피가 −15% 위) — 저장할 것 없음")
    elif not result["signal"]:
        print(f"국면 안({result['phase_start']}부터 · 가장 깊은 날 {result['phase_low']})이지만 오늘은 새 바닥이 아님 — 저장할 것 없음")
    else:
        print(f"새 바닥 — {result['count']}종목(코스피 고점일 {result['kospi_peak_date']})")
        for row in result["rows"][:30]:
            print(f"  {row['code']} {row['name']} · {row['close']:,.0f} · 코스피 고점일 대비 {row['dd_from_kospi_peak_pct']:+.1f}%")
    if result["date"] != today and not FAKE:
        print(f"마지막 봉({result['date']})이 오늘({today})이 아님 — 휴장이거나 아직 안 들어옴. 파일은 안 쓴다")
        return 0
    if FAKE or ANY_DAY:
        print("시험 실행 — 파일은 안 쓴다")
        return 0
    path = save(result)
    print(f"저장: {path}" if path else "저장 안 함(신호 없음 또는 이미 있음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
