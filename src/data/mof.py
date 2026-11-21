"""財務省 国債金利情報 (CSV)。今月分 jgbcm.csv と、先月までの全期間 jgbcm_all.csv がある。"""

from __future__ import annotations

import csv
import io
import re

import requests

CURRENT_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
TIMEOUT = 60
ERA_OFFSETS = {"S": 1925, "H": 1988, "R": 2018}
WAREKI = re.compile(r"^([SHR])(\d+)\.(\d+)\.(\d+)$")


class MofError(RuntimeError):
    pass


def wareki_to_iso(text: str) -> str | None:
    """「R8.11.19」→「2026-11-19」。和暦の日付でなければ None。"""
    m = WAREKI.match(text.strip())
    if not m:
        return None
    year = ERA_OFFSETS[m.group(1)] + int(m.group(2))
    return f"{year:04d}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"


def parse_csv(text: str) -> list[dict]:
    """[{date, yields: {"10年": 2.87, ...}}] (古い順)。値のない年限 ("-") は含めない。"""
    rows = list(csv.reader(io.StringIO(text)))
    header = next((r for r in rows if r and r[0].strip() == "基準日"), None)
    if header is None:
        raise MofError("国債金利の CSV に見出し行 (基準日) がありません")
    tenors = [h.strip() for h in header[1:]]
    out = []
    for r in rows:
        day = wareki_to_iso(r[0]) if r else None
        if day is None:
            continue
        yields = {}
        for tenor, value in zip(tenors, r[1:]):
            try:
                yields[tenor] = float(value)
            except ValueError:
                continue
        out.append({"date": day, "yields": yields})
    return sorted(out, key=lambda x: x["date"])


def _download(url: str) -> str:
    try:
        res = requests.get(url, timeout=TIMEOUT)
        res.raise_for_status()
        return res.content.decode("cp932")
    except (requests.RequestException, UnicodeDecodeError) as e:
        raise MofError(f"財務省の国債金利を取得できませんでした: {e}") from e


def fetch_yields(until: str, min_rows: int) -> list[dict]:
    """until 以前の日次の金利 (古い順)。今月分で min_rows に足りなければ全期間の CSV も読む。"""
    rows = [r for r in parse_csv(_download(CURRENT_URL)) if r["date"] <= until]
    if len(rows) < min_rows:
        older = [r for r in parse_csv(_download(ALL_URL)) if r["date"] <= until]
        seen = {r["date"] for r in rows}
        rows = sorted([*(r for r in older if r["date"] not in seen), *rows], key=lambda x: x["date"])
    return rows
