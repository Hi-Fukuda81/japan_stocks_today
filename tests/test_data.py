import io
import json
import os
import time
import zipfile
from types import SimpleNamespace

import pytest
import requests

from src.config import DayPaths
from src.data import boj, build, calendar_jp, edinet, mof
from src.data import fetch as fetch_mod

CODES = {
    "E1": {"edinet_code": "E1", "name": "株式会社　アルファ", "sec_code": "11110", "listed": "上場"},
    "E2": {"edinet_code": "E2", "name": "ベータ合同会社", "sec_code": "", "listed": "非上場"},
}


def doc(code, filer="提出者株式会社", time_="15:30", **kw):
    return {"docTypeCode": code, "filerName": filer, "submitDateTime": f"2026-11-13 {time_}", "withdrawalStatus": "0",
            "disclosureStatus": "0", "secCode": None, "docDescription": "", **kw}


# ---- 営業日 ----

@pytest.mark.parametrize("day,expected", [
    ("2026-11-20", True), ("2026-11-21", False), ("2026-11-23", False), ("2026-12-31", False), ("2027-01-04", True)])
def test_is_trading_day(day, expected):
    assert calendar_jp.is_trading_day(day) is expected
    assert (calendar_jp.closed_reason(day) is None) is expected


def test_previous_trading_day_skips_holiday_and_weekend():
    assert calendar_jp.previous_trading_day("2026-11-24") == "2026-11-20"


# ---- 組み立て ----

def test_short_name_and_sec_code():
    assert build.short_name("株式会社　アルファ") == "アルファ"
    assert build.sec_code4("72030") == "7203" and build.sec_code4("") is None and build.sec_code4(None) is None


def test_active_documents_excludes_withdrawn_and_untyped():
    docs = [doc("350"), doc("350", withdrawalStatus="1"), doc(None), doc("180", disclosureStatus="1")]
    assert len(build.active_documents(docs)) == 1


def test_build_filings_drops_documents_submitted_on_another_day():
    docs = [doc("030"), {**doc("030"), "submitDateTime": "2026-11-12 16:00"}]
    assert build.build_filings(docs, CODES, "2026-11-13", 8, 8)["total"] == 1


def test_count_by_type_ranks_and_limits():
    rows = build.count_by_type([doc("030"), doc("030"), doc("350"), doc("999")], top=2)
    assert rows == [{"code": "030", "name": "有価証券届出書", "count": 2},
                    {"code": "350", "name": "大量保有報告書", "count": 1}]


@pytest.mark.parametrize("reason,expected", [
    ("第19条第2項第9号の2", ["株主総会の議決権行使結果"]),
    ("第19条第2項第4号,第19条第2項第9号", ["主要株主の異動", "代表取締役の異動"]),
    ("第19条第2項第1号", []), (None, []),
])
def test_reason_labels(reason, expected):
    assert build.reason_labels(reason) == expected


def test_large_holdings_lists_only_listed_issuers_new_first():
    docs = [
        doc("350", "変更ファンド株式会社", "09:00", issuerEdinetCode="E1", docDescription="変更報告書"),
        doc("350", "新規ファンド株式会社", "10:00", issuerEdinetCode="E1", docDescription="大量保有報告書"),
        doc("350", "非上場相手", "11:00", issuerEdinetCode="E2", docDescription="大量保有報告書"),
        doc("350", "不明相手", "12:00", issuerEdinetCode="E9", docDescription="変更報告書"),
    ]
    h = build.build_large_holdings(docs, CODES, max_items=1)
    assert (h["count"], h["listed_count"], h["listed_new_count"], h["listed_change_count"]) == (4, 2, 1, 1)
    assert h["items"] == [{"issuer": "アルファ", "sec_code": "1111", "kind": "大量保有報告書",
                           "filer": "新規ファンド", "submitted_at": "10:00"}]


def test_extraordinary_needs_listed_filer_and_known_reason():
    docs = [doc("180", "株式会社アルファ", secCode="11110", currentReportReason="第19条第2項第9号"),
            doc("180", "株式会社ガンマ", secCode="22220", currentReportReason="第19条第2項第1号"),
            doc("180", "非上場", currentReportReason="第19条第2項第9号")]
    e = build.build_extraordinary(docs, max_items=8)
    assert (e["count"], e["listed_count"]) == (3, 2)
    assert e["items"] == [{"filer": "アルファ", "sec_code": "1111", "reasons": ["代表取締役の異動"],
                           "submitted_at": "15:30"}]


def test_tender_offers_resolve_target():
    t = build.build_tender_offers([doc("240", "買付者株式会社", subjectEdinetCode="E1"),
                                   doc("240", "買付者2", subjectEdinetCode="E2")], CODES)
    assert t == {"count": 2, "items": [{"filer": "買付者", "target": "アルファ", "sec_code": "1111"},
                                       {"filer": "買付者2", "target": None, "sec_code": None}]}


def test_build_usdjpy():
    rows = [{"date": "2026-11-10", "close": 158.0}, {"date": "2026-11-11", "close": 158.88},
            {"date": "2026-11-12", "close": 159.71}]
    fx = build.build_usdjpy(rows, history_days=2)
    assert (fx["date"], fx["prev_date"], fx["change"], fx["direction"]) == ("2026-11-12", "2026-11-11", 0.83, "円安")
    assert fx["period_low"] == 158.88 and len(fx["history"]) == 2
    assert build.fx_direction(-0.1) == "円高" and build.fx_direction(0) == "横ばい"
    with pytest.raises(ValueError):
        build.build_usdjpy(rows[:1], 30)


def test_build_jgb():
    rows = [{"date": "2026-11-11", "yields": {"10年": 2.84, "2年": 1.861}},
            {"date": "2026-11-12", "yields": {"10年": 2.841, "2年": 1.857}}]
    jgb = build.build_jgb(rows, ["2年", "10年"])
    assert jgb["yields"][0] == {"tenor": "2年", "yield_pct": 1.857, "prev_pct": 1.861, "change_pt": -0.004}
    assert jgb["yields"][1]["change_pt"] == 0.001
    with pytest.raises(ValueError, match="30年"):
        build.build_jgb(rows, ["30年"])


# ---- EDINET ----

def _res(payload):
    return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)


def test_fetch_documents_ok_and_api_error():
    ok = SimpleNamespace(get=lambda *a, **k: _res({"metadata": {"status": "200"}, "results": [{"docID": "S1"}]}))
    assert edinet.fetch_documents("k", "2026-11-13", session=ok) == [{"docID": "S1"}]
    denied = SimpleNamespace(get=lambda *a, **k: _res({"StatusCode": 401, "message": "Access denied"}))
    with pytest.raises(edinet.EdinetError, match="401.*Access denied"):
        edinet.fetch_documents("k", "2026-11-13", session=denied)


def test_fetch_documents_error_hides_api_key():
    def boom(*a, **k):
        raise requests.ConnectionError("https://x?Subscription-Key=secret")
    with pytest.raises(edinet.EdinetError) as e:
        edinet.fetch_documents("secret", "2026-11-13", session=SimpleNamespace(get=boom))
    assert "secret" not in str(e.value) and e.value.__cause__ is None


def _codelist_zip():
    text = ('ダウンロード実行日,2026年11月21日現在,件数,1件\n'
            'ＥＤＩＮＥＴコード,提出者種別,上場区分,連結の有無,資本金,決算日,提出者名,提出者名（英字）,提出者名（ヨミ）,'
            '所在地,提出者業種,証券コード,提出者法人番号\n'
            '"E00004","内国法人・組合","上場","有","1491","5月31日","カネコ種苗株式会社","K","カ","前橋市","水産・農林業",'
            '"13760","5070001000715"\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("EdinetcodeDlInfo.csv", text.encode("cp932"))
    return buf.getvalue()


def test_load_codes_downloads_then_uses_cache(tmp_path):
    cache = tmp_path / "data" / "codes.csv"
    calls = []

    def download():
        calls.append(1)
        return _codelist_zip()

    codes = edinet.load_codes(cache, 30, download=download)
    assert codes["E00004"] == {"edinet_code": "E00004", "name": "カネコ種苗株式会社", "sec_code": "13760",
                               "listed": "上場"}
    edinet.load_codes(cache, 30, download=download)
    assert len(calls) == 1


def test_load_codes_falls_back_to_stale_cache(tmp_path):
    cache = tmp_path / "codes.csv"
    edinet.load_codes(cache, 30, download=_codelist_zip)
    os.utime(cache, (time.time() - 40 * 86400,) * 2)

    def boom():
        raise edinet.EdinetError("down")

    assert "E00004" in edinet.load_codes(cache, 30, download=boom)
    with pytest.raises(edinet.EdinetError):
        edinet.load_codes(tmp_path / "none.csv", 30, download=boom)
    with pytest.raises(edinet.EdinetError):
        edinet.parse_codelist(b"not a zip")


# ---- 日銀・財務省 ----

def test_boj_parse_series_skips_missing_days():
    body = {"STATUS": 200, "RESULTSET": [{"VALUES": {"SURVEY_DATES": [20261101, 20261102, 20261104],
                                                     "VALUES": [None, 157.75, 158.08]}}]}
    assert boj.parse_series(body) == [{"date": "2026-11-02", "close": 157.75}, {"date": "2026-11-04", "close": 158.08}]
    with pytest.raises(boj.BojError):
        boj.parse_series({"STATUS": 400, "MESSAGE": "bad"})


def test_boj_fetch_filters_until(monkeypatch):
    body = {"STATUS": 200, "RESULTSET": [{"VALUES": {"SURVEY_DATES": [20261112, 20261113], "VALUES": [159.71, 159.85]}}]}
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        return _res(body)

    monkeypatch.setattr(boj.requests, "get", fake_get)
    assert [r["date"] for r in boj.fetch_usdjpy("FXERD04", "2026-11-12", 75)] == ["2026-11-12"]
    assert (seen["startDate"], seen["endDate"], seen["code"]) == ("202608", "202611", "FXERD04")


MOF_CSV = ("国債金利情報 (令和8年11月),,,(単位 : %)\n基準日,1年,10年,40年\n"
           "R8.11.11,1.6,2.84,3.9\nR8.11.12,1.61,2.841,-\n,,,\n※注記,,,\n")


def test_mof_parse_csv_and_wareki():
    rows = mof.parse_csv(MOF_CSV)
    assert rows[-1] == {"date": "2026-11-12", "yields": {"1年": 1.61, "10年": 2.841}}
    assert mof.wareki_to_iso("H31.4.30") == "2019-04-30" and mof.wareki_to_iso("S49.9.24") == "1974-09-24"
    assert mof.wareki_to_iso("基準日") is None
    with pytest.raises(mof.MofError):
        mof.parse_csv("a,b\n1,2\n")


def test_mof_fetch_reads_all_history_only_when_needed(monkeypatch):
    older = "基準日,10年\nR8.10.29,2.8\nR8.10.30,2.81\nR8.11.11,9.9\n"
    urls = []

    def fake_download(url):
        urls.append(url)
        return MOF_CSV if url == mof.CURRENT_URL else older

    monkeypatch.setattr(mof, "_download", fake_download)
    assert len(mof.fetch_yields("2026-11-12", 2)) == 2 and urls == [mof.CURRENT_URL]
    rows = mof.fetch_yields("2026-11-12", 4)
    assert [r["date"] for r in rows] == ["2026-10-29", "2026-10-30", "2026-11-11", "2026-11-12"]
    assert rows[2]["yields"]["10年"] == 2.84  # 重なった日は今月分を優先する


# ---- fetch ----

@pytest.fixture
def fake_sources(monkeypatch, tmp_path, example_data):
    docs = [doc("350", issuerEdinetCode="E1", docDescription="大量保有報告書"), doc("180"), doc("030")]
    monkeypatch.setattr(fetch_mod.DayPaths, "for_date", classmethod(lambda cls, d: DayPaths(tmp_path / d)))
    monkeypatch.setattr(fetch_mod, "env", lambda name: "key")
    monkeypatch.setattr(fetch_mod.edinet, "load_codes", lambda *a, **k: CODES)
    monkeypatch.setattr(fetch_mod.edinet, "fetch_documents", lambda key, date: docs)
    monkeypatch.setattr(fetch_mod.boj, "fetch_usdjpy", lambda *a: example_data["usdjpy"]["history"])
    monkeypatch.setattr(fetch_mod.mof, "fetch_yields", lambda *a, **k: [
        {"date": "2026-11-11", "yields": {t: 2.0 for t in ("2年", "5年", "10年", "20年", "30年")}},
        {"date": "2026-11-12", "yields": {t: 2.1 for t in ("2年", "5年", "10年", "20年", "30年")}}])
    return docs


def test_fetch_writes_valid_data_json(fake_sources):
    data = json.loads(fetch_mod.fetch("2026-11-13").read_text(encoding="utf-8"))
    assert data["edition"] == "evening" and data["filings"]["total"] == 3
    assert data["filings"]["large_holdings"]["items"][0]["issuer"] == "アルファ"
    assert data["reference"]["large_holding_threshold_pct"] == 5
    assert len(data["notes"]) == 2 and "2026-11-12" in data["notes"][0]


def test_fetch_requires_api_key_and_documents(fake_sources, monkeypatch):
    monkeypatch.setattr(fetch_mod.edinet, "fetch_documents", lambda key, date: [])
    with pytest.raises(RuntimeError, match="書類が EDINET にありません"):
        fetch_mod.fetch("2026-11-13")
    monkeypatch.setattr(fetch_mod, "env", lambda name: None)
    with pytest.raises(RuntimeError, match="EDINET_API_KEY"):
        fetch_mod.fetch("2026-11-13")
