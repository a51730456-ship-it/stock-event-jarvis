"""그날의 종목 목록을 **찍은 그대로** 날짜별로 남기는 창고 (2026-08-09 상하님 지시).

왜 만들었나
-----------
상하님 말씀 그대로다 — "매수 시점 리스트를 그대로 옮겨 놓아라, 그래야 시간이
지나서 어느 정도 맞아떨어지는 데이터를 만들 수 있다."

지금까지 네 갈래(눌림목 찾기 · 상승장 · 급락 후 반등장 · 매수심사결과 높은 순위 7)는
누를 때마다 **그 순간의 시세로 새로 계산**했다. 그래서 어제 무엇이 1위였는지는
어디에도 남지 않았고, 나중에 "그때 그 목록이 맞았나"를 잴 방법이 없었다.
이 파일은 그날 화면에 뜬 줄을 손대지 않고 그대로 한 줄씩 적어 둔다.

두 가지 원칙
------------
1. **다시 계산하지 않는다.** 저장할 때도, 불러올 때도 값을 고치지 않는다.
   나중에 성적을 재는 것은 이 자료를 읽는 쪽이 할 일이다.
2. **하루에 한 판씩.** 같은 날 같은 갈래를 여러 번 저장하면 **마지막 것이 이긴다**
   (덮어쓴다). 장중에 눌러 보는 것과 마감 뒤 자동 저장이 섞이면 마감값이 남는다.

어디에 쌓나
-----------
``data/picklist/{날짜}.{시장}.csv`` — 날짜·시장마다 파일 하나다.
  * 하루치가 80줄 안팎(네 갈래 × 20위 × 두 시장)이라 자비스5처럼 gzip으로 묶지
    않는다. 그냥 CSV라야 저장소에서 눈으로 읽히고 무엇이 바뀌었는지 보인다.
  * 미국과 한국은 장 마감 시각이 달라 따로 저장한다. 한쪽을 쓰는 동안 다른 쪽
    파일을 건드리지 않으므로 클라우드에서 두 작업이 겹쳐도 서로를 지우지 않는다.
  * **저장소가 공개다**(CLAUDE.md 10번). 여기 들어가는 것은 시세·점수뿐이고
    비밀번호·열쇠는 한 글자도 들어가지 않는다.

칸을 늘리거나 줄이면 ``SCHEMA_VERSION``을 올린다. 옛 파일은 없는 칸을 빈칸으로
읽어 들이므로 지우지 않아도 된다.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 계산 결과나 저장 칸을 바꾸면 이 숫자를 올리고, 페이지의 요구 리비전도 올린다
# (CLAUDE.md 11번 규칙).
MODULE_REVISION = 2026081210

SCHEMA_VERSION = 2

_SEOUL = ZoneInfo("Asia/Seoul")
_NEW_YORK = ZoneInfo("America/New_York")

ARCHIVE_DIR = Path(__file__).parent / "data" / "picklist"

MARKETS = ("US", "KR")

# 갈래 이름은 **화면에 쓰는 말 그대로** 둔다(CLAUDE.md 14번·쉬운 말 규칙).
# 파일에는 영문 열쇠를 적고, 화면에 보일 때만 이 표로 바꾼다.
LIST_KINDS = {
    "pullback": "눌림목 찾기",
    "breakout": "상승장 (신고가 눌림매수)",
    "crash": "급락 후 반등장 (낙폭종목)",
    "top7": "매수심사결과 높은 순위 7",
}
KIND_ORDER = ("pullback", "breakout", "crash", "top7")

# 칸 순서가 곧 CSV·엑셀의 칸 순서다. 상하님이 부르신 이름을 그대로 쓴다.
FIELDS = (
    "trade_date",            # 매수 날짜 — 이 목록이 선 날
    "market",                # US · KR
    "list_kind",             # 위 LIST_KINDS의 열쇠
    "rank",                  # 1~20위
    "code",                  # 티커(미국) · 종목코드(한국)
    "name",                  # 종목명
    "themes",                # 소속 테마 (여럿이면 ' · '로 잇는다)
    "score",                 # 그 갈래가 순위를 매긴 점수
    "stock_score",           # 종목 조건점수 (순위 7이 쓰는 점수)
    "price",                 # 신호일 종가 — 신호가 난 그날의 값
    # **실제로 사는 값은 다음 거래일 시가다**(설명서 규칙, 2026-08-09 상하님 지시).
    # 신호가 난 날에는 아직 모르는 값이라 빈칸으로 저장되고, 다음 날 이후에
    # 화면에서 '계산' 단추를 누를 때 그날 시가를 찾아 채운다. 한 번 채워지면
    # 다시는 안 바뀐다 — 과거의 시가는 고정된 사실이다.
    "buy_open",              # 다음 거래일 시가 — 진짜 매수금액
    "change_pct",            # 그날 등락
    "from_high_pct",         # 고점 대비 (상승장에서는 '눌린 하락율')
    "judged_from_high_pct",  # 기준일 낙폭 — 급락 갈래가 갈래를 정하는 값
    "bucket_label",          # 낙폭 갈래 이름
    "wait_days",             # 고점 찍고 며칠 지났나 (상승장)
    "hold_days",             # 며칠 들고 가는 규칙인가
    "together_count",        # 같은 테마에서 함께 걸린 종목 수
    "recent_gain_pct",       # 최근 11일 등락
    "state",                 # 매수 상태
    "origin",                # 순위 7이 어느 갈래에서 데려온 줄인가
    "saved_at",              # 적은 시각
    "schema",                # 칸 판 번호
)

_NUMBER_FIELDS = {
    "rank", "score", "stock_score", "price", "buy_open", "change_pct", "from_high_pct",
    "judged_from_high_pct", "wait_days", "hold_days", "together_count",
    "recent_gain_pct", "schema",
}


# ──────────────────────────────────────────────────────────────────────────
# 값 꺼내기 — 갈래마다 줄 모양이 조금씩 다르다
# ──────────────────────────────────────────────────────────────────────────

def _num(value):
    """숫자로 바꿔 준다. 못 바꾸면 None — **0으로 채우지 않는다.**

    0과 '못 잰 값'은 다른 것이다. 0으로 채우면 나중에 성적을 잴 때 안 잰 자리가
    잰 것처럼 섞인다.
    """
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN·무한대
        return None
    return number


def _first(row: dict, *paths):
    """``("metrics", "current")``처럼 여러 자리를 차례로 뒤져 첫 값을 준다."""
    for path in paths:
        keys = path if isinstance(path, tuple) else (path,)
        cursor = row
        for key in keys:
            if not isinstance(cursor, dict):
                cursor = None
                break
            cursor = cursor.get(key)
        if cursor not in (None, ""):
            return cursor
    return None


def _themes_text(row: dict) -> str:
    """테마 이름을 한 칸에 담는다. 여럿이면 ' · '로 잇는다."""
    for key in ("themes", "sources"):
        value = row.get(key)
        if isinstance(value, (list, tuple)):
            names = [str(item) for item in value if item]
            if names:
                return " · ".join(names)
        elif isinstance(value, str) and value:
            return value
    single = row.get("theme") or row.get("together_theme")
    return str(single) if single else ""


def normalize_row(row: dict, *, market: str, list_kind: str,
                  trade_date: str, rank: int, saved_at: str) -> dict:
    """화면의 한 줄을 창고의 한 줄로 옮긴다. **값은 하나도 고치지 않는다.**

    갈래마다 같은 뜻의 값이 다른 자리에 들어 있어(예: 눌림 점수는 눌림목 표에서는
    ``pullback.score``, 상승장·급락 표에서는 ``score``) 여기서 한 번만 맞춰 둔다.
    없는 값은 빈칸으로 남긴다 — 지어내지 않는다.
    """
    return {
        "trade_date": trade_date,
        "market": str(market).upper(),
        "list_kind": list_kind,
        "rank": int(rank),
        "code": str(_first(row, "ticker", "code") or ""),
        "name": str(_first(row, "name") or ""),
        "themes": _themes_text(row),
        "score": _num(_first(row, "score", ("pullback", "score"))),
        "stock_score": _num(_first(row, "stock_score", ("plan", "score"))),
        "price": _num(_first(row, ("metrics", "current"), "current", "price")),
        # 신호가 난 날에는 다음 거래일 시가를 알 수 없다. 나중에 채운다.
        "buy_open": _num(_first(row, "buy_open")),
        "change_pct": _num(_first(row, ("metrics", "change_pct"), "change_pct")),
        "from_high_pct": _num(_first(
            row, ("metrics", "from_high_pct"), ("pullback", "from_high_pct"),
            "from_high_pct", "now_from_high_pct")),
        "judged_from_high_pct": _num(_first(row, "judged_from_high_pct")),
        "bucket_label": str(_first(row, "bucket_label", "bucket") or ""),
        "wait_days": _num(_first(row, "wait_days", ("pullback", "high52_days_ago"),
                                 "high52_days_ago")),
        "hold_days": _num(_first(row, "hold_days")),
        "together_count": _num(_first(row, "together_count")),
        "recent_gain_pct": _num(_first(row, "recent_gain_pct")),
        "state": str(_first(row, ("plan", "state"), "state") or ""),
        "origin": str(_first(row, "top7_origin", "origin") or ""),
        "saved_at": saved_at,
        "schema": SCHEMA_VERSION,
    }


def rows_from_result(result, *, market: str, list_kind: str,
                     trade_date: str, saved_at: str | None = None,
                     limit: int = 20) -> list[dict]:
    """찾기 결과(dict)를 창고 줄들로 바꾼다. 실패한 결과는 빈 목록이다.

    순위는 줄에 적힌 순위(``pullback_rank``·``pick_rank``)를 먼저 쓰고, 없으면
    목록에 담긴 차례를 쓴다 — 화면에 보이던 번호가 그대로 남아야 한다.
    """
    if list_kind not in LIST_KINDS:
        raise ValueError(f"모르는 갈래입니다: {list_kind}")
    if not isinstance(result, dict) or not result.get("ok"):
        return []
    saved_at = saved_at or datetime.now(_SEOUL).isoformat(timespec="seconds")
    # **순위 7은 자기 번호(pick_rank)를 먼저 본다.** 순위 7의 줄은 눌림목 결과에서
    # 데려온 것이라 눌림목 때의 번호(pullback_rank)를 그대로 달고 있다. 그것을 먼저
    # 보면 순위 7 표에 같은 번호가 두 번 찍힌다(2026-08-09 실제 자료에서 2위가 둘).
    rank_keys = (("pick_rank", "rank", "pullback_rank") if list_kind == "top7"
                 else ("pullback_rank", "pick_rank", "rank"))
    out = []
    for index, row in enumerate(list(result.get("rows") or [])[: max(0, int(limit))], 1):
        if not isinstance(row, dict):
            continue
        rank = _num(_first(row, *rank_keys)) or index
        out.append(normalize_row(
            row, market=market, list_kind=list_kind,
            trade_date=trade_date, rank=int(rank), saved_at=saved_at,
        ))
    return out


# ──────────────────────────────────────────────────────────────────────────
# 파일 읽고 쓰기
# ──────────────────────────────────────────────────────────────────────────

def trade_date_for(market: str, now: datetime | None = None) -> str:
    """그 시장의 '오늘'. 미국은 뉴욕 날짜, 한국은 서울 날짜다.

    한국시각으로 새벽 6시에 미국장이 끝나면 서울 날짜는 이미 다음 날이다. 서울
    날짜로 적으면 목록이 하루 뒤로 밀려 붙는다.
    """
    stamp = now or datetime.now(_SEOUL)
    zone = _NEW_YORK if str(market).upper() == "US" else _SEOUL
    return stamp.astimezone(zone).date().isoformat()


def archive_path(trade_date: str, market: str, out_dir: Path | str | None = None) -> Path:
    base = Path(out_dir) if out_dir else ARCHIVE_DIR
    return base / f"{trade_date}.{str(market).upper()}.csv"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _restore_types(row: dict) -> dict:
    """CSV는 전부 글자로 읽힌다. 숫자 칸만 숫자로 되돌린다."""
    out = {field: row.get(field, "") for field in FIELDS}
    for field in _NUMBER_FIELDS:
        out[field] = _num(out.get(field))
    for field in FIELDS:
        if field not in _NUMBER_FIELDS:
            out[field] = str(out.get(field) or "")
    return out


def save_rows(rows, *, trade_date: str, market: str,
              out_dir: Path | str | None = None) -> Path | None:
    """한 갈래(또는 여러 갈래)의 줄을 그 날짜 파일에 넣는다.

    **같은 날·같은 갈래는 덮어쓴다.** 장중에 눌러 본 것과 마감 뒤 자동 저장이
    섞이면 마지막(=마감) 것이 남아야 한다. 다른 갈래는 건드리지 않는다.
    빈 목록을 주면 아무것도 하지 않고 None을 준다 — 조회에 실패한 날 멀쩡한
    어제 자료를 빈 파일로 덮는 사고를 막는다.
    """
    rows = [dict(row) for row in (rows or [])]
    if not rows:
        return None
    market = str(market).upper()
    path = archive_path(trade_date, market, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    replacing = {str(row.get("list_kind") or "") for row in rows}
    kept = [
        row for row in _read_csv(path)
        if str(row.get("list_kind") or "") not in replacing
    ]
    merged = kept + rows
    merged.sort(key=lambda row: (
        KIND_ORDER.index(str(row.get("list_kind")))
        if str(row.get("list_kind")) in KIND_ORDER else len(KIND_ORDER),
        _num(row.get("rank")) or 0,
    ))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in merged:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    return path


def available_dates(market: str | None = None,
                    out_dir: Path | str | None = None) -> list[str]:
    """저장된 날짜를 **새것부터** 준다. 폴더가 없으면 빈 목록."""
    base = Path(out_dir) if out_dir else ARCHIVE_DIR
    if not base.exists():
        return []
    wanted = str(market).upper() if market else None
    dates = set()
    for path in base.glob("*.csv"):
        parts = path.name.split(".")
        if len(parts) != 3:
            continue
        day, tag, _ = parts
        if wanted and tag.upper() != wanted:
            continue
        dates.add(day)
    return sorted(dates, reverse=True)


def load_rows(trade_date: str, market: str,
              out_dir: Path | str | None = None) -> list[dict]:
    """그 날짜·그 시장의 줄 전부. 없으면 빈 목록."""
    rows = [_restore_types(row) for row in _read_csv(archive_path(trade_date, market, out_dir))]
    rows.sort(key=lambda row: (
        KIND_ORDER.index(str(row.get("list_kind")))
        if str(row.get("list_kind")) in KIND_ORDER else len(KIND_ORDER),
        row.get("rank") or 0,
    ))
    return rows


def saved_kinds(trade_date: str, market: str,
                out_dir: Path | str | None = None) -> set[str]:
    """그날 이미 저장된 갈래 이름들. 하루 한 번만 적으려는 쪽이 물어본다."""
    return {
        str(row.get("list_kind") or "")
        for row in _read_csv(archive_path(trade_date, market, out_dir))
    }


# ──────────────────────────────────────────────────────────────────────────
# 내려받기
# ──────────────────────────────────────────────────────────────────────────

# 화면에서 그때그때 재는 칸. 파일에는 안 들어 있지만 **내려받을 때는 같이 나간다**
# (2026-08-09 상하님 지시) — 엑셀로 받아 놓고 손익을 못 보면 받을 값이 없다.
COMPUTED_FIELDS = ("now_price", "profit_pct", "days_since")


def download_fields(rows) -> tuple:
    """내려받을 칸 목록. 수익률이 계산된 줄이 있으면 그 칸도 붙인다."""
    extras = tuple(
        field for field in COMPUTED_FIELDS
        if any(row.get(field) not in (None, "") for row in rows)
    )
    return FIELDS + extras


def _display_rows(rows) -> list[dict]:
    """엑셀·CSV에 넣을 때는 갈래를 화면에 쓰는 말로 바꿔 적는다."""
    out = []
    for row in rows:
        item = dict(row)
        item["list_kind"] = LIST_KINDS.get(str(row.get("list_kind")), str(row.get("list_kind") or ""))
        out.append(item)
    return out


def to_csv_bytes(rows) -> bytes:
    """엑셀이 바로 여는 CSV. **BOM을 붙인다** — 없으면 한글이 깨져 열린다."""
    fields = download_fields(rows)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in _display_rows(rows):
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def to_excel_bytes(rows):
    """엑셀 파일(.xlsx) 알맹이. openpyxl이 없으면 None — 부르는 쪽이 CSV로 돌린다.

    온라인에 openpyxl이 안 깔린 판이 있어도 화면이 죽으면 안 된다(쿠키 로그인과
    같은 원칙). 그래서 없으면 조용히 None을 주고 CSV 단추만 남긴다.
    """
    try:
        import pandas as pd
    except Exception:
        return None
    try:
        frame = pd.DataFrame(_display_rows(rows), columns=list(download_fields(rows)))
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="목록")
        return buffer.getvalue()
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# 그 뒤로 얼마나 됐나 — 저장된 값은 건드리지 않고 견주기만 한다
# ──────────────────────────────────────────────────────────────────────────

def profit_pct(buy_price, now_price):
    """산 값 대비 지금 값이 몇 %인가. 못 재면 None.

    **저장된 값을 고치지 않는다.** 매수금액은 그날 찍힌 그대로 두고, 지금 값과
    견주기만 한다. 그래야 나중에 다시 봐도 그날 목록이 그대로다.
    0으로 나누는 자리(값이 0이거나 없는 종목)는 None으로 둔다 — 0%로 적으면
    '본전'이라는 뜻이 돼서 안 잰 것과 구별되지 않는다.
    """
    buy, now = _num(buy_price), _num(now_price)
    if buy is None or now is None or buy <= 0:
        return None
    return (now / buy - 1.0) * 100.0


def days_since(trade_date, today=None):
    """매수일에서 며칠이 지났나. 못 세면 None.

    **수익률은 다음 날부터 뜻이 생긴다.** 매수일 당일은 산 값과 지금 값이 같은
    자리라 0%가 나오는데, 그게 '본전'이 아니라 '아직 하루도 안 지났다'는 뜻이다.
    그 둘을 화면에서 가르려고 지난 날수를 같이 센다.
    달력 날수다 — 거래일이 아니다. 주말이 끼면 그만큼 더 세어진다.
    """
    try:
        start = date.fromisoformat(str(trade_date))
    except (TypeError, ValueError):
        return None
    end = today or datetime.now(_SEOUL).date()
    if isinstance(end, datetime):
        end = end.date()
    return (end - start).days


def fetch_buy_opens(market: str, rows) -> dict:
    """줄마다 **다음 거래일 시가**를 찾아 온다. 못 찾으면 목록에서 빠진다.

    설명서의 규칙이 "종가를 확인하고 다음 거래일 시가에 산다"이므로, 실제로 살 수
    있었던 값은 신호일 다음 거래일의 시가다(2026-08-09 상하님 지시).

    **화면(picklist_ui)과 클라우드 수집기(picklist_collector)가 같이 쓴다.**
    2026-08-12까지는 이 함수가 화면 쪽에만 있어서 상하님이 단추를 눌러야만 채워졌고,
    온라인에서 눌러 채운 값은 저장소에 안 올라가 앱이 한 번 쉬면 사라졌다. 그래서
    저장된 232줄 전부 매수금액이 빈칸이었다 — 수익률이 영원히 안 나왔다.
    여기(streamlit을 안 쓰는 창고)로 옮겨 수집기도 부를 수 있게 한다.

    `price_data.get_ohlc_history_for_chart`는 **차트 전용 읽기 함수**다 — 점수 계산과
    무관하고, 조회에 실패하면 예외 대신 None을 준다. (price_data는 고치지 않는다.
    읽기만 한다 — CLAUDE.md 2번.)

    주말·공휴일이 끼면 다음 거래일이 며칠 뒤일 수 있어 2주치를 받아 그중
    **신호일보다 뒤에 있는 첫 거래일**의 시가를 쓴다.
    """
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    import price_data

    wanted = {}
    for row in rows:
        code = str(row.get("code") or "")
        if not code or _num(row.get("buy_open")) is not None:
            continue     # 이미 채워진 줄은 다시 찾지 않는다
        wanted[code] = str(row.get("trade_date") or "")
    if not wanted:
        return {}

    def _one(item):
        code, day = item
        try:
            start = date.fromisoformat(day)
        except (TypeError, ValueError):
            return code, None
        try:
            frame = price_data.get_ohlc_history_for_chart(
                code, start.isoformat(), (start + timedelta(days=16)).isoformat())
        except Exception:
            return code, None
        if frame is None or getattr(frame, "empty", True) or "Open" not in frame:
            return code, None
        try:
            for stamp, bar in frame.iterrows():
                if getattr(stamp, "date", lambda: stamp)() > start:
                    value = float(bar["Open"])
                    return code, (value if value == value and value > 0 else None)
        except Exception:
            return code, None
        return code, None      # 아직 다음 거래일이 오지 않았다

    out = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for code, value in pool.map(_one, wanted.items()):
            if value is not None:
                out[code] = value
    return out


def backfill_buy_opens(market: str, *, out_dir=None, days: int = 10) -> dict:
    """지난 며칠치 저장 목록에서 **빈 매수금액을 채운다** (2026-08-12).

    신호가 난 날에는 다음 거래일 시가를 알 수 없어 빈칸으로 저장된다. 그것을
    **다음 날 이후에 누군가 채워 넣어야** 수익률이 나오는데, 그 일을 아무도 하지
    않아 232줄 전부 빈칸이었다. 이제 클라우드 수집기가 새 목록을 찍을 때 함께 돈다.

    **한 번 채워진 값은 다시 안 건드린다** — 과거의 시가는 고정된 사실이다.
    조회에 실패한 날은 그냥 넘어간다. 다음 날 다시 시도한다.

    돌려주는 값: {날짜: 채운 줄 수}
    """
    filled: dict[str, int] = {}
    for trade_date in available_dates(market, out_dir)[: max(0, int(days))]:
        rows = load_rows(trade_date, market, out_dir)
        missing = [row for row in rows if _num(row.get("buy_open")) is None]
        if not missing:
            continue
        try:
            opens = fetch_buy_opens(market, missing)
        except Exception:
            continue          # 하루가 막혀도 나머지 날은 계속한다
        if not opens:
            continue
        merged = set_buy_opens(rows, opens)
        if save_rows(merged, trade_date=trade_date, market=market, out_dir=out_dir):
            filled[trade_date] = sum(
                1 for row in merged if _num(row.get("buy_open")) is not None
            ) - (len(rows) - len(missing))
    return filled


def set_buy_opens(rows, opens) -> list[dict]:
    """다음 거래일 시가를 채워 준다. **이미 채워진 줄은 건드리지 않는다.**

    과거의 시가는 고정된 사실이다. 한 번 적힌 값을 다시 덮으면 자료원이 바뀔 때
    옛 손익률이 조용히 달라진다.
    """
    opens = opens or {}
    out = []
    for row in rows:
        item = dict(row)
        if _num(item.get("buy_open")) is None:
            item["buy_open"] = _num(opens.get(str(row.get("code") or "")))
        out.append(item)
    return out


def with_profit(rows, prices, *, today=None) -> list[dict]:
    """줄마다 '지금 값'·'수익률'·'지난 날수'를 붙여 돌려준다. 원본은 안 바꾼다.

    **무엇을 산 값으로 보나 — 다음 거래일 시가다.** 설명서의 규칙이 "종가를
    확인하고 다음 거래일 시가에 산다"이므로, 신호일 종가가 아니라 그 다음 날
    시가와 견뎌야 실제로 살 수 있었던 값이 된다(2026-08-09 상하님 지시).
    시가를 아직 못 채운 줄은 **수익률을 내지 않는다** — 종가로 대신 재면 반나절
    이른 값이라 실제보다 좋아 보이거나 나빠 보인다.

    prices : {종목코드: 지금 값}. 목록에 없는 종목은 빈칸으로 남는다
             (상장폐지·조회 실패 — 지어내지 않는다).
    """
    prices = prices or {}
    out = []
    for row in rows:
        item = dict(row)
        now = _num(prices.get(str(row.get("code") or "")))
        buy = _num(item.get("buy_open"))
        item["now_price"] = now
        item["profit_pct"] = profit_pct(buy, now)
        item["days_since"] = days_since(row.get("trade_date"), today)
        out.append(item)
    return out


def summarize(rows) -> str:
    """'눌림목 8 · 상승장 20' 처럼 그날 몇 줄이 남았는지 한 줄로."""
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("list_kind") or "")
        counts[key] = counts.get(key, 0) + 1
    parts = [
        f"{LIST_KINDS.get(kind, kind)} {counts[kind]}"
        for kind in KIND_ORDER if kind in counts
    ]
    return " · ".join(parts)


def to_json(rows) -> str:
    """사람이 읽어 보라고 두는 것이 아니라, 시험이 모양을 굳히는 데 쓴다."""
    return json.dumps(list(rows), ensure_ascii=False, sort_keys=True)
