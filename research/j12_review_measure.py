"""자비스12 급락 후 반등장 · 상승장의 고르는 법과 배점을 10년치로 잰다 (2026-11-12 상하님 「재 봐라」).

재기만 한다 — 앱 코드 · 배점 · 그물은 손대지 않는다. 숫자를 보여 드린 뒤 상하님이 정하신다(CLAUDE.md 0-1).
**값을 따로 계산하지 않는다** — 화면이 부르는 함수를 그대로 부른다.
  · 급락: jarvis12_crash._pick(그날 걸린 종목 · 점수 · 경고 · 순서) — 지금 자비스12 그물(QQQ −5% · QQQ 고점일 고가 → 그날 종가 ·
    10~50% · 3배 경고)을 10년 동안의 급락에 그대로 댄다.
  · 상승장: us_swing_selector.scan_eod(US_SWING_V1) 를 날마다 돌린다.
산 값은 화면과 같이 「그날 목록 → 다음 거래일 시가」, 판 값은 그 뒤 N거래일째 종가다.

급락에서 보는 것 — 날의 종류(목록이 처음 뜬 날 · 기준일이 옮겨진 날 · 가장 깊은 날 · 급락 중 아무 날)마다
  ① 변동성 큰 쪽 절반(40점)과 나머지 ② 다른 세 항목 ③ 3배 경고 ④ 낙폭 칸 ⑤ 점수 높은 쪽과 낮은 쪽
  ⑥ 성적표 10개를 동점 규칙만 바꿔 뽑았을 때(지금 = 테마 20일선 위 등수).
상승장에서 보는 것 — 정식 후보와 아무 종목 · 문이 닫힌 동안 같은 자격을 채운 종목 · 점수 · 항목별.

한계 — 지금 명부(살아남은 종목) 10년 · 테마 명부는 지금 것 · 급락 사건 수가 적다. 야후가 막힌 작업 칸에서는 못 돈다(깃허브에서 돈다).
J12_FAKE=1 이면 만든 값으로 틀만 돌려 본다(성적은 뜻이 없다).
"""
from __future__ import annotations

import hashlib
import multiprocessing
import os
import pathlib
import sys
import time
import warnings

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")

import jarvis3_data as j3            # noqa: E402
import jarvis12_crash as c12         # noqa: E402
import us_swing_selector as us_swing  # noqa: E402

FAKE = os.environ.get("J12_FAKE") == "1"
STEP = max(1, int(os.environ.get("J12_STEP") or 1))         # 상승장을 며칠마다 돌리나(시험용)
CRASH_HOLDS = ((60, "3개월"), (120, "6개월"), (250, "1년"))
SWING_HOLDS = ((20, "20일"), (60, "3개월"), (120, "6개월"), (250, "1년"))
STARTED = time.time()


def say(text: str = "") -> None:
    print(text, flush=True)


# ───────────────────────── 자료 ─────────────────────────
def _fake(tickers, start, seed0) -> dict:
    days = pd.bdate_range(start, "2026-11-10")
    market = np.cumsum(np.random.default_rng(7).normal(0.0005, 0.011, len(days)))
    frames = {}
    for place, ticker in enumerate(tickers):
        rng = np.random.default_rng(seed0 + place)
        beta = 0.6 + rng.random() * 1.6
        own = np.cumsum(rng.normal(0.0002, 0.012 + rng.random() * 0.02, len(days)))
        close = 50 * np.exp(beta * market + own)
        spread = np.abs(rng.normal(0, 0.012, len(days)))
        frames[ticker] = pd.DataFrame({
            "Open": close * (1 + rng.normal(0, 0.004, len(days))), "High": close * (1 + spread),
            "Low": close * (1 - spread), "Close": close, "Volume": rng.integers(1e6, 5e6, len(days)).astype(float)}, index=days)
    return frames


def load() -> tuple:
    tickers = tuple(dict.fromkeys(list(j3.US_LARGE_CAP_UNIVERSE) + ["QQQ"]))
    if FAKE:
        raw = _fake(tickers, "2016-11-01", 100)
        index = _fake(("^IXIC",), "2001-11-01", 9)["^IXIC"]
        # 만든 값에서는 QQQ 와 나스닥 종합을 같은 시장 흐름으로 둔다(틀만 본다).
    else:
        import yfinance as yf
        raw = {}
        for start in range(0, len(tickers), 50):
            chunk = tickers[start:start + 50]
            for attempt in range(3):
                got = yf.download(list(chunk), period="10y", interval="1d", group_by="ticker", auto_adjust=True,
                                  prepost=False, threads=True, progress=False, timeout=30, multi_level_index=True)
                part = j3._split_download(got, chunk)
                if len(part) >= len(chunk) * 0.8:
                    break
                time.sleep(3)
            raw.update(part)
        got = yf.download(["^IXIC"], period="25y", interval="1d", group_by="ticker", auto_adjust=True,
                          prepost=False, progress=False, timeout=30, multi_level_index=True)
        index = j3._split_download(got, ("^IXIC",)).get("^IXIC")
    frames = {}
    for ticker, frame in raw.items():
        clean = us_swing._clean_frame(frame)
        if clean is not None and len(clean) >= 300:
            frames[ticker] = clean
    ixic = us_swing._clean_frame(index)
    memberships: dict = {}
    for theme in j3.US_THEMES:
        for ticker in theme["stocks"]:
            memberships.setdefault(ticker, []).append(theme["name"])
    return frames, ixic, memberships


def forward(frame: pd.DataFrame, pos: int, holds) -> dict:
    """pos 번째 날 목록 → 다음 거래일 시가에 사서 N거래일째 종가. 못 재면 None."""
    out = {}
    opens, closes, lows = frame["Open"].values, frame["Close"].values, frame["Low"].values
    if pos + 1 >= len(frame):
        return {label: None for _h, label in holds} | {"mae60": None}
    buy = float(opens[pos + 1])
    for hold, label in holds:
        end = pos + 1 + hold
        out[label] = (float(closes[end]) / buy - 1.0) * 100.0 if buy > 0 and end < len(frame) else None
    end = pos + 61
    out["mae60"] = (float(np.nanmin(lows[pos + 1:end])) / buy - 1.0) * 100.0 if buy > 0 and end <= len(frame) else None
    return out


def stat(values) -> str:
    arr = np.array([v for v in values if v is not None and v == v], dtype=float)
    if len(arr) < 5:
        return f"{len(arr)}개(모자람)"
    return f"{len(arr)}개 이긴 {(arr > 0).mean() * 100:.1f}% 가운데 {np.median(arr):+.1f}% 평균 {arr.mean():+.1f}%"


def line(label: str, rows: list, holds, extra: str = "") -> None:
    """한 무리를 한 줄로 — 보유기간마다 「개수 · 이긴 비율 · 가운데 · 평균」."""
    say(f"    {label} ▸ " + " | ".join(f"{name} {stat([row.get(name) for row in rows])}" for _hold, name in holds)
        + (f" | {extra}" if extra else ""))


def day_wins(by_day: dict, pick_a, pick_b, key: str) -> str:
    """날마다 두 무리의 가운데 값을 견줘 A 가 이긴 날 수."""
    won = total = 0
    for rows in by_day.values():
        a = [r[key] for r in rows if pick_a(r) and r.get(key) is not None]
        b = [r[key] for r in rows if pick_b(r) and r.get(key) is not None]
        if len(a) >= 3 and len(b) >= 3:
            total += 1
            won += int(np.median(a) > np.median(b))
    return f"{won}/{total}일"


# ───────────────────────── 급락 후 반등장 ─────────────────────────
def qqq_episodes(qqq: pd.DataFrame) -> list:
    """jarvis12_crash.episodes 와 같은 셈(문턱 −5% · 52주 최고 종가를 되찾으면 끝)을 10년치에. 기준일이 옮겨진 날을 다 적는다."""
    close = qqq["Close"].astype(float)
    high52 = qqq["High"].astype(float).rolling(252, min_periods=252).max()
    close52 = close.rolling(252, min_periods=252).max()
    drop = (close / high52 - 1.0) * 100.0
    found, current = [], None
    for place in range(len(qqq)):
        value = drop.iloc[place]
        if pd.isna(value):
            continue
        value = float(value)
        if current is not None and float(close.iloc[place]) >= float(close52.iloc[place]) - 1e-9:
            found.append(current)
            current = None
        if value <= c12.THRESHOLD:
            if current is None:
                current = {"days": [place], "moves": [place], "deep": value}
            else:
                current["days"].append(place)
                if value < current["deep"]:
                    current["deep"] = value
                    current["moves"].append(place)
    if current is not None:
        found.append(current)
    return found


def crash_rows(frames: dict, memberships: dict, qqq: pd.DataFrame, place: int) -> list:
    """그날(place)을 기준일로 본 자비스12 급락 목록 전부(자르지 않음) + 그 뒤 성적."""
    day = qqq.index[place]
    ref_day = day.date()
    peak = c12._peak_of(qqq.iloc[max(0, place - 259):place + 1], ref_day.isoformat())
    if not peak.get("peak_date"):
        return []
    window, where = {}, {}
    for ticker, frame in frames.items():
        if ticker == "QQQ":
            continue
        pos = int(frame.index.searchsorted(day, side="right")) - 1
        if pos < 300 or frame.index[pos] != day:
            continue
        window[ticker] = frame.iloc[pos - 449 if pos >= 449 else 0:pos + 3]
        where[ticker] = pos
    try:
        picked, counts = c12._pick(window, memberships, ref_day, peak["peak_date"], peak["nasdaq_drop"], show=9999)
    except Exception as exc:
        say(f"    (못 잼 {ref_day} — {exc})")
        return []
    rows = []
    for order, row in enumerate(picked):
        ticker = row["ticker"]
        out = forward(frames[ticker], where[ticker], CRASH_HOLDS)
        drop = abs(float(row.get("judged_from_high_pct") or 0.0))
        market = abs(float(peak["nasdaq_drop"] or 0.0)) or 1.0
        out.update(day=ref_day.isoformat(), ticker=ticker, order=order, score=float(row.get("score") or 0.0),
                   bucket=row.get("bucket"), suspicious=bool(row.get("suspicious")),
                   vol_top=bool(row.get("vol_top")), vol60=row.get("vol60"),
                   above150=bool(row.get("theme_above150_top")), together=int(row.get("together_count") or 0) >= j3.CRASH_TOGETHER_FULL,
                   ret120=bool(row.get("theme_ret120_top")), above20=int(row.get("theme_above20") or 99),
                   ratio=drop / market, drop=drop, market=float(peak["nasdaq_drop"] or 0.0))
        rows.append(out)
    return rows


def scorecard(rows: list, key) -> list:
    """앱 규칙대로 — 점수 차례(동점은 key) 위 20개 중 경고 없는 10개, 모자라면 경고 종목으로 채움."""
    ordered = sorted(rows, key=lambda row: (-row["score"], key(row)))[:c12.SHOW_COUNT]
    chosen = [row for row in ordered if not row["suspicious"]][:c12.SCORECARD_COUNT]
    if len(chosen) < c12.SCORECARD_COUNT:
        chosen += [row for row in ordered if row["suspicious"]][:c12.SCORECARD_COUNT - len(chosen)]
    return chosen


def _neutral(row: dict) -> str:
    return hashlib.md5(f"{row['day']}{row['ticker']}".encode()).hexdigest()


TIE_RULES = (
    ("지금 규칙(테마 20일선 위 등수 · 앱 순서 그대로)", None),
    ("20일선 등수 거꾸로", lambda row: -row["above20"]),
    ("덜 수상한 순(종목 낙폭 ÷ QQQ 낙폭 작은 순)", lambda row: row["ratio"]),
    ("더 많이 빠진 순", lambda row: -row["drop"]),
    ("평소 덜 움직이는 순", lambda row: row["vol60"] if row.get("vol60") is not None else 99.0),
    ("아무 뜻 없는 순서(견줄 자)", _neutral),
)


def crash_report(title: str, by_day: dict) -> None:
    rows = [row for day_rows in by_day.values() for row in day_rows]
    say(f"\n■ {title} — {len(by_day)}일 · 걸린 종목 {len(rows)}줄")
    if len(rows) < 20:
        say("    (자리가 모자라 건너뜀)")
        return
    line("걸린 종목 전부(견줄 자)", rows, CRASH_HOLDS, "산 뒤 60일 안 가장 깊은 손실(가운데) "
         + f"{np.median([r['mae60'] for r in rows if r.get('mae60') is not None] or [np.nan]):+.1f}%")
    groups = (
        ("① 변동성 큰 쪽 절반(40점)", lambda r: r["vol_top"], lambda r: not r["vol_top"]),
        ("② 테마 30주선 위 상위 3(30점)", lambda r: r["above150"], lambda r: not r["above150"]),
        ("② 같은 테마 4개↑ 동시 하락(20점)", lambda r: r["together"], lambda r: not r["together"]),
        ("② 테마 6개월 수익 상위 3(10점)", lambda r: r["ret120"], lambda r: not r["ret120"]),
        ("③ 3배 경고(수상하게 빠짐)", lambda r: r["suspicious"], lambda r: not r["suspicious"]),
        ("⑤ 점수 70점↑", lambda r: r["score"] >= 70, lambda r: r["score"] < 70),
    )
    for label, yes, no in groups:
        a, b = [r for r in rows if yes(r)], [r for r in rows if no(r)]
        mae_a = np.median([r["mae60"] for r in a if r.get("mae60") is not None] or [np.nan])
        mae_b = np.median([r["mae60"] for r in b if r.get("mae60") is not None] or [np.nan])
        say(f"  {label} — 해당 {len(a) / max(1, len(rows)) * 100:.0f}% · 날마다 견줘 해당이 이긴 날(6개월 가운데) "
            f"{day_wins(by_day, yes, no, '6개월')} · 1년 {day_wins(by_day, yes, no, '1년')}")
        line(f"해당 (60일 안 가장 깊은 손실 {mae_a:+.1f}%)", a, CRASH_HOLDS)
        line(f"아님 (60일 안 가장 깊은 손실 {mae_b:+.1f}%)", b, CRASH_HOLDS)
    say("  ④ 낙폭 칸")
    for key, label in (("d10", "10~20%"), ("d20", "20~30%"), ("d30", "30~50%")):
        line(label, [r for r in rows if r["bucket"] == key], CRASH_HOLDS)
    say("  ⑤ 점수가 몇 가지로 갈리나 — 날마다 위 20개 안에서")
    kinds, biggest = [], []
    for day_rows in by_day.values():
        top = sorted(day_rows, key=lambda r: r["order"])[:20]
        if len(top) >= 10:
            counts = pd.Series([r["score"] for r in top]).value_counts()
            kinds.append(len(counts))
            biggest.append(int(counts.iloc[0]))
    if kinds:
        say(f"    점수 종류 가운데 {np.median(kinds):.0f}가지 · 가장 큰 동점 무리 가운데 {np.median(biggest):.0f}개(최대 {max(biggest)}개)")
    say("  ⑥ 성적표 10개 — 동점 규칙만 바꿔 뽑으면(날마다 10개 평균을 낸 뒤 날끼리 평균 · 괄호는 「아무 뜻 없는 순서」를 이긴 날)")
    neutral_by_day = {day: scorecard(day_rows, _neutral) for day, day_rows in by_day.items()}
    for label, key in TIE_RULES:
        text = []
        for _hold, name in CRASH_HOLDS:
            means, won, total = [], 0, 0
            for day, day_rows in by_day.items():
                chosen = scorecard(day_rows, (lambda r: r["order"]) if key is None else key)
                mine = [r[name] for r in chosen if r.get(name) is not None]
                base = [r[name] for r in neutral_by_day[day] if r.get(name) is not None]
                if len(mine) >= 5 and len(base) >= 5:
                    means.append(float(np.mean(mine)))
                    total += 1
                    won += int(np.mean(mine) > np.mean(base))
            text.append(f"{name} {np.mean(means):+6.1f}%({won}/{total})" if means else f"{name} —")
        say(f"    {label:<32} " + " · ".join(text))


def measure_crash(frames: dict, memberships: dict) -> None:
    qqq = frames["QQQ"]
    episodes = qqq_episodes(qqq)
    any_step = 3
    if FAKE:                       # 만든 값은 급락 날이 지나치게 많다 — 틀만 보게 줄인다
        episodes, any_step = episodes[-3:], 40
    say(f"\n════════ 급락 후 반등장 — 자비스12 그물을 10년에 ({qqq.index[0].date()} ~ {qqq.index[-1].date()}) ════════")
    say(f"급락 {len(episodes)}번 · 기준일이 옮겨진 횟수 가운데 {np.median([len(e['moves']) - 1 for e in episodes]):.0f}번"
        f"(최대 {max(len(e['moves']) - 1 for e in episodes)}번) · −5% 아래 날 {sum(len(e['days']) for e in episodes)}일")
    first, middle, deep, anyday = {}, {}, {}, {}
    cache: dict = {}

    def rows_for(place: int) -> list:
        if place not in cache:
            cache[place] = crash_rows(frames, memberships, qqq, place)
        return cache[place]

    gaps = []
    for number, episode in enumerate(episodes, 1):
        moves = episode["moves"]
        for target, place in ((first, moves[0]), (deep, moves[-1])):
            rows = rows_for(place)
            if rows:
                target[qqq.index[place].date().isoformat()] = rows
        for place in moves[1:-1]:
            rows = rows_for(place)
            if rows:
                middle[qqq.index[place].date().isoformat()] = rows
        rest = [place for place in episode["days"] if place not in moves][::any_step]
        for place in rest:
            rows = rows_for(place)
            if rows:
                anyday[qqq.index[place].date().isoformat()] = rows
        close = qqq["Close"]
        gaps.append((float(close.iloc[moves[-1]]) / float(close.iloc[moves[0]]) - 1.0) * 100.0)
        if number % 5 == 0:
            say(f"  … 급락 {number}/{len(episodes)} · {time.time() - STARTED:.0f}초")
    say(f"목록이 처음 뜬 날 종가 → 가장 깊은 날 종가(QQQ): 가운데 {np.median(gaps):+.1f}% · 가장 나쁜 {min(gaps):+.1f}% · "
        f"첫날이 곧 가장 깊은 날이었던 급락 {sum(1 for e in episodes if len(e['moves']) == 1)}번")
    crash_report("가. 목록이 처음 뜬 날(−5% 아래 첫날)", first)
    crash_report("나. 기준일이 옮겨진 날(가운데 — 그날은 가장 깊은 날로 보였음)", middle)
    crash_report("다. 가장 깊은 날(지나고 나서야 아는 날 · 지금 성적표가 세는 날)", deep)
    crash_report("라. 급락 중 그 밖의 날(사흘에 하루)", anyday)
    live = dict(first)
    live.update(middle)
    crash_report("마. 화면을 보고 살 수 있던 날 모음(가 + 나)", live)
    # 성적표 10개를 「처음 뜬 날」에 산 것과 「가장 깊은 날」에 산 것
    say("\n■ 바. 성적표 10개(지금 규칙 그대로) — 처음 뜬 날에 산 것과 가장 깊은 날에 산 것(급락마다 10개 평균 → 급락끼리 평균)")
    for label, source in (("처음 뜬 날", first), ("가장 깊은 날", deep)):
        text = []
        for _hold, name in CRASH_HOLDS:
            means = []
            for day_rows in source.values():
                chosen = scorecard(day_rows, lambda r: r["order"])
                values = [r[name] for r in chosen if r.get(name) is not None]
                if len(values) >= 5:
                    means.append(float(np.mean(values)))
            text.append(f"{name} {np.mean(means):+6.1f}% · 이익 난 급락 {sum(1 for m in means if m > 0)}/{len(means)}" if means else f"{name} —")
        say(f"    {label:<8} " + " | ".join(text))


# ───────────────────────── 상승장 ─────────────────────────
_G: dict = {}


def _swing_chunk(days: list) -> list:
    frames, ixic, memberships = _G["frames"], _G["ixic"], _G["memberships"]
    records, config = _G["records"], _G["config"]
    out = []
    for day in days:
        ipos = int(ixic.index.searchsorted(day, side="right")) - 1
        if ipos < 300 or ixic.index[ipos] != day:
            continue
        index_window = ixic.iloc[:ipos + 1]
        index_window.attrs[us_swing._CLEAN_FLAG] = True
        window, where = {}, {}
        for ticker, frame in frames.items():
            if ticker == "QQQ":
                continue
            pos = int(frame.index.searchsorted(day, side="right")) - 1
            if pos < 260:
                continue
            piece = frame.iloc[pos - 419 if pos >= 419 else 0:pos + 1]
            piece.attrs[us_swing._CLEAN_FLAG] = True
            window[ticker] = piece
            where[ticker] = pos
        try:
            scan = us_swing.scan_eod(window, index_window, memberships, universe_records=records,
                                     universe_mode=us_swing.UniverseMode.LEGACY_RESEARCH_200.value, as_of=day, config=config)
        except Exception:
            continue
        if not scan.get("ok"):
            continue
        status = (scan.get("market") or {}).get("market_status")
        out.append({"kind": "day", "day": day, "status": status})
        for row in scan.get("all_rows") or []:
            try:
                fits = (row.get("rs60_valid") and row.get("rs120_valid") and row.get("breakout_data_valid")
                        and float(row["rs60_percentile"]) >= 80 and float(row["rs120_percentile"]) >= 80
                        and row.get("has_valid_52w_breakout") and 1 <= int(row.get("days_since_anchor") or 0) <= 3
                        and row.get("pullback_status") in ("VALID_PULLBACK", "PRIORITY_PULLBACK"))
            except (TypeError, ValueError, KeyError):
                fits = False
            if not fits:
                continue
            ticker = row["ticker"]
            frame, pos = frames[ticker], where[ticker]
            since = int(row.get("days_since_anchor") or 1)
            closes = frame["Close"].values
            changes = closes[pos - since + 1:pos + 1] / closes[pos - since:pos] - 1.0
            item = forward(frame, pos, SWING_HOLDS)
            item.update(kind="row", day=day, ticker=ticker, status=status, eligible=bool(row.get("eligible_primary")),
                        total=float(row.get("total_score") or 0), core=float(row.get("core_score") or 0),
                        support=float(row.get("support_score") or 0), pullback=row.get("pullback_status"),
                        rebound=row.get("rebound_status"), theme=float(row.get("theme_score") or 0),
                        volume=float(row.get("volume_score") or 0), breadth=float(row.get("breadth_score") or 0),
                        elite=row.get("rs_core_status") == "ELITE", since=since,
                        shock=bool(len(changes) and float(np.min(changes)) <= -0.05))
            out.append(item)
    return out


def measure_swing(frames: dict, ixic: pd.DataFrame, memberships: dict) -> None:
    qqq = frames["QQQ"]
    days = list(qqq.index[300::STEP])
    say(f"\n════════ 상승장(신고가 눌림매수 · {us_swing.SCORE_MODEL_VERSION}) — {days[0].date()} ~ {days[-1].date()} · {len(days)}일 ════════")
    _G.update(frames=frames, ixic=ixic, memberships=memberships, records=j3._swing_universe_records(),
              config=us_swing.merged_config({"universe": {"include_adr": True}}))
    workers = max(1, min(4, multiprocessing.cpu_count()))
    chunks = [days[start::workers * 6] for start in range(workers * 6)]
    try:
        with multiprocessing.get_context("fork").Pool(workers) as pool:
            parts = pool.map(_swing_chunk, chunks)
    except Exception as exc:
        say(f"  (나눠 돌리기 실패 — 한 줄로 돌림: {exc})")
        parts = [_swing_chunk(chunk) for chunk in chunks]
    found = [item for part in parts for item in part]
    status_of = {item["day"]: item["status"] for item in found if item["kind"] == "day"}
    rows = [item for item in found if item["kind"] == "row"]
    counts = pd.Series(list(status_of.values())).value_counts().to_dict()
    say(f"돌린 날 {len(status_of)}일 · 시장 상태별 {counts} · 자격을 채운 줄(시장 문 빼고) {len(rows)} · {time.time() - STARTED:.0f}초")

    # 견줄 자 — 같은 날들에 명부 아무 종목
    base = {"on": {name: [] for _h, name in SWING_HOLDS}, "off": {name: [] for _h, name in SWING_HOLDS}}
    on_days = pd.DatetimeIndex([day for day, status in status_of.items() if status == "MARKET_ON"])
    off_days = pd.DatetimeIndex([day for day, status in status_of.items() if status != "MARKET_ON"])
    for ticker, frame in frames.items():
        if ticker == "QQQ":
            continue
        buy = frame["Open"].shift(-1)
        for hold, name in SWING_HOLDS:
            ret = (frame["Close"].shift(-(1 + hold)) / buy - 1.0) * 100.0
            base["on"][name].append(ret.reindex(on_days).dropna().values)
            base["off"][name].append(ret.reindex(off_days).dropna().values)

    def base_line(which: str, label: str) -> None:
        say(f"    {label} ▸ " + " | ".join(
            f"{name} {stat(np.concatenate(base[which][name]) if base[which][name] else [])}" for _hold, name in SWING_HOLDS))

    on = [row for row in rows if row["eligible"]]
    off = [row for row in rows if not row["eligible"]]
    per_day = pd.Series([row["day"] for row in on]).value_counts()
    say(f"\n■ 가. 정식 후보(문 열림) {len(on)}줄 · 후보가 나온 날 {len(per_day)}일 / 문 열린 날 {len(on_days)}일 · 하루 후보 수 가운데 {per_day.median() if len(per_day) else 0:.0f}개")
    line("정식 후보", on, SWING_HOLDS)
    base_line("on", "견줄 자 — 문 열린 날 명부 아무 종목")
    say(f"\n■ 나. 문이 닫힌 동안 같은 자격을 채운 종목 {len(off)}줄 (닫힌 날 {len(off_days)}일)")
    line("자격은 채웠지만 문이 닫혀 안 나온 종목", off, SWING_HOLDS)
    for code in ("MARKET_OFF", "MARKET_RECOVERY", "MARKET_RISK"):
        part = [row for row in off if row["status"] == code]
        if part:
            line(f"  그중 {code}", part, SWING_HOLDS)
    base_line("off", "견줄 자 — 문 닫힌 날 명부 아무 종목")
    say("\n■ 다. 정식 후보 안에서 — 점수와 항목이 갈랐나")
    groups = (
        ("총점 80점↑", lambda r: r["total"] >= 80), ("총점 80점 미만", lambda r: r["total"] < 80),
        ("보조 15점↑", lambda r: r["support"] >= 15), ("보조 15점 미만", lambda r: r["support"] < 15),
        ("핵심 66점↑", lambda r: r["core"] >= 66), ("핵심 66점 미만", lambda r: r["core"] < 66),
        ("눌림 6~10%(20점)", lambda r: r["pullback"] == "PRIORITY_PULLBACK"), ("눌림 3~6%(16점)", lambda r: r["pullback"] == "VALID_PULLBACK"),
        ("3 · 6개월 둘 다 상위 10%", lambda r: r["elite"]), ("그 밖(상위 20% 안)", lambda r: not r["elite"]),
        ("재상승: 전날 고가 넘음(7점)", lambda r: r["rebound"] == "PRIOR_DAY_HIGH_RECLAIM"), ("재상승: 첫 양봉(5점)", lambda r: r["rebound"] == "FIRST_GREEN"),
        ("재상승: 없음 · 닿기만", lambda r: r["rebound"] in ("NONE", "PULLBACK_TOUCH")),
        ("돌파일 거래량 점수 있음", lambda r: r["volume"] > 0), ("돌파일 거래량 점수 없음", lambda r: r["volume"] <= 0),
        ("테마 강도 7점↑", lambda r: r["theme"] >= 7), ("테마 강도 7점 미만", lambda r: r["theme"] < 7),
        ("테마 확산 3점↑", lambda r: r["breadth"] >= 3), ("테마 확산 3점 미만", lambda r: r["breadth"] < 3),
        ("신고가 뒤 1일째", lambda r: r["since"] == 1), ("2일째", lambda r: r["since"] == 2), ("3일째", lambda r: r["since"] == 3),
        ("하루에 5% 넘게 급락한 날이 있었음", lambda r: r["shock"]), ("그런 날 없이 눌림", lambda r: not r["shock"]),
    )
    for label, pick in groups:
        line(label, [row for row in on if pick(row)], SWING_HOLDS)
    say("\n■ 라. 같은 종목이 이어서 나온 것을 빼고 — 신고가 뒤 처음 후보가 된 날만")
    seen, firsts = {}, []
    for row in sorted(on, key=lambda r: (r["ticker"], r["day"])):
        last = seen.get(row["ticker"])
        if last is None or (row["day"] - last).days > 7:
            firsts.append(row)
        seen[row["ticker"]] = row["day"]
    line("처음 후보가 된 날만", firsts, SWING_HOLDS)


def main() -> int:
    say(f"자비스12 점검 측정 — {'⚠ 시험용 만든 값' if FAKE else '야후 일봉 10년'}")
    frames, ixic, memberships = load()
    say(f"받은 종목 {len(frames) - 1}/{len(j3.US_LARGE_CAP_UNIVERSE)} · QQQ {len(frames.get('QQQ', []))}일 · 나스닥 종합 {len(ixic)}일 · {time.time() - STARTED:.0f}초")
    if "QQQ" not in frames or ixic is None or len(ixic) < 1000:
        say("QQQ 나 나스닥 종합을 못 받았습니다 — 그만둡니다")
        return 1
    which = os.environ.get("J12_PART") or "both"
    if which in ("both", "crash"):
        measure_crash(frames, memberships)
    if which in ("both", "swing"):
        measure_swing(frames, ixic, memberships)
    say(f"\n끝 · {time.time() - STARTED:.0f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
