"""EDINET API v2 (金融庁)。提出書類の一覧と、EDINET コード一覧 (提出者名・証券コード) を取得する。"""

from __future__ import annotations

import csv
import io
import logging
import time
import zipfile
from pathlib import Path

import requests

log = logging.getLogger(__name__)

DOCUMENTS_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
CODELIST_URL = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip"
TIMEOUT = 60
CODE_FIELDS = ("edinet_code", "name", "sec_code", "listed")


class EdinetError(RuntimeError):
    pass


def fetch_documents(api_key: str, date: str, session: requests.Session | None = None) -> list[dict]:
    """date (YYYY-MM-DD) に提出された書類のメタデータ一覧。"""
    http = session or requests
    try:
        res = http.get(DOCUMENTS_URL, params={"date": date, "type": 2, "Subscription-Key": api_key}, timeout=TIMEOUT)
        body = res.json()
    except (requests.RequestException, ValueError) as e:
        # 例外の文言に URL (API キー入り) が含まれるので、種類だけを出す
        raise EdinetError(f"EDINET の書類一覧を取得できませんでした: {e.__class__.__name__}") from None
    status = str((body.get("metadata") or {}).get("status") or body.get("StatusCode") or body.get("statusCode") or "")
    if status != "200":
        message = (body.get("metadata") or {}).get("message") or body.get("message") or "理由不明"
        raise EdinetError(f"EDINET API がエラーを返しました (status {status or '?'}): {message}")
    return body.get("results") or []


def parse_codelist(zip_bytes: bytes) -> list[dict]:
    """Edinetcode.zip の CSV (cp932、1行目は件数、2行目が見出し) を {edinet_code, name, sec_code, listed} にする。"""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            text = z.read(z.namelist()[0]).decode("cp932")
    except (zipfile.BadZipFile, IndexError, UnicodeDecodeError) as e:
        raise EdinetError(f"EDINET コード一覧を読めませんでした: {e}") from e
    rows = list(csv.reader(io.StringIO(text)))[1:]
    if not rows:
        raise EdinetError("EDINET コード一覧が空です")
    col = {name: i for i, name in enumerate(rows[0])}
    try:
        idx = [col["ＥＤＩＮＥＴコード"], col["提出者名"], col["証券コード"], col["上場区分"]]
    except KeyError as e:
        raise EdinetError(f"EDINET コード一覧の列が見つかりません: {e}") from e
    return [dict(zip(CODE_FIELDS, (r[i].strip() for i in idx))) for r in rows[1:] if len(r) > max(idx)]


def load_codes(cache: Path, max_age_days: int, now: float | None = None,
               download=None) -> dict[str, dict]:
    """EDINET コード → {name, sec_code, listed}。キャッシュが古いか無ければダウンロードし直す。"""
    now = now or time.time()
    if not cache.exists() or now - cache.stat().st_mtime > max_age_days * 86400:
        try:
            rows = parse_codelist((download or _download_codelist)())
            cache.parent.mkdir(parents=True, exist_ok=True)
            with cache.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CODE_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            log.info("EDINET コード一覧を更新しました (%d 件)", len(rows))
        except (EdinetError, OSError) as e:
            if not cache.exists():
                raise EdinetError(f"EDINET コード一覧がありません: {e}") from e
            log.warning("EDINET コード一覧を更新できないため、古いキャッシュを使います: %s", e)
    with cache.open(encoding="utf-8", newline="") as f:
        return {r["edinet_code"]: r for r in csv.DictReader(f)}


def _download_codelist() -> bytes:
    try:
        res = requests.get(CODELIST_URL, timeout=TIMEOUT)
        res.raise_for_status()
        return res.content
    except requests.RequestException as e:
        raise EdinetError(f"EDINET コード一覧をダウンロードできませんでした: {e}") from e
