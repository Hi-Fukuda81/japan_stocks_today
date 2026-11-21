"""取得した生データから data.json の各セクションを組み立てる純粋関数群。"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from src.data import holdings

# EDINET の書類種別コード (docTypeCode)
DOC_TYPES = {
    "010": "有価証券通知書", "020": "変更通知書", "030": "有価証券届出書", "040": "訂正有価証券届出書",
    "050": "届出の取下げ願い", "060": "発行登録通知書", "070": "変更通知書", "080": "発行登録書",
    "090": "訂正発行登録書", "100": "発行登録追補書類", "110": "発行登録取下届出書", "120": "有価証券報告書",
    "130": "訂正有価証券報告書", "135": "確認書", "136": "訂正確認書", "140": "四半期報告書",
    "150": "訂正四半期報告書", "160": "半期報告書", "170": "訂正半期報告書", "180": "臨時報告書",
    "190": "訂正臨時報告書", "200": "親会社等状況報告書", "210": "訂正親会社等状況報告書",
    "220": "自己株券買付状況報告書", "230": "訂正自己株券買付状況報告書", "235": "内部統制報告書",
    "236": "訂正内部統制報告書", "240": "公開買付届出書", "250": "訂正公開買付届出書",
    "260": "公開買付撤回届出書", "270": "公開買付報告書", "280": "訂正公開買付報告書", "290": "意見表明報告書",
    "300": "訂正意見表明報告書", "310": "対質問回答報告書", "320": "訂正対質問回答報告書",
    "330": "別途買付け禁止の特例を受けるための申出書", "340": "訂正別途買付け禁止の特例を受けるための申出書",
    "350": "大量保有報告書", "360": "訂正大量保有報告書", "370": "基準日の届出書", "380": "変更の届出書",
}
LARGE_HOLDING, EXTRAORDINARY, BUYBACK, TENDER_OFFER = "350", "180", "220", "240"

# 臨時報告書の提出事由 (企業内容等の開示に関する内閣府令 第19条第2項の号)。確実なものだけ載せる
REPORT_REASONS = {
    "2の2": "新株予約権の発行", "3": "親会社または特定子会社の異動", "4": "主要株主の異動",
    "6の2": "株式交換", "7の3": "吸収合併", "8の2": "子会社取得", "9": "代表取締役の異動",
    "9の2": "株主総会の議決権行使結果", "9の4": "監査法人の異動",
    "12": "財政状態や経営成績に著しい影響を与える事象", "19": "連結ベースで著しい影響を与える事象",
}
REASON_ITEM = re.compile(r"第(\d+)号(?:の(\d+))?")
# 制度上の基準値 (台本で制度を説明するときに使う。数値照合の対象にするため data.json に入れる)
REFERENCE = {"large_holding_threshold_pct": 5, "change_report_threshold_pct": 1}


def short_name(name: str) -> str:
    """「株式会社」などを外した読み上げ・表示用の社名。全角の英数字は半角にし、英単語の間の空白だけ残す。"""
    text = unicodedata.normalize("NFKC", name or "")
    cleaned = re.sub(r"(株式会社|有限会社|合同会社|\(株\))", "", text).strip()
    cleaned = re.sub(r"(?<![!-~])\s+|\s+(?![!-~])", "", cleaned)
    return re.sub(r"\s+", " ", cleaned) or (name or "")


def sec_code4(code: str | None) -> str | None:
    """EDINET の証券コード (5桁、末尾は予備) を 4 桁にする。"""
    code = (code or "").strip()
    return code[:4] if len(code) >= 4 else None


def submitted_date(doc: dict) -> str:
    return (doc.get("submitDateTime") or "")[:10]


def submitted_time(doc: dict) -> str:
    return (doc.get("submitDateTime") or "")[11:16]


def active_documents(docs: list[dict]) -> list[dict]:
    """取下げ・不開示を除いた、種別のわかる書類。"""
    return [d for d in docs if d.get("docTypeCode") and str(d.get("withdrawalStatus", "0")) == "0"
            and str(d.get("disclosureStatus", "0")) == "0"]


def count_by_type(docs: list[dict], top: int) -> list[dict]:
    counts = Counter(d["docTypeCode"] for d in docs)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"code": code, "name": DOC_TYPES.get(code, f"その他 ({code})"), "count": n} for code, n in ranked[:top]]


def reason_labels(reason: str | None) -> list[str]:
    labels = []
    for m in REASON_ITEM.finditer(reason or ""):
        key = m.group(1) + (f"の{m.group(2)}" if m.group(2) else "")
        label = REPORT_REASONS.get(key)
        if label and label not in labels:
            labels.append(label)
    return labels


def _company(codes: dict[str, dict], edinet_code: str | None) -> dict | None:
    """上場会社なら {name, sec_code}。上場していない、または不明なら None。"""
    row = codes.get(edinet_code or "")
    code = sec_code4(row["sec_code"]) if row else None
    return {"name": short_name(row["name"]), "sec_code": code} if code else None


def _listed_holdings(docs: list[dict], codes: dict[str, dict]) -> list[dict]:
    """発行会社が上場会社の大量保有報告書・変更報告書 (訂正報告書は含まない)。"""
    items = []
    for d in docs:
        issuer = _company(codes, d.get("issuerEdinetCode")) if d["docTypeCode"] == LARGE_HOLDING else None
        if issuer is None:
            continue
        kind = "変更報告書" if "変更報告書" in (d.get("docDescription") or "") else "大量保有報告書"
        items.append({"issuer": issuer["name"], "sec_code": issuer["sec_code"], "kind": kind,
                      "filer": short_name(d.get("filerName") or ""), "date": submitted_date(d),
                      "submitted_at": submitted_time(d), "doc_id": d.get("docID")})
    return items


def holding_doc_ids(docs: list[dict], codes: dict[str, dict], days: list[str]) -> list[str]:
    """保有割合を読むために本文を取りに行く書類の ID。"""
    active = [d for d in active_documents(docs) if submitted_date(d) in days]
    return [x["doc_id"] for x in _listed_holdings(active, codes) if x["doc_id"]]


def build_large_holdings(docs: list[dict], codes: dict[str, dict], max_items: int,
                         details: dict[str, dict] | None = None) -> dict:
    """大量保有報告書・変更報告書。一覧は発行会社が上場会社のものだけ。

    details は {書類ID: holdings.parse_holding の結果}。一覧は保有割合の動きが大きいものを選ぶ。
    """
    rows = [d for d in docs if d["docTypeCode"] == LARGE_HOLDING]
    details = details or {}
    items = [holdings.with_detail(x, details.get(x["doc_id"])) for x in _listed_holdings(docs, codes)]
    per_issuer = Counter((x["issuer"], x["sec_code"]) for x in items)
    # 期間中に2件以上の報告が出た発行会社 (週間まとめで使う)
    top_issuers = [{"issuer": name, "sec_code": code, "count": n}
                   for (name, code), n in sorted(per_issuer.items(), key=lambda kv: (-kv[1], kv[0][1])) if n >= 2]
    return {
        "top_issuers": top_issuers[:max_items],
        "count": len(rows),
        "listed_new_count": sum(1 for x in items if x["kind"] == "大量保有報告書"),
        "listed_change_count": sum(1 for x in items if x["kind"] == "変更報告書"),
        "listed_count": len(items),
        "detail_count": sum(1 for x in items if x["ratio_pct"] is not None),
        "items": holdings.notable(items, max_items),
    }


# 一覧で先に出す提出事由 (会社の支配や経営に関わるものを優先する)
REASON_PRIORITY = ("代表取締役の異動", "主要株主の異動", "親会社または特定子会社の異動", "監査法人の異動",
                   "子会社取得", "吸収合併", "株式交換")


def _reason_rank(labels: list[str]) -> int:
    ranks = [REASON_PRIORITY.index(x) for x in labels if x in REASON_PRIORITY]
    return min(ranks) if ranks else len(REASON_PRIORITY)


def build_extraordinary(docs: list[dict], max_items: int) -> dict:
    """臨時報告書。一覧は提出者が上場会社で、提出事由がわかるものだけ。支配や経営に関わる事由を先に出す。"""
    rows = [d for d in docs if d["docTypeCode"] == EXTRAORDINARY]
    items = []
    for d in rows:
        code, labels = sec_code4(d.get("secCode")), reason_labels(d.get("currentReportReason"))
        if code and labels:
            items.append({"filer": short_name(d.get("filerName") or ""), "sec_code": code, "reasons": labels,
                          "date": submitted_date(d), "submitted_at": submitted_time(d)})
    by_reason = Counter(label for x in items for label in x["reasons"])
    ranked = sorted(items, key=lambda x: (_reason_rank(x["reasons"]), x["date"], x["submitted_at"]))
    seen: set[str] = set()
    unique = [x for x in ranked if not (x["sec_code"] in seen or seen.add(x["sec_code"]))]  # 1社1件
    return {"count": len(rows), "listed_count": sum(1 for d in rows if sec_code4(d.get("secCode"))),
            "by_reason": [{"reason": r, "count": n} for r, n in sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))],
            "items": unique[:max_items]}


def build_tender_offers(docs: list[dict], codes: dict[str, dict]) -> dict:
    """公開買付届出書。買付者と対象会社が同じなら自己株式の公開買付。"""
    rows = [d for d in docs if d["docTypeCode"] == TENDER_OFFER]
    items = []
    for d in rows:
        target = _company(codes, d.get("subjectEdinetCode"))
        filer = short_name(d.get("filerName") or "")
        items.append({"filer": filer, "date": submitted_date(d),
                      "target": target["name"] if target else None,
                      "sec_code": target["sec_code"] if target else None,
                      "self_tender": bool(target) and (d.get("edinetCode") == d.get("subjectEdinetCode")
                                                       or filer == target["name"])})
    self_count = sum(1 for x in items if x["self_tender"])
    return {"count": len(rows), "self_count": self_count, "other_count": len(items) - self_count, "items": items}


def build_filings(docs: list[dict], codes: dict[str, dict], days: list[str], top_types: int,
                  max_items: int, holding_details: dict[str, dict] | None = None) -> dict:
    """days は対象の提出日 (夕方便は1日、週間まとめはその週の営業日)。"""
    # 一覧には、その日に取下げや修正の操作があった別の日の書類も混ざるので、提出日でも絞る
    active = [d for d in active_documents(docs) if submitted_date(d) in days]
    per_day = Counter(submitted_date(d) for d in active)
    return {
        "date": days[-1],
        "total": len(active),
        "daily": [{"date": day, "total": per_day.get(day, 0)} for day in days],
        "by_type": count_by_type(active, top_types),
        "large_holdings": build_large_holdings(active, codes, max_items, holding_details),
        "extraordinary": build_extraordinary(active, max_items),
        "tender_offers": build_tender_offers(active, codes),
        "buybacks": {"count": sum(1 for d in active if d["docTypeCode"] == BUYBACK)},
    }


def fx_direction(change: float) -> str:
    return "円安" if change > 0 else "円高" if change < 0 else "横ばい"


def _last_and_base(rows: list[dict], base_before: str | None, label: str) -> tuple[dict, dict]:
    """(最新の行, 比べる相手の行)。base_before があれば、その日より前でいちばん新しい行と比べる (前週末比)。"""
    if not rows:
        raise ValueError(f"{label}のデータがありません")
    last = rows[-1]
    earlier = [r for r in rows[:-1] if base_before is None or r["date"] < base_before]
    if not earlier or (base_before and last["date"] < base_before):
        raise ValueError(f"{label}の変化を計算するためのデータが足りません ({last['date']} 時点)")
    return last, earlier[-1]


def build_usdjpy(rows: list[dict], history_days: int, base_before: str | None = None) -> dict:
    """rows は [{date, close}] の古い順。最新の日と、その前の日 (週間なら前週末) を比べる。"""
    last, prev = _last_and_base(rows, base_before, "ドル円")
    change = round(last["close"] - prev["close"], 2)
    history = [{"date": r["date"], "close": round(r["close"], 2)} for r in rows[-history_days:]]
    closes = [h["close"] for h in history]
    return {
        "date": last["date"], "prev_date": prev["date"],
        "close": round(last["close"], 2), "prev_close": round(prev["close"], 2),
        "change": change, "change_pct": round(change / prev["close"] * 100, 2),
        "direction": fx_direction(change),
        "period_high": max(closes), "period_low": min(closes), "history": history,
    }


def build_jgb(rows: list[dict], tenors: list[str], base_before: str | None = None) -> dict:
    """rows は [{date, yields}] の古い順。年限ごとの利回りと、前日 (週間なら前週末) からの変化 (ポイント)。"""
    last, prev = _last_and_base(rows, base_before, "国債金利")
    yields = []
    for tenor in tenors:
        if tenor not in last["yields"] or tenor not in prev["yields"]:
            raise ValueError(f"国債金利に {tenor} のデータがありません ({last['date']})")
        now, before = last["yields"][tenor], prev["yields"][tenor]
        yields.append({"tenor": tenor, "yield_pct": now, "prev_pct": before, "change_pt": round(now - before, 3)})
    return {"date": last["date"], "prev_date": prev["date"], "yields": yields}
