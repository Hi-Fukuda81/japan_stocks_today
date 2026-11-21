"""[1. fetch] 当日の開示・為替・金利を取得して output/DATE/data.json に書き出す (夕方便)。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from src.config import REPO_ROOT, DayPaths, env, load_config
from src.data import boj, build, edinet, mof

log = logging.getLogger(__name__)
SCHEMA_PATH = Path(__file__).with_name("schema.json")
LOOKBACK_CALENDAR_DAYS = 75  # 30営業日ぶんの履歴を取るための暦日


def validate_data(data: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def fetch_filings(date: str, cfg: dict) -> dict:
    api_key = env("EDINET_API_KEY")
    if not api_key:
        raise RuntimeError("EDINET_API_KEY が設定されていません (.env.example を参照)")
    codes = edinet.load_codes(REPO_ROOT / cfg["codes_csv"], cfg["codes_max_age_days"])
    docs = edinet.fetch_documents(api_key, date)
    filings = build.build_filings(docs, codes, date, cfg["top_types"], cfg["max_items"])
    if filings["total"] == 0:
        raise RuntimeError(f"{date} に提出された書類が EDINET にありません (休日か、まだ反映されていません)")
    return filings


def fetch(date: str) -> Path:
    cfg = load_config()["data"]
    filings = fetch_filings(date, cfg["edinet"])
    fx_rows = boj.fetch_usdjpy(cfg["usdjpy"]["series"], date, LOOKBACK_CALENDAR_DAYS)
    jgb_rows = mof.fetch_yields(date, min_rows=2)  # 前日比に必要な2日分
    usdjpy = build.build_usdjpy(fx_rows, cfg["usdjpy"]["history_days"])
    jgb = build.build_jgb(jgb_rows, cfg["jgb"]["tenors"])
    notes = [f"{label}は {section['date']} 時点 (当日分は未公表)"
             for label, section in (("ドル円", usdjpy), ("国債金利", jgb)) if section["date"] != date]
    data = {
        "date": date,
        "edition": "evening",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filings": filings,
        "usdjpy": usdjpy,
        "jgb": jgb,
        "reference": build.REFERENCE,
        "notes": notes,
    }
    validate_data(data)
    paths = DayPaths.for_date(date)
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.data_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("data.json を書き出しました: %s (開示 %d 件)", paths.data_json, filings["total"])
    return paths.data_json
