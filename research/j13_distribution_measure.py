"""분산일이 코스피·코스닥에서 뜻이 있었나 — 12년치로 잰다 (2026-10-30 상하님 「다 넣어라」 — 자비스에 넣을 기능 ⑤ 분산일).

화면(자비스13 「🧮 분산일」 줄)은 미국 기준(25거래일에 5~6일이면 경고)을 **그리지 않고** 숫자만 보인다. 그 기준이 한국에서도
맞는지 재기 전에는 문턱을 그리지 않기로 했다(CLAUDE.md 0-1 — 과거 차트 → 기준 → 설명서 → 코드). 이 스크립트가 그 재기다.

세는 법은 화면과 **같은 함수**(jarvis13_market.distribution_days)를 날마다 부른다 — 따로 셈을 쓰면 화면 숫자와 갈라진다.
  · 분산일 = 지수가 0.2% 넘게 내리고 거래량이 전날보다 많은 날 · 25거래일 · 그 뒤 종가가 5% 넘게 오르면 뺌
보는 것
  ① 분산일 수(0~2 · 3~4 · 5~6 · 7↑)별로 그날부터 20 · 40거래일 지수 수익률 · 오른 날 비율 · 40일 안에 −5% · −10% 넘게 빠진 비율
  ② 「5일 이상이 된 첫날」 사건(앞 사건에서 20거래일 넘게 떨어진 것만) — 사건마다 그 뒤 20 · 40일
  ③ 앞 6년(2021년 전) · 뒤 6년(2021년부터)을 나눠 같은 쪽으로 나오나
  아무 날이나 고른 값(기준선)과 견준다. 거래비용 없음 · 지수 그대로.

클라우드 작업 칸은 네이버가 막혀 못 돈다 — 깃허브(.github/workflows/j13_distribution.yml)에서 돈다. 저장소에는 아무것도 쓰지 않는다.
J13_FAKE=1 이면 만든 값으로 틀만 돌려 본다(시험용 — 성적은 뜻이 없다).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import jarvis13_market  # noqa: E402  — 화면과 같은 분산일 셈

OUT = pathlib.Path(os.environ.get("J13_OUT") or "/tmp/j13dist")
FAKE = os.environ.get("J13_FAKE") == "1"
SPLIT = pd.Timestamp("2021-01-01")
BUCKETS = ((0, 2, "0~2일"), (3, 4, "3~4일"), (5, 6, "5~6일"), (7, 99, "7일↑"))
EVENT_AT = 5           # 미국에서 경고로 보는 수(5~6일)의 아래 끝
EVENT_GAP = 20         # 사건끼리 20거래일 넘게 떨어진 것만 따로 센다
_AFTER_CLOSE = pd.Timestamp("2100-01-01 16:00", tz="Asia/Seoul").to_pydatetime()   # 모든 봉을 끝난 장으로 본다


def load(name: str) -> pd.DataFrame:
    if FAKE:
        rng = np.random.default_rng(11 if name == "KOSPI" else 12)
        days = pd.bdate_range("2014-01-02", "2026-10-29")
        close = 2000 * np.exp(np.cumsum(rng.normal(0.0002, 0.011, len(days))))
        volume = rng.lognormal(12, 0.3, len(days))
        return pd.DataFrame({"Close": close, "Volume": volume}, index=days)
    import jarvis4_data as j4data            # 얼린 파일 — 지수 받기를 부르기만 한다
    frame = j4data._read_index_naver(name, days=4700)
    if frame is None or frame.empty:
        raise RuntimeError(f"{name} 일봉을 못 받았다")
    return frame[["Close", "Volume"]].dropna()


def counts(frame: pd.DataFrame) -> pd.Series:
    """날마다 그날까지 끝난 장 기준 분산일 수 — 화면 함수를 그날까지의 60줄에 부른다(셈은 마지막 26줄만 본다)."""
    out = {}
    for end in range(30, len(frame)):
        part = frame.iloc[max(0, end - 60):end + 1]
        dist = jarvis13_market.distribution_days(part, now=_AFTER_CLOSE)
        if dist is not None:
            out[frame.index[end]] = dist["count"]
    return pd.Series(out, dtype=float)


def forward(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["Close"].astype(float)
    values = close.to_numpy()
    n = len(values)
    low40 = np.full(n, np.nan)
    for i in range(n - 40):
        low40[i] = values[i + 1:i + 41].min() / values[i] - 1.0
    return pd.DataFrame({
        "r20": close.shift(-20) / close - 1.0,
        "r40": close.shift(-40) / close - 1.0,
        "low40": low40,
    }, index=frame.index) * 100.0


def describe(rows: pd.DataFrame) -> dict:
    rows = rows.dropna(subset=["r20", "r40", "low40"])
    if rows.empty:
        return {"days": 0}
    return {"days": int(len(rows)),
            "r20": float(rows["r20"].mean()), "up20": float((rows["r20"] > 0).mean() * 100),
            "r40": float(rows["r40"].mean()), "up40": float((rows["r40"] > 0).mean() * 100),
            "dd5": float((rows["low40"] <= -5).mean() * 100), "dd10": float((rows["low40"] <= -10).mean() * 100)}


def fmt(d: dict) -> str:
    if not d.get("days"):
        return "없음"
    return (f"{d['days']:>5}일 · 20일 {d['r20']:+.2f}% (오른 {d['up20']:.0f}%) · 40일 {d['r40']:+.2f}% (오른 {d['up40']:.0f}%) · "
            f"40일 안 −5%↓ {d['dd5']:.0f}% · −10%↓ {d['dd10']:.0f}%")


def events(count: pd.Series, fwd: pd.DataFrame) -> list[dict]:
    """분산일이 EVENT_AT 일 이상이 된 첫날 — 앞 사건에서 EVENT_GAP 거래일 넘게 떨어진 것만."""
    out, last = [], None
    previous = count.shift(1)
    for position, stamp in enumerate(count.index):
        if count.iloc[position] >= EVENT_AT and (previous.iloc[position] if position else 0) < EVENT_AT:
            if last is not None and position - last <= EVENT_GAP:
                continue
            last = position
            row = fwd.loc[stamp] if stamp in fwd.index else None
            out.append({"date": str(stamp.date()), "count": int(count.iloc[position]),
                        "r20": None if row is None or pd.isna(row["r20"]) else float(row["r20"]),
                        "r40": None if row is None or pd.isna(row["r40"]) else float(row["r40"]),
                        "low40": None if row is None or pd.isna(row["low40"]) else float(row["low40"])})
    return out


def event_summary(items: list[dict]) -> str:
    done = [item for item in items if item["r20"] is not None and item["r40"] is not None and item["low40"] is not None]
    if not done:
        return f"사건 {len(items)}번 · 끝난 것 없음"
    r20 = np.array([item["r20"] for item in done])
    r40 = np.array([item["r40"] for item in done])
    low = np.array([item["low40"] for item in done])
    return (f"사건 {len(items)}번(끝난 것 {len(done)}) · 20일 평균 {r20.mean():+.2f}% · 내린 사건 {(r20 < 0).mean() * 100:.0f}% · "
            f"40일 평균 {r40.mean():+.2f}% · 40일 안 −5%↓ {(low <= -5).mean() * 100:.0f}% · −10%↓ {(low <= -10).mean() * 100:.0f}%")


def measure(name: str) -> dict:
    frame = load(name)
    started = time.time()
    count = counts(frame)
    fwd = forward(frame).reindex(count.index)
    table = fwd.assign(count=count)
    print(f"\n######## {name} — {frame.index[0].date()} ~ {frame.index[-1].date()} · {len(frame)}거래일 · 셈 {time.time() - started:.0f}초")
    print(f"  분산일 수 나눔: " + " · ".join(f"{label} {int(((count >= lo) & (count <= hi)).sum())}일" for lo, hi, label in BUCKETS)
          + f" · 평균 {count.mean():.2f}일 · 가장 많은 날 {int(count.max())}일")
    result = {"name": name, "from": str(frame.index[0].date()), "to": str(frame.index[-1].date()),
              "now": int(count.iloc[-1]), "buckets": {}, "halves": {}, "events": []}
    base = describe(table)
    result["base"] = base
    print(f"  기준선(아무 날) {fmt(base)}")
    for lo, hi, label in BUCKETS:
        part = describe(table[(table["count"] >= lo) & (table["count"] <= hi)])
        result["buckets"][label] = part
        print(f"  분산일 {label:<5} {fmt(part)}")
    for half, mask in (("앞(2021년 전)", table.index < SPLIT), ("뒤(2021년부터)", table.index >= SPLIT)):
        rows = table[mask]
        hot = describe(rows[rows["count"] >= EVENT_AT])
        cold = describe(rows[rows["count"] < EVENT_AT])
        result["halves"][half] = {"5일↑": hot, "5일 아래": cold}
        print(f"  {half} 5일↑ {fmt(hot)}")
        print(f"  {half} 5일 아래 {fmt(cold)}")
    items = events(count, fwd)
    result["events"] = items
    result["event_line"] = event_summary(items)
    print(f"  「{EVENT_AT}일 이상이 된 첫날」 {result['event_line']}")
    for item in items[-8:]:
        print(f"    {item['date']} {item['count']}일 → 20일 "
              + ("—" if item["r20"] is None else f"{item['r20']:+.1f}%")
              + " · 40일 " + ("—" if item["r40"] is None else f"{item['r40']:+.1f}%")
              + " · 40일 안 가장 깊게 " + ("—" if item["low40"] is None else f"{item['low40']:+.1f}%"))
    print(f"  지금(끝난 장 기준) {result['now']}일")
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    results = [measure(name) for name in ("KOSPI", "KOSDAQ")]
    (OUT / "j13_distribution.json").write_text(json.dumps(results, ensure_ascii=False, indent=1, default=str),
                                               encoding="utf-8")
    # 마지막 요약 — 깃허브 기록은 끝부분만 쉽게 읽힌다(작업 칸에서는 기록 파일·첨부를 못 받는다)
    print("\n\n### 마지막 요약 (위 내용을 짧게 다시)" + (" — ⚠ 시험용 만든 값" if FAKE else ""))
    for res in results:
        print(f"  {res['name']} {res['from']} ~ {res['to']} · 지금 {res['now']}일")
        print(f"    기준선   {fmt(res['base'])}")
        for label, part in res["buckets"].items():
            print(f"    {label:<5} {fmt(part)}")
        print(f"    「{EVENT_AT}일 이상이 된 첫날」 {res['event_line']}")
        for half, pair in res["halves"].items():
            hot, cold = pair["5일↑"], pair["5일 아래"]
            if hot.get("days") and cold.get("days"):
                print(f"    {half}: 5일↑ 20일 {hot['r20']:+.2f}% · −10%↓ {hot['dd10']:.0f}% / 5일 아래 20일 {cold['r20']:+.2f}% · "
                      f"−10%↓ {cold['dd10']:.0f}%")
    print(f"\n끝 · {time.time() - started:.0f}초 · 결과 파일 {OUT / 'j13_distribution.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
