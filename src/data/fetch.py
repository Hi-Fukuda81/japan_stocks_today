"""[1. fetch] 開示・為替・金利を取得して output/DATE/data.json に書き出す (夕方便・週間まとめ)。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from src.config import REPO_ROOT, DayPaths, env, load_config
from src.data import boj, build, edinet, mof
from src.data.calendar_jp import week_trading_days

log = logging.getLogger(__name__)
SCHEMA_PATH = Path(__file__).with_name("schema.json")
LOOKBACK_CALENDAR_DAYS = 75  # 30営業日ぶんの履歴を取るための暦日
MIN_JGB_ROWS = 8  # 前週末比まで計算できる行数 (今月分で足りなければ全期間の CSV も読む)
EDITIONS = ("evening", "weekly")


def validate_data(data: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def fetch_filings(days: list[str], cfg: dict) -> dict:
    api_key = env("EDINET_API_KEY")
    if not api_key:
        raise RuntimeError("EDINET_API_KEY が設定されていません (.env.example を参照)")
    codes = edinet.load_codes(REPO_ROOT / cfg["codes_csv"], cfg["codes_max_age_days"])
    docs = [doc for day in days for doc in edinet.fetch_documents(api_key, day)]
    filings = build.build_filings(docs, codes, days, cfg["top_types"], cfg["max_items"])
    if filings["total"] == 0:
        raise RuntimeError(f"{days[0]}〜{days[-1]} に提出された書類が EDINET にありません (休日か、まだ反映されていません)")
    return filings


def period_for(date: str, edition: str) -> dict:
    """対象の提出日。夕方便は動画の日付の1日、週間まとめは直近の週の営業日。"""
    days = week_trading_days(date) if edition == "weekly" else [date]
    return {"kind": edition, "start": days[0], "end": days[-1], "days": days}


def _lag_notes(period: dict, usdjpy: dict, jgb: dict) -> list[str]:
    return [f"{label}は {section['date']} 時点 ({period['end']} の分は未公表)"
            for label, section in (("ドル円", usdjpy), ("国債金利", jgb)) if section["date"] != period["end"]]


def fetch(date: str, edition: str = "evening") -> Path:
    """edition="weekly" なら、直近の週 (月〜金) の提出書類をまとめ、為替・金利は前週末と比べる。"""
    if edition not in EDITIONS:
        raise ValueError(f"不明な便です: {edition}")
    cfg = load_config()["data"]
    period = period_for(date, edition)
    base_before = period["start"] if edition == "weekly" else None
    filings = fetch_filings(period["days"], cfg["edinet"])
    fx_rows = boj.fetch_usdjpy(cfg["usdjpy"]["series"], period["end"], LOOKBACK_CALENDAR_DAYS)
    jgb_rows = mof.fetch_yields(period["end"], min_rows=MIN_JGB_ROWS)
    usdjpy = build.build_usdjpy(fx_rows, cfg["usdjpy"]["history_days"], base_before)
    jgb = build.build_jgb(jgb_rows, cfg["jgb"]["tenors"], base_before)
    data = {
        "date": date,
        "edition": edition,
        "period": period,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filings": filings,
        "usdjpy": usdjpy,
        "jgb": jgb,
        "reference": build.REFERENCE,
        "notes": _lag_notes(period, usdjpy, jgb),
    }
    validate_data(data)
    paths = DayPaths.for_date(date)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.data_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("data.json を書き出しました: %s (%s, 開示 %d 件)", paths.data_json, edition, filings["total"])
    return paths.data_json
