"""새 테마 명부 (2026-08-13) — StockTitan 12개 + 우리 것 7개.

## 왜 바꾸나

지금 명부 20개는 **내가(Claude가) 손으로 묶은 것**이다. 근거가 없고,
「빅테크10」처럼 테마가 아닌 것도 섞여 있다.

2026-08-13에 상하님과 셋을 확인했다.

  · **StockTitan**  https://www.stocktitan.net/stocks/themes
    로그인 없이 종목이 다 보이고 **affinity 점수**(테마와 얼마나 붙어 있는지,
    5점 만점)까지 준다. **여기 것을 쓴다.**
  · **Barchart**  표가 로그인 없이는 안 채워진다(머리글만 나온다). 테마 이름만 참고.
  · **MarketScreener** 접근 차단(403).
  · **ETF 보유종목** yfinance가 상위 10개만 준다. 시총 큰 순이라 어느 테마를 봐도
    MSFT·AMZN이 올라온다. 검산용으로만.

## 규칙

**① StockTitan이 다루는 테마는 그쪽 명부를 쓴다 — affinity 5점(순수 테마주)만.**
   5점이 3개 미만이면 4점까지 내린다. 그래도 3개 미만이면 그 테마는 버린다.
   4점 이하를 넣으면 테마가 흐려진다 — 양자컴퓨팅에 AMZN이 들어오는 식이다.

**② StockTitan에 없는 테마 7개는 지금 것을 그대로 둔다.**
   전력망·희토류·인프라·클라우드·핀테크·주택·유전체. Barchart도 이 중 넷을
   테마로 잡고 있으니 근거가 있다.

**③ 「빅테크10」은 뺀다.** 테마가 아니라 큰 회사 열 개 모음이고, 그 열 개가
   이미 반도체·AI·클라우드에 다 들어가 있어 같은 종목을 두 번 센다.

**④ 「암호화폐·블록체인」은 안 쓴다.** 우리 「핀테크·블록체인」과 겹친다.

**⑤ 「금·귀금속」·「물·수처리」는 못 쓴다.** 우리 199종목 안에 해당 종목이 없다.

## 반드시 지킬 것

명부는 그물과 같은 급이다(CLAUDE.md 0-1 라). **이 명부로 바꾸면 배점을
처음부터 다시 잰다.** 2026-08-09에 종목 하나(CRWD→ORCL) 바꿨더니
'테마 동반 4개↑'가 합격에서 탈락으로 뒤집혔다.

쓰는 법:  python research/us_theme_roster_v2.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

# StockTitan 테마 이름 → 앱에서 쓸 이름. 여기 없는 것은 안 쓴다.
FROM_STOCKTITAN = {
    "인공지능": "AI·데이터센터",
    "반도체": "반도체",
    "원전·우라늄": "원전·우라늄",
    "방산·군수": "방산·드론",
    "사이버보안": "사이버보안",
    "우주·위성": "우주·위성",
    "양자컴퓨팅": "양자컴퓨팅",
    "로봇·자동화": "로봇·자동화",
    "석유·가스": "석유·가스",
    "전기차": "배터리·전기차",
    "재생에너지": "태양광·청정에너지",
    "바이오·제약": "바이오",
}

# StockTitan에 없어 지금 것을 그대로 두는 테마.
KEEP_OURS = ("전력망·전력설비", "희토류·핵심광물", "인프라·리쇼어링",
             "클라우드·SaaS", "핀테크·블록체인", "주택·홈빌더", "유전체·정밀의료")

MIN_MEMBERS = 3


def build() -> list[dict]:
    """새 명부. jarvis3_data.US_THEMES와 같은 모양으로 돌려준다."""
    import jarvis3_data as j3
    from us_theme_source_stocktitan import STOCKTITAN

    universe = set(j3.US_LARGE_CAP_UNIVERSE)
    ours = {theme["name"]: list(theme["stocks"]) for theme in j3.US_THEMES}

    themes: list[dict] = []
    for source, name in FROM_STOCKTITAN.items():
        table = STOCKTITAN[source]
        pure = [t for t, s in table.items() if s >= 5 and t in universe]
        picked = pure if len(pure) >= MIN_MEMBERS else \
            [t for t, s in table.items() if s >= 4 and t in universe]
        if len(picked) < MIN_MEMBERS:
            continue
        themes.append({"name": name, "stocks": picked,
                       "source": f"StockTitan {'5점' if picked is pure else '4점'}↑"})
    for name in KEEP_OURS:
        themes.append({"name": name, "stocks": ours[name], "source": "지금 명부 유지"})
    return themes


def main() -> None:
    import jarvis3_data as j3

    themes = build()
    old = {t["name"]: set(t["stocks"]) for t in j3.US_THEMES}
    new_all = {s for t in themes for s in t["stocks"]}
    old_all = set().union(*old.values())

    print(f"\n{'=' * 92}\n### 새 명부 — 테마 {len(themes)}개 · 종목 {len(new_all)}개"
          f"  (지금 {len(old)}개 · {len(old_all)}종목)\n{'=' * 92}")
    for theme in themes:
        mark = ""
        if theme["name"] in old:
            gone = sorted(old[theme["name"]] - set(theme["stocks"]))
            added = sorted(set(theme["stocks"]) - old[theme["name"]])
            if gone:
                mark += "  빠짐: " + " ".join(gone)
            if added:
                mark += "  들어옴: " + " ".join(added)
        else:
            mark = "  **새 테마**"
        print(f"  {theme['name']:<16}{theme['source']:<16}{len(theme['stocks']):>2}개  "
              f"{' '.join(theme['stocks'])}")
        if mark.strip():
            print(f"  {'':<34}{mark.strip()}")

    print(f"\n  ── 통째로 빠지는 테마 ──")
    for name in old:
        if name not in {t["name"] for t in themes}:
            print(f"     {name}  ({' '.join(sorted(old[name]))})")
    print(f"\n  명부에서 아주 빠지는 종목 {len(old_all - new_all)}개:")
    print("     " + " ".join(sorted(old_all - new_all)))
    print(f"  새로 들어오는 종목 {len(new_all - old_all)}개:")
    print("     " + " ".join(sorted(new_all - old_all)))


if __name__ == "__main__":
    main()
