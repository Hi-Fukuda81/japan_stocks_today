"""日本銀行 時系列統計データ検索サイトの API。ドル円 (東京市場 17時時点) の日次データを取得する。"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

import requests

API_URL = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
DB = "FM08"  # 外国為替市況
TIMEOUT = 60


class BojError(RuntimeError):
    pass


def parse_series(body: dict) -> list[dict]:
    """API の応答を [{date, close}] (古い順、値のない日は除く) にする。"""
    if body.get("STATUS") != 200 or not body.get("RESULTSET"):
        raise BojError(f"日銀 API がエラーを返しました: {body.get('MESSAGE') or body.get('STATUS')}")
    values = body["RESULTSET"][0]["VALUES"]
    rows = []
    for raw, value in zip(values["SURVEY_DATES"], values["VALUES"]):
        if value is None:
            continue
        s = str(raw)
        rows.append({"date": f"{s[:4]}-{s[4:6]}-{s[6:8]}", "close": float(value)})
    return rows


def fetch_usdjpy(series: str, until: str, lookback_days: int) -> list[dict]:
    """until 以前の日次データ (古い順)。lookback_days は暦日。"""
    end = Date.fromisoformat(until)
    start = end - timedelta(days=lookback_days)
    params = {"format": "json", "lang": "jp", "db": DB, "code": series,
              "startDate": start.strftime("%Y%m"), "endDate": end.strftime("%Y%m")}
    try:
        res = requests.get(API_URL, params=params, timeout=TIMEOUT)
        res.raise_for_status()
        body = res.json()
    except (requests.RequestException, ValueError) as e:
        raise BojError(f"日銀の為替データを取得できませんでした: {e}") from e
    return [r for r in parse_series(body) if r["date"] <= until]
