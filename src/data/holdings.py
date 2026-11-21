"""大量保有報告書・変更報告書の本文 (EDINET の CSV) から保有割合を読み、動画で取り上げるものを選ぶ純粋関数群。"""

from __future__ import annotations

import re

TOTAL_CONTEXT = "FilingDateInstant"  # 提出者と共同保有者の合計。提出者ごとの値は別のコンテキストに入る
RATIO = "jplvh_cor:HoldingRatioOfShareCertificatesEtc"
PREV_RATIO = "jplvh_cor:HoldingRatioOfShareCertificatesEtcPerLastReport"
PURPOSE = "jplvh_cor:PurposeOfHolding"
OBLIGATION_DATE = "jplvh_cor:DateWhenFilingRequirementAroseCoverPage"
PURPOSE_MAX = 60
NEW, UP, DOWN, FLAT = "新規", "増加", "減少", "変わらず"
DIRECTIONS = (NEW, UP, DOWN)


def _pct(value: str | None) -> float | None:
    """「0.0673」→ 6.73。空欄や「－」は None。"""
    try:
        return round(float(value) * 100, 2)
    except (TypeError, ValueError):
        return None


def _first(rows: list[dict], element: str, context: str | None = None) -> str | None:
    for r in rows:
        if r["element"] == element and (context is None or r["context"] == context):
            value = (r["value"] or "").strip()
            if value and value != "－":
                return value
    return None


def _total(rows: list[dict], element: str) -> str | None:
    """合計の値。提出者が1人だけの報告書は合計の欄がなく、提出者ごとの欄にしか値がないので、それを使う。"""
    total = _first(rows, element, TOTAL_CONTEXT)
    if total is not None:
        return total
    contexts = {r["context"] for r in rows if r["element"] == element}
    return _first(rows, element) if len(contexts) == 1 else None


def parse_holding(rows: list[dict]) -> dict | None:
    """保有割合 (%)・前回の保有割合 (%)・保有目的・報告義務発生日。保有割合が読めなければ None。"""
    ratio = _pct(_total(rows, RATIO))
    if ratio is None:
        return None
    purpose = re.sub(r"\s+", "", _first(rows, PURPOSE) or "")
    date = _first(rows, OBLIGATION_DATE) or ""
    return {
        "ratio_pct": ratio,
        "prev_ratio_pct": _pct(_total(rows, PREV_RATIO)),
        "purpose": purpose[:PURPOSE_MAX] or None,
        "obligation_date": date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else None,
    }


def with_detail(item: dict, detail: dict | None) -> dict:
    """一覧の1件に保有割合を足す。前回の割合がなければ新規、あれば差 (ポイント) と向きを入れる。"""
    if detail is None:
        return {**item, "ratio_pct": None, "prev_ratio_pct": None, "change_pt": None, "direction": None,
                "purpose": None, "obligation_date": None}
    prev = detail["prev_ratio_pct"]
    if item["kind"] == "大量保有報告書":
        change, direction, prev = None, NEW, None
    elif prev is None:
        change, direction = None, None  # 変更報告書なのに前回の割合が読めない。新規とは呼ばない
    else:
        change = round(detail["ratio_pct"] - prev, 2)
        direction = UP if change > 0 else DOWN if change < 0 else FLAT
    return {**item, **detail, "prev_ratio_pct": prev, "change_pt": change, "direction": direction}


def latest_per_pair(items: list[dict]) -> list[dict]:
    """同じ提出者・発行会社の報告が複数あれば、いちばん新しい1件だけを残す。"""
    latest: dict[tuple, dict] = {}
    for x in sorted(items, key=lambda x: (x["date"], x["submitted_at"])):
        latest[(x["filer"], x["sec_code"])] = x
    return list(latest.values())


def _rank_key(x: dict) -> float:
    return -(x["ratio_pct"] if x["direction"] == NEW else abs(x["change_pt"]))


def notable(items: list[dict], max_items: int) -> list[dict]:
    """新規は保有割合の大きい順、増加・減少は動いた幅の大きい順に並べ、3種類から順番に取って max_items 件にする。"""
    latest = latest_per_pair(items)
    ranked = {d: sorted((x for x in latest if x["direction"] == d), key=_rank_key) for d in DIRECTIONS}
    picked: list[dict] = []
    depth = 0
    while len(picked) < max_items and any(depth < len(ranked[d]) for d in DIRECTIONS):
        picked = picked + [ranked[d][depth] for d in DIRECTIONS if depth < len(ranked[d])]
        depth += 1
    # 向きがわからないもの・変化のないものは後ろに (新規を先に、提出の早い順)
    rest = sorted((x for x in latest if x["direction"] not in DIRECTIONS),
                  key=lambda x: (x["kind"] != "大量保有報告書", x["date"], x["submitted_at"]))
    return (picked + rest)[:max_items]
