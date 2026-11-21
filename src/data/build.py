"""取得した生データから data.json の各セクションを組み立てる純粋関数群。"""

from __future__ import annotations

import re
from collections import Counter

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
    """「株式会社」などを外した読み上げ・表示用の社名。"""
    cleaned = re.sub(r"(株式会社|有限会社|合同会社|\(株\)|（株）)", "", name or "")
    return re.sub(r"[\s　]+", "", cleaned) or (name or "")


def sec_code4(code: str | None) -> str | None:
    """EDINET の証券コード (5桁、末尾は予備) を 4 桁にする。"""
    code = (code or "").strip()
    return code[:4] if len(code) >= 4 else None


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


def build_large_holdings(docs: list[dict], codes: dict[str, dict], max_items: int) -> dict:
    """大量保有報告書・変更報告書。一覧は発行会社が上場会社のものだけ。"""
    rows = [d for d in docs if d["docTypeCode"] == LARGE_HOLDING]
    items = []
    for d in rows:
        issuer = _company(codes, d.get("issuerEdinetCode"))
        if issuer is None:
            continue
        kind = "変更報告書" if "変更報告書" in (d.get("docDescription") or "") else "大量保有報告書"
        items.append({"issuer": issuer["name"], "sec_code": issuer["sec_code"], "kind": kind,
                      "filer": short_name(d.get("filerName") or ""), "submitted_at": submitted_time(d)})
    # 新規の大量保有報告書を先に、同じ種類の中では提出の早い順
    items = sorted(items, key=lambda x: (x["kind"] != "大量保有報告書", x["submitted_at"]))
    return {
        "count": len(rows),
        "listed_new_count": sum(1 for x in items if x["kind"] == "大量保有報告書"),
        "listed_change_count": sum(1 for x in items if x["kind"] == "変更報告書"),
        "listed_count": len(items),
        "items": items[:max_items],
    }


def build_extraordinary(docs: list[dict], max_items: int) -> dict:
    """臨時報告書。一覧は提出者が上場会社で、提出事由がわかるものだけ。"""
    rows = [d for d in docs if d["docTypeCode"] == EXTRAORDINARY]
    items = []
    for d in rows:
        code, labels = sec_code4(d.get("secCode")), reason_labels(d.get("currentReportReason"))
        if code and labels:
            items.append({"filer": short_name(d.get("filerName") or ""), "sec_code": code, "reasons": labels,
                          "submitted_at": submitted_time(d)})
    return {"count": len(rows), "listed_count": sum(1 for d in rows if sec_code4(d.get("secCode"))),
            "items": sorted(items, key=lambda x: x["submitted_at"])[:max_items]}


def build_tender_offers(docs: list[dict], codes: dict[str, dict]) -> dict:
    rows = [d for d in docs if d["docTypeCode"] == TENDER_OFFER]
    items = []
    for d in rows:
        target = _company(codes, d.get("subjectEdinetCode"))
        items.append({"filer": short_name(d.get("filerName") or ""),
                      "target": target["name"] if target else None,
                      "sec_code": target["sec_code"] if target else None})
    return {"count": len(rows), "items": items}


def build_filings(docs: list[dict], codes: dict[str, dict], date: str, top_types: int, max_items: int) -> dict:
    # 一覧には、その日に取下げや修正の操作があった別の日の書類も混ざるので、提出日でも絞る
    active = [d for d in active_documents(docs) if (d.get("submitDateTime") or "").startswith(date)]
    return {
        "date": date,
        "total": len(active),
        "by_type": count_by_type(active, top_types),
        "large_holdings": build_large_holdings(active, codes, max_items),
        "extraordinary": build_extraordinary(active, max_items),
        "tender_offers": build_tender_offers(active, codes),
        "buybacks": {"count": sum(1 for d in active if d["docTypeCode"] == BUYBACK)},
    }


def fx_direction(change: float) -> str:
    return "円安" if change > 0 else "円高" if change < 0 else "横ばい"


def build_usdjpy(rows: list[dict], history_days: int) -> dict:
    """rows は [{date, close}] の古い順。最新の日と、その前の日を比べる。"""
    if len(rows) < 2:
        raise ValueError("ドル円の前日比を計算するには2日分以上のデータが必要です")
    last, prev = rows[-1], rows[-2]
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


def build_jgb(rows: list[dict], tenors: list[str]) -> dict:
    """rows は [{date, yields}] の古い順。年限ごとの利回りと前日からの変化 (ポイント)。"""
    if len(rows) < 2:
        raise ValueError("国債金利の前日比を計算するには2日分以上のデータが必要です")
    last, prev = rows[-1], rows[-2]
    yields = []
    for tenor in tenors:
        if tenor not in last["yields"] or tenor not in prev["yields"]:
            raise ValueError(f"国債金利に {tenor} のデータがありません ({last['date']})")
        now, before = last["yields"][tenor], prev["yields"][tenor]
        yields.append({"tenor": tenor, "yield_pct": now, "prev_pct": before, "change_pt": round(now - before, 3)})
    return {"date": last["date"], "prev_date": prev["date"], "yields": yields}
